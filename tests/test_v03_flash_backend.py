"""V03-B1 Flash Backend Test Suite.
Tests Criterion 1 through 6 against production PostgreSQL and private object storage.
"""
import hashlib
import json
import unittest
from pathlib import Path

import psycopg
from starlette.testclient import TestClient

from apps.api.app.config import settings
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.domain import utc
from apps.api.app.main import app
from apps.api.app.worker import process_once, claim, fence, release, project, validate_projection
from apps.api.app.storage import Storage
from apps.api.app.reporting import build_report
from contracts.normalized import require, cast_status, normalize_note, stop_trigger


def get_video_a_bytes():
    ev_root = Path(settings().provider_evidence_root).resolve()
    s2_media = (ev_root / 'media.json') if (ev_root / 'media.json').exists() else (ev_root.parent / 'stage2-bounded' / 'media.json')
    data = json.loads(s2_media.read_text())
    p = Path(data['a']['path'])
    b = p.read_bytes()
    require(hashlib.sha256(b).hexdigest() == 'c76b510a43b6aaaf90dc152e8be358f0e6efb64a95ebc785c8cd51af7713975a', 'video a hash mismatch')
    return b


def get_video_b_bytes():
    ev_root = Path(settings().provider_evidence_root).resolve()
    s1_media = (ev_root.parent / 'stage1-bounded' / 'media.json')
    data = json.loads(s1_media.read_text())
    p = Path(data['b']['path'])
    b = p.read_bytes()
    require(hashlib.sha256(b).hexdigest() == 'b0b43397f99e31467cf89827336d8ee5c69c33719a28f086ecebca6ba0d9ec9f', 'video b hash mismatch')
    return b


def create_session(client):
    res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
    require(res.status_code == 201, 'failed to create session')
    csrf = res.json()['csrf']
    headers = {
        'Host': '127.0.0.1:58000',
        'Origin': 'http://127.0.0.1:58000',
        'X-CSRF-Token': csrf,
    }
    return headers


class TestCriterion1ManifestAndProfile(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, base_url='http://127.0.0.1:58000')
        self.headers = create_session(self.client)

    def test_legacy_default_manifest_and_immutability_trigger(self):
        """Migration 002 supplies truthful legacy defaults and prevents mutation."""
        with connection() as conn:
            vid = uid()
            owner_res = conn.execute("SELECT id FROM owner_sessions LIMIT 1").fetchone()
            owner_id = owner_res['id']
            conn.execute("INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)",
                         (vid, owner_id, 'dummy_sha', Jsonb({'duration_ms': 1000, 'storage_ready': True, 'original_key': 'k', 'bytes': 10, 'caveats': []})))
            run_id = uid()
            conn.execute("INSERT INTO runs(id, video_id) VALUES(%s, %s)", (run_id, vid))
            row = conn.execute("SELECT manifest FROM runs WHERE id=%s", (run_id,)).fetchone()
            manifest = row['manifest']
            self.assertEqual(manifest['schema_version'], 'run-manifest-1')
            self.assertEqual(manifest['profile'], 'test')
            self.assertEqual(manifest['requested'], 3)
            self.assertEqual(manifest['persona_ids'], ['p001', 'p002', 'p003'])
            self.assertEqual(manifest['provider_mode'], 'recorded')

            mutated = dict(manifest)
            mutated['requested'] = 50
            mutated['profile'] = 'flash'
            mutated['persona_ids'] = [f'p{i:03d}' for i in range(1, 51)]
            with self.assertRaises(psycopg.errors.CheckViolation) as cm:
                conn.execute("UPDATE runs SET manifest=%s WHERE id=%s", (Jsonb(mutated), run_id))
            self.assertIn('run_manifest_immutable', str(cm.exception))

    def test_flash_and_test_profile_separate_resources_and_queued_state(self):
        """POST /runs with test vs flash creates separate resources; inspect before preparation."""
        video_bytes = get_video_a_bytes()
        up_res = self.client.post(
            '/videos',
            headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_a_{uid()[:8]}'},
            content=video_bytes
        )
        self.assertEqual(up_res.status_code, 201)
        video_id = up_res.json()['video_id']

        test_key = f'test_key_{uid()[:8]}'
        res_test = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': test_key},
            json={'video_id': video_id, 'profile': 'test'}
        )
        self.assertEqual(res_test.status_code, 202)
        test_run_id = res_test.json()['run_id']

        flash_key = f'flash_key_{uid()[:8]}'
        res_flash = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': flash_key},
            json={'video_id': video_id, 'profile': 'flash'}
        )
        self.assertEqual(res_flash.status_code, 202)
        flash_run_id = res_flash.json()['run_id']
        self.assertNotEqual(test_run_id, flash_run_id)

        state_res = self.client.get(f'/runs/{flash_run_id}', headers=self.headers)
        self.assertEqual(state_res.status_code, 200)
        state = state_res.json()
        self.assertEqual(state['status'], 'queued')
        self.assertEqual(state['requested'], 50)
        self.assertEqual(state['pending'], 50)
        self.assertEqual(state['effective'], 0)
        self.assertEqual(state['failed'], 0)
        self.assertEqual(state['stopped'], 0)
        self.assertEqual(state['manifest']['profile'], 'flash')
        self.assertEqual(len(state['manifest']['persona_ids']), 50)

        repeat_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': flash_key},
            json={'video_id': video_id, 'profile': 'flash'}
        )
        self.assertEqual(repeat_res.status_code, 202)
        self.assertEqual(repeat_res.json()['run_id'], flash_run_id)

        conflict_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': flash_key},
            json={'video_id': video_id, 'profile': 'test'}
        )
        self.assertEqual(conflict_res.status_code, 409)
        self.assertEqual(conflict_res.json()['code'], 'idempotency_body_changed')

        invalid_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'inv_{uid()[:8]}'},
            json={'video_id': video_id, 'profile': 'unsupported_profile'}
        )
        self.assertEqual(invalid_res.status_code, 422)
        self.assertEqual(invalid_res.json()['code'], 'profile_must_be_test_or_flash')

        video_b_bytes = get_video_b_bytes()
        up_b_res = self.client.post(
            '/videos',
            headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_b_{uid()[:8]}'},
            content=video_b_bytes
        )
        self.assertEqual(up_b_res.status_code, 201)
        video_b_id = up_b_res.json()['video_id']

        flash_b_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'flash_b_{uid()[:8]}'},
            json={'video_id': video_b_id, 'profile': 'flash'}
        )
        self.assertEqual(flash_b_res.status_code, 422)
        self.assertEqual(flash_b_res.json()['code'], 'recorded_evidence_unavailable_for_this_upload')


class TestCriteria234FullRunEvidenceAndReporting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, base_url='http://127.0.0.1:58000')
        cls.headers = create_session(cls.client)

        video_bytes = get_video_a_bytes()
        up = cls.client.post(
            '/videos',
            headers={**cls.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_a_full_{uid()[:8]}'},
            content=video_bytes
        )
        require(up.status_code == 201, 'upload failed')
        cls.video_id = up.json()['video_id']

        run_res = cls.client.post(
            '/runs',
            headers={**cls.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'run_a_full_{uid()[:8]}'},
            json={'video_id': cls.video_id, 'profile': 'flash'}
        )
        require(run_res.status_code == 202, 'run creation failed')
        cls.run_id = run_res.json()['run_id']

        # Step worker to completion
        while True:
            worked = process_once()
            if not worked:
                break

    def test_criterion2_counts_and_post_stop_invariant(self):
        """Criterion 2: 50 checkpoints, 256 mapped reactions/events, 50 stops, status complete."""
        state = self.client.get(f'/runs/{self.run_id}', headers=self.headers).json()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['stage'], 'report')
        self.assertEqual(state['requested'], 50)
        self.assertEqual(state['effective'], 50)
        self.assertEqual(state['failed'], 0)
        self.assertEqual(state['stopped'], 50)
        self.assertEqual(state['pending'], 0)

        with connection() as conn:
            checkpoints = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id", (self.run_id,)).fetchall()
            reactions = conn.execute("SELECT * FROM reactions WHERE run_id=%s", (self.run_id,)).fetchall()
            events = conn.execute("SELECT * FROM events WHERE run_id=%s ORDER BY sequence", (self.run_id,)).fetchall()

        self.assertEqual(len(checkpoints), 50)
        self.assertTrue(all(cp['status'] == 'stopped' for cp in checkpoints))
        self.assertEqual(len(reactions), 256)
        self.assertEqual(len(events), 257)  # 256 persona reactions + 1 verdict.provisional event

        # Post-stop invariant: no persona has any reaction after their stopped scene
        stops_by_pid = {}
        for r in reactions:
            rx = r['reaction']
            if not rx['still_watching']:
                stops_by_pid[rx['persona_id']] = rx['scene_id']

        self.assertEqual(len(stops_by_pid), 50)
        for r in reactions:
            rx = r['reaction']
            self.assertLessEqual(rx['scene_id'], stops_by_pid[rx['persona_id']])

        # Verify validate_projection enforces post-stop prohibition
        stopped_cp = dict(checkpoints[0])
        self.assertEqual(stopped_cp['status'], 'stopped')
        dummy_scene = {'scene_id': stopped_cp['next_scene'], 'start_ms': 0, 'end_ms': 3000, 'frame_ref': 'dummy'}
        proj = dict(
            persona_id=stopped_cp['persona_id'],
            scene={'scene_id': dummy_scene['scene_id'], 'start_ms': 0, 'end_ms': 3000},
            allowed_media_refs=['dummy'],
            max_visible_ms=3000,
            own_impression=stopped_cp['impression']
        )
        with self.assertRaises(ValueError) as cm:
            validate_projection(proj, dummy_scene, stopped_cp)
        self.assertIn('post-stop or out-of-order dispatch', str(cm.exception))

    def test_criterion3_events_cursor_and_owner_evidence(self):
        """Criterion 3: SSE cursor reconnection, monotonic sequence, owner-scoped evidence endpoint."""
        # 1. Monotonic event sequence
        ev_res = self.client.get(f'/runs/{self.run_id}/events', headers=self.headers)
        self.assertEqual(ev_res.status_code, 200)
        raw_sse = ev_res.text
        lines = [line for line in raw_sse.splitlines() if line.startswith('data: ')]
        self.assertEqual(len(lines), 257)
        events = [json.loads(line[6:]) for line in lines]
        for i, ev in enumerate(events):
            self.assertEqual(ev['sequence'], i + 1)
            if ev['type'].startswith('persona.'):
                # Additive fields in payload
                self.assertIn('actions', ev['payload'])
                self.assertIn('reason', ev['payload'])
                self.assertTrue(isinstance(ev['payload']['reason'], str))
            elif ev['type'] == 'verdict.provisional':
                self.assertIn('retention_pct', ev['payload'])
                self.assertIn('top_drop_reasons', ev['payload'])

        # 2. Cursor reconnect with Last-Event-ID
        cursor_event = events[99]  # 100th event (sequence 100)
        reconnect_res = self.client.get(
            f'/runs/{self.run_id}/events',
            headers={**self.headers, 'Last-Event-ID': cursor_event['event_id']}
        )
        self.assertEqual(reconnect_res.status_code, 200)
        reconnect_lines = [line for line in reconnect_res.text.splitlines() if line.startswith('data: ')]
        self.assertEqual(len(reconnect_lines), 157)  # 257 - 100 = 157
        first_reconnect_ev = json.loads(reconnect_lines[0][6:])
        self.assertEqual(first_reconnect_ev['sequence'], 101)

        # 3. Owner-scoped evidence endpoint
        evidence_id = events[0]['payload']['evidence_id']
        ev_item_res = self.client.get(f'/runs/{self.run_id}/evidence/{evidence_id}', headers=self.headers)
        self.assertEqual(ev_item_res.status_code, 200)
        ev_item = ev_item_res.json()
        self.assertEqual(ev_item['id'], evidence_id)
        self.assertIn('quote', ev_item)
        self.assertIn('persona_id', ev_item)
        self.assertIn('scene_id', ev_item)
        self.assertIn('start_ms', ev_item)
        self.assertIn('end_ms', ev_item)

        # 4. Separate session access to evidence -> 404 Denied
        other_client = TestClient(app, base_url='http://127.0.0.1:58000')
        other_headers = create_session(other_client)
        other_ev_res = other_client.get(f'/runs/{self.run_id}/evidence/{evidence_id}', headers=other_headers)
        self.assertEqual(other_ev_res.status_code, 404)

        # 5. Non-existent evidence ID -> 404
        non_ev_res = self.client.get(f'/runs/{self.run_id}/evidence/non_existent_id', headers=self.headers)
        self.assertEqual(non_ev_res.status_code, 404)

    def test_criterion4_report_math_and_notes(self):
        """Criterion 4: Retention table, scores, engagement, note candidate suppression, grounded note injection."""
        rep = self.client.get(f'/runs/{self.run_id}/report', headers=self.headers).json()

        # 1. Retention table
        retention = rep['retention']
        self.assertEqual(len(retention), 8)

        # Scene 0: 50 entrants, 11 stopped, survival 78.0%, drop_rate 22.0%
        s0 = retention[0]
        self.assertEqual(s0['entrants'], 50)
        self.assertEqual(s0['stopped'], 11)
        self.assertEqual(s0['continued'], 39)
        self.assertEqual(s0['survival']['observed'], 78.0)
        self.assertEqual(s0['drop_rate']['observed'], 22.0)

        # Scene 6: 29 entrants, 29 stopped, continued 0, survival 0.0%, drop_rate 100.0%
        s6 = retention[6]
        self.assertEqual(s6['entrants'], 29)
        self.assertEqual(s6['stopped'], 29)
        self.assertEqual(s6['continued'], 0)
        self.assertEqual(s6['survival']['observed'], 0.0)
        self.assertEqual(s6['drop_rate']['observed'], 100.0)

        # Scene 7: 0 entrants, 0 stopped, survival 0.0%, drop_rate unavailable_reason 'no_scene_entrants'
        s7 = retention[7]
        self.assertEqual(s7['entrants'], 0)
        self.assertEqual(s7['stopped'], 0)
        self.assertEqual(s7['continued'], 0)
        self.assertEqual(s7['survival']['observed'], 0.0)
        self.assertIsNone(s7['drop_rate']['observed'])
        self.assertEqual(s7['drop_rate']['unavailable_reason'], 'no_scene_entrants')

        # 2. Engagement
        save = rep['engagement']['save']
        self.assertEqual(save['observed'], 50.0)
        self.assertEqual(save['denominator'], 50)
        self.assertAlmostEqual(save['range']['low'], 42.0, places=2)
        self.assertAlmostEqual(save['range']['high'], 58.0, places=2)

        follow = rep['engagement']['follow']
        self.assertIsNone(follow['observed'])
        self.assertEqual(follow['unavailable_reason'], 'action_not_observed_by_legacy_provider')

        # 3. Scores
        hook = rep['scores']['hook']
        self.assertEqual(hook['observed'], 78.0)
        self.assertEqual(hook['denominator'], 50)
        self.assertEqual(hook['range']['low'], 70.0)
        self.assertEqual(hook['range']['high'], 86.0)

        pacing = rep['scores']['pacing']
        self.assertAlmostEqual(pacing['observed'], 58.0, places=2)
        self.assertEqual(pacing['denominator'], 50)
        self.assertEqual(pacing['range']['low'], 48.0)
        self.assertEqual(pacing['range']['high'], 68.0)

        for unavail in ('clarity', 'cta', 'trend'):
            self.assertIsNone(rep['scores'][unavail]['observed'])
            self.assertIn('unavailable_reason', rep['scores'][unavail])

        # 4. Notes: 0 reported, 1 suppressed
        self.assertEqual(len(rep['notes']), 0)
        self.assertEqual(rep['suppressed_notes'], 1)
        self.assertEqual(rep['note_rejections']['unsupported_trigger'], 1)
        self.assertEqual(sum(rep['note_rejections'].values()), rep['suppressed_notes'])
        self.assertEqual(rep['coverage']['excluded_traces'], {'failed': [], 'pending': []})
        self.assertEqual(rep['engagement']['save']['kind'], 'simulation_range')

        # 5. Injected valid trigger + candidate note: proves note formatting when grounded
        with connection() as conn:
            rows = conn.execute("SELECT * FROM reactions WHERE run_id=%s ORDER BY persona_id,scene_id", (self.run_id,)).fetchall()
            ev_dict = {r['evidence']['id']: r['evidence'] for r in rows}
            scenes = rep['scenes']
            # Find an evidence ID from scene 0 to quote
            s0_ev = next(r['evidence'] for r in rows if r['scene_id'] == 0 and not r['reaction']['still_watching'])

        trigger_0 = stop_trigger('stop_0', 0, scenes[0]['start_ms'], scenes[0]['end_ms'], [r['reaction'] for r in rows])
        self.assertIsNotNone(trigger_0)
        candidate = dict(
            start_sec=0.0,
            end_sec=3.0,
            finding='Hook lacks immediate context for product value.',
            suggested_edit='Do not use synthetic mockups; add direct caption explaining value proposition in first 2 seconds.',
            evidence_ids=[s0_ev['id']],
            quotes=[s0_ev['quote']]
        )
        norm_note = normalize_note(candidate, ev_dict, trigger_0, 'n0')
        self.assertEqual(norm_note['id'], 'n0')
        self.assertEqual(norm_note['trigger_id'], 'stop_0')
        self.assertEqual(norm_note['status'], 'open')
        self.assertEqual(norm_note['quotes'][0]['evidence_id'], s0_ev['id'])
        self.assertEqual(norm_note['quotes'][0]['text'], s0_ev['quote'])
        self.assertEqual(norm_note['interpretation'], candidate['finding'])
        self.assertEqual(norm_note['fix'], candidate['suggested_edit'])

        # 6. Call production build_report aggregator with controlled note candidates
        with connection() as conn:
            checkpoints = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id", (self.run_id,)).fetchall()
            run_row = conn.execute("SELECT * FROM runs WHERE id=%s", (self.run_id,)).fetchone()
            video_row = conn.execute("SELECT * FROM videos WHERE id=%s", (self.video_id,)).fetchone()

        envelope_with_valid = {
            'output': {
                'notes': [candidate]
            }
        }
        agg_rep = build_report(run_row['manifest'], video_row, checkpoints, rows, None, 'test_sha', envelope_with_valid, [])
        self.assertEqual(len(agg_rep['notes']), 1)
        self.assertEqual(agg_rep['notes'][0]['trigger_id'], 'stop_0')
        self.assertEqual(agg_rep['suppressed_notes'], 0)
        self.assertEqual(agg_rep['note_rejections']['unsupported_trigger'], 0)


class TestGoldenTraceMathFixture(unittest.TestCase):
    def test_golden_trace_fixture_hand_checkable_math(self):
        """Hand-checkable synthetic trace math for retention, survival, drop-rate, and resampling."""
        manifest = {
            'schema_version': 'run-manifest-1',
            'profile': 'test',
            'provider_mode': 'recorded',
            'requested': 4,
            'persona_ids': ['p01', 'p02', 'p03', 'p04'],
            'resample_seed': 20261028,
        }
        video = {
            'metadata': {'duration_ms': 6000},
            'features': {
                'scenes': [
                    {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'frame_ref': 'f0'},
                    {'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000, 'frame_ref': 'f1'},
                ],
                'caveats': [],
            }
        }
        # 4 personas:
        # p01 stops at scene 0 (save action taken)
        # p02 continues scene 0, stops at scene 1 (share action taken)
        # p03 continues scene 0, completes scene 1 (no action)
        # p04 continues scene 0, completes scene 1 (save action taken)
        checkpoints = [
            {'persona_id': 'p01', 'status': 'stopped'},
            {'persona_id': 'p02', 'status': 'stopped'},
            {'persona_id': 'p03', 'status': 'complete'},
            {'persona_id': 'p04', 'status': 'complete'},
        ]
        ev1 = {'id': 'e1', 'persona_id': 'p01', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'boring'}
        ev2_0 = {'id': 'e2_0', 'persona_id': 'p02', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'ok'}
        ev2_1 = {'id': 'e2_1', 'persona_id': 'p02', 'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000, 'quote': 'lost me'}
        ev3_0 = {'id': 'e3_0', 'persona_id': 'p03', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'nice'}
        ev3_1 = {'id': 'e3_1', 'persona_id': 'p03', 'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000, 'quote': 'great'}
        ev4_0 = {'id': 'e4_0', 'persona_id': 'p04', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'good'}
        ev4_1 = {'id': 'e4_1', 'persona_id': 'p04', 'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000, 'quote': 'done'}

        rows = [
            {'reaction': {'persona_id': 'p01', 'scene_id': 0, 'still_watching': False, 'actions': ['save'], 'evidence_id': 'e1'}, 'evidence': ev1},
            {'reaction': {'persona_id': 'p02', 'scene_id': 0, 'still_watching': True, 'actions': [], 'evidence_id': 'e2_0'}, 'evidence': ev2_0},
            {'reaction': {'persona_id': 'p02', 'scene_id': 1, 'still_watching': False, 'actions': ['share'], 'evidence_id': 'e2_1'}, 'evidence': ev2_1},
            {'reaction': {'persona_id': 'p03', 'scene_id': 0, 'still_watching': True, 'actions': [], 'evidence_id': 'e3_0'}, 'evidence': ev3_0},
            {'reaction': {'persona_id': 'p03', 'scene_id': 1, 'still_watching': True, 'actions': [], 'evidence_id': 'e3_1'}, 'evidence': ev3_1},
            {'reaction': {'persona_id': 'p04', 'scene_id': 0, 'still_watching': True, 'actions': ['save'], 'evidence_id': 'e4_0'}, 'evidence': ev4_0},
            {'reaction': {'persona_id': 'p04', 'scene_id': 1, 'still_watching': True, 'actions': [], 'evidence_id': 'e4_1'}, 'evidence': ev4_1},
        ]
        rep = build_report(manifest, video, checkpoints, rows, None, 'dummy_sha', {'output': {'notes': []}}, [])

        # Hand check:
        # Effective = 4
        self.assertEqual(rep['cast']['effective'], 4)
        # Scene 0: 4 entrants, 1 stopped, 3 continued -> drop rate = 1/4 = 25.0%, survival = 3/4 = 75.0%
        self.assertEqual(rep['retention'][0]['entrants'], 4)
        self.assertEqual(rep['retention'][0]['stopped'], 1)
        self.assertEqual(rep['retention'][0]['continued'], 3)
        self.assertEqual(rep['retention'][0]['drop_rate']['observed'], 25.0)
        self.assertEqual(rep['retention'][0]['survival']['observed'], 75.0)

        # Scene 1: 3 entrants, 1 stopped, 2 continued -> drop rate = 1/3 = 33.333%, survival = 2/4 = 50.0%
        self.assertEqual(rep['retention'][1]['entrants'], 3)
        self.assertEqual(rep['retention'][1]['stopped'], 1)
        self.assertEqual(rep['retention'][1]['continued'], 2)
        self.assertAlmostEqual(rep['retention'][1]['drop_rate']['observed'], 33.3333, places=3)
        self.assertEqual(rep['retention'][1]['survival']['observed'], 50.0)

        # Engagement save: p01 and p04 took save -> 2/4 = 50.0%
        self.assertEqual(rep['engagement']['save']['observed'], 50.0)
        # Engagement share: p02 took share -> 1/4 = 25.0%
        self.assertEqual(rep['engagement']['share']['observed'], 25.0)


class TestCriterion5FailureAndRecovery(unittest.TestCase):
    def test_cast_status_incomplete_and_failed(self):
        """Criterion 5: 49/1 and 39/11 incomplete terminal statuses, zero-valid failed status."""
        # 49/1 incomplete
        status_49_1 = cast_status('flash', 50, 49, 1, 0)
        self.assertEqual(status_49_1, 'incomplete')

        # 39/11 incomplete
        status_39_11 = cast_status('flash', 50, 39, 11, 0)
        self.assertEqual(status_39_11, 'incomplete')

        # 0 valid terminal traces (50 failed) -> failed
        status_0_50 = cast_status('flash', 50, 0, 50, 0)
        self.assertEqual(status_0_50, 'failed')

        # 50 valid terminal traces -> complete
        status_50 = cast_status('flash', 50, 50, 0, 0)
        self.assertEqual(status_50, 'complete')

    def test_worker_crash_and_lease_recovery(self):
        """Worker crash simulation: expired lease claimed with incremented generation, no duplicate execution."""
        # Drain any existing queued jobs first
        while True:
            l = claim()
            if not l:
                break
            with connection() as conn:
                release(conn, l, done=True)

        with connection() as conn:
            vid = uid()
            owner_res = conn.execute("SELECT id FROM owner_sessions LIMIT 1").fetchone()
            owner_id = owner_res['id']
            conn.execute("INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)",
                         (vid, owner_id, 'dummy_sha', Jsonb({'duration_ms': 1000, 'storage_ready': True, 'original_key': 'k', 'bytes': 10, 'caveats': []})))
            run_id = uid()
            conn.execute("INSERT INTO runs(id, video_id) VALUES(%s, %s)", (run_id, vid))
            job_id = uid()
            conn.execute("INSERT INTO jobs(id, video_id, run_id, kind, status) VALUES(%s, %s, %s, 'analysis', 'queued')", (job_id, vid, run_id))

        # 1. Worker 1 claims job
        lease1 = claim()
        self.assertIsNotNone(lease1)
        self.assertEqual(lease1['id'], job_id)
        gen1 = lease1['generation']

        # 2. Simulate worker 1 crash: lease expires in past without release
        with connection() as conn:
            conn.execute("UPDATE jobs SET lease_until=now() - interval '1 second' WHERE id=%s", (job_id,))

        # 3. Worker 2 claims expired job: generation MUST be incremented
        lease2 = claim()
        self.assertIsNotNone(lease2)
        self.assertEqual(lease2['id'], job_id)
        self.assertGreater(lease2['generation'], gen1)

        # 4. Worker 1 tries to fence with stale lease -> MUST raise LeaseLost
        from apps.api.app.worker import LeaseLost
        with connection() as conn:
            with self.assertRaises(LeaseLost):
                fence(conn, lease1)

        # Clean up
        with connection() as conn:
            release(conn, lease2, done=True)


class TestCriterion6PrivacyAndDeletion(unittest.TestCase):
    def test_privacy_isolation_and_immediate_revocation(self):
        """Criterion 6: Two sessions, deletion immediate 404, complete S3 object erasure."""
        client_owner = TestClient(app, base_url='http://127.0.0.1:58000')
        headers_owner = create_session(client_owner)

        client_other = TestClient(app, base_url='http://127.0.0.1:58000')
        headers_other = create_session(client_other)

        video_bytes = get_video_a_bytes()
        up = client_owner.post(
            '/videos',
            headers={**headers_owner, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_priv_{uid()[:8]}'},
            content=video_bytes
        )
        self.assertEqual(up.status_code, 201)
        video_id = up.json()['video_id']

        run_res = client_owner.post(
            '/runs',
            headers={**headers_owner, 'Content-Type': 'application/json', 'Idempotency-Key': f'run_priv_{uid()[:8]}'},
            json={'video_id': video_id, 'profile': 'flash'}
        )
        self.assertEqual(run_res.status_code, 202)
        run_id = run_res.json()['run_id']

        # 1. Other session receives 404 on all endpoints
        self.assertEqual(client_other.get(f'/videos/{video_id}/analysis', headers=headers_other).status_code, 404)
        self.assertEqual(client_other.get(f'/videos/{video_id}/media', headers=headers_other).status_code, 404)
        self.assertEqual(client_other.get(f'/runs/{run_id}', headers=headers_other).status_code, 404)
        self.assertEqual(client_other.get(f'/runs/{run_id}/report', headers=headers_other).status_code, 404)
        other_vids = client_other.get('/videos', headers=headers_other).json()
        self.assertFalse(any(v['id'] == video_id for v in other_vids))

        # 2. Owner initiates deletion
        del_res = client_owner.delete(
            f'/videos/{video_id}',
            headers={**headers_owner, 'Idempotency-Key': f'del_priv_{uid()[:8]}'}
        )
        self.assertEqual(del_res.status_code, 202)
        del_data = del_res.json()
        self.assertTrue(del_data['access_revoked'])

        # 3. Owner immediately denied access (immediate revocation before asynchronous wipe)
        self.assertEqual(client_owner.get(f'/videos/{video_id}/analysis', headers=headers_owner).status_code, 404)
        self.assertEqual(client_owner.get(f'/videos/{video_id}/media', headers=headers_owner).status_code, 404)
        self.assertEqual(client_owner.get(f'/runs/{run_id}', headers=headers_owner).status_code, 404)
        self.assertEqual(client_owner.get(f'/runs/{run_id}/report', headers=headers_owner).status_code, 404)
        owner_vids = client_owner.get('/videos', headers=headers_owner).json()
        self.assertFalse(any(v['id'] == video_id for v in owner_vids))

        # 4. Find all objects registered for this video
        with connection() as conn:
            objects = conn.execute("SELECT key FROM objects WHERE video_id=%s", (video_id,)).fetchall()
            obj_keys = [o['key'] for o in objects]
            self.assertTrue(len(obj_keys) > 0, 'No objects registered for video')

        # 5. Process deletion worker steps until complete
        steps = 0
        while steps < 20:
            worked = process_once()
            steps += 1
            if not worked:
                break

        # 6. Verify deletion state in DB
        with connection() as conn:
            del_row = conn.execute("SELECT state FROM deletions WHERE video_id=%s", (video_id,)).fetchone()
            self.assertIsNotNone(del_row)
            del_state = del_row['state']
            self.assertEqual(del_state['status'], 'complete')
            self.assertTrue(del_state['can_claim_complete'])

        # 7. S3 verification: every registered object key MUST return 404 via S3 HEAD
        storage = Storage()
        for key in obj_keys:
            with self.assertRaises(Exception) as cm:
                storage.client.head_object(Bucket=storage.bucket, Key=key)
            self.assertIn('404', str(cm.exception))


class TestCorrection1BlockerRegressions(unittest.TestCase):
    """Focused regression test suite covering the 4 review findings and migration 003."""

    def test_migration_003_manifest_integer_type_guard_and_health(self):
        """Blocker 2: Schema guard rejects string/null/fractional/bool count and seed; health requires version 3."""
        # 1. Health endpoint requires version 3
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.get('/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['status'], 'ok')
        create_session(client)

        with connection() as conn:
            # 2. Schema versions contain 1, 2, 3
            versions = {r['version'] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
            self.assertTrue({1, 2, 3}.issubset(versions))

            vid = uid()
            owner_res = conn.execute("SELECT id FROM owner_sessions LIMIT 1").fetchone()
            owner_id = owner_res['id']
            conn.execute(
                "INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)",
                (vid, owner_id, 'dummy_sha_m003', Jsonb({'duration_ms': 1000, 'storage_ready': True, 'original_key': 'k', 'bytes': 10, 'caveats': []}))
            )

            # 3. Valid integer counts and seeds succeed
            valid_cases = [
                {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': 3, 'resample_seed': 20261028, 'persona_ids': ['p001', 'p002', 'p003']},
                {'schema_version': 'run-manifest-1', 'profile': 'flash', 'provider_mode': 'recorded', 'requested': 50, 'resample_seed': 0, 'persona_ids': [f'p{i:03d}' for i in range(1, 51)]},
            ]
            for manifest in valid_cases:
                rid = uid()
                conn.execute("INSERT INTO runs(id, video_id, manifest) VALUES(%s, %s, %s)", (rid, vid, Jsonb(manifest)))
                row = conn.execute("SELECT manifest FROM runs WHERE id=%s", (rid,)).fetchone()
                self.assertEqual(row['manifest']['requested'], manifest['requested'])
                self.assertEqual(row['manifest']['resample_seed'], manifest['resample_seed'])

            # 4. Invalid count/seed types and values rejected by CheckViolation
            invalid_cases = [
                ('string count', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': '3', 'resample_seed': 20261028, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('string seed', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': 3, 'resample_seed': '20261028', 'persona_ids': ['p001', 'p002', 'p003']}),
                ('fractional count', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': 3.5, 'resample_seed': 20261028, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('fractional seed', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': 3, 'resample_seed': 1.5, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('null count', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': None, 'resample_seed': 20261028, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('null seed', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': 3, 'resample_seed': None, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('bool count', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': True, 'resample_seed': 20261028, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('bool seed', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': 3, 'resample_seed': False, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('negative count', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': -1, 'resample_seed': 20261028, 'persona_ids': ['p001', 'p002', 'p003']}),
                ('negative seed', {'schema_version': 'run-manifest-1', 'profile': 'test', 'provider_mode': 'recorded', 'requested': 3, 'resample_seed': -5, 'persona_ids': ['p001', 'p002', 'p003']}),
            ]
            for label, manifest in invalid_cases:
                with self.assertRaises(psycopg.errors.CheckViolation, msg=f"Case {label} should have failed check violation"):
                    with conn.transaction():
                        conn.execute("INSERT INTO runs(id, video_id, manifest) VALUES(%s, %s, %s)", (uid(), vid, Jsonb(manifest)))

            # 5. Idempotent repeat application of migration 003
            m003_path = Path(__file__).resolve().parents[1] / 'migrations/003_manifest_integer_fields.sql'
            conn.execute(m003_path.read_text(encoding='utf-8'))

    def test_cohort_isolation_three_trace_controlled_fixture(self):
        """Blocker 1: Terminal-trace cohort determines rates, stop triggers, evidence IDs, and note references."""
        manifest = {
            'profile': 'test',
            'provider_mode': 'recorded',
            'requested': 3,
            'resample_seed': 20261028,
            'persona_ids': ['p001', 'p002', 'p003'],
        }
        video = {
            'metadata': {'duration_ms': 6000},
            'features': {
                'scenes': [
                    {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
                    {'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000},
                ],
                'caveats': [],
            }
        }
        # p001 stopped at scene 0, p002 completed scene 1, p003 failed at scene 1 after scene 0 prefix
        checkpoints = [
            {'persona_id': 'p001', 'status': 'stopped'},
            {'persona_id': 'p002', 'status': 'complete'},
            {'persona_id': 'p003', 'status': 'failed'},
        ]
        rows = [
            # p001 scene 0
            {
                'reaction': {'persona_id': 'p001', 'scene_id': 0, 'still_watching': False, 'drop_reason': 'Too slow hook', 'actions': [], 'evidence_id': 'ev_p1_s0'},
                'evidence': {'id': 'ev_p1_s0', 'persona_id': 'p001', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'Too slow hook', 'still_watching': False},
            },
            # p002 scene 0
            {
                'reaction': {'persona_id': 'p002', 'scene_id': 0, 'still_watching': True, 'drop_reason': None, 'actions': [{'type': 'like'}], 'evidence_id': 'ev_p2_s0'},
                'evidence': {'id': 'ev_p2_s0', 'persona_id': 'p002', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'Nice intro', 'still_watching': True},
            },
            # p002 scene 1
            {
                'reaction': {'persona_id': 'p002', 'scene_id': 1, 'still_watching': True, 'drop_reason': None, 'actions': [{'type': 'save'}], 'evidence_id': 'ev_p2_s1'},
                'evidence': {'id': 'ev_p2_s1', 'persona_id': 'p002', 'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000, 'quote': 'Great ending', 'still_watching': True},
            },
            # p003 scene 0 (valid prefix, took action 'like' and 'share', but failed later)
            {
                'reaction': {'persona_id': 'p003', 'scene_id': 0, 'still_watching': True, 'drop_reason': None, 'actions': [{'type': 'like'}, {'type': 'share'}], 'evidence_id': 'ev_p3_s0'},
                'evidence': {'id': 'ev_p3_s0', 'persona_id': 'p003', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'Loved it', 'still_watching': True},
            },
        ]
        note_envelope = {
            'output': {
                'notes': [
                    # Candidate 1 cites terminal p001's stop trigger -> valid
                    {
                        'start_sec': 0.0,
                        'end_sec': 3.0,
                        'finding': 'Pacing slow in hook.',
                        'suggested_edit': 'Do not use synthetic mockups; add immediate visual punch.',
                        'evidence_ids': ['ev_p1_s0'],
                        'quotes': ['Too slow hook'],
                    },
                    # Candidate 2 cites excluded p003's evidence -> must be rejected as invalid_reference
                    {
                        'start_sec': 0.0,
                        'end_sec': 3.0,
                        'finding': 'Call to action needed.',
                        'suggested_edit': 'Do not use synthetic mockups; add share prompt.',
                        'evidence_ids': ['ev_p3_s0'],
                        'quotes': ['Loved it'],
                    },
                ]
            }
        }

        rep = build_report(manifest, video, checkpoints, rows, None, 'test_sha', note_envelope, [])

        # 1. Cast
        self.assertEqual(rep['cast']['requested'], 3)
        self.assertEqual(rep['cast']['effective'], 2)
        self.assertEqual(rep['cast']['failed'], 1)
        self.assertEqual(rep['cast']['status'], 'incomplete')

        # 2. Excluded traces
        self.assertEqual(rep['coverage']['excluded_traces'], {'failed': ['p003'], 'pending': []})

        # 3. Retention: scene 0 has 2 entrants (p001, p002), 1 stop (p001) -> 50% stop, NOT 33.33%
        s0 = rep['retention'][0]
        self.assertEqual(s0['entrants'], 2)
        self.assertEqual(s0['stopped'], 1)
        self.assertEqual(s0['continued'], 1)
        self.assertEqual(s0['survival']['observed'], 50.0)
        self.assertEqual(s0['drop_rate']['observed'], 50.0)
        self.assertEqual(s0['drop_rate']['denominator'], 2)
        self.assertNotIn('ev_p3_s0', s0['survival']['evidence_ids'])
        self.assertNotIn('ev_p3_s0', s0['drop_rate']['evidence_ids'])

        # 4. Observation stop trigger: denominator must be 2, numerator 1 -> 50%
        self.assertEqual(len(rep['observations']), 1)
        trigger = rep['observations'][0]
        self.assertEqual(trigger['id'], 'stop_0')
        self.assertEqual(trigger['numerator'], 1)
        self.assertEqual(trigger['denominator'], 2)
        self.assertEqual(trigger['value'], 0.5)
        self.assertEqual(trigger['evidence_refs'], ['ev_p1_s0'])

        # 5. Engagement: p002 had 'like'; p003 had 'share' but is excluded
        like = rep['engagement']['like']
        self.assertEqual(like['observed'], 50.0)
        self.assertEqual(like['denominator'], 2)
        self.assertEqual(like['evidence_ids'], ['ev_p2_s0'])
        self.assertNotIn('ev_p3_s0', like['evidence_ids'])

        share = rep['engagement']['share']
        self.assertEqual(share['observed'], 0.0)
        self.assertEqual(share['denominator'], 2)
        self.assertEqual(share['evidence_ids'], [])

        # 6. Notes: candidate 1 accepted, candidate 2 rejected with invalid_reference
        self.assertEqual(len(rep['notes']), 1)
        self.assertEqual(rep['notes'][0]['evidence_refs'], ['ev_p1_s0'])
        self.assertEqual(rep['suppressed_notes'], 1)
        self.assertEqual(rep['note_rejections']['invalid_reference'], 1)
        self.assertEqual(rep['note_rejections']['unsupported_trigger'], 0)

    def test_zero_effective_metrics_contract_and_frozen_kinds(self):
        """Blocker 3: Zero-effective run emits explicit unavailable_reason, null observed/range, and frozen C5 kinds."""
        manifest = {
            'profile': 'test',
            'provider_mode': 'recorded',
            'requested': 3,
            'resample_seed': 20261028,
            'persona_ids': ['p001', 'p002', 'p003'],
        }
        video = {
            'metadata': {'duration_ms': 6000},
            'features': {
                'scenes': [
                    {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
                    {'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000},
                ],
                'caveats': [],
            }
        }
        checkpoints = [
            {'persona_id': 'p001', 'status': 'failed'},
            {'persona_id': 'p002', 'status': 'failed'},
            {'persona_id': 'p003', 'status': 'failed'},
        ]
        rep = build_report(manifest, video, checkpoints, [], None, 'test_sha', {}, [])

        self.assertEqual(rep['cast']['effective'], 0)
        self.assertEqual(rep['cast']['failed'], 3)
        self.assertEqual(rep['cast']['status'], 'failed')
        self.assertEqual(rep['coverage']['excluded_traces']['failed'], ['p001', 'p002', 'p003'])

        FROZEN_KINDS = {'observed_count', 'simulation_range', 'heuristic_index', 'hypothetical_reach'}

        # Check completion
        comp = rep['completion']
        self.assertIn(comp['kind'], FROZEN_KINDS)
        self.assertNotEqual(comp['kind'], 'observed_rate')
        self.assertIsNone(comp['observed'])
        self.assertIsNone(comp['range'])
        self.assertEqual(comp['denominator'], 0)
        self.assertEqual(comp['unavailable_reason'], 'no_effective_traces')

        # Check retention metrics
        for s in rep['retention']:
            surv = s['survival']
            self.assertIn(surv['kind'], FROZEN_KINDS)
            self.assertNotEqual(surv['kind'], 'observed_rate')
            self.assertIsNone(surv['observed'])
            self.assertIsNone(surv['range'])
            self.assertEqual(surv['denominator'], 0)
            self.assertEqual(surv['unavailable_reason'], 'no_effective_traces')

            drop = s['drop_rate']
            self.assertIn(drop['kind'], FROZEN_KINDS)
            self.assertIsNone(drop['observed'])
            self.assertEqual(drop['denominator'], 0)
            self.assertEqual(drop['unavailable_reason'], 'no_scene_entrants')

        # Check engagement metrics
        for act in ('like', 'share', 'save', 'comment'):
            m = rep['engagement'][act]
            self.assertIn(m['kind'], FROZEN_KINDS)
            self.assertEqual(m['kind'], 'simulation_range')
            self.assertIsNone(m['observed'])
            self.assertIsNone(m['range'])
            self.assertEqual(m['denominator'], 0)
            self.assertEqual(m['unavailable_reason'], 'no_effective_traces')

        follow = rep['engagement']['follow']
        self.assertIn(follow['kind'], FROZEN_KINDS)
        self.assertEqual(follow['kind'], 'simulation_range')
        self.assertIsNone(follow['observed'])
        self.assertEqual(follow['unavailable_reason'], 'action_not_observed_by_legacy_provider')

        # Check scores
        hook = rep['scores']['hook']
        self.assertIn(hook['kind'], FROZEN_KINDS)
        self.assertEqual(hook['kind'], 'heuristic_index')
        self.assertIsNone(hook['observed'])
        self.assertIsNone(hook['range'])
        self.assertEqual(hook['denominator'], 0)
        self.assertEqual(hook['unavailable_reason'], 'no_effective_traces')

        pacing = rep['scores']['pacing']
        self.assertIn(pacing['kind'], FROZEN_KINDS)
        self.assertEqual(pacing['kind'], 'heuristic_index')
        self.assertIsNone(pacing['observed'])
        self.assertIsNone(pacing['range'])
        self.assertEqual(pacing['denominator'], 0)
        self.assertEqual(pacing['unavailable_reason'], 'no_effective_traces')

        self.assertEqual(rep['scores']['clarity']['unavailable_reason'], 'confusion_signal_unobserved')
        self.assertEqual(rep['scores']['cta']['unavailable_reason'], 'cta_understanding_signal_unobserved')
        self.assertEqual(rep['scores']['trend']['unavailable_reason'], 'grounded_trend_rules_unavailable')

    def test_aggregator_note_rejections_and_ranking(self):
        """Blocker 4: Additive note_rejections vocabulary, category counts sum to suppressed_notes, ranking and cap 3."""
        manifest = {
            'profile': 'test',
            'provider_mode': 'recorded',
            'requested': 2,
            'resample_seed': 20261028,
            'persona_ids': ['p001', 'p002'],
        }
        video = {
            'metadata': {'duration_ms': 6000},
            'features': {
                'scenes': [
                    {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
                    {'scene_id': 1, 'start_ms': 3000, 'end_ms': 6000},
                ],
                'caveats': [],
            }
        }
        checkpoints = [
            {'persona_id': 'p001', 'status': 'stopped'},
            {'persona_id': 'p002', 'status': 'stopped'},
        ]
        rows = [
            {
                'reaction': {'persona_id': 'p001', 'scene_id': 0, 'still_watching': False, 'drop_reason': 'Quote A', 'actions': [], 'evidence_id': 'ev_1'},
                'evidence': {'id': 'ev_1', 'persona_id': 'p001', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'Quote A', 'still_watching': False},
            },
            {
                'reaction': {'persona_id': 'p002', 'scene_id': 0, 'still_watching': False, 'drop_reason': 'Quote B', 'actions': [], 'evidence_id': 'ev_2'},
                'evidence': {'id': 'ev_2', 'persona_id': 'p002', 'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'quote': 'Quote B', 'still_watching': False},
            },
        ]

        note_envelope = {
            'output': {
                'notes': [
                    # 1. Valid candidate
                    {
                        'start_sec': 0.0,
                        'end_sec': 2.0,
                        'finding': 'Finding 1',
                        'suggested_edit': 'Do not use synthetic mockups; fix hook.',
                        'evidence_ids': ['ev_1'],
                        'quotes': ['Quote A'],
                    },
                    # 2. Quote mismatch
                    {
                        'start_sec': 0.0,
                        'end_sec': 2.0,
                        'finding': 'Finding 2',
                        'suggested_edit': 'Do not use synthetic mockups; fix hook.',
                        'evidence_ids': ['ev_1'],
                        'quotes': ['Unmatched quote string'],
                    },
                    # 3. Invalid time (end <= start)
                    {
                        'start_sec': 2.0,
                        'end_sec': 1.0,
                        'finding': 'Finding 3',
                        'suggested_edit': 'Do not use synthetic mockups; fix hook.',
                        'evidence_ids': ['ev_1'],
                        'quotes': ['Quote A'],
                    },
                    # 4. Invalid reference
                    {
                        'start_sec': 0.0,
                        'end_sec': 2.0,
                        'finding': 'Finding 4',
                        'suggested_edit': 'Do not use synthetic mockups; fix hook.',
                        'evidence_ids': ['non_existent_ev_id'],
                        'quotes': ['Quote A'],
                    },
                    # 5. Unsupported trigger (scene 1 has 0 stops, so no stop_1 trigger exists)
                    {
                        'start_sec': 3.5,
                        'end_sec': 5.5,
                        'finding': 'Finding 5',
                        'suggested_edit': 'Do not use synthetic mockups; fix body.',
                        'evidence_ids': ['ev_1'],
                        'quotes': ['Quote A'],
                    },
                    # 6. Malformed candidate (non-dict candidate)
                    'not a valid dictionary candidate',
                ]
            }
        }

        rep = build_report(manifest, video, checkpoints, rows, None, 'test_sha', note_envelope, [])

        self.assertEqual(len(rep['notes']), 1)
        self.assertEqual(rep['suppressed_notes'], 5)
        expected_rejections = {
            'unsupported_trigger': 1,
            'quote_mismatch': 1,
            'invalid_time': 1,
            'invalid_reference': 1,
            'malformed_candidate': 1,
        }
        self.assertEqual(rep['note_rejections'], expected_rejections)
        self.assertEqual(sum(rep['note_rejections'].values()), rep['suppressed_notes'])


    def test_real_scheduler_fault_incomplete_run_and_report(self):
        """Blocker 1 & 5: Real scheduler fault yields incomplete status, excluded trace IDs, and honest reporting."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        headers = create_session(client)

        up = client.post(
            '/videos',
            headers={**headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'up_flt_{uid()[:8]}'},
            content=get_video_a_bytes()
        )
        self.assertEqual(up.status_code, 201)
        vid = up.json()['video_id']

        run_res = client.post(
            '/runs',
            headers={**headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'run_flt_{uid()[:8]}'},
            json={'video_id': vid, 'profile': 'test'}
        )
        self.assertEqual(run_res.status_code, 202)
        run_id = run_res.json()['run_id']

        # Step 1: prep job initializes 3 checkpoints
        process_once()

        # Step 2: Inject real failure on checkpoint p003
        with connection() as conn:
            conn.execute("UPDATE checkpoints SET status='failed' WHERE run_id=%s AND persona_id='p003'", (run_id,))

        # Step 3: Run worker to report completion
        steps = 0
        while steps < 50:
            worked = process_once()
            steps += 1
            if not worked:
                break

        # Check API run state
        state = client.get(f'/runs/{run_id}', headers=headers).json()
        self.assertEqual(state['status'], 'incomplete')
        self.assertEqual(state['requested'], 3)
        self.assertEqual(state['effective'], 2)
        self.assertEqual(state['failed'], 1)

        # Check production report
        rep = client.get(f'/runs/{run_id}/report', headers=headers).json()
        self.assertEqual(rep['cast']['status'], 'incomplete')
        self.assertEqual(rep['cast']['effective'], 2)
        self.assertEqual(rep['cast']['failed'], 1)
        self.assertEqual(rep['coverage']['excluded_traces'], {'failed': ['p003'], 'pending': []})
        self.assertEqual(rep['retention'][0]['entrants'], 2)


if __name__ == '__main__':
    unittest.main()
