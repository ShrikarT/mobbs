import os
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MOBBS_RUNTIME', os.environ.get('VIRALIST_RUNTIME') or 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json')
os.environ.setdefault('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json')
os.environ.setdefault('MOBBS_PROVIDER_MODE', 'standard')
os.environ.setdefault('VIRALIST_PROVIDER_MODE', 'standard')
os.environ.setdefault('MODEL_API_KEY', 'DUMMY_KEY_LOCAL')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import httpx
from apps.api.app.worker import process_once
from apps.api.app.standard_provider import StandardProvider
from apps.api.app.db import connection
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
        t = d['supported_triggers'][0]
        e = t['evidence'][0]
        raw = make_notes_response([dict(
            start_sec=t['start_sec'],
            end_sec=t['end_sec'],
            finding='Synthetic supported note',
            suggested_edit='Capture a clearer real workflow.',
            evidence_ids=[e['evidence_id']],
            quotes=[e['quote']],
        )])
    return httpx.Response(200, json=raw)


def factory(handler):
    t = httpx.MockTransport(handler)
    return lambda h, d, profile='test', lease=None: StandardProvider(h, d, profile=profile, lease=lease, transport=t)


def run_child(rid, action, folder):
    d = Path(folder)

    def handler(req):
        b, data = info(req)
        with (d / f"{rid}.http").open('a') as f:
            f.write(('verdict' if 'viewer' in data else 'notes') + '\n')
        (d / f"{rid}.entered").write_text('1')
        if action == 'hold':
            deadline = time.monotonic() + 30
            while not (d / 'release').exists():
                if time.monotonic() > deadline:
                    raise RuntimeError('parent_release_timeout')
                time.sleep(0.03)
        return response(req, 'stop')

    def fault(lease):
        with connection() as db:
            row = db.execute("select status from provider_calls where run_id=%s and unit='notes'", (rid,)).fetchone()
        if action == 'notes-fault' and row and row['status'] == 'accepted':
            os._exit(72)

    try:
        limit = 10 if action.startswith('notes-') else 1
        for _ in range(limit):
            worked = process_once(provider_factory=factory(handler), before_publish=fault)
            if not worked:
                break
    except Exception as e:
        (d / f"{rid}.error").write_text(type(e).__name__)
        raise


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'once':
        run_child(*sys.argv[2:])
        sys.exit(0)
