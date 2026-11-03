import json
import os
os.environ.setdefault('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')
import threading
import time
import unittest
from pathlib import Path

import httpx
from starlette.testclient import TestClient

from apps.api.app.config import settings
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.domain import fence
from apps.api.app.main import app
from apps.api.app.providers import StandardProvider
from apps.api.app.standard_provider import build_note_context
from apps.api.app.reporting import build_report
from apps.api.app.worker import (
    clear_operational_pause,
    process_once,
    maybe_emit_provisional_verdict,
)
from tests.test_v03_standard_app import (
    create_session,
    get_video_a_bytes,
    make_verdict_response,
    make_notes_response,
)


class TestV03ProvisionalVerdict(unittest.TestCase):
    def setUp(self):
        clear_operational_pause()
        self.client = TestClient(app, base_url='http://127.0.0.1:58000')
        self.headers = create_session(self.client)
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")

    def tearDown(self):
        clear_operational_pause()
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")

    def _create_test_video(self, idempotency_prefix="prov_vid"):
        up = self.client.post(
            '/videos',
            headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'{idempotency_prefix}_{uid()[:8]}'},
            content=get_video_a_bytes()
        )
        self.assertEqual(up.status_code, 201)
        return up.json()['video_id']

    def test_verdict_provisional_emitted_exactly_once_when_scene_0_completes(self):
        """(a) verdict.provisional is emitted atomically and exactly once when all personas complete Scene 0."""
        vid = self._create_test_video("pv_emit")
        run_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rpv_{uid()[:8]}'},
            json={'video_id': vid, 'profile': 'test'}
        )
        self.assertEqual(run_res.status_code, 202)
        run_id = run_res.json()['run_id']

        def handler(request: httpx.Request):
            body = json.loads(request.read().decode())
            if 'verdicts' in body['text']['format']['schema']['properties']:
                text = body['input'][0]['content'][0]['text']
                data = json.loads(text[text.index('{'):])
                pid = data['viewer']['persona_id']
                scene_id = data['current_segment']['scene_id']

                # Persona 2 drops in Scene 0; Personas 1 and 3 continue
                if pid == 'p002' and scene_id == 0:
                    resp = make_verdict_response(pid, still_watching=False, reason="Too slow at the start", impression="Weak hook")
                else:
                    resp = make_verdict_response(pid, still_watching=True, reason="Engaging visual", impression="Good pace")
                return httpx.Response(200, json=resp)
            else:
                return httpx.Response(200, json=make_notes_response([]))

        transport = httpx.MockTransport(handler)

        def mock_factory(vhash, dur, profile='test', lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=transport)

        # Step 1: Persona 1 evaluates Scene 0
        worked = process_once(provider_factory=mock_factory)
        self.assertTrue(worked)
        with connection() as conn:
            pv_count = conn.execute("SELECT count(*) AS count FROM events WHERE run_id=%s AND type='verdict.provisional'", (run_id,)).fetchone()['count']
        self.assertEqual(pv_count, 0, "Must NOT emit provisional verdict before all personas complete Scene 0")

        # Step 2: Persona 2 evaluates Scene 0
        worked = process_once(provider_factory=mock_factory)
        self.assertTrue(worked)
        with connection() as conn:
            pv_count = conn.execute("SELECT count(*) AS count FROM events WHERE run_id=%s AND type='verdict.provisional'", (run_id,)).fetchone()['count']
        self.assertEqual(pv_count, 0, "Must NOT emit provisional verdict while Persona 3 is still pending Scene 0")

        # Step 3: Persona 3 evaluates Scene 0 (All 3 personas have now completed Scene 0!)
        worked = process_once(provider_factory=mock_factory)
        self.assertTrue(worked)
        with connection() as conn:
            pv_events = conn.execute("SELECT * FROM events WHERE run_id=%s AND type='verdict.provisional'", (run_id,)).fetchall()
        self.assertEqual(len(pv_events), 1, "Must emit verdict.provisional when all personas complete Scene 0")

        pv_payload = pv_events[0]['payload']
        self.assertEqual(pv_payload['scene_id'], 0)
        self.assertEqual(pv_payload['total_personas'], 3)
        self.assertEqual(pv_payload['retained_count'], 2)
        self.assertEqual(pv_payload['dropped_count'], 1)
        self.assertEqual(pv_payload['retention_pct'], 66.7)
        self.assertEqual(pv_payload['drop_pct'], 33.3)
        self.assertEqual(len(pv_payload['top_drop_reasons']), 1)
        self.assertEqual(pv_payload['top_drop_reasons'][0]['reason'], "Too slow at the start")
        self.assertEqual(pv_payload['top_drop_reasons'][0]['count'], 1)
        self.assertEqual(pv_payload['top_drop_reasons'][0]['percentage'], 33.3)
        self.assertEqual(len(pv_payload['top_drop_reasons'][0]['evidence_quotes']), 1)
        self.assertEqual(pv_payload['top_drop_reasons'][0]['evidence_quotes'][0]['persona_id'], 'p002')
        self.assertEqual(pv_payload['top_drop_reasons'][0]['evidence_quotes'][0]['quote'], "Too slow at the start")

        # Step 4: Run further steps into Scene 1: verify event is emitted EXACTLY ONCE
        for _ in range(5):
            worked = process_once(provider_factory=mock_factory)
            if not worked:
                break
        with connection() as conn:
            final_pv_count = conn.execute("SELECT count(*) AS count FROM events WHERE run_id=%s AND type='verdict.provisional'", (run_id,)).fetchone()['count']
        self.assertEqual(final_pv_count, 1, "verdict.provisional must be emitted strictly exactly once per run")

    def test_get_runs_recovers_provisional_verdict_and_reload_preserves_it(self):
        """(b) GET /runs/{id} recovers provisional_verdict, and (c) reload preserves it without depending on live SSE."""
        vid = self._create_test_video("pv_get")
        run_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rpv_get_{uid()[:8]}'},
            json={'video_id': vid, 'profile': 'test'}
        )
        run_id = run_res.json()['run_id']

        # Before Scene 0 completion: GET /runs/{id} has provisional_verdict as None
        st_before = self.client.get(f'/runs/{run_id}', headers=self.headers).json()
        self.assertIsNone(st_before.get('provisional_verdict'))

        def handler(request: httpx.Request):
            body = json.loads(request.read().decode())
            if 'verdicts' in body['text']['format']['schema']['properties']:
                text = body['input'][0]['content'][0]['text']
                data = json.loads(text[text.index('{'):])
                pid = data['viewer']['persona_id']
                scene_id = data['current_segment']['scene_id']
                if pid == 'p001' and scene_id == 0:
                    resp = make_verdict_response(pid, still_watching=False, reason="Unclear hook value", impression="Confused")
                else:
                    resp = make_verdict_response(pid, still_watching=True, reason="Clear value", impression="Kept watching")
                return httpx.Response(200, json=resp)
            else:
                return httpx.Response(200, json=make_notes_response([]))

        transport = httpx.MockTransport(handler)

        def mock_factory(vhash, dur, profile='test', lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=transport)

        # Run all 3 personas through Scene 0
        for _ in range(3):
            process_once(provider_factory=mock_factory)

        # (b) GET /runs/{id} recovers provisional_verdict
        st_after = self.client.get(f'/runs/{run_id}', headers=self.headers)
        self.assertEqual(st_after.status_code, 200)
        data = st_after.json()
        pv = data.get('provisional_verdict')
        self.assertIsNotNone(pv, "GET /runs/{id} must expose provisional_verdict")
        self.assertEqual(pv['scene_id'], 0)
        self.assertEqual(pv['total_personas'], 3)
        self.assertEqual(pv['retained_count'], 2)
        self.assertEqual(pv['dropped_count'], 1)
        self.assertEqual(pv['retention_pct'], 66.7)
        self.assertEqual(pv['drop_pct'], 33.3)
        self.assertEqual(len(pv['top_drop_reasons']), 1)
        self.assertEqual(pv['top_drop_reasons'][0]['reason'], "Unclear hook value")

        # (c) Simulate page reload (new client session with preserved session cookies)
        fresh_client = TestClient(app, base_url='http://127.0.0.1:58000', cookies=self.client.cookies)
        reloaded = fresh_client.get(f'/runs/{run_id}', headers=self.headers)
        self.assertEqual(reloaded.status_code, 200)
        reloaded_pv = reloaded.json().get('provisional_verdict')
        self.assertIsNotNone(reloaded_pv, "Page reload must preserve provisional_verdict without active SSE stream")
        self.assertEqual(reloaded_pv['retention_pct'], 66.7)
        self.assertEqual(reloaded_pv['drop_pct'], 33.3)
        self.assertEqual(reloaded_pv['top_drop_reasons'][0]['reason'], "Unclear hook value")

    def test_positive_directors_note_and_evidence_inspector_when_scene_crosses_15_percent_threshold(self):
        """Positive Director's Note generation & Evidence Inspector when drop rate crosses 15% threshold."""
        manifest = {'requested': 50, 'profile': 'flash', 'provider_mode': 'standard'}
        scenes = [
            {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
            {'scene_id': 1, 'start_ms': 3000, 'end_ms': 7000},
            {'scene_id': 2, 'start_ms': 7000, 'end_ms': 12000},
            {'scene_id': 3, 'start_ms': 12000, 'end_ms': 16000},
        ]
        video = {
            'metadata': {'duration_ms': 16000},
            'features': {'scenes': scenes, 'caveats': []}
        }

        # 50 checkpoints: 10 stopped in scene 0 (10/50 = 20% drop >= 15% threshold -> trigger stop_0!)
        checkpoints = []
        rows = []
        for i in range(1, 51):
            pid = f'p{i:03d}'
            if i <= 10:
                checkpoints.append({'persona_id': pid, 'status': 'stopped'})
                rows.append({
                    'reaction': {'persona_id': pid, 'scene_id': 0, 'still_watching': False, 'evidence_id': f'ev_{pid}_s0'},
                    'evidence': {'id': f'ev_{pid}_s0', 'persona_id': pid, 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'Opening hook lacks clear demonstration'}
                })
            else:
                checkpoints.append({'persona_id': pid, 'status': 'complete'})
                rows.append({
                    'reaction': {'persona_id': pid, 'scene_id': 0, 'still_watching': True, 'evidence_id': f'ev_{pid}_s0'},
                    'evidence': {'id': f'ev_{pid}_s0', 'persona_id': pid, 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'Good start'}
                })

        # 1. build_note_context generates supported triggers for Scene 0
        note_ctx = build_note_context(manifest, video, checkpoints, rows)
        self.assertEqual(len(note_ctx['supported_triggers']), 1)
        trig = note_ctx['supported_triggers'][0]
        self.assertEqual(trig['scene_id'], 0)
        self.assertEqual(trig['stop_fraction'], 0.20)
        self.assertGreaterEqual(trig['stop_fraction'], 0.15)
        self.assertEqual(len(trig['evidence']), 10)
        ev0 = trig['evidence'][0]
        self.assertEqual(ev0['quote'], 'Opening hook lacks clear demonstration')

        # 2. Provider generates note citing this supported trigger
        note_envelope = {
            'output': {
                'notes': [
                    {
                        'start_sec': 0.0,
                        'end_sec': 3.0,
                        'finding': 'High initial drop rate in the opening 3 seconds.',
                        'suggested_edit': 'Show the product interface immediately without talking-head delay.',
                        'evidence_ids': [ev0['evidence_id']],
                        'quotes': [ev0['quote']],
                    }
                ]
            }
        }

        # 3. build_report normalizes the note without crashes and surfaces it
        report = build_report(
            manifest=manifest,
            video=video,
            checkpoints=checkpoints,
            rows=rows,
            provider=None,
            source_sha='test_sha',
            note_envelope=note_envelope,
            receipts=[]
        )
        self.assertEqual(len(report['notes']), 1)
        n0 = report['notes'][0]
        self.assertEqual(n0['start_ms'], 0)
        self.assertEqual(n0['end_ms'], 3000)
        self.assertEqual(n0['interpretation'], 'High initial drop rate in the opening 3 seconds.')
        self.assertEqual(n0['fix'], 'Show the product interface immediately without talking-head delay.')
        self.assertEqual(len(n0['quotes']), 1)
        self.assertEqual(n0['quotes'][0]['text'], 'Opening hook lacks clear demonstration')
        self.assertEqual(report['suppressed_notes'], 0)


if __name__ == '__main__':
    unittest.main()
