"""Separate durable worker. Each unit commits checkpoint, verdict and event atomically."""
import argparse
import json
import math
import random
import subprocess
import tempfile
import time
from pathlib import Path
from contracts.normalized import (cast_status, content_hash, normalize_note, stop_trigger,
    validate_reaction, require)
from .config import ROOT, settings
from .db import connection, uid, Jsonb
from .domain import (fence, event, LeaseLost, reserve_object, put_reserved,
    delete_step, retention_cleanup, utc)
from .media import extract
from .providers import RecordedProvider, ProviderUnavailable, digest
from .storage import Storage


def claim():
    with connection() as conn:
        job = conn.execute("""SELECT * FROM jobs WHERE available_at<=now() AND
            (status='queued' OR (status='leased' AND lease_until<=now()))
            ORDER BY CASE kind WHEN 'deletion' THEN 0 ELSE 1 END,created_at
            FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not job: return None
        return conn.execute("UPDATE jobs SET status='leased',generation=generation+1,lease_until=now()+%s*interval '1 second' WHERE id=%s RETURNING *",
            (settings().lease_seconds,job['id'])).fetchone()


def release(conn, lease, done=False):
    conn.execute('UPDATE jobs SET status=%s,lease_until=NULL WHERE id=%s AND generation=%s',
        ('complete' if done else 'queued',lease['id'],lease['generation']))


def stage(conn, run_id, value):
    conn.execute("UPDATE runs SET stage=%s,status='processing' WHERE id=%s",(value,run_id))


def project(scene, checkpoint):
    # No whole FeatureBundle, raw transcript, other personas or future refs cross this boundary.
    return dict(persona_id=checkpoint['persona_id'],
        scene={k:scene[k] for k in ('scene_id','start_ms','end_ms')},
        allowed_media_refs=[scene['frame_ref']],max_visible_ms=scene['end_ms'],
        own_impression=checkpoint['impression'])


def validate_projection(value, scene, checkpoint):
    require(set(value) == {'persona_id','scene','allowed_media_refs','max_visible_ms','own_impression'}, 'unapproved scene context')
    require(value == project(scene,checkpoint), 'future/peer/context mismatch')
    require(checkpoint['status'] == 'active' and checkpoint['next_scene'] == scene['scene_id'], 'post-stop or out-of-order dispatch')


def source_sha():
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()


def prepare(lease, provider):
    with connection() as conn:
        video = fence(conn,lease)
        if video['features']: return
        stage(conn,lease['run_id'],'decoding')
    with tempfile.TemporaryDirectory(prefix='viralist-worker-') as tmp:
        directory = Path(tmp)
        path = directory/'original.mp4'
        body = Storage().get(video['metadata']['original_key'])['Body']
        try:
            with path.open('wb') as f:
                for chunk in body.iter_chunks(1024*1024): f.write(chunk)
        finally: body.close()
        require(digest(path.read_bytes()) == video['sha256'], 'stored original hash mismatch')
        scenes = extract(path,directory,video['metadata']['duration_ms'])
        for scene in scenes:
            key = reserve_object(video['id'],'derivatives','jpg',lease)
            with connection() as conn:
                fence(conn,lease)
                put_reserved(conn,video['id'],key,scene.pop('frame_path').read_bytes(),'image/jpeg')
            scene['frame_ref'] = key
        bundle = dict(schema_version='normalized-1',extractor_version='ffmpeg-local-v02',timebase='milliseconds',
            scenes=scenes,caveats=video['metadata']['caveats']+['No local transcript or OCR extraction.'],
            provenance=['Decoded from uploaded bytes; scene frames regenerated locally.'])
        with connection() as conn:
            fence(conn,lease)
            conn.execute('UPDATE videos SET features=%s WHERE id=%s',(Jsonb(bundle),video['id']))
            for pid in provider.persona_ids:
                conn.execute('INSERT INTO checkpoints(run_id,persona_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(lease['run_id'],pid))
            stage(conn,lease['run_id'],'simulating')


def report_data(video, checkpoints, rows, provider, source, note_envelope, receipts):
    reactions = [r['reaction'] for r in rows]
    evidence = {r['evidence']['id']:r['evidence'] for r in rows}
    observations,notes,suppressed = [],[],0
    for scene in video['features']['scenes']:
        trigger = stop_trigger(f"stop_{scene['scene_id']}",scene['scene_id'],scene['start_ms'],scene['end_ms'],reactions)
        if trigger: observations.append(trigger)
    for i,item in enumerate(note_envelope['output'].get('notes',[])):
        try:
            candidates = [t for t in observations if t['start_ms'] <= item['start_sec']*1000 < item['end_sec']*1000 <= t['end_ms']]
            notes.append(normalize_note(item,evidence,candidates[0] if candidates else None,f'n{i}'))
        except (ValueError,KeyError,TypeError,IndexError): suppressed += 1
    counts = {status:sum(c['status'] == status for c in checkpoints) for status in ('complete','stopped','failed','active')}
    effective = counts['complete']+counts['stopped']
    cast = dict(profile='test',requested=len(checkpoints),effective=effective,failed=counts['failed'],pending=counts['active'],stopped=counts['stopped'])
    cast['status'] = cast_status('test',cast['requested'],effective,cast['failed'],cast['pending'])
    completed = {c['persona_id'] for c in checkpoints if c['status']=='complete'}
    valid = [c['persona_id'] for c in checkpoints if c['status'] in ('stopped','complete')]
    rng = random.Random(20261028)
    samples = sorted(sum(rng.choice(valid) in completed for _ in valid)/effective*100 for _ in range(200)) if effective else []
    metric = dict(kind='simulation_range',unit='percent',observed=len(completed)/effective*100 if effective else None,
        denominator=effective,range=dict(low=samples[19],high=samples[179],method='nearest-rank p10–p90; 200 whole-persona resamples; seed 20261028') if samples else None,
        evidence_ids=list(evidence))
    trust = provider.provenance()
    trust.update(app_source_sha=source,observed_at=utc(),feature_sha256=content_hash(video['features']),
        cast_sha256=content_hash(provider.persona_ids),config_sha256=content_hash({'profile':'test','mode':'recorded'}),
        prompt_sha256=content_hash({'projection':'current-frame-and-own-prior-v02'}),usage_ledger=receipts)
    return dict(schema_version='normalized-1',cast=cast,notes=notes[:3],observations=observations,
        evidence=list(evidence.values()),completion=metric,trust=trust,
        duration_ms=video['metadata']['duration_ms'],
        scenes=video['features']['scenes'],
        suppressed_notes=suppressed,
        methodology=dict(range_kind='simulation_resampling_not_confidence',ranking='heuristic stop fraction',
            assumptions=['Independent simulated traces; not real viewers.','Internal cast variability omits model bias and real audience mismatch.']),
        caveats=video['features']['caveats']+[f'{suppressed} unsupported note(s) suppressed.',
            'Signals for confusion, CTA understanding and trend fit unavailable.',
            'No causal, virality, reach or audience calibration claim.'],
        coverage=dict(transcript=False,ocr=False,confused=None,cta_understood=None,trend_fit=None))


def process_analysis(lease, provider_factory=RecordedProvider, before_publish=None):
    with connection() as conn:
        video = fence(conn,lease)
    provider = provider_factory(video['sha256'],video['metadata']['duration_ms'])
    prepare(lease,provider)
    with connection() as conn:
        video = fence(conn,lease)
        cp = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s AND status='active' ORDER BY persona_id LIMIT 1",(lease['run_id'],)).fetchone()
        if cp:
            scene = video['features']['scenes'][cp['next_scene']]
            projection = project(scene,cp)
            validate_projection(projection,scene,cp)
            unit = f"{cp['persona_id']}:{scene['scene_id']}"
            # No DB locks held across external boundary. Recorded replay can reconcile
            # an interrupted dispatched unit by reading the same immutable artifact.
            conn.execute("INSERT INTO provider_calls(run_id,unit,status,audit) VALUES(%s,%s,'dispatched',%s) ON CONFLICT DO NOTHING",(lease['run_id'],unit,Jsonb(projection)))
    if cp:
        try:
            reaction,evidence,normalized,data,sha = provider.verdict(projection)
            validate_reaction(reaction,set(provider.persona_ids),{s['scene_id']:(s['start_ms'],s['end_ms']) for s in video['features']['scenes']})
            require(reaction['persona_id'] == cp['persona_id'] and reaction['scene_id'] == scene['scene_id'], 'response identity mismatch')
            require(evidence['id'] == reaction['evidence_id'] and evidence['persona_id'] == cp['persona_id'] and evidence['scene_id'] == scene['scene_id'], 'missing evidence')
            require((evidence['start_ms'],evidence['end_ms']) == (scene['start_ms'],scene['end_ms']), 'evidence time mismatch')
            require(isinstance(evidence['quote'],str) and evidence['quote'].strip(), 'missing reason')
        except (ValueError,KeyError,TypeError,StopIteration):
            with connection() as conn:
                fence(conn,lease)
                conn.execute("UPDATE checkpoints SET status='failed' WHERE run_id=%s AND persona_id=%s",(lease['run_id'],cp['persona_id']))
                conn.execute("UPDATE provider_calls SET status='failed' WHERE run_id=%s AND unit=%s",(lease['run_id'],unit))
                conn.execute("UPDATE runs SET error_code='provider_response_rejected' WHERE id=%s",(lease['run_id'],))
                release(conn,lease)
            return
        key = reserve_object(video['id'],'provider_files','json',lease)
        if before_publish: before_publish(lease)
        with connection() as conn:
            fence(conn,lease)
            put_reserved(conn,video['id'],key,data,'application/json')
            # Stored receipt excludes private raw output/reasoning, retains hashes and historical usage.
            receipt = {k:v for k,v in normalized.items() if k != 'output'}
            receipt.update(response_sha256=sha,mode='recorded',new_provider_calls=0)
            conn.execute('INSERT INTO reactions VALUES(%s,%s,%s,%s,%s)',(lease['run_id'],cp['persona_id'],scene['scene_id'],Jsonb(reaction),Jsonb(evidence)))
            status = 'stopped' if not reaction['still_watching'] else ('complete' if scene['scene_id']==len(video['features']['scenes'])-1 else 'active')
            conn.execute('UPDATE checkpoints SET next_scene=next_scene+1,status=%s,impression=%s WHERE run_id=%s AND persona_id=%s',(status,reaction['impression_update'],lease['run_id'],cp['persona_id']))
            conn.execute("UPDATE provider_calls SET status='accepted',receipt=%s WHERE run_id=%s AND unit=%s",(Jsonb(receipt),lease['run_id'],unit))
            event(conn,lease['run_id'],'persona.continued' if reaction['still_watching'] else 'persona.stopped',
                dict(persona_id=cp['persona_id'],scene_id=scene['scene_id'],at_ms=scene['end_ms'],evidence_id=evidence['id']))
            release(conn,lease)
        return
    with connection() as conn:
        fence(conn,lease)
        stage(conn,lease['run_id'],'reporting')
        checkpoints = conn.execute('SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id',(lease['run_id'],)).fetchall()
        rows = conn.execute('SELECT * FROM reactions WHERE run_id=%s ORDER BY persona_id,scene_id',(lease['run_id'],)).fetchall()
        receipts = [r['receipt'] for r in conn.execute('SELECT receipt FROM provider_calls WHERE run_id=%s AND receipt IS NOT NULL ORDER BY unit',(lease['run_id'],)).fetchall()]
    normalized,data,sha = provider.notes()
    # Notes are the sole whole-run aggregation boundary, after every persona is terminal.
    report = report_data(video,checkpoints,rows,provider,source_sha(),normalized,receipts)
    key = reserve_object(video['id'],'provider_files','json',lease)
    with connection() as conn:
        fence(conn,lease)
        put_reserved(conn,video['id'],key,data,'application/json')
        conn.execute('UPDATE runs SET report=%s,status=%s,stage=%s,completed_at=now() WHERE id=%s',
            (Jsonb(report),'complete' if report['cast']['status']=='complete_test_profile' else report['cast']['status'],'report',lease['run_id']))
        release(conn,lease,True)


def process_once(provider_factory=RecordedProvider, before_publish=None):
    lease = claim()
    if not lease: return False
    try:
        if lease['kind']=='deletion': delete_step(lease)
        else: process_analysis(lease,provider_factory,before_publish)
    except LeaseLost:
        pass  # Tombstone/another generation owns all future publication.
    except Exception as exc:
        with connection() as conn:
            try:
                fence(conn,lease)
            except LeaseLost: return True
            # No unbounded retry or raw provider/decoder prose in logs.
            code = str(exc) if isinstance(exc,ProviderUnavailable) else 'analysis_failed'
            conn.execute("UPDATE runs SET status='failed',stage='failed',error_code=%s WHERE id=%s",(code,lease['run_id']))
            release(conn,lease,True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    args = parser.parse_args()
    while True:
        retention_cleanup()
        worked = process_once()
        if args.once: return
        time.sleep(.1 if worked else .5)


if __name__ == '__main__': main()
