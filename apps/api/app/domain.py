"""Persistent state transitions. Lock order is video, then job/run."""
from datetime import datetime, timezone
from contracts.normalized import content_hash, validate_deletion
from .db import connection, uid, Jsonb
from .storage import Storage


class Denied(ValueError):
    pass


class Conflict(ValueError):
    pass


class LeaseLost(ValueError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def owned_video(conn, owner, video_id, deleted=False, lock=False):
    row = conn.execute('SELECT * FROM videos WHERE id=%s AND owner_id=%s'+(' FOR UPDATE' if lock else ''), (video_id, owner)).fetchone()
    if not row or (row['deleted_at'] and not deleted): raise Denied('not_found')
    return row


def owned_run(conn, owner, run_id):
    row = conn.execute('SELECT r.* FROM runs r JOIN videos v ON v.id=r.video_id WHERE r.id=%s AND v.owner_id=%s AND v.deleted_at IS NULL', (run_id, owner)).fetchone()
    if not row: raise Denied('not_found')
    return row


def idem(conn, owner, route, key, body_hash, result=None):
    row = conn.execute('SELECT * FROM idempotency WHERE owner_id=%s AND route=%s AND key=%s', (owner,route,key)).fetchone()
    if row:
        if row['body_hash'] != body_hash: raise Conflict('idempotency_body_changed')
        return row['result']
    if result is not None:
        conn.execute('INSERT INTO idempotency VALUES(%s,%s,%s,%s,%s)',(owner,route,key,body_hash,Jsonb(result)))
    return None


def event(conn, run_id, kind, payload):
    seq = conn.execute('UPDATE runs SET sequence=sequence+1 WHERE id=%s RETURNING sequence',(run_id,)).fetchone()['sequence']
    eid = uid()
    conn.execute('INSERT INTO events VALUES(%s,%s,%s,%s,%s)',(run_id,seq,eid,kind,Jsonb(payload)))


def fence(conn, lease):
    video = conn.execute('SELECT * FROM videos WHERE id=%s FOR UPDATE',(lease['video_id'],)).fetchone()
    job = conn.execute("SELECT * FROM jobs WHERE id=%s AND generation=%s AND status='leased' AND lease_until>now() FOR UPDATE",(lease['id'],lease['generation'])).fetchone()
    if not video or not job or (lease['kind'] == 'analysis' and video['deleted_at']): raise LeaseLost('lease_lost')
    return video


def save_object(conn, video_id, data, kind, suffix):
    """Register before bytes; call only while holding the video lock.

    Inventory is committed separately before I/O so crash cleanup can find the key.
    A second connection cannot register while deletion holds the same video lock;
    callers reserve all keys before entering their publish transaction.
    """
    raise RuntimeError('use reserve_object then put_reserved')


def reserve_object(video_id, kind, suffix, lease=None):
    key = f'v02/{video_id}/{uid()}.{suffix}'
    with connection() as conn:
        if lease:
            fence(conn, lease)
        else:
            video = conn.execute('SELECT * FROM videos WHERE id=%s FOR UPDATE',(video_id,)).fetchone()
            if video['deleted_at']: raise LeaseLost('deleted')
        conn.execute('INSERT INTO objects(key,video_id,kind) VALUES(%s,%s,%s)',(key,video_id,kind))
    return key


def put_reserved(conn, video_id, key, data, kind='application/octet-stream'):
    # Caller holds video lock until storage I/O completes; deletion waits, then removes it.
    assert conn.execute('SELECT 1 FROM objects WHERE video_id=%s AND key=%s',(video_id,key)).fetchone()
    Storage().put(key, data, kind)


TARGETS = ('originals','derivatives','provider_files','runs','events','reports','jobs')


def request_deletion(conn, owner, video_id):
    video = owned_video(conn,owner,video_id,deleted=True,lock=True)
    existing = conn.execute('SELECT * FROM deletions WHERE video_id=%s',(video_id,)).fetchone()
    if existing: return existing['state']
    deletion_id, now = uid(), utc()
    generation = video['fence']+1
    state = dict(deletion_id=deletion_id, repeat_deletion_id=deletion_id,
        access_revoked=True,access_revoked_at=now,fence_generation=generation,
        targets={k:dict(status='pending',attempts=0,completed_at=None,retry_at=None,error_code=None) for k in TARGETS},
        pending_targets=sorted(TARGETS),can_claim_complete=False,status='pending',completed_at=None,
        caveat='App-owned copies only. Historical source evidence and upstream backups are not erased by this operation.')
    validate_deletion(state)
    conn.execute('UPDATE videos SET deleted_at=now(),fence=%s WHERE id=%s',(generation,video_id))
    conn.execute("UPDATE jobs SET status='cancelled', generation=generation+1,lease_until=NULL WHERE video_id=%s AND kind='analysis'",(video_id,))
    conn.execute('INSERT INTO deletions VALUES(%s,%s,%s,%s)',(deletion_id,video_id,owner,Jsonb(state)))
    conn.execute("INSERT INTO jobs(id,video_id,kind) VALUES(%s,%s,'deletion')",(uid(),video_id))
    return state


def retention_cleanup():
    with connection() as conn:
        rows = conn.execute('SELECT v.id,v.owner_id FROM videos v JOIN owner_sessions s ON s.id=v.owner_id WHERE s.expires_at<=now() AND v.deleted_at IS NULL LIMIT 20').fetchall()
        for row in rows: request_deletion(conn,row['owner_id'],row['id'])
        # Only credential hashes are retained while their content is being deleted.
        conn.execute("UPDATE owner_sessions SET csrf_hash='',token_hash='expired:'||id WHERE expires_at<=now()")


def delete_step(lease, store=None):
    store = store or Storage()
    with connection() as conn:
        fence(conn,lease)
        operation = conn.execute('SELECT * FROM deletions WHERE video_id=%s FOR UPDATE',(lease['video_id'],)).fetchone()
        state = operation['state']
        for kind in ('originals','derivatives','provider_files'):
            target = state['targets'][kind]
            if target['status'] == 'complete': continue
            target['attempts'] += 1
            objects = conn.execute('SELECT key FROM objects WHERE video_id=%s AND kind=%s',(lease['video_id'],kind)).fetchall()
            try:
                for obj in objects:
                    store.delete(obj['key'])
                    conn.execute('DELETE FROM objects WHERE key=%s',(obj['key'],))
                target.update(status='complete',completed_at=utc(),retry_at=None,error_code=None)
            except Exception:
                from datetime import timedelta
                target.update(status='failed',completed_at=None,
                    retry_at=(datetime.now(timezone.utc)+timedelta(seconds=10)).isoformat().replace('+00:00','Z'),error_code='storage_cleanup_unavailable')
        # Cascade removes checkpoints/reactions/calls/events/reports; content stripped from tombstone.
        conn.execute('DELETE FROM runs WHERE video_id=%s',(lease['video_id'],))
        conn.execute("DELETE FROM jobs WHERE video_id=%s AND kind='analysis'",(lease['video_id'],))
        conn.execute("UPDATE videos SET features=NULL,metadata='{}',sha256='' WHERE id=%s",(lease['video_id'],))
        for kind in ('runs','events','reports','jobs'):
            state['targets'][kind].update(status='complete',attempts=1,completed_at=utc(),retry_at=None,error_code=None)
        state['pending_targets'] = sorted(k for k,v in state['targets'].items() if v['status'] != 'complete')
        complete = not state['pending_targets']
        state.update(can_claim_complete=complete,status='complete' if complete else 'pending',completed_at=utc() if complete else None)
        validate_deletion(state)
        conn.execute('UPDATE deletions SET state=%s WHERE id=%s',(Jsonb(state),operation['id']))
        if complete:
            conn.execute('DELETE FROM jobs WHERE id=%s',(lease['id'],))
        else:
            conn.execute("UPDATE jobs SET status='queued',lease_until=NULL,available_at=now()+interval '10 seconds' WHERE id=%s",(lease['id'],))
        return state
