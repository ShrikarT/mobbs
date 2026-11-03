"""Child worker process for bounded pool concurrency and fault recovery tests."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MOBBS_PROVIDER_MODE', 'standard')
os.environ.setdefault('VIRALIST_PROVIDER_MODE', 'standard')
os.environ.setdefault('MODEL_API_KEY', 'DUMMY_KEY_LOCAL')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import httpx
from apps.api.app.config import settings
from apps.api.app.db import connection
from apps.api.app.standard_provider import StandardProvider
from apps.api.app.worker import process_once
from tests.test_v03_standard_app import make_verdict_response, make_notes_response


def info(req):
    b = json.loads(req.content)
    text = b['input'][0]['content'][0]['text']
    data = json.loads(text[text.index('{'):])
    return b, data


def response(req, kind='normal'):
    b, d = info(req)
    if 'viewer' in d:
        p = d['viewer']['persona_id']
        raw = make_verdict_response(p, still_watching=(kind != 'stop'), reason='Synthetic test reason', impression='Own observed frame')
    else:
        triggers = d.get('supported_triggers', [])
        if triggers:
            t = triggers[0]
            e = t['evidence'][0]
            raw = make_notes_response([dict(
                start_sec=t['start_sec'],
                end_sec=t['end_sec'],
                finding='Synthetic supported note',
                suggested_edit='Capture a clearer real workflow.',
                evidence_ids=[e['evidence_id']],
                quotes=[e['quote']],
            )])
        else:
            raw = make_notes_response([])
    return httpx.Response(200, json=raw)


def run_child(rid, action, folder):
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    concurrency_file = d / "concurrency.log"
    active_count_file = d / f"{rid}.active"

    def handler(req):
        b, data = info(req)
        is_verdict = 'viewer' in data
        pid = data['viewer']['persona_id'] if is_verdict else 'notes'

        # Record HTTP start
        with (d / f"{rid}.http").open('a') as f:
            f.write(f"{pid}\n")
        (d / f"{rid}.entered").write_text('1')

        if action == 'hold':
            with (d / f"{rid}.held_count").open('a') as f:
                f.write(f"{pid}\n")
            deadline = time.monotonic() + 30
            while not (d / 'release').exists():
                if time.monotonic() > deadline:
                    raise RuntimeError('parent_release_timeout')
                time.sleep(0.02)
            return response(req, 'stop')

        if action == 'kill-on-dispatch':
            # Abrupt exit while call is in-flight to simulate worker crash
            os._exit(42)

        if action == 'error-429':
            if pid == 'p002':
                return httpx.Response(429, json={'error': {'message': 'rate limited'}})

        if action == 'timeout':
            if pid == 'p002':
                raise httpx.ReadTimeout("Simulated provider read timeout")

        if action == 'delay':
            time.sleep(0.03)

        return response(req, 'normal')

    t = httpx.MockTransport(handler)

    def factory(h, dur, profile='test', lease=None):
        if lease is not None:
            assert lease['run_id'] == rid, f"expected lease run_id {rid}, got {lease['run_id']}"
        return StandardProvider(h, dur, profile=profile, lease=lease, transport=t)

    try:
        worked = process_once(provider_factory=factory)
        (d / f"{rid}.done").write_text(str(worked))
    except Exception as e:
        (d / f"{rid}.error").write_text(type(e).__name__)
        raise


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        run_child(*sys.argv[2:])
        sys.exit(0)
