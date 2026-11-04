import hashlib
import json
import re
import secrets
import tempfile
import psycopg
from urllib.parse import urlsplit
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict
from .config import ROOT, settings
from .db import connection, uid, Jsonb
from .storage import Storage
from .domain import (Denied, Conflict, LeaseLost, owned_video, owned_run, idem,
    request_deletion, reserve_object, put_reserved)
from .media import probe, MediaError, MAX_BYTES
from .providers import RecordedProvider, ProviderUnavailable, digest
from .cast import get_persona_ids, get_cast_hash

STANDARD_MEDIA_PIPELINE = 'scene-av-v1'

app = FastAPI(title='Mobbs local evidence desk', docs_url=None, redoc_url=None)


def error(code, status=400, stage='request'):
    return JSONResponse(dict(code=code,stage=stage,message=code.replace('_',' '),retryable=False,request_id=uid()),status_code=status)


@app.exception_handler(psycopg.OperationalError)
@app.exception_handler(psycopg.InterfaceError)
async def database_unavailable(_, exc):
    response = error('database_temporarily_unavailable',503,'storage')
    response.headers['Retry-After'] = '3'
    return response


@app.exception_handler(Denied)
async def denied(_, exc): return error(str(exc),404)


@app.exception_handler(Conflict)
async def conflict(_, exc): return error(str(exc),409)


@app.middleware('http')
async def security(request, call_next):
    cfg = settings()
    if request.headers.get('host','').lower() != urlsplit(cfg.origin).netloc.lower():
        return error('invalid_host',403)
    if request.method in ('POST','PUT','PATCH','DELETE'):
        if request.headers.get('origin') != cfg.origin or request.headers.get('sec-fetch-site') == 'cross-site':
            return error('same_origin_required',403)
    response = await call_next(request)
    response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        'Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
        'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
    return response


def owner(request, mutate=False):
    token = request.cookies.get('vir_session','')
    with connection() as conn:
        row = conn.execute('SELECT * FROM owner_sessions WHERE token_hash=%s AND expires_at>now()', (digest(token.encode()),)).fetchone()
    if not row: raise HTTPException(401,'Session expired or absent. Create a new private session.')
    if mutate:
        csrf = request.headers.get('x-csrf-token','')
        if not csrf or not secrets.compare_digest(digest(csrf.encode()),row['csrf_hash']):
            raise HTTPException(403,'csrf_required')
    return row['id']


def key(request):
    value = request.headers.get('idempotency-key','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',value): raise HTTPException(400,'idempotency_key_required')
    return value


@app.post('/sessions')
def session(request: Request):
    existing_token = request.cookies.get('vir_session','')
    csrf = request.cookies.get('vir_csrf','')
    provider_mode = settings().provider_mode
    with connection() as conn:
        row = conn.execute('SELECT * FROM owner_sessions WHERE token_hash=%s AND expires_at>now()', (digest(existing_token.encode()),)).fetchone()
        if row and digest(csrf.encode()) == row['csrf_hash']:
            return dict(csrf=csrf,expires_at=row['expires_at'].isoformat(),retention_hours=24,provider_mode=provider_mode)
        token,csrf = secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        row = conn.execute("INSERT INTO owner_sessions(id,token_hash,csrf_hash,expires_at) VALUES(%s,%s,%s,now()+interval '24 hours') RETURNING expires_at",(uid(),digest(token.encode()),digest(csrf.encode()))).fetchone()
    response = JSONResponse(dict(csrf=csrf,expires_at=row['expires_at'].isoformat(),retention_hours=24,provider_mode=provider_mode),status_code=201)
    secure=settings().origin.startswith('https://')
    response.set_cookie('vir_session',token,httponly=True,secure=secure,samesite='strict',max_age=86400,path='/')
    response.set_cookie('vir_csrf',csrf,httponly=False,secure=secure,samesite='strict',max_age=86400,path='/')
    return response


@app.post('/videos',status_code=201)
async def upload(request: Request):
    owner_id = owner(request,True)
    request_key = key(request)
    if request.headers.get('content-type','').split(';')[0] != 'video/mp4': return error('mp4_required',422,'upload')
    try:
        length = int(request.headers.get('content-length','0'))
    except ValueError: return error('invalid_content_length')
    if length > MAX_BYTES: return error('maximum_size_200000000_bytes',413,'upload')
    with tempfile.TemporaryDirectory(prefix='mobbs-ingest-') as tmp:
        path = Path(tmp)/'upload.mp4'
        sha, size = hashlib.sha256(), 0
        with path.open('wb') as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES: return error('maximum_size_200000000_bytes',413,'upload')
                sha.update(chunk); f.write(chunk)
        if size == 0: return error('empty_upload',422,'upload')
        media_hash = sha.hexdigest()
        try:
            metadata = await run_in_threadpool(probe,path)
        except (MediaError,ValueError,KeyError): return error('invalid_mp4_or_limit_exceeded',422,'validation')
        with connection() as conn:
            conn.execute('SELECT id FROM owner_sessions WHERE id=%s FOR UPDATE',(owner_id,))
            previous = idem(conn,owner_id,'upload',request_key,media_hash)
            if previous:
                video = owned_video(conn,owner_id,previous['video_id'])
                if video['metadata'].get('storage_ready'): return previous
                video_id = video['id']
            else:
                video_id = uid()
                conn.execute('INSERT INTO videos(id,owner_id,sha256,metadata) VALUES(%s,%s,%s,%s)',(video_id,owner_id,media_hash,Jsonb(metadata)))
                idem(conn,owner_id,'upload',request_key,media_hash,dict(video_id=video_id,status='uploaded'))
        # A committed inventory precedes object I/O; crash recovery/retention can clean it.
        objkey = reserve_object(video_id,'originals','mp4')
        with connection() as conn:
            video = owned_video(conn,owner_id,video_id,lock=True)
            with path.open('rb') as f: put_reserved(conn,video_id,objkey,f,'video/mp4')
            metadata.update(original_key=objkey,storage_ready=True)
            conn.execute('UPDATE videos SET metadata=%s WHERE id=%s',(Jsonb(metadata),video_id))
        return dict(video_id=video_id,status='uploaded')


@app.get('/videos')
def videos(request: Request):
    owner_id = owner(request)
    with connection() as conn:
        return conn.execute('SELECT v.id,v.metadata,v.created_at,(SELECT r.id FROM runs r WHERE r.video_id=v.id ORDER BY r.created_at DESC LIMIT 1) AS run_id FROM videos v WHERE owner_id=%s AND deleted_at IS NULL ORDER BY created_at DESC',(owner_id,)).fetchall()


@app.get('/videos/{video_id}/analysis')
def analysis(video_id: str,request: Request):
    with connection() as conn:
        v = owned_video(conn,owner(request),video_id)
        mode = settings().provider_mode
        if mode == 'standard':
            profiles = ['test', 'flash']
        else:
            profiles = []
            try:
                RecordedProvider(v['sha256'], v['metadata']['duration_ms'], profile='test')
                profiles.append('test')
            except Exception:
                pass
            try:
                RecordedProvider(v['sha256'], v['metadata']['duration_ms'], profile='flash')
                profiles.append('flash')
            except Exception:
                pass
        return dict(video_id=v['id'],metadata={k:v['metadata'][k] for k in ('duration_ms','width','height','audio_present','bytes','caveats')},features=v['features'],available_profiles=profiles)


@app.get('/videos/{video_id}/media')
def media(video_id: str,request: Request):
    owner_id = owner(request)
    with connection() as conn:
        v = owned_video(conn,owner_id,video_id)
        if not v['metadata'].get('storage_ready'): raise HTTPException(409,'upload_not_ready')
        objkey = v['metadata']['original_key']
        size = v['metadata']['bytes']
    start,end,status = 0,size-1,200
    requested = request.headers.get('range')
    if requested:
        match = re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
        if not match: return error('unsupported_range',416)
        start = int(match[1]); end = min(int(match[2]) if match[2] else size-1,size-1)
        if start > end: return error('invalid_range',416)
        status = 206
    def chunks():
        # Reauthorize each bounded range so tombstone/expiry also stops an open stream.
        position = start
        while position <= end:
            with connection() as conn:
                current_owner = owner(request)
                owned_video(conn,current_owner,video_id)
                stop = min(end,position+256*1024-1)
                obj = Storage().get(objkey,Range=f'bytes={position}-{stop}')
                try: data = obj['Body'].read()
                finally: obj['Body'].close()
            if not data: return
            yield data
            position = stop+1
    headers = {'Accept-Ranges':'bytes','Content-Length':str(end-start+1)}
    if status == 206: headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    return StreamingResponse(chunks(),status_code=status,media_type='video/mp4',headers=headers)


class RunBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    video_id: str
    profile: str = 'test'


@app.post('/runs',status_code=202)
def start_run(body: RunBody,request: Request):
    owner_id,request_key = owner(request,True),key(request)
    if body.profile not in ('test', 'flash'):
        return error('profile_must_be_test_or_flash', 422)
    body_hash = digest(body.model_dump_json().encode())
    with connection() as conn:
        conn.execute('SELECT id FROM owner_sessions WHERE id=%s FOR UPDATE',(owner_id,))
        video = owned_video(conn,owner_id,body.video_id,lock=True)
        previous = idem(conn,owner_id,'run',request_key,body_hash)
        if previous: return previous
        if not video['metadata'].get('storage_ready'): return error('upload_not_ready',409)

        cfg = settings()
        provider_mode = cfg.provider_mode

        # Unsupported recorded flash must fail explicitly before enqueue
        if provider_mode == 'recorded' and body.profile == 'flash':
            try:
                RecordedProvider(video['sha256'], video['metadata']['duration_ms'], profile=body.profile)
            except ProviderUnavailable:
                return error('recorded_evidence_unavailable_for_this_upload', 422)

        existing = conn.execute(
            "SELECT id,status FROM runs WHERE video_id=%s AND manifest->>'profile'=%s AND manifest->>'provider_mode'=%s ORDER BY created_at DESC LIMIT 1",
            (body.video_id, body.profile, provider_mode)
        ).fetchone()
        if existing:
            result = dict(run_id=existing['id'],status=existing['status'])
            idem(conn,owner_id,'run',request_key,body_hash,result)
            return result

        persona_ids = get_persona_ids(body.profile)
        requested = len(persona_ids)
        cast_hash = get_cast_hash(body.profile)
        provider_concurrency = 8 if (provider_mode == 'standard' and body.profile == 'flash') else 1

        manifest = dict(
            schema_version='run-manifest-1',
            profile=body.profile,
            provider_mode=provider_mode,
            requested=requested,
            persona_ids=persona_ids,
            resample_seed=20261028,
            provider_concurrency=provider_concurrency,
            model_id='muse-spark-1.3',
            cast_hash=cast_hash,
            prompt_version='spark13-standard-v1' if provider_mode == 'standard' else 'spark13-recorded-v1',
        )
        if provider_mode == 'standard' and STANDARD_MEDIA_PIPELINE:
            manifest.update(media_pipeline=STANDARD_MEDIA_PIPELINE, prompt_version='spark13-engagement-v2', signals_version='engagement-v2')

        run_id = uid()
        conn.execute('INSERT INTO runs(id,video_id,manifest) VALUES(%s,%s,%s)', (run_id, body.video_id, Jsonb(manifest)))
        conn.execute("INSERT INTO jobs(id,video_id,run_id,kind) VALUES(%s,%s,%s,'analysis')", (uid(), body.video_id, run_id))
        result = dict(run_id=run_id,status='queued')
        idem(conn,owner_id,'run',request_key,body_hash,result)
        return result


def run_snapshot(conn, row):
    run_id = row['id']
    manifest = row['manifest']
    requested = manifest['requested']
    cast = conn.execute("SELECT status,count(*) AS count FROM checkpoints WHERE run_id=%s GROUP BY status",(run_id,)).fetchall()
    counts = {r['status']:r['count'] for r in cast}
    stopped = counts.get('stopped', 0)
    completed = counts.get('complete', 0)
    failed = counts.get('failed', 0)
    active = counts.get('active', 0)
    effective = completed + stopped
    if row['status'] in ('complete', 'incomplete', 'failed'):
        pending = 0
    else:
        pending = active if cast else requested
    prov_event = conn.execute(
        "SELECT payload FROM events WHERE run_id=%s AND type='verdict.provisional' ORDER BY sequence ASC LIMIT 1",
        (run_id,)
    ).fetchone()
    provisional_verdict = prov_event['payload'] if prov_event else None
    decisions = conn.execute('SELECT count(*) AS n FROM reactions WHERE run_id=%s',(run_id,)).fetchone()['n']
    job = conn.execute("SELECT status,lease_until>now() AS active FROM jobs WHERE run_id=%s AND kind='analysis' LIMIT 1",(run_id,)).fetchone()
    return dict(
        run_id=run_id,
        created_at=row['created_at'].isoformat(),
        observed_reactions=decisions,
        worker_active=bool(job and job['status']=='leased' and job['active']),
        video_id=row['video_id'],
        status=row['status'],
        stage=row['stage'],
        error_code=row['error_code'],
        sequence=row['sequence'],
        manifest=manifest,
        requested=requested,
        effective=effective,
        failed=failed,
        pending=pending,
        stopped=stopped,
        provisional_verdict=provisional_verdict,
    )



@app.get('/runs/{run_id}')
def run_state(run_id: str,request: Request):
    with connection() as conn:
        row = owned_run(conn,owner(request),run_id)
        return run_snapshot(conn,row)


@app.get('/runs/{run_id}/evidence/{evidence_id}')
def evidence(run_id: str, evidence_id: str, request: Request):
    owner_id = owner(request)
    with connection() as conn:
        owned_run(conn, owner_id, run_id)
        row = conn.execute(
            'SELECT evidence FROM reactions WHERE run_id=%s AND evidence->>\'id\'=%s',
            (run_id, evidence_id)
        ).fetchone()
        if not row:
            raise Denied('evidence_not_found')
        ev = row['evidence']
        return dict(
            id=ev['id'],
            persona_id=ev['persona_id'],
            scene_id=ev['scene_id'],
            start_ms=ev['start_ms'],
            end_ms=ev['end_ms'],
            quote=ev['quote'],
            still_watching=ev.get('still_watching', True),
        )


@app.get('/runs/{run_id}/events')
def events(run_id: str,request: Request,after: int=0):
    if after < 0: return error('invalid_cursor')
    with connection() as conn:
        run = owned_run(conn,owner(request),run_id)
        cursor = request.headers.get('last-event-id')
        if cursor:
            event_row = conn.execute('SELECT sequence FROM events WHERE run_id=%s AND event_id=%s',(run_id,cursor)).fetchone()
            if not event_row: return error('invalid_event_cursor')
            after = event_row['sequence']
        if after > run['sequence']: return error('invalid_cursor')
        rows = conn.execute('SELECT * FROM events WHERE run_id=%s AND sequence>%s ORDER BY sequence LIMIT 1000',(run_id,after)).fetchall()
        snapshot = run_snapshot(conn, run)
    # Finite SSE response: browser reconnects with last persisted ID. Polling is also available.
    text = ''.join(f"id: {r['event_id']}\nevent: {r['type']}\ndata: {json.dumps(r)}\n\n" for r in rows)
    # Ephemeral state has no SSE id, preserving the persisted Last-Event-ID cursor.
    text += 'event: run.snapshot\ndata: ' + json.dumps(dict(type='run.snapshot', sequence=snapshot['sequence'], payload=dict(state=snapshot))) + '\n\n'
    return StreamingResponse(iter([text or ': heartbeat\n\n']),media_type='text/event-stream')


@app.get('/runs/{run_id}/report')
def report(run_id: str,request: Request):
    with connection() as conn:
        row = conn.execute(
            'SELECT r.report, r.status, r.stage, v.metadata, v.features FROM runs r JOIN videos v ON v.id=r.video_id WHERE r.id=%s AND v.owner_id=%s AND v.deleted_at IS NULL',
            (run_id, owner(request))
        ).fetchone()
        if not row: raise Denied('not_found')
        if row['report'] is None: return JSONResponse(dict(status=row['status'],stage=row['stage']),status_code=202)
        rep = dict(row['report'])
        if 'duration_ms' not in rep and row['metadata'] and 'duration_ms' in row['metadata']:
            rep['duration_ms'] = row['metadata']['duration_ms']
        if 'scenes' not in rep and row['features'] and 'scenes' in row['features']:
            rep['scenes'] = row['features']['scenes']
        if 'suppressed_notes' not in rep:
            for c in rep.get('caveats', []):
                if 'unsupported note' in c:
                    m = re.search(r'(\d+)', c)
                    if m:
                        rep['suppressed_notes'] = int(m.group(1))
                        break
        return rep


@app.delete('/videos/{video_id}',status_code=202)
def delete(video_id: str,request: Request):
    owner_id = owner(request,True)
    request_key = key(request)
    request_hash = digest(f'delete:{video_id}'.encode())
    with connection() as conn:
        conn.execute('SELECT id FROM owner_sessions WHERE id=%s FOR UPDATE',(owner_id,))
        previous = idem(conn,owner_id,'delete',request_key,request_hash)
        existing = conn.execute('SELECT state FROM deletions WHERE video_id=%s AND owner_id=%s',(video_id,owner_id)).fetchone()
        if existing:
            state = existing['state']
            if not previous:
                idem(conn,owner_id,'delete',request_key,request_hash,state)
            return state
        if previous: return previous
        state = request_deletion(conn,owner_id,video_id)
        idem(conn,owner_id,'delete',request_key,request_hash,state)
        return state


@app.get('/deletions')
def list_deletions(request: Request):
    owner_id = owner(request)
    with connection() as conn:
        rows = conn.execute(
            'SELECT id, video_id, state FROM deletions WHERE owner_id=%s ORDER BY (state->>\'access_revoked_at\') DESC LIMIT 10',
            (owner_id,)
        ).fetchall()
        return [dict(id=r['id'],video_id=r['video_id'],state=r['state']) for r in rows]


@app.get('/deletions/{deletion_id}')
def deletion(deletion_id: str,request: Request):
    with connection() as conn:
        row = conn.execute('SELECT state FROM deletions WHERE id=%s AND owner_id=%s',(deletion_id,owner(request))).fetchone()
        if not row: raise Denied('not_found')
        return row['state']


@app.get('/health')
def health():
    with connection() as conn:
        rows = {r['version'] for r in conn.execute('SELECT version FROM schema_migrations').fetchall()}
        assert 1 in rows and 2 in rows and 3 in rows
    Storage().check()
    mode = settings().provider_mode
    return {'status': 'ok', 'database': 'postgresql', 'storage': 'private_s3', 'inference': 'standard' if mode == 'standard' else 'recorded_only'}


dist = ROOT/'apps/web/dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='web')
