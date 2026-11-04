"""Comprehensive test suite for V03 Standard Provider to App Integration.
Tests StandardProvider unit behavior, request capture, MockTransport double,
notes context & omission, API routes, manifest sealing, worker lifecycle,
concurrency 1, call ceiling, restart recovery, and uncertainty handling.
"""
import base64
import copy
import hashlib
import json
import os
os.environ.setdefault('MOBBS_RUNTIME', os.environ.get('VIRALIST_RUNTIME') or 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json')
os.environ.setdefault('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json')
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
import psycopg
from starlette.testclient import TestClient

from apps.api.app.config import settings, Settings
from apps.api.app.cast import get_persona_ids, get_persona_card, get_cast_hash, get_policies
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.domain import utc
from apps.api.app.main import app
from apps.api.app.providers import (
    StandardProvider,
    RecordedProvider,
    build_note_context,
    ProviderUnavailable,
    digest,
)
from apps.api.app.standard_provider import (
    compute_cost_usd,
    VERDICTS_SCHEMA,
    NOTES_SCHEMA,
    MODEL_ID,
    PRICING_VERSION,
)
from apps.api.app.storage import Storage
from apps.api.app.worker import (
    clear_operational_pause,
    is_operationally_paused,
    STANDARD_CONCURRENCY_GATE_KEY,
    process_once,
    claim,
    fence,
    release,
    project,
    validate_projection,
    instantiate_provider,
)
from contracts.normalized import require


def make_verdict_response(persona_id, still_watching=True, reason="Looking good", impression="Clear UI", actions=None, input_tokens=1500, cached_tokens=100, output_tokens=200, reasoning_tokens=120):
    if actions is None:
        actions = ["save"]
    payload = {
        "id": f"resp_{uid()[:12]}",
        "model": MODEL_ID,
        "status": "completed",
        "usage": {
            "input_tokens": input_tokens,
            "input_tokens_details": {"cached_tokens": cached_tokens},
            "output_tokens": output_tokens,
            "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
            "total_tokens": input_tokens + output_tokens,
        },
        "output": [
            {"type": "reasoning"},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps({
                            "verdicts": [
                                {
                                    "persona_id": persona_id,
                                    "still_watching": still_watching,
                                    "reason": reason,
                                    "impression": impression,
                                    "actions": actions,
                                }
                            ]
                        })
                    }
                ]
            }
        ]
    }
    return payload


def make_notes_response(notes_list=None, input_tokens=2000, output_tokens=300):
    if notes_list is None:
        notes_list = []
    payload = {
        "id": f"resp_{uid()[:12]}",
        "model": MODEL_ID,
        "status": "completed",
        "usage": {
            "input_tokens": input_tokens,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": output_tokens,
            "output_tokens_details": {"reasoning_tokens": 150},
            "total_tokens": input_tokens + output_tokens,
        },
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps({"notes": notes_list, "limitations": []})
                    }
                ]
            }
        ]
    }
    return payload


def create_session(client):
    res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
    require(res.status_code == 201, 'failed to create session')
    csrf = res.json()['csrf']
    return {
        'Host': '127.0.0.1:58000',
        'Origin': 'http://127.0.0.1:58000',
        'X-CSRF-Token': csrf,
    }


def get_video_a_bytes():
    ev_root = Path(settings().provider_evidence_root).resolve()
    s2_media = (ev_root / 'media.json') if (ev_root / 'media.json').exists() else (ev_root.parent / 'stage2-bounded' / 'media.json')
    data = json.loads(s2_media.read_text())
    p = Path(data['a']['path'])
    return p.read_bytes()


class TestStandardProviderUnit(unittest.TestCase):
    def setUp(self):
        # Set dummy 1x1 jpeg in storage for tests
        self.storage = Storage()
        self.dummy_frame_key = f"test_frame_{uid()[:8]}.jpg"
        self.dummy_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x22\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xbf\x00\xff\xd9"
        self.storage.put(self.dummy_frame_key, self.dummy_jpeg_bytes, 'image/jpeg')

    def test_pricing_calculation(self):
        """Pricing matches Meta pricing schedule: $1.25 input / $0.15 cached / $4.25 output per 1M."""
        # 1000 uncached input + 500 cached input + 200 output:
        # uncached = 1000 * 1.25 / 1M = 0.00125
        # cached = 500 * 0.15 / 1M = 0.000075
        # output = 200 * 4.25 / 1M = 0.00085
        # total = 0.002175
        usage = {
            'input_tokens': 1500,
            'cached_tokens': 500,
            'output_tokens': 200,
            'total_tokens': 1700
        }
        cost = compute_cost_usd(usage)
        self.assertEqual(cost, 0.002175)

    def test_50_persona_cards_in_order(self):
        """Map source p01..p50 in fifty-policies.json in order to live p001..p050."""
        policies, fhash = get_policies()
        self.assertEqual(len(policies), 50)
        self.assertEqual(fhash, '66d9649bf11e24fda80bddb721e0783f5c7ef72c0c203f448e70b5a744118ffd')

        flash_ids = get_persona_ids('flash')
        self.assertEqual(len(flash_ids), 50)
        self.assertEqual(flash_ids[0], 'p001')
        self.assertEqual(flash_ids[-1], 'p050')

        test_ids = get_persona_ids('test')
        self.assertEqual(test_ids, ['p001', 'p002', 'p003'])

        c1 = get_persona_card('p001')
        self.assertEqual(c1['goal'], policies[0]['card']['goal'])
        c50 = get_persona_card('p050')
        self.assertEqual(c50['goal'], policies[49]['card']['goal'])

        with self.assertRaises(ValueError):
            get_persona_card('p000')
        with self.assertRaises(ValueError):
            get_persona_card('p051')

    def test_verdict_request_capture_and_normalization(self):
        """Production StandardProvider captures correct request shape, sends to Meta endpoint, and normalizes."""
        captured_requests = []

        def handler(request: httpx.Request):
            captured_requests.append(request)
            body = json.loads(request.read().decode())
            # Ensure schema conforms to VERDICTS_SCHEMA
            self.assertEqual(body['text']['format']['schema'], VERDICTS_SCHEMA)
            self.assertEqual(body['text']['format']['strict'], True)
            self.assertEqual(body['model'], 'muse-spark-1.3')
            self.assertEqual(body['store'], False)
            self.assertEqual(body['reasoning'], {'effort': 'minimal'})
            self.assertEqual(body['max_output_tokens'], 4096)

            # Ensure prompt contains persona card and scene bounds
            inp = body['input'][0]['content']
            prompt = inp[0]['text']
            self.assertIn('p001', prompt)
            self.assertIn('scene_id', prompt)
            # Ensure frame image is present
            img_url = inp[1]['image_url']
            self.assertTrue(img_url.startswith('data:image/jpeg;base64,'))

            resp_json = make_verdict_response("p001", still_watching=True, reason="Clear workflow", impression="Helpful")
            return httpx.Response(200, json=resp_json, headers={'x-request-id': 'req_test_123'})

        transport = httpx.MockTransport(handler)
        provider = StandardProvider('dummy_hash', 10000, profile='test', transport=transport)

        projection = {
            'persona_id': 'p001',
            'scene': {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
            'allowed_media_refs': [self.dummy_frame_key],
            'max_visible_ms': 3000,
            'own_impression': 'Initial impression',
        }

        reaction, evidence, normalized, raw_bytes, sha = provider.verdict(projection)
        self.assertEqual(len(captured_requests), 1)
        req = captured_requests[0]
        self.assertEqual(str(req.url), 'https://api.meta.ai/v1/responses')
        self.assertEqual(req.headers['authorization'], 'Bearer DUMMY_KEY')

        # Check normalized outputs
        self.assertEqual(reaction['persona_id'], 'p001')
        self.assertEqual(reaction['scene_id'], 0)
        self.assertTrue(reaction['still_watching'])
        self.assertEqual(evidence['quote'], 'Clear workflow')
        self.assertEqual(normalized['status'], 'completed')
        self.assertEqual(normalized['mode'], 'standard')
        self.assertGreater(normalized['cost_usd'], 0.0)
        self.assertEqual(normalized['pricing_version'], PRICING_VERSION)
        self.assertEqual(provider.live_calls, 1)

    def test_verdict_timeout_uncertain_charge_fails_closed(self):
        """Transport timeout raises ProviderUnavailable with transport error and does not blind retry."""
        def handler(request: httpx.Request):
            raise httpx.ReadTimeout("Connection timed out")

        transport = httpx.MockTransport(handler)
        provider = StandardProvider('dummy_hash', 10000, profile='test', transport=transport)

        projection = {
            'persona_id': 'p001',
            'scene': {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
            'allowed_media_refs': [self.dummy_frame_key],
            'max_visible_ms': 3000,
            'own_impression': '',
        }
        with self.assertRaises(ProviderUnavailable) as cm:
            provider.verdict(projection)
        self.assertIn('provider_transport_error', str(cm.exception))


class TestNotesContextAndOmission(unittest.TestCase):
    def test_deterministic_omission_when_no_supported_triggers(self):
        """When no stop trigger qualifies (stop fraction < 15%), notes call is skipped and returns 0 calls."""
        transport_called = False

        def handler(request: httpx.Request):
            nonlocal transport_called
            transport_called = True
            return httpx.Response(200, json={})

        transport = httpx.MockTransport(handler)
        provider = StandardProvider('dummy_hash', 10000, profile='test', transport=transport)

        empty_context = {
            'schema_version': 'note-context-1',
            'duration_ms': 10000,
            'cohort': {'requested': 3, 'effective': 3, 'failed': 0, 'pending': 0, 'included_persona_ids': ['p001', 'p002', 'p003'], 'excluded_persona_ids': []},
            'supported_triggers': [],
        }

        normalized, data, sha = provider.notes(empty_context)
        self.assertFalse(transport_called, "Transport must not be called when no supported triggers")
        self.assertEqual(normalized['output']['notes'], [])
        self.assertEqual(normalized['cost_usd'], 0.0)
        self.assertEqual(normalized['status'], 'completed')
        self.assertEqual(provider.live_calls, 0)

    def test_build_note_context_filters_failed_and_unsupported_triggers(self):
        """build_note_context excludes failed personas and generates supported triggers only when >=15% stop."""
        manifest = {'requested': 3, 'profile': 'test', 'provider_mode': 'standard'}
        video = {
            'metadata': {'duration_ms': 6000},
            'features': {
                'scenes': [
                    {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
                    {'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000},
                ]
            }
        }
        checkpoints = [
            {'persona_id': 'p001', 'status': 'complete'},
            {'persona_id': 'p002', 'status': 'stopped'},
            {'persona_id': 'p003', 'status': 'failed'},  # failed persona
        ]
        rows = [
            # Scene 0: p001 continues, p002 continues (0/2 stopped -> no trigger)
            {
                'reaction': {'persona_id': 'p001', 'scene_id': 0, 'still_watching': True, 'evidence_id': 'ev_1_0'},
                'evidence': {'id': 'ev_1_0', 'persona_id': 'p001', 'scene_id': 0, 'quote': 'Good intro', 'start_ms': 0, 'end_ms': 3000}
            },
            {
                'reaction': {'persona_id': 'p002', 'scene_id': 0, 'still_watching': True, 'evidence_id': 'ev_2_0'},
                'evidence': {'id': 'ev_2_0', 'persona_id': 'p002', 'scene_id': 0, 'quote': 'Interesting', 'start_ms': 0, 'end_ms': 3000}
            },
            # Scene 1: p001 continues, p002 stops (1/2 stopped = 50% >= 15% -> trigger!)
            {
                'reaction': {'persona_id': 'p001', 'scene_id': 1, 'still_watching': True, 'evidence_id': 'ev_1_1'},
                'evidence': {'id': 'ev_1_1', 'persona_id': 'p001', 'scene_id': 1, 'quote': 'Still watching', 'start_ms': 3000, 'end_ms': 6000}
            },
            {
                'reaction': {'persona_id': 'p002', 'scene_id': 1, 'still_watching': False, 'evidence_id': 'ev_2_1'},
                'evidence': {'id': 'ev_2_1', 'persona_id': 'p002', 'scene_id': 1, 'quote': 'Confusing section', 'start_ms': 3000, 'end_ms': 6000}
            },
        ]

        ctx = build_note_context(manifest, video, checkpoints, rows)
        self.assertEqual(ctx['cohort']['effective'], 2)
        self.assertEqual(ctx['cohort']['failed'], 1)
        self.assertEqual(ctx['cohort']['included_persona_ids'], ['p001', 'p002'])
        self.assertEqual(ctx['cohort']['excluded_persona_ids'], ['p003'])

        # Only scene 1 qualifies for trigger
        self.assertEqual(len(ctx['supported_triggers']), 1)
        trig = ctx['supported_triggers'][0]
        self.assertEqual(trig['scene_id'], 1)
        self.assertEqual(trig['stop_fraction'], 0.5)
        # Evidence only cites p002's drop reason
        self.assertEqual(len(trig['evidence']), 1)
        self.assertEqual(trig['evidence'][0]['quote'], 'Confusing section')
        self.assertEqual(trig['evidence'][0]['persona_id'], 'p002')


class TestStandardAppRoutesAndManifest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, base_url='http://127.0.0.1:58000')
        self.headers = create_session(self.client)

    def test_standard_manifest_sealing_and_mode_isolation(self):
        """POST /runs in standard mode seals provider_mode='standard', model_id, cast_hash, and isolates repeats."""
        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        rec_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='recorded'
        )

        with patch('apps.api.app.main.settings', return_value=std_settings):
            up = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_std_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            self.assertEqual(up.status_code, 201)
            vid = up.json()['video_id']

            run_std = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_std_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            self.assertEqual(run_std.status_code, 202)
            std_run_id = run_std.json()['run_id']

            state = self.client.get(f'/runs/{std_run_id}', headers=self.headers).json()
            manifest = state['manifest']
            self.assertEqual(manifest['provider_mode'], 'standard')
            self.assertEqual(manifest['profile'], 'test')
            self.assertEqual(manifest['model_id'], 'muse-spark-1.3')
            self.assertEqual(manifest['prompt_version'], 'spark13-scene-av-v1')
            self.assertEqual(manifest['media_pipeline'], 'scene-av-v1')
            self.assertEqual(manifest['cast_hash'], get_cast_hash('test'))
            self.assertEqual(manifest['requested'], 3)

        # When mode is switched to recorded, repeat request creates a separate recorded run
        with patch('apps.api.app.main.settings', return_value=rec_settings):
            run_rec = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_rec_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            self.assertEqual(run_rec.status_code, 202)
            rec_run_id = run_rec.json()['run_id']
            self.assertNotEqual(std_run_id, rec_run_id)

    def test_standard_mode_accepts_upload_without_historical_fixtures(self):
        """In standard mode, any video upload is accepted for flash and not rejected for missing recorded fixture."""
        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_flash_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid = up.json()['video_id']
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))

            run_res = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_flash_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'flash'}
            )
            self.assertEqual(run_res.status_code, 202)
            run_id = run_res.json()['run_id']

            state = self.client.get(f'/runs/{run_id}', headers=self.headers).json()
            self.assertEqual(state['requested'], 50)
            self.assertEqual(state['manifest']['profile'], 'flash')
            self.assertEqual(state['manifest']['provider_mode'], 'standard')


class TestStandardWorkerAndLifecycle(unittest.TestCase):
    def setUp(self):
        # These frozen responses exercise recovery of the historical frame-only
        # manifests. New AV manifests have separate production-worker journeys.
        legacy_pipeline = patch('apps.api.app.main.STANDARD_MEDIA_PIPELINE', None)
        legacy_pipeline.start()
        self.addCleanup(legacy_pipeline.stop)
        clear_operational_pause()
        self.client = TestClient(app, base_url='http://127.0.0.1:58000')
        self.headers = create_session(self.client)
        # Clean pending jobs from any prior runs
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")

    def tearDown(self):
        clear_operational_pause()

    def test_standard_worker_end_to_end_test_profile(self):
        """Full execution of Standard run with transport double: sequential checkpoints, call markers, cost, report."""
        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_e2e_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid = up.json()['video_id']
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))

            run_res = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_e2e_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            run_id = run_res.json()['run_id']

        # Custom transport double responding to verdict & notes
        dispatched_count = 0

        def handler(request: httpx.Request):
            nonlocal dispatched_count
            dispatched_count += 1
            body = json.loads(request.read().decode())
            if 'verdicts' in body['text']['format']['schema']['properties']:
                prompt = body['input'][0]['content'][0]['text']
                # Determine persona_id from prompt
                pid = 'p001'
                for candidate in ('p001', 'p002', 'p003'):
                    if candidate in prompt:
                        pid = candidate
                        break
                # p001 continues, p002 continues, p003 stops in scene 0
                still_watching = (pid != 'p003')
                resp = make_verdict_response(pid, still_watching=still_watching, reason="Simulated feedback", impression="Clear")
                return httpx.Response(200, json=resp, headers={'x-request-id': f'req_{uid()[:8]}'})
            else:
                # Notes call
                resp = make_notes_response([])
                return httpx.Response(200, json=resp, headers={'x-request-id': f'req_{uid()[:8]}'})

        mock_transport = httpx.MockTransport(handler)

        def mock_provider_factory(vhash, dur, profile='test', lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=mock_transport)

        # Step worker to completion
        steps = 0
        while steps < 100:
            worked = process_once(provider_factory=mock_provider_factory)
            steps += 1
            if not worked:
                break

        # Check DB state
        with connection() as conn:
            checkpoints = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id", (run_id,)).fetchall()
            calls = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s ORDER BY unit", (run_id,)).fetchall()

        self.assertEqual(len(checkpoints), 3)
        self.assertEqual(checkpoints[2]['status'], 'stopped')  # p003 stopped

        # Check that provider_calls has accepted receipts with cost and standard mode
        for call in calls:
            self.assertEqual(call['status'], 'accepted')
            self.assertEqual(call['receipt']['mode'], 'standard')
            self.assertIn('cost_usd', call['receipt'])
            self.assertGreater(call['receipt']['cost_usd'], 0.0)

        # Check report
        state = self.client.get(f'/runs/{run_id}', headers=self.headers).json()
        self.assertIn(state['status'], ('complete_test_profile', 'complete'))

        rep = self.client.get(f'/runs/{run_id}/report', headers=self.headers).json()
        trust = rep['trust']
        self.assertEqual(trust['mode'], 'standard')
        self.assertGreater(trust['total_cost_usd'], 0.0)
        self.assertGreater(trust['live_calls'], 0)
        self.assertEqual(trust['pricing_version'], PRICING_VERSION)

    def test_unresolved_dispatched_marker_halts_without_reissue(self):
        """An unresolved dispatched marker after a crash halts with uncertain_provider_charge and zero blind reissue."""
        up = self.client.post(
            '/videos',
            headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_unres_{uid()[:8]}'},
            content=get_video_a_bytes()
        )
        vid = up.json()['video_id']

        with connection() as conn:
            run_id = uid()
            manifest = {
                'schema_version': 'run-manifest-1',
                'profile': 'test',
                'provider_mode': 'standard',
                'requested': 3,
                'persona_ids': ['p001', 'p002', 'p003'],
                'resample_seed': 20261028
            }
            conn.execute('INSERT INTO runs(id,video_id,manifest) VALUES(%s,%s,%s)', (run_id, vid, Jsonb(manifest)))
            conn.execute("INSERT INTO jobs(id,video_id,run_id,kind) VALUES(%s,%s,%s,'analysis')", (uid(), vid, run_id))

        calls_made = 0

        def handler(request: httpx.Request):
            nonlocal calls_made
            calls_made += 1
            return httpx.Response(200, json=make_verdict_response('p001'))

        transport = httpx.MockTransport(handler)

        def factory(vhash, dur, profile='test', lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=transport)

        # Prepare run and do first step
        process_once(provider_factory=factory)
        self.assertEqual(calls_made, 1)

        # Reset call counter
        calls_made = 0

        # Simulate in-flight crash on next step: update p001:1 call to 'dispatched' without accepted status
        with connection() as conn:
            conn.execute("UPDATE provider_calls SET status='dispatched', receipt=NULL WHERE run_id=%s AND unit='p001:0'", (run_id,))
            conn.execute("UPDATE checkpoints SET status='active', next_scene=0 WHERE run_id=%s AND persona_id='p001'", (run_id,))
            conn.execute("UPDATE jobs SET status='queued', lease_until=NULL WHERE run_id=%s", (run_id,))

        # Next worker tick encounters the unresolved dispatched call
        process_once(provider_factory=factory)

        # Must NOT have made a new call to the provider!
        self.assertEqual(calls_made, 0, "Must not reissue call for unresolved dispatched unit")

        # Must mark call failed with uncertain charge and run failed
        with connection() as conn:
            run = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (run_id,)).fetchone()
            call = conn.execute("SELECT status, receipt FROM provider_calls WHERE run_id=%s AND unit='p001:0'", (run_id,)).fetchone()

        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['error_code'], 'uncertain_provider_charge')
        self.assertEqual(call['status'], 'failed')
        self.assertEqual(call['receipt']['error']['charge_state'], 'uncertain')

    def test_call_ceiling_enforcement(self):
        """Worker stops admissions and fails closed when per-run call ceiling is reached."""
        up = self.client.post(
            '/videos',
            headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_ceil_{uid()[:8]}'},
            content=get_video_a_bytes()
        )
        vid = up.json()['video_id']

        with connection() as conn:
            run_id = uid()
            manifest = {
                'schema_version': 'run-manifest-1',
                'profile': 'test',
                'provider_mode': 'standard',
                'requested': 3,
                'persona_ids': ['p001', 'p002', 'p003'],
                'resample_seed': 20261028
            }
            conn.execute('INSERT INTO runs(id,video_id,manifest) VALUES(%s,%s,%s)', (run_id, vid, Jsonb(manifest)))
            conn.execute("INSERT INTO jobs(id,video_id,run_id,kind) VALUES(%s,%s,%s,'analysis')", (uid(), vid, run_id))

        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=make_verdict_response('p001')))

        def factory(vhash, dur, profile='test', lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=transport)

        # Prepare run
        process_once(provider_factory=factory)

        # Artificially insert 40 calls (the test ceiling limit: <= 40)
        with connection() as conn:
            for i in range(40):
                conn.execute(
                    "INSERT INTO provider_calls(run_id, unit, status, audit) VALUES(%s, %s, 'accepted', %s)",
                    (run_id, f"dummy_unit_{i}", Jsonb({}))
                )
            conn.execute("UPDATE jobs SET status='queued', lease_until=NULL WHERE run_id=%s", (run_id,))

        # Worker attempts next step
        process_once(provider_factory=factory)

        with connection() as conn:
            run = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (run_id,)).fetchone()

        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['error_code'], 'run_call_ceiling_exceeded')

    def test_standard_worker_50_persona_flash_full_journey(self):
        """50-instance sequential scene-aware simulation with real StandardProvider transport double.
        Exercises 50 terminal traces, post-stop invariant, supported note generation, honest usage/cost reporting, and deletion.
        """
        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_50_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid = up.json()['video_id']
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))

            run_res = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_50_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'flash'}
            )
            run_id = run_res.json()['run_id']

        # Controlled provider boundary scenario:
        # 50 personas: p001..p010 stop at scene 0 (10/50 = 20% >= 15% -> stop trigger)
        # p011..p050 continue through all 8 scenes (scenes 0..7)
        total_calls_dispatched = 0

        def handler(request: httpx.Request):
            nonlocal total_calls_dispatched
            total_calls_dispatched += 1
            body = json.loads(request.read().decode())
            if 'verdicts' in body['text']['format']['schema']['properties']:
                prompt = body['input'][0]['content'][0]['text']
                pid = None
                for i in range(1, 51):
                    cand = f'p{i:03d}'
                    if cand in prompt:
                        pid = cand
                        break
                pid = pid or 'p001'

                is_stop_persona = int(pid[1:]) <= 10
                if is_stop_persona:
                    resp = make_verdict_response(pid, still_watching=False, reason="Opening hook did not fit workflow", impression="Confusing hook", actions=[])
                else:
                    resp = make_verdict_response(pid, still_watching=True, reason="Clear progression", impression="Relevant tool", actions=["like", "save"])
                return httpx.Response(200, json=resp, headers={'x-request-id': f'req_{uid()[:8]}'})
            else:
                prompt_text = body['input'][0]['content'][0]['text']
                ctx_str = prompt_text[prompt_text.find('{'):] if '{' in prompt_text else '{}'
                ctx = json.loads(ctx_str)
                notes_list = []
                if ctx.get('supported_triggers'):
                    trig = ctx['supported_triggers'][0]
                    ev = trig['evidence'][0]
                    notes_list = [
                        {
                            "start_sec": trig['start_sec'],
                            "end_sec": trig['end_sec'],
                            "finding": "High drop-off in opening hook.",
                            "suggested_edit": "Show concrete workflow demonstration immediately.",
                            "evidence_ids": [ev['evidence_id']],
                            "quotes": [ev['quote']],
                        }
                    ]
                resp = make_notes_response(notes_list)
                return httpx.Response(200, json=resp, headers={'x-request-id': f'req_{uid()[:8]}'})

        mock_transport = httpx.MockTransport(handler)

        def mock_factory(vhash, dur, profile='test', lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=mock_transport)

        # Step worker through all units to completion
        steps = 0
        while steps < 400:
            worked = process_once(provider_factory=mock_factory)
            steps += 1
            if not worked:
                break

        # Check DB state
        with connection() as conn:
            checkpoints = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id", (run_id,)).fetchall()
            reactions = conn.execute("SELECT * FROM reactions WHERE run_id=%s ORDER BY persona_id, scene_id", (run_id,)).fetchall()
            calls = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s", (run_id,)).fetchall()

        self.assertEqual(len(checkpoints), 50)
        stopped_cps = [c for c in checkpoints if c['status'] == 'stopped']
        complete_cps = [c for c in checkpoints if c['status'] == 'complete']
        self.assertEqual(len(stopped_cps), 10)
        self.assertEqual(len(complete_cps), 40)

        reactions_by_pid = {}
        for rx in reactions:
            reactions_by_pid.setdefault(rx['persona_id'], []).append(rx)

        for i in range(1, 11):
            pid = f'p{i:03d}'
            self.assertEqual(len(reactions_by_pid[pid]), 1, f"Persona {pid} must only have 1 reaction at scene 0")
            self.assertEqual(reactions_by_pid[pid][0]['scene_id'], 0)

        for i in range(11, 51):
            pid = f'p{i:03d}'
            self.assertEqual(len(reactions_by_pid[pid]), 8, f"Persona {pid} must have 8 reactions across all scenes")

        self.assertEqual(len(reactions), 330)
        self.assertEqual(len(calls), 331)
        self.assertEqual(total_calls_dispatched, 331)
        self.assertTrue(all(c['status'] == 'accepted' for c in calls))

        # Check Report
        state = self.client.get(f'/runs/{run_id}', headers=self.headers).json()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['requested'], 50)
        self.assertEqual(state['effective'], 50)
        self.assertEqual(state['stopped'], 10)
        self.assertEqual(state['failed'], 0)

        rep = self.client.get(f'/runs/{run_id}/report', headers=self.headers).json()
        self.assertIn(rep['cast']['status'], ('complete_test_profile', 'complete'))
        self.assertEqual(rep['cast']['effective'], 50)

        trust = rep['trust']
        self.assertEqual(trust['mode'], 'standard')
        self.assertEqual(trust['live_calls'], 331)
        self.assertGreater(trust['total_cost_usd'], 0.0)
        self.assertEqual(trust['pricing_version'], PRICING_VERSION)

        self.assertEqual(len(rep['notes']), 1)
        note = rep['notes'][0]
        self.assertEqual(note['interpretation'], 'High drop-off in opening hook.')
        self.assertEqual(note['fix'], 'Show concrete workflow demonstration immediately.')
        self.assertEqual(note['quotes'][0]['text'], 'Opening hook did not fit workflow')

        self.assertEqual(len(rep['retention']), 8)
        self.assertEqual(rep['retention'][0]['entrants'], 50)
        self.assertEqual(rep['retention'][0]['stopped'], 10)
        self.assertEqual(rep['retention'][0]['continued'], 40)
        self.assertEqual(rep['retention'][1]['entrants'], 40)

        # Deletion safety test
        del_res = self.client.delete(
            f'/videos/{vid}',
            headers={**self.headers, 'Idempotency-Key': f'del_50_{uid()[:8]}'}
        )
        self.assertEqual(del_res.status_code, 202)
        rep_after_del = self.client.get(f'/runs/{run_id}/report', headers=self.headers)
        self.assertEqual(rep_after_del.status_code, 404)

    def test_notes_recovery_across_restart_no_generation(self):
        """Actual child process exits 72 after accepted notes receipt; fresh child reuses durable output without 2nd HTTP request."""
        clear_operational_pause()
        import subprocess, tempfile, sys, os

        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_rec_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid = up.json()['video_id']
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))

            run_res = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_rec_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            run_id = run_res.json()['run_id']

            with connection() as conn:
                m = conn.execute("SELECT manifest FROM runs WHERE id=%s", (run_id,)).fetchone()['manifest']
            self.assertEqual(m['provider_mode'], 'standard')

        counter_path = os.path.join(tempfile.gettempdir(), f"notes_counter_{uid()[:8]}.json")
        Path(counter_path).write_text(json.dumps({'notes': 0, 'verdicts': 0}), encoding='utf-8')

        py_exe = sys.executable
        cwd = os.getcwd()
        runtime_env = os.environ.get('MOBBS_RUNTIME') or os.environ.get('VIRALIST_RUNTIME') or 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json'

        child_script = f"""
import os, sys, json
sys.path.insert(0, r'{cwd}')
os.environ['MOBBS_RUNTIME'] = r'{runtime_env}'
os.environ['VIRALIST_RUNTIME'] = r'{runtime_env}'
os.environ['MODEL_API_KEY'] = 'DUMMY_KEY'

import httpx
from apps.api.app.db import connection
from apps.api.app.worker import process_once
from apps.api.app.providers import StandardProvider
from tests.test_v03_standard_app import make_verdict_response, make_notes_response

counter_file = r'{counter_path}'

def handler(request: httpx.Request):
    body = json.loads(request.read().decode())
    with open(counter_file, 'r+', encoding='utf-8') as f:
        data = json.load(f)
        if 'verdicts' in body['text']['format']['schema']['properties']:
            data['verdicts'] += 1
            f.seek(0); json.dump(data, f); f.truncate()
            prompt = body['input'][0]['content'][0]['text']
            pid = 'p001'
            for cand in ('p001', 'p002', 'p003'):
                if cand in prompt:
                    pid = cand; break
            still = (pid != 'p003')
            resp = make_verdict_response(pid, still_watching=still, reason='Simulated feedback')
            return httpx.Response(200, json=resp)
        else:
            data['notes'] += 1
            f.seek(0); json.dump(data, f); f.truncate()
            resp = make_notes_response([])
            return httpx.Response(200, json=resp)

transport = httpx.MockTransport(handler)
def factory(v, d, profile='test', lease=None):
    return StandardProvider(v, d, profile=profile, lease=lease, transport=transport)

def before_pub(lease):
    if lease['run_id'] == '{run_id}':
        with connection() as conn:
            notes_call = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s AND unit='notes'", (lease['run_id'],)).fetchone()
            if notes_call and notes_call['status'] == 'accepted':
                os._exit(72)

worked = True
while worked:
    worked = process_once(provider_factory=factory, before_publish=before_pub)
os._exit(0)
"""

        # Step Child 1: exits with code 72 right after notes receipt commits and raw object is saved
        p1 = subprocess.run([py_exe, "-c", child_script])
        self.assertEqual(p1.returncode, 72, "Child process must exit with code 72 at fault hook")

        counts1 = json.loads(Path(counter_path).read_text(encoding='utf-8'))
        self.assertEqual(counts1['notes'], 1, "Exactly 1 notes HTTP request must have been made")
        self.assertEqual(counts1['verdicts'], 17, "17 verdict HTTP requests made across 8 scenes")

        # In DB, verify notes call is already accepted and has durable normalized output in audit
        with connection() as conn:
            notes_call = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s AND unit='notes'", (run_id,)).fetchone()
            self.assertIsNotNone(notes_call)
            self.assertEqual(notes_call['status'], 'accepted')
            self.assertIn('normalized', notes_call['audit'])
            self.assertIn('output', notes_call['audit']['normalized'])
            self.assertIn('response_sha256', notes_call['receipt'])
            self.assertIn('response_sha256', notes_call['audit'])
            self.assertEqual(notes_call['receipt']['response_sha256'], notes_call['audit']['response_sha256'])

            # Reset lease on job so fresh child can reclaim it
            conn.execute("UPDATE jobs SET status='queued', lease_until=NULL WHERE run_id=%s", (run_id,))

        # Step Child 2: fresh process reclaims expired lease and finishes run WITHOUT generating notes again
        child_script2 = child_script.replace("os._exit(72)", "pass")
        p2 = subprocess.run([py_exe, "-c", child_script2])
        self.assertEqual(p2.returncode, 0, "Fresh child process must exit 0 on completion")

        counts2 = json.loads(Path(counter_path).read_text(encoding='utf-8'))
        self.assertEqual(counts2['notes'], 1, "Notes HTTP count MUST remain 1 on fresh process recovery!")
        self.assertEqual(counts2['verdicts'], 17)

        # Verify completed report
        rep = self.client.get(f'/runs/{run_id}/report', headers=self.headers).json()
        self.assertIn(rep['cast']['status'], ('complete_test_profile', 'complete'))
        self.assertEqual(len(rep['notes']), 0)

        # Verify receipt not appended twice and live_calls accurate
        trust = rep['trust']
        self.assertEqual(trust['live_calls'], 18)
        notes_receipts = [r for r in trust.get('usage_ledger', []) if r.get('unit') == 'notes' or r.get('mode') == 'standard']
        self.assertEqual(len(notes_receipts), 18)

        # Verify ceiling equality: call_count == 18 == max_calls allowed recovery to complete without run_call_ceiling_exceeded
        state = self.client.get(f'/runs/{run_id}', headers=self.headers).json()
        self.assertIn(state['status'], ('complete_test_profile', 'complete'))

        # Test Storage boundary integrity fault on accepted notes recovery without deleting another fixture
        with patch('apps.api.app.storage.Storage.get', side_effect=OSError('synthetic_storage_fault')):
            with connection() as conn:
                conn.execute("UPDATE jobs SET status='queued', lease_until=NULL WHERE run_id=%s", (run_id,))
            process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(AssertionError('no_http_generation_permitted')))))
            with connection() as conn:
                fault_run = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (run_id,)).fetchone()
            self.assertEqual(fault_run['status'], 'failed')
            self.assertEqual(fault_run['error_code'], 'missing_durable_notes_output')

        # Also verify that an accepted notes row with missing durable output fails visibly without resend
        with patch('apps.api.app.main.settings', return_value=std_settings):
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))
            run_res_bad = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_bad_{uid()[:8]}'}, json={'video_id': vid, 'profile': 'test'})
            run_id_bad = run_res_bad.json()['run_id']
            with connection() as conn:
                for pid in ('p001', 'p002', 'p003'):
                    conn.execute("INSERT INTO checkpoints(run_id,persona_id,next_scene,status) VALUES(%s,%s,8,'complete')", (run_id_bad, pid))
                conn.execute("INSERT INTO provider_calls(run_id, unit, status, receipt, audit) VALUES(%s, 'notes', 'accepted', %s, %s)",
                             (run_id_bad, Jsonb({'mode': 'standard', 'live_calls': 1}), Jsonb({})))
            process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))))
            with connection() as conn:
                bad_run = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (run_id_bad,)).fetchone()
            self.assertEqual(bad_run['status'], 'failed')
            self.assertEqual(bad_run['error_code'], 'missing_durable_notes_output')

    def test_missing_and_inconsistent_usage(self):
        """Missing usage yields total_cost_usd='unavailable'; inconsistent usage yields uncertain charge and stops new admissions."""
        clear_operational_pause()
        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_usg_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid = up.json()['video_id']

            # Part A: Missing usage (usage=None) -> total_cost_usd becomes 'unavailable', not 0.0
            run_res1 = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_usg1_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            run_id1 = run_res1.json()['run_id']
            with connection() as conn:
                m1 = conn.execute("SELECT manifest FROM runs WHERE id=%s", (run_id1,)).fetchone()['manifest']
            self.assertEqual(m1['provider_mode'], 'standard')

            def null_usage_handler(request: httpx.Request):
                body = json.loads(request.read().decode())
                if 'verdicts' in body['text']['format']['schema']['properties']:
                    prompt = body['input'][0]['content'][0]['text']
                    pid = 'p001'
                    for candidate in ('p001', 'p002', 'p003'):
                        if candidate in prompt:
                            pid = candidate
                            break
                    resp = make_verdict_response(pid, still_watching=True, reason="Simulated feedback")
                    resp['usage'] = None
                    return httpx.Response(200, json=resp, headers={'x-request-id': f'req_{uid()[:8]}'})
                else:
                    resp = make_notes_response([])
                    resp['usage'] = None
                    return httpx.Response(200, json=resp, headers={'x-request-id': f'req_{uid()[:8]}'})

            transport1 = httpx.MockTransport(null_usage_handler)
            for _ in range(50):
                if not process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=transport1)):
                    break

            rep1 = self.client.get(f'/runs/{run_id1}/report', headers=self.headers).json()
            self.assertIn('trust', rep1, f"Report must be available: {rep1}")
            self.assertEqual(rep1['trust']['total_cost_usd'], 'unavailable', "Missing usage must be unavailable, not 0.0")

            # Part B: Inconsistent usage -> fails with uncertain_provider_charge and sets operational pause
            clear_operational_pause()
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))
            run_res2 = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_usg2_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            run_id2 = run_res2.json()['run_id']
            with connection() as conn:
                m2 = conn.execute("SELECT manifest FROM runs WHERE id=%s", (run_id2,)).fetchone()['manifest']
            self.assertEqual(m2['provider_mode'], 'standard')

            def bad_usage_handler(request: httpx.Request):
                resp = make_verdict_response('p001')
                resp['usage']['total_tokens'] = 999999  # Mismatch: input + output != total
                resp['usage']['diagnostic'] = 'SYNTHETIC_USAGE_PROSE_CANARY_R2'
                return httpx.Response(200, json=resp, headers={'x-request-id': 'req_safe_test_r2'})

            transport2 = httpx.MockTransport(bad_usage_handler)
            process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=transport2))

            with connection() as conn:
                run2 = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (run_id2,)).fetchone()
                call2 = conn.execute("SELECT status, receipt FROM provider_calls WHERE run_id=%s AND unit='p001:0'", (run_id2,)).fetchone()

            self.assertEqual(run2['status'], 'failed')
            self.assertEqual(run2['error_code'], 'uncertain_provider_charge')
            self.assertEqual(call2['status'], 'failed')
            self.assertEqual(call2['receipt']['error']['charge_state'], 'uncertain')
            self.assertIn('usage', call2['receipt'])
            self.assertIn('response_id', call2['receipt'])
            self.assertEqual(call2['receipt']['usage']['total_tokens'], 999999)
            self.assertNotIn('SYNTHETIC_USAGE_PROSE_CANARY_R2', json.dumps(call2['receipt']))
            self.assertTrue(is_operationally_paused())

            # Part C: Operational pause stops subsequent Standard run admissions without making any HTTP calls
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))
            run_res3 = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'r_usg3_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            run_id3 = run_res3.json()['run_id']

            calls_made3 = 0
            def counting_handler(request: httpx.Request):
                nonlocal calls_made3
                calls_made3 += 1
                return httpx.Response(200, json=make_verdict_response('p001'))

            transport3 = httpx.MockTransport(counting_handler)
            process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=transport3))

            self.assertEqual(calls_made3, 0, "No provider HTTP calls must be made when paused due to unresolved charge")
            with connection() as conn:
                run3 = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (run_id3,)).fetchone()
            self.assertEqual(run3['status'], 'failed')
            self.assertEqual(run3['error_code'], 'uncertain_provider_charge')
            clear_operational_pause()

    def test_concurrency_gate_enforces_single_active_generation(self):
        """Two concurrent workers serialize execution so maximum active HTTP requests is 1, verified across distinct videos/jobs."""
        clear_operational_pause()
        import threading
        import time

        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up1 = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_c1_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid1 = up1.json()['video_id']

            # Use Video B for distinct upload and job
            ev_root = Path(settings().provider_evidence_root).resolve()
            s1_media = (ev_root.parent / 'stage1-bounded' / 'media.json')
            data_b = json.loads(s1_media.read_text())
            video_b_bytes = Path(data_b['b']['path']).read_bytes()

            up2 = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_c2_{uid()[:8]}'},
                content=video_b_bytes
            )
            vid2 = up2.json()['video_id']
            self.assertNotEqual(vid1, vid2, "Videos must be distinct resources")

            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id IN (%s, %s)", (vid1, vid2))

            # Queue two separate runs for distinct videos under active Standard settings patch
            r1 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rc1_{uid()[:8]}'}, json={'video_id': vid1, 'profile': 'test'}).json()['run_id']
            r2 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rc2_{uid()[:8]}'}, json={'video_id': vid2, 'profile': 'test'}).json()['run_id']
            self.assertNotEqual(r1, r2, "Runs must be distinct resources")

            with connection() as conn:
                m1 = conn.execute("SELECT manifest FROM runs WHERE id=%s", (r1,)).fetchone()['manifest']
                m2 = conn.execute("SELECT manifest FROM runs WHERE id=%s", (r2,)).fetchone()['manifest']
            self.assertEqual(m1['provider_mode'], 'standard')
            self.assertEqual(m2['provider_mode'], 'standard')

        active_count = 0
        max_active = 0
        lock = threading.Lock()
        t1_in_request = threading.Event()
        t2_attempted = threading.Event()

        def concurrent_handler(request: httpx.Request):
            nonlocal active_count, max_active
            with lock:
                active_count += 1
                if active_count > max_active:
                    max_active = active_count
            t1_in_request.set()
            # Wait for thread 2 to attempt entry while thread 1 holds lock
            t2_attempted.wait(timeout=1.0)
            time.sleep(0.02)
            with lock:
                active_count -= 1
            return httpx.Response(200, json=make_verdict_response('p001'))

        transport = httpx.MockTransport(concurrent_handler)
        def factory(v, d, profile='test', lease=None):
            return StandardProvider(v, d, profile=profile, lease=lease, transport=transport)

        def worker_thread1():
            process_once(provider_factory=factory)

        def worker_thread2():
            # Wait until thread 1 is actively inside generation
            t1_in_request.wait(timeout=2.0)
            t2_attempted.set()
            # Attempt concurrent execution; must be serialized by standard_concurrency_gate
            process_once(provider_factory=factory)

        t1 = threading.Thread(target=worker_thread1)
        t2 = threading.Thread(target=worker_thread2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(max_active, 1, "Standard concurrency gate must limit maximum concurrent HTTP requests to 1")

    def test_canary_redaction_transport_error(self):
        """Controlled ReadTimeout containing sensitive synthetic canary is redacted from provider_calls error receipt."""
        clear_operational_pause()
        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_can_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid = up.json()['video_id']
            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))

            run_res = self.client.post(
                '/runs',
                headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rcan_{uid()[:8]}'},
                json={'video_id': vid, 'profile': 'test'}
            )
            run_id = run_res.json()['run_id']
            with connection() as conn:
                m = conn.execute("SELECT manifest FROM runs WHERE id=%s", (run_id,)).fetchone()['manifest']
            self.assertEqual(m['provider_mode'], 'standard')

        secret_canary = "SYNTHETIC_SECRET_CANARY_X998877"

        def timeout_handler(request: httpx.Request):
            raise httpx.ReadTimeout(f"Read timed out with secret canary {secret_canary}")

        transport = httpx.MockTransport(timeout_handler)
        process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=transport))

        with connection() as conn:
            call = conn.execute("SELECT status, receipt, audit FROM provider_calls WHERE run_id=%s AND unit='p001:0'", (run_id,)).fetchone()

        self.assertEqual(call['status'], 'failed')
        receipt_str = json.dumps(call['receipt'])
        self.assertNotIn(secret_canary, receipt_str, "Sensitive canary string must not be persisted in receipt")
        self.assertEqual(call['receipt']['error']['code'], 'provider_transport_error')
        self.assertEqual(call['receipt']['error']['charge_state'], 'uncertain')
        clear_operational_pause()

    def test_ui_disclosures_truthful(self):
        """UI and session truthful disclosures for Standard mode and Flash 50 candidate persona policies."""
        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            res = self.client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
            self.assertIn(res.status_code, (200, 201))
            session_data = res.json()
            self.assertEqual(session_data.get('provider_mode'), 'standard')

            p50 = StandardProvider('dummy_sha', 4000, profile='flash')
            prov = p50.provenance()
            self.assertEqual(prov['mode'], 'standard')
            self.assertEqual(prov['model_ids'], ['muse-spark-1.3'])
            self.assertTrue(any('Fifty fictional candidate policies' in lim for lim in prov['limitations']))
            self.assertTrue(any('not calibrated against human viewers' in lim for lim in prov['limitations']))

            from apps.api.app.providers import RecordedProvider
            p_rec = RecordedProvider('c76b510a43b6aaaf90dc152e8be358f0e6efb64a95ebc785c8cd51af7713975a', 33782, profile='flash')
            prov_rec = p_rec.provenance()
            self.assertEqual(prov_rec['mode'], 'recorded')
            self.assertTrue(any('five archetypes' in lim for lim in prov_rec['limitations']))

    def test_post_wait_deletion_yields_zero_second_http(self):
        """Parent-held first HTTP + real PG waiter + second distinct child -> delete second via owner API -> release first yields ZERO second HTTP."""
        clear_operational_pause()
        import tempfile
        import subprocess
        import time
        import sys

        std_settings = Settings(
            database_url=settings().database_url,
            s3_endpoint=settings().s3_endpoint,
            s3_access_key=settings().s3_access_key,
            s3_secret_key=settings().s3_secret_key,
            s3_bucket=settings().s3_bucket,
            provider_evidence_root=settings().provider_evidence_root,
            origin='http://127.0.0.1:58000',
            provider_mode='standard'
        )
        with patch('apps.api.app.main.settings', return_value=std_settings):
            up1 = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_wd1_{uid()[:8]}'},
                content=get_video_a_bytes()
            )
            vid1 = up1.json()['video_id']

            ev_root = Path(settings().provider_evidence_root).resolve()
            s1_media = (ev_root.parent / 'stage1-bounded' / 'media.json')
            data_b = json.loads(s1_media.read_text())
            video_b_bytes = Path(data_b['b']['path']).read_bytes()

            up2 = self.client.post(
                '/videos',
                headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_wd2_{uid()[:8]}'},
                content=video_b_bytes
            )
            vid2 = up2.json()['video_id']
            self.assertNotEqual(vid1, vid2)

            with connection() as conn:
                conn.execute("DELETE FROM runs WHERE video_id IN (%s, %s)", (vid1, vid2))

            r1 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rc_wd1_{uid()[:8]}'}, json={'video_id': vid1, 'profile': 'test'}).json()['run_id']
            r2 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rc_wd2_{uid()[:8]}'}, json={'video_id': vid2, 'profile': 'test'}).json()['run_id']
            self.assertNotEqual(r1, r2)

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            helper = str(Path(__file__).resolve().parent / 'v03_standard_r2_worker.py')
            env = os.environ.copy()
            runtime_env = os.environ.get('MOBBS_RUNTIME') or os.environ.get('VIRALIST_RUNTIME') or 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json'
            env['MOBBS_RUNTIME'] = str(Path(runtime_env).resolve())
            env['VIRALIST_RUNTIME'] = str(Path(runtime_env).resolve())
            env['MOBBS_PROVIDER_MODE'] = 'standard'
            env['VIRALIST_PROVIDER_MODE'] = 'standard'
            env['MODEL_API_KEY'] = 'DUMMY_KEY_LOCAL'
            env['PYTHONDONTWRITEBYTECODE'] = '1'

            one = subprocess.Popen([sys.executable, helper, 'once', r1, 'hold', str(d)], env=env)
            two = None
            try:
                deadline = time.monotonic() + 20
                while not (d / f"{r1}.entered").exists():
                    self.assertIsNone(one.poll(), 'Child 1 exited unexpectedly before entering HTTP')
                    self.assertLess(time.monotonic(), deadline, 'Child 1 timed out before entering HTTP')
                    time.sleep(0.05)

                two = subprocess.Popen([sys.executable, helper, 'once', r2, 'normal', str(d)], env=env)

                waiting = False
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    with connection() as db:
                        waiting = bool(db.execute(
                            "SELECT 1 FROM pg_locks WHERE locktype='advisory' AND objid=58004001 AND NOT granted"
                        ).fetchone())
                    if waiting:
                        break
                    self.assertIsNone(two.poll(), 'Child 2 exited before reaching gate')
                    time.sleep(0.05)
                self.assertTrue(waiting, 'Child 2 must be observed waiting on pg_advisory_lock 58004001')
                self.assertFalse((d / f"{r2}.entered").exists(), 'Child 2 must not enter HTTP while child 1 holds gate')

                del_res = self.client.delete(f'/videos/{vid2}', headers={**self.headers, 'Idempotency-Key': f'del_{uid()[:8]}'})
                self.assertEqual(del_res.status_code, 202)

                (d / 'release').write_text('1')
                one.wait(timeout=20)
                two.wait(timeout=20)
                self.assertEqual(one.returncode, 0, f'Child 1 exited with code {one.returncode}')
                self.assertEqual(two.returncode, 0, f'Child 2 exited with code {two.returncode}')

                self.assertFalse((d / f"{r2}.entered").exists(), 'Child 2 must not enter HTTP after deletion')
                self.assertFalse((d / f"{r2}.http").exists(), 'Child 2 must have zero HTTP dispatches')
            finally:
                (d / 'release').write_text('1')
                for ch in (one, two):
                    if ch is not None and ch.poll() is None:
                        try:
                            ch.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            ch.terminate()
                            ch.wait(timeout=5)
        with patch('apps.api.app.main.settings', return_value=std_settings):
            self.client.delete(f'/videos/{vid1}', headers={**self.headers, 'Idempotency-Key': f'del1_{uid()[:8]}'})
