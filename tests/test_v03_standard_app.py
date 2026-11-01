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
            self.assertEqual(body['max_output_tokens'], 1200)

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
            self.assertEqual(manifest['prompt_version'], 'spark13-standard-v1')
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
        self.client = TestClient(app, base_url='http://127.0.0.1:58000')
        self.headers = create_session(self.client)
        # Clean pending jobs from any prior runs
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status='queued'")

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
        self.assertEqual(rep['cast']['status'], 'complete')
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
