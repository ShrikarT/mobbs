import os
import psycopg
import httpx
from contextlib import contextmanager
"""Separate durable worker. Each unit commits checkpoint, verdict and event atomically."""
import argparse
import json
import math
import random
import subprocess
import tempfile
import time
from pathlib import Path
from contracts.normalized import (
    cast_status,
    content_hash,
    normalize_note,
    stop_trigger,
    validate_reaction,
    require,
)
from .config import ROOT, settings
from .db import connection, uid, Jsonb
from .domain import (
    fence,
    event,
    LeaseLost,
    reserve_object,
    put_reserved,
    delete_step,
    retention_cleanup,
    utc,
)
from .media import extract
from .providers import RecordedProvider, StandardProvider, build_note_context, ProviderUnavailable, digest
from .reporting import build_report
from .storage import Storage


def claim():
    with connection() as conn:
        job = conn.execute("""SELECT * FROM jobs WHERE available_at<=now() AND
            (status='queued' OR (status='leased' AND lease_until<=now()))
            ORDER BY CASE kind WHEN 'deletion' THEN 0 ELSE 1 END,created_at
            FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not job:
            return None
        return conn.execute("UPDATE jobs SET status='leased',generation=generation+1,lease_until=now()+%s*interval '1 second' WHERE id=%s RETURNING *",
            (settings().lease_seconds, job['id'])).fetchone()


def release(conn, lease, done=False):
    conn.execute('UPDATE jobs SET status=%s,lease_until=NULL WHERE id=%s AND generation=%s',
        ('complete' if done else 'queued', lease['id'], lease['generation']))


def stage(conn, run_id, value):
    conn.execute("UPDATE runs SET stage=%s,status='processing' WHERE id=%s", (value, run_id))


def project(scene, checkpoint):
    # No whole FeatureBundle, raw transcript, other personas or future refs cross this boundary.
    return dict(persona_id=checkpoint['persona_id'],
        scene={k: scene[k] for k in ('scene_id', 'start_ms', 'end_ms')},
        allowed_media_refs=[scene['frame_ref']], max_visible_ms=scene['end_ms'],
        own_impression=checkpoint['impression'])


def validate_projection(value, scene, checkpoint):
    require(set(value) == {'persona_id', 'scene', 'allowed_media_refs', 'max_visible_ms', 'own_impression'}, 'unapproved scene context')
    require(value == project(scene, checkpoint), 'future/peer/context mismatch')
    require(checkpoint['status'] == 'active' and checkpoint['next_scene'] == scene['scene_id'], 'post-stop or out-of-order dispatch')


def source_sha():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except Exception:
        return 'unknown'


def prepare(lease, provider):
    with connection() as conn:
        video = fence(conn, lease)
        if video['features']:
            has_cp = conn.execute('SELECT 1 FROM checkpoints WHERE run_id=%s LIMIT 1', (lease['run_id'],)).fetchone()
            if not has_cp:
                for pid in provider.persona_ids:
                    conn.execute('INSERT INTO checkpoints(run_id,persona_id) VALUES(%s,%s) ON CONFLICT DO NOTHING', (lease['run_id'], pid))
                stage(conn, lease['run_id'], 'simulating')
            return
        stage(conn, lease['run_id'], 'decoding')
    with tempfile.TemporaryDirectory(prefix='viralist-worker-') as tmp:
        directory = Path(tmp)
        path = directory / 'original.mp4'
        body = Storage().get(video['metadata']['original_key'])['Body']
        try:
            with path.open('wb') as f:
                for chunk in body.iter_chunks(1024 * 1024):
                    f.write(chunk)
        finally:
            body.close()
        require(digest(path.read_bytes()) == video['sha256'], 'stored original hash mismatch')
        scenes = extract(path, directory, video['metadata']['duration_ms'])
        for scene in scenes:
            key = reserve_object(video['id'], 'derivatives', 'jpg', lease)
            with connection() as conn:
                fence(conn, lease)
                put_reserved(conn, video['id'], key, scene.pop('frame_path').read_bytes(), 'image/jpeg')
            scene['frame_ref'] = key
        bundle = dict(
            schema_version='normalized-1',
            extractor_version='ffmpeg-local-v02',
            timebase='milliseconds',
            scenes=scenes,
            caveats=video['metadata']['caveats'] + ['No local transcript or OCR extraction.'],
            provenance=['Decoded from uploaded bytes; scene frames regenerated locally.'],
        )
        with connection() as conn:
            fence(conn, lease)
            conn.execute('UPDATE videos SET features=%s WHERE id=%s', (Jsonb(bundle), video['id']))
            for pid in provider.persona_ids:
                conn.execute('INSERT INTO checkpoints(run_id,persona_id) VALUES(%s,%s) ON CONFLICT DO NOTHING', (lease['run_id'], pid))
            stage(conn, lease['run_id'], 'simulating')




def get_operational_pause_marker_path():
    runtime_path = os.environ.get('VIRALIST_RUNTIME')
    if runtime_path:
        return Path(runtime_path).parent / 'operational_pause.marker'
    return ROOT / 'operational_pause.marker'


def set_operational_pause():
    p = get_operational_pause_marker_path()
    try:
        p.write_text('paused', encoding='utf-8')
    except Exception:
        pass


def clear_operational_pause():
    p = get_operational_pause_marker_path()
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def is_operationally_paused():
    p = get_operational_pause_marker_path()
    return p.exists()


STANDARD_CONCURRENCY_GATE_KEY = 58004001


@contextmanager
def standard_concurrency_gate():
    with psycopg.connect(settings().database_url, autocommit=True) as gate_conn:
        gate_conn.execute("SELECT pg_advisory_lock(%s)", (STANDARD_CONCURRENCY_GATE_KEY,))
        try:
            yield
        finally:
            try:
                gate_conn.execute("SELECT pg_advisory_unlock(%s)", (STANDARD_CONCURRENCY_GATE_KEY,))
            except Exception:
                pass


def sanitize_error_receipt(exc, mode='standard', model_id=None, req_id=None):
    exc_str = exc.__class__.__name__
    is_uncertain = (
        isinstance(exc, (httpx.TimeoutException, httpx.TransportError))
        or 'timeout' in exc_str.lower()
        or 'transport' in exc_str.lower()
        or 'http_error_5' in str(exc).lower()
        or getattr(exc, 'charge_state', None) == 'uncertain'
    )
    safe_code = getattr(exc, 'code', None)
    if not safe_code:
        if isinstance(exc, httpx.TimeoutException):
            safe_code = 'provider_timeout'
        elif isinstance(exc, httpx.TransportError):
            safe_code = 'provider_transport_error'
        elif 'http_error_' in str(exc):
            safe_code = 'provider_http_error'
        else:
            safe_code = 'provider_response_rejected'

    receipt = getattr(exc, 'receipt', None) or {}
    clean_receipt = {
        'mode': mode,
        'model_id': model_id or receipt.get('requested_model'),
        'request_id': receipt.get('request_id') or req_id,
        'http_status': receipt.get('http_status'),
        'usage': receipt.get('usage'),
        'error': {
            'code': safe_code,
            'error_class': getattr(exc, 'original_exception_class', None) or exc.__class__.__name__,
            'charge_state': 'uncertain' if is_uncertain else 'unconfirmed',
        }
    }
    return clean_receipt


def report_data(video, checkpoints, rows, provider, source, note_envelope, receipts, manifest=None):
    if manifest is None:
        manifest = dict(
            schema_version='run-manifest-1',
            profile='test',
            provider_mode='recorded',
            requested=len(checkpoints),
            persona_ids=sorted(c['persona_id'] for c in checkpoints),
            resample_seed=20261028,
        )
    return build_report(manifest, video, checkpoints, rows, provider, source, note_envelope, receipts)


def instantiate_provider(provider_factory, video_sha256, duration_ms, profile='test', lease=None):
    try:
        return provider_factory(video_sha256, duration_ms, profile=profile, lease=lease)
    except TypeError:
        try:
            return provider_factory(video_sha256, duration_ms, profile=profile)
        except TypeError:
            return provider_factory(video_sha256, duration_ms)


def process_analysis(lease, provider_factory=None, before_publish=None):
    with connection() as conn:
        video = fence(conn, lease)
        run_row = conn.execute('SELECT * FROM runs WHERE id=%s', (lease['run_id'],)).fetchone()
    manifest = run_row['manifest'] if (run_row and run_row.get('manifest')) else {}
    profile = manifest.get('profile', 'test')
    mode = manifest.get('provider_mode', 'recorded')

    if provider_factory is None:
        provider_factory = StandardProvider if mode == 'standard' else RecordedProvider

    provider = instantiate_provider(provider_factory, video['sha256'], video['metadata']['duration_ms'], profile=profile, lease=lease)
    prepare(lease, provider)

    with connection() as conn:
        video = fence(conn, lease)
        scenes = video['features']['scenes']
        scenes_count = len(scenes)
        requested = manifest.get('requested', len(provider.persona_ids))
        max_calls = min(40 if profile == 'test' else 651, requested * scenes_count + 1)

        cp = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s AND status='active' ORDER BY persona_id LIMIT 1", (lease['run_id'],)).fetchone()
        if cp:
            scene = scenes[cp['next_scene']]
            projection = project(scene, cp)
            validate_projection(projection, scene, cp)
            unit = f"{cp['persona_id']}:{scene['scene_id']}"

            existing_call = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s AND unit=%s", (lease['run_id'], unit)).fetchone()
            if existing_call:
                if existing_call['status'] == 'accepted':
                    # Durable received payload can publish once without another generation
                    rx_row = conn.execute("SELECT * FROM reactions WHERE run_id=%s AND persona_id=%s AND scene_id=%s", (lease['run_id'], cp['persona_id'], scene['scene_id'])).fetchone()
                    if rx_row:
                        status = 'stopped' if not rx_row['reaction']['still_watching'] else ('complete' if scene['scene_id'] == len(scenes) - 1 else 'active')
                        conn.execute('UPDATE checkpoints SET next_scene=next_scene+1,status=%s,impression=%s WHERE run_id=%s AND persona_id=%s', (status, rx_row['reaction']['impression_update'], lease['run_id'], cp['persona_id']))
                        release(conn, lease)
                        return
                elif existing_call['status'] == 'dispatched':
                    if mode == 'standard':
                        # Unresolved dispatched call after restart becomes visible uncertainty with NO reissue
                        err_receipt = {
                            'mode': 'standard',
                            'model_id': provider.model_id,
                            'error': {'code': 'unresolved_dispatched_call', 'error_class': 'WorkerCrash', 'charge_state': 'uncertain'}
                        }
                        conn.execute("UPDATE provider_calls SET status='failed',receipt=%s WHERE run_id=%s AND unit=%s", (Jsonb(err_receipt), lease['run_id'], unit))
                        conn.execute("UPDATE checkpoints SET status='failed' WHERE run_id=%s AND persona_id=%s", (lease['run_id'], cp['persona_id']))
                        conn.execute("UPDATE runs SET error_code='uncertain_provider_charge',status='failed',stage='failed' WHERE id=%s", (lease['run_id'],))
                        set_operational_pause()
                        release(conn, lease, True)
                        return
            else:
                # 1. Enforce call ceiling before admitting a NEW provider call
                call_count = conn.execute("SELECT count(*) AS count FROM provider_calls WHERE run_id=%s", (lease['run_id'],)).fetchone()['count']
                if call_count >= max_calls:
                    conn.execute("UPDATE checkpoints SET status='failed' WHERE run_id=%s AND status='active'", (lease['run_id'],))
                    conn.execute("UPDATE runs SET error_code='run_call_ceiling_exceeded',status='failed',stage='failed' WHERE id=%s", (lease['run_id'],))
                    release(conn, lease, True)
                    return

                # 2. Check if previous call had uncertain charge or operational pause before admitting a NEW provider call
                uncertain_call = conn.execute(
                    "SELECT 1 FROM provider_calls WHERE run_id=%s AND status='failed' AND (receipt->'error'->>'charge_state'='uncertain' OR receipt->'error'->>'code'='unresolved_dispatched_call') LIMIT 1",
                    (lease['run_id'],)
                ).fetchone()
                if uncertain_call or (mode == 'standard' and is_operationally_paused()):
                    conn.execute("UPDATE checkpoints SET status='failed' WHERE run_id=%s AND status='active'", (lease['run_id'],))
                    conn.execute("UPDATE runs SET error_code='uncertain_provider_charge',status='failed',stage='failed' WHERE id=%s", (lease['run_id'],))
                    release(conn, lease, True)
                    return

                # Durable provider_calls marker committed under fence before send
                conn.execute("INSERT INTO provider_calls(run_id,unit,status,audit) VALUES(%s,%s,'dispatched',%s)", (lease['run_id'], unit, Jsonb(projection)))

    if cp:
        try:
            if mode == 'standard':
                with standard_concurrency_gate():
                    reaction, evidence, normalized, data, sha = provider.verdict(projection)
            else:
                reaction, evidence, normalized, data, sha = provider.verdict(projection)
            validate_reaction(reaction, set(provider.persona_ids), {s['scene_id']: (s['start_ms'], s['end_ms']) for s in video['features']['scenes']})
            require(reaction['persona_id'] == cp['persona_id'] and reaction['scene_id'] == scene['scene_id'], 'response identity mismatch')
            require(evidence['id'] == reaction['evidence_id'] and evidence['persona_id'] == cp['persona_id'] and evidence['scene_id'] == scene['scene_id'], 'missing evidence')
            require((evidence['start_ms'], evidence['end_ms']) == (scene['start_ms'], scene['end_ms']), 'evidence time mismatch')
            require(isinstance(evidence['quote'], str) and evidence['quote'].strip(), 'missing reason')
        except (ValueError, KeyError, TypeError, StopIteration) as exc:
            with connection() as conn:
                fence(conn, lease)
                conn.execute("UPDATE checkpoints SET status='failed' WHERE run_id=%s AND persona_id=%s", (lease['run_id'], cp['persona_id']))
                err_receipt = sanitize_error_receipt(exc, mode, provider.model_id)
                conn.execute("UPDATE provider_calls SET status='failed',receipt=%s WHERE run_id=%s AND unit=%s", (Jsonb(err_receipt), lease['run_id'], unit))
                err_code = 'uncertain_provider_charge' if err_receipt['error']['charge_state'] == 'uncertain' else err_receipt['error']['code']
                if err_receipt['error']['charge_state'] == 'uncertain': set_operational_pause()
                conn.execute("UPDATE runs SET error_code=%s,status='failed',stage='failed' WHERE id=%s", (err_code, lease['run_id']))
                release(conn, lease, True)
            return

        key = reserve_object(video['id'], 'provider_files', 'json', lease)
        if before_publish:
            before_publish(lease)
        with connection() as conn:
            fence(conn, lease)
            put_reserved(conn, video['id'], key, data, 'application/json')
            # Stored receipt excludes private raw output/reasoning, retains hashes and usage/cost.
            receipt = {k: v for k, v in normalized.items() if k != 'output'}
            receipt.update(
                response_sha256=sha,
                mode=mode,
                new_provider_calls=1 if mode == 'standard' else 0
            )
            conn.execute('INSERT INTO reactions VALUES(%s,%s,%s,%s,%s)', (lease['run_id'], cp['persona_id'], scene['scene_id'], Jsonb(reaction), Jsonb(evidence)))
            status = 'stopped' if not reaction['still_watching'] else ('complete' if scene['scene_id'] == len(video['features']['scenes']) - 1 else 'active')
            conn.execute('UPDATE checkpoints SET next_scene=next_scene+1,status=%s,impression=%s WHERE run_id=%s AND persona_id=%s', (status, reaction['impression_update'], lease['run_id'], cp['persona_id']))
            conn.execute("UPDATE provider_calls SET status='accepted',receipt=%s WHERE run_id=%s AND unit=%s", (Jsonb(receipt), lease['run_id'], unit))
            event_payload = dict(
                persona_id=cp['persona_id'],
                scene_id=scene['scene_id'],
                at_ms=scene['end_ms'],
                evidence_id=evidence['id'],
                actions=reaction['actions'],
                reason=evidence['quote'],
            )
            event(conn, lease['run_id'], 'persona.continued' if reaction['still_watching'] else 'persona.stopped', event_payload)
            release(conn, lease)
        return

    # No more active checkpoints: move to reporting
    with connection() as conn:
        fence(conn, lease)
        stage(conn, lease['run_id'], 'reporting')
        run_row = conn.execute('SELECT * FROM runs WHERE id=%s', (lease['run_id'],)).fetchone()
        checkpoints = conn.execute('SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id', (lease['run_id'],)).fetchall()
        rows = conn.execute('SELECT * FROM reactions WHERE run_id=%s ORDER BY persona_id,scene_id', (lease['run_id'],)).fetchall()
        receipts = [r['receipt'] for r in conn.execute('SELECT receipt FROM provider_calls WHERE run_id=%s AND receipt IS NOT NULL ORDER BY unit', (lease['run_id'],)).fetchall()]

    if mode == 'standard':
        reused_notes = False
        with connection() as conn:
            fence(conn, lease)
            existing_notes_call = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s AND unit='notes'", (lease['run_id'],)).fetchone()
            if existing_notes_call:
                if existing_notes_call['status'] == 'accepted':
                    audit_data = existing_notes_call.get('audit') or {}
                    normalized = audit_data.get('normalized')
                    if not normalized:
                        # Accepted notes row without durable output must fail visibly with no resend
                        conn.execute("UPDATE runs SET error_code='missing_durable_notes_output',status='failed',stage='failed' WHERE id=%s", (lease['run_id'],))
                        release(conn, lease, True)
                        return
                    notes_receipt = existing_notes_call.get('receipt')
                    if notes_receipt and notes_receipt not in receipts:
                        receipts.append(notes_receipt)
                    reused_notes = True
                elif existing_notes_call['status'] == 'dispatched':
                    err_receipt = {
                        'mode': 'standard',
                        'model_id': provider.model_id,
                        'error': {'code': 'unresolved_dispatched_call', 'error_class': 'WorkerCrash', 'charge_state': 'uncertain'}
                    }
                    conn.execute("UPDATE provider_calls SET status='failed',receipt=%s WHERE run_id=%s AND unit='notes'", (Jsonb(err_receipt), lease['run_id']))
                    conn.execute("UPDATE runs SET error_code='uncertain_provider_charge',status='failed',stage='failed' WHERE id=%s", (lease['run_id'],))
                    set_operational_pause()
                    release(conn, lease, True)
                    return
                else:
                    release(conn, lease, True)
                    return

        if not reused_notes:
            note_context = build_note_context(manifest, video, checkpoints, rows)
            if note_context and note_context.get('supported_triggers'):
                with connection() as conn:
                    fence(conn, lease)
                    # 1. Ceiling check before admitting new notes call
                    call_count = conn.execute("SELECT count(*) AS count FROM provider_calls WHERE run_id=%s", (lease['run_id'],)).fetchone()['count']
                    if call_count >= max_calls:
                        conn.execute("UPDATE runs SET error_code='run_call_ceiling_exceeded',status='failed',stage='failed' WHERE id=%s", (lease['run_id'],))
                        release(conn, lease, True)
                        return
                    # 2. Uncertainty / operational pause check before admitting new notes call
                    uncertain_call = conn.execute(
                        "SELECT 1 FROM provider_calls WHERE run_id=%s AND status='failed' AND (receipt->'error'->>'charge_state'='uncertain' OR receipt->'error'->>'code'='unresolved_dispatched_call') LIMIT 1",
                        (lease['run_id'],)
                    ).fetchone()
                    if uncertain_call or (mode == 'standard' and is_operationally_paused()):
                        conn.execute("UPDATE runs SET error_code='uncertain_provider_charge',status='failed',stage='failed' WHERE id=%s", (lease['run_id'],))
                        release(conn, lease, True)
                        return
                    conn.execute("INSERT INTO provider_calls(run_id,unit,status,audit) VALUES(%s,'notes','dispatched',%s)", (lease['run_id'], Jsonb(note_context)))

                try:
                    with standard_concurrency_gate():
                        normalized, data, sha = provider.notes(note_context)
                except Exception as exc:
                    with connection() as conn:
                        fence(conn, lease)
                        err_receipt = sanitize_error_receipt(exc, 'standard', provider.model_id)
                        conn.execute("UPDATE provider_calls SET status='failed',receipt=%s WHERE run_id=%s AND unit='notes'", (Jsonb(err_receipt), lease['run_id']))
                        err_code = 'uncertain_provider_charge' if err_receipt['error']['charge_state'] == 'uncertain' else err_receipt['error']['code']
                        if err_receipt['error']['charge_state'] == 'uncertain':
                            set_operational_pause()
                        conn.execute("UPDATE runs SET error_code=%s,status='failed',stage='failed' WHERE id=%s", (err_code, lease['run_id']))
                        release(conn, lease, True)
                    return

                key = reserve_object(video['id'], 'provider_files', 'json', lease)
                with connection() as conn:
                    fence(conn, lease)
                    put_reserved(conn, video['id'], key, data, 'application/json')
                    if normalized.get('new_provider_calls', 0) > 0:
                        notes_receipt = {k: v for k, v in normalized.items() if k != 'output'}
                        notes_receipt.update(
                            request_id=normalized.get('request_id'),
                            status=normalized.get('status'),
                            cost_usd=normalized.get('cost_usd'),
                            mode='standard',
                            pricing_version=normalized.get('pricing_version', provider.pricing_version)
                        )
                        conn.execute(
                            "UPDATE provider_calls SET status='accepted',receipt=%s,audit=%s WHERE run_id=%s AND unit='notes'",
                            (Jsonb(notes_receipt), Jsonb({'context': note_context, 'normalized': normalized, 'object_key': key}), lease['run_id'])
                        )
                        receipts.append(notes_receipt)
            else:
                normalized, data, sha = provider.notes(note_context)
                key = reserve_object(video['id'], 'provider_files', 'json', lease)
                with connection() as conn:
                    fence(conn, lease)
                    put_reserved(conn, video['id'], key, data, 'application/json')
    else:
        normalized, data, sha = provider.notes()
        key = reserve_object(video['id'], 'provider_files', 'json', lease)
        with connection() as conn:
            fence(conn, lease)
            put_reserved(conn, video['id'], key, data, 'application/json')

    report = build_report(run_row['manifest'], video, checkpoints, rows, provider, source_sha(), normalized, receipts)
    if before_publish:
        before_publish(lease)
    with connection() as conn:
        fence(conn, lease)
        terminal_status = 'complete' if report['cast']['status'] in ('complete', 'complete_test_profile') else report['cast']['status']
        conn.execute('UPDATE runs SET report=%s,status=%s,stage=%s,completed_at=now() WHERE id=%s',
            (Jsonb(report), terminal_status, 'report', lease['run_id']))
        release(conn, lease, True)


def process_once(provider_factory=None, before_publish=None):
    lease = claim()
    if not lease:
        return False
    try:
        if lease['kind'] == 'deletion':
            delete_step(lease)
        else:
            process_analysis(lease, provider_factory, before_publish)
    except LeaseLost:
        pass  # Tombstone/another generation owns all future publication.
    except Exception as exc:
        with connection() as conn:
            try:
                fence(conn, lease)
            except LeaseLost:
                return True
            code = str(exc) if isinstance(exc, ProviderUnavailable) else 'analysis_failed'
            conn.execute("UPDATE runs SET status='failed',stage='failed',error_code=%s WHERE id=%s", (code, lease['run_id']))
            release(conn, lease, True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    while True:
        retention_cleanup()
        worked = process_once()
        if args.once:
            return
        time.sleep(.1 if worked else .5)


if __name__ == '__main__':
    main()
