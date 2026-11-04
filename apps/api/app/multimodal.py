"""Durable preparation units; only current-scene features reach a persona."""
import threading
from contextlib import contextmanager

from contracts.normalized import require
from .config import settings
from .db import connection, Jsonb
from .domain import fence, LeaseLost, reserve_object, put_reserved
from .media import decoder, INPUT
from .scene_models import SceneModels, PIPELINE
from .standard_provider import ProviderUnavailable, digest


@contextmanager
def preparation_lease(lease):
    stopped, lost = threading.Event(), threading.Event()
    def heartbeat():
        while not stopped.wait(4):
            try:
                with connection() as conn:
                    row = conn.execute("UPDATE jobs SET lease_until=now()+%s*interval '1 second' WHERE id=%s AND generation=%s AND status='leased' RETURNING id",
                                       (settings().lease_seconds, lease['id'], lease['generation'])).fetchone()
                    if not row: lost.set(); return
            except Exception:
                lost.set(); return
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        yield
        if lost.is_set(): raise LeaseLost('preparation_lease_lost')
    finally:
        stopped.set(); thread.join(timeout=6)


def durable_feature(lease, unit, send):
    with connection() as conn:
        fence(conn, lease)
        existing = conn.execute('SELECT * FROM provider_calls WHERE run_id=%s AND unit=%s', (lease['run_id'], unit)).fetchone()
        if existing:
            if existing['status'] == 'accepted': return existing['audit']['feature']
            raise ProviderUnavailable('uncertain_provider_charge', charge_state='uncertain')
        require(not conn.execute("SELECT 1 FROM provider_calls WHERE run_id=%s AND status='dispatched'", (lease['run_id'],)).fetchone(),
                'unresolved_preparation_request')
        conn.execute("INSERT INTO provider_calls(run_id,unit,status,audit) VALUES(%s,%s,'dispatched','{}')", (lease['run_id'], unit))
    try:
        feature, data, receipt = send()
        key = reserve_object(lease['video_id'], 'provider_files', 'json', lease)
        with connection() as conn:
            fence(conn, lease)
            put_reserved(conn, lease['video_id'], key, data, 'application/json')
            receipt['response_sha256'] = digest(data)
            conn.execute("UPDATE provider_calls SET status='accepted',receipt=%s,audit=%s WHERE run_id=%s AND unit=%s",
                         (Jsonb(receipt), Jsonb({'feature': feature, 'object_key': key}), lease['run_id'], unit))
        return feature
    except LeaseLost:
        raise
    except Exception as exc:
        receipt = dict(getattr(exc, 'receipt', {}) or {})
        uncertain = getattr(exc, 'charge_state', 'uncertain') == 'uncertain'
        receipt.update(mode='standard', error={'code': 'media_preparation_failed', 'charge_state': 'uncertain' if uncertain else 'unconfirmed'})
        with connection() as conn:
            fence(conn, lease)
            conn.execute("UPDATE provider_calls SET status='failed',receipt=%s WHERE run_id=%s AND unit=%s", (Jsonb(receipt), lease['run_id'], unit))
        raise ProviderUnavailable('uncertain_provider_charge' if uncertain else 'media_preparation_failed',
                                  charge_state=receipt['error']['charge_state'], receipt=receipt) from None


def enrich_scenes(lease, provider, path, directory, scenes, audio_present):
    # Shared once per scene, never once per persona; inline media leaves no Files API ID.
    models = SceneModels(provider)
    from .worker import standard_concurrency_gate
    for scene in scenes:
        with connection() as conn:
            fence(conn, lease)
            conn.execute("UPDATE runs SET stage='reading_video',status='processing' WHERE id=%s", (lease['run_id'],))
        index, duration = scene['scene_id'], (scene['end_ms'] - scene['start_ms']) / 1000
        clip = directory / f'scene-{index}.mp4'
        decoder(['ffmpeg', '-v', 'error', '-xerror', *INPUT, '-ss', str(scene['start_ms']/1000), '-i', str(path),
                 '-t', str(duration), '-an', '-vf', 'scale=640:640:force_original_aspect_ratio=decrease,fps=8',
                 '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-threads', '1', '-movflags', '+faststart', '-y', str(clip)], timeout=35)
        with standard_concurrency_gate(8, run_id=lease['run_id']):
            scene['observations'] = durable_feature(lease, f'prep:visual:{index}', lambda: models.observe(clip, scene))
        scene['ocr'] = scene['observations']['visible_text']
        if audio_present:
            with connection() as conn:
                fence(conn, lease)
                conn.execute("UPDATE runs SET stage='transcribing' WHERE id=%s", (lease['run_id'],))
            audio = directory / f'scene-{index}.wav'
            decoder(['ffmpeg', '-v', 'error', '-xerror', *INPUT, '-ss', str(scene['start_ms']/1000), '-i', str(path),
                     '-t', str(duration), '-vn', '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', '-threads', '1', '-y', str(audio)])
            with standard_concurrency_gate(8, run_id=lease['run_id']):
                scene['transcript'] = durable_feature(lease, f'prep:audio:{index}', lambda: models.transcribe(audio, scene))
        scene['media_pipeline'] = PIPELINE
