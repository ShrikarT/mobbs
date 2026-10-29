"""Security, session isolation, origin/CSRF, and media boundary tests for FastAPI app."""
import unittest
from starlette.testclient import TestClient
from apps.api.app.main import app
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.providers import digest


class TestApiSecurityIsolation(unittest.TestCase):
    def test_host_header_validation(self):
        """Requests with wrong or missing host are rejected with 403."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.get('/health', headers={'Host': 'evil.com'})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 'invalid_host')

    def test_mutating_origin_csrf_enforcement(self):
        """POST/DELETE without matching Origin or CSRF token are rejected with 403."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        self.assertEqual(res.status_code, 201)

        # Missing Origin on mutating POST
        res = client.post('/videos', headers={'Host': '127.0.0.1:58000'})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 'same_origin_required')

        # Cross-site origin
        res = client.post(
            '/videos',
            headers={'Host': '127.0.0.1:58000', 'Origin': 'http://attacker.com'}
        )
        self.assertEqual(res.status_code, 403)

        # Missing CSRF header
        res = client.post(
            '/videos',
            headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000', 'Content-Type': 'video/mp4', 'Idempotency-Key': 'key_12345678'}
        )
        self.assertEqual(res.status_code, 403)

    def test_cross_session_resource_isolation(self):
        """Session B cannot view, stream, or delete Session A's video or run."""
        client_a = TestClient(app, base_url='http://127.0.0.1:58000')
        res_a = client_a.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        self.assertEqual(res_a.status_code, 201)
        token_a = client_a.cookies.get('vir_session')

        client_b = TestClient(app, base_url='http://127.0.0.1:58000')
        res_b = client_b.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        self.assertEqual(res_b.status_code, 201)
        csrf_b = res_b.json()['csrf']

        # Seed video for Session A
        with connection() as conn:
            token_hash = digest(token_a.encode())
            owner_a = conn.execute("SELECT id FROM owner_sessions WHERE token_hash=%s", (token_hash,)).fetchone()['id']
            vid = uid()
            conn.execute(
                "INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)",
                (vid, owner_a, 'sha_a', Jsonb({'duration_ms': 10000, 'width': 1080, 'height': 1920, 'audio_present': True, 'bytes': 500, 'storage_ready': True, 'original_key': f'v02/{vid}/test.mp4', 'caveats': []}))
            )
            run_id = uid()
            conn.execute("INSERT INTO runs(id, video_id, status) VALUES(%s, %s, 'queued')", (run_id, vid))

        headers_b = {'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'}

        # Session B attempts to read Session A's video analysis -> 404
        res = client_b.get(f'/videos/{vid}/analysis', headers=headers_b)
        self.assertEqual(res.status_code, 404)

        # Session B attempts to stream Session A's media -> 404
        res = client_b.get(f'/videos/{vid}/media', headers=headers_b)
        self.assertEqual(res.status_code, 404)

        # Session B attempts to inspect Session A's run -> 404
        res = client_b.get(f'/runs/{run_id}', headers=headers_b)
        self.assertEqual(res.status_code, 404)

        # Session B attempts to delete Session A's video -> 404
        res = client_b.delete(
            f'/videos/{vid}',
            headers={**headers_b, 'X-CSRF-Token': csrf_b, 'Idempotency-Key': 'del_key_12345678'}
        )
        self.assertEqual(res.status_code, 404)

        # Session B does not see Session A's video in /videos list
        res = client_b.get('/videos', headers=headers_b)
        self.assertEqual(res.status_code, 200)
        vids = [v['id'] for v in res.json()]
        self.assertNotIn(vid, vids)

    def test_media_validation_rejections(self):
        """Corrupt input, non-MP4, and size violations are rejected before model dispatch."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        csrf = res.json()['csrf']
        headers = {
            'Host': '127.0.0.1:58000',
            'Origin': 'http://127.0.0.1:58000',
            'X-CSRF-Token': csrf,
            'Idempotency-Key': 'up_key_12345678',
            'Content-Type': 'video/mp4'
        }

        # Corrupt bytes (not an MP4 container)
        res = client.post('/videos', headers=headers, content=b'not a valid mp4 header')
        self.assertEqual(res.status_code, 422)
        self.assertIn('mp4', res.json()['code'])

        # Over 200 MB limit check via header
        oversized_headers = {**headers, 'Content-Length': str(200_000_001), 'Idempotency-Key': 'up_key_oversized'}
        res = client.post('/videos', headers=oversized_headers, content=b'x')
        self.assertEqual(res.status_code, 413)
        self.assertEqual(res.json()['code'], 'maximum_size_200000000_bytes')



    def test_idempotency_binding_on_existing_run_counterexample(self):
        """Reproduction fix: POST /runs with fresh key on existing run records binding; reuse with different video returns 409."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        token = client.cookies.get('vir_session')
        csrf = res.json()['csrf']
        headers = {'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000', 'X-CSRF-Token': csrf}

        with connection() as conn:
            owner_id = conn.execute('SELECT id FROM owner_sessions WHERE token_hash=%s', (digest(token.encode()),)).fetchone()['id']
            vid_b = uid()
            vid_a = uid()
            conn.execute('INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)', (vid_b, owner_id, 'sha_b', Jsonb({'duration_ms': 17108, 'storage_ready': True, 'original_key': 'b.mp4', 'bytes': 100, 'caveats': []})))
            conn.execute('INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)', (vid_a, owner_id, 'sha_a', Jsonb({'duration_ms': 33782, 'storage_ready': True, 'original_key': 'a.mp4', 'bytes': 100, 'caveats': []})))

        # 1. Create run for owned B with initial key
        res1 = client.post('/runs', headers={**headers, 'Idempotency-Key': 'key_initial_12345678'}, json={'video_id': vid_b, 'profile': 'test'})
        self.assertEqual(res1.status_code, 202)
        run_b_id = res1.json()['run_id']

        # 2. POST /runs for owned B with fresh key K (existing-run path)
        res2 = client.post('/runs', headers={**headers, 'Idempotency-Key': 'key_fresh_k_12345678'}, json={'video_id': vid_b, 'profile': 'test'})
        self.assertEqual(res2.status_code, 202)
        self.assertEqual(res2.json()['run_id'], run_b_id)

        # 3. Reuse key K with owned A -> MUST return 409 Conflict
        res3 = client.post('/runs', headers={**headers, 'Idempotency-Key': 'key_fresh_k_12345678'}, json={'video_id': vid_a, 'profile': 'test'})
        self.assertEqual(res3.status_code, 409)
        self.assertEqual(res3.json()['code'], 'idempotency_body_changed')

    def test_idempotency_binding_on_delete_counterexample_and_stable_repeat(self):
        """Reproduction fix: DELETE B with key D binds canonical request; reuse D with A returns 409; repeat B is stable."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        token = client.cookies.get('vir_session')
        csrf = res.json()['csrf']
        headers = {'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000', 'X-CSRF-Token': csrf}

        with connection() as conn:
            owner_id = conn.execute('SELECT id FROM owner_sessions WHERE token_hash=%s', (digest(token.encode()),)).fetchone()['id']
            vid_b = uid()
            vid_a = uid()
            conn.execute('INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)', (vid_b, owner_id, 'sha_b', Jsonb({'duration_ms': 17108, 'storage_ready': True, 'original_key': 'b.mp4', 'bytes': 100, 'caveats': []})))
            conn.execute('INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)', (vid_a, owner_id, 'sha_a', Jsonb({'duration_ms': 33782, 'storage_ready': True, 'original_key': 'a.mp4', 'bytes': 100, 'caveats': []})))

        # 1. DELETE B using key D
        res1 = client.delete(f'/videos/{vid_b}', headers={**headers, 'Idempotency-Key': 'key_del_d_12345678'})
        self.assertEqual(res1.status_code, 202)
        del_b_id = res1.json()['deletion_id']
        self.assertTrue(res1.json()['access_revoked'])

        # 2. Repeated DELETE B with same key D -> returns 202 and same deletion ID
        res2 = client.delete(f'/videos/{vid_b}', headers={**headers, 'Idempotency-Key': 'key_del_d_12345678'})
        self.assertEqual(res2.status_code, 202)
        self.assertEqual(res2.json()['deletion_id'], del_b_id)

        # 3. Repeated DELETE B with different key D2 -> returns 202 and same deletion ID
        res3 = client.delete(f'/videos/{vid_b}', headers={**headers, 'Idempotency-Key': 'key_del_d2_87654321'})
        self.assertEqual(res3.status_code, 202)
        self.assertEqual(res3.json()['deletion_id'], del_b_id)

        # 4. Reuse key D with owned A -> MUST return 409 Conflict
        res4 = client.delete(f'/videos/{vid_a}', headers={**headers, 'Idempotency-Key': 'key_del_d_12345678'})
        self.assertEqual(res4.status_code, 409)
        self.assertEqual(res4.json()['code'], 'idempotency_body_changed')

    def test_list_deletions_and_incomplete_report_and_sse_events(self):
        """Test GET /deletions recovery, incomplete report HTTP 200, and SSE named events."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        token = client.cookies.get('vir_session')
        csrf = res.json()['csrf']
        headers = {'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000', 'X-CSRF-Token': csrf}

        with connection() as conn:
            owner_id = conn.execute('SELECT id FROM owner_sessions WHERE token_hash=%s', (digest(token.encode()),)).fetchone()['id']
            vid = uid()
            conn.execute('INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)', (vid, owner_id, 'sha_test', Jsonb({'duration_ms': 17108, 'storage_ready': True, 'original_key': 'test.mp4', 'bytes': 100, 'caveats': []})))
            run_id = uid()
            partial_report = {'schema_version': 'normalized-1', 'cast': {'status': 'incomplete', 'requested': 3, 'effective': 2, 'failed': 1, 'pending': 0, 'stopped': 1, 'profile': 'test'}, 'notes': [], 'observations': [], 'evidence': [], 'caveats': ['0 unsupported note(s) suppressed.'], 'coverage': {}}
            conn.execute('INSERT INTO runs(id, video_id, status, stage, sequence, report) VALUES(%s, %s, \'incomplete\', \'reporting\', 2, %s)', (run_id, vid, Jsonb(partial_report)))
            ev1 = f'ev1_{uid()}'
            ev2 = f'ev2_{uid()}'
            conn.execute('INSERT INTO events(run_id, sequence, event_id, type, payload) VALUES(%s, 1, %s, \'persona.continued\', %s)', (run_id, ev1, Jsonb({'persona_id': 'p1', 'scene_id': 0, 'at_ms': 3000})))
            conn.execute('INSERT INTO events(run_id, sequence, event_id, type, payload) VALUES(%s, 2, %s, \'persona.stopped\', %s)', (run_id, ev2, Jsonb({'persona_id': 'p2', 'scene_id': 1, 'drop_reason': 'pacing'})))

        # Incomplete report returns HTTP 200
        rep_res = client.get(f'/runs/{run_id}/report', headers=headers)
        self.assertEqual(rep_res.status_code, 200)
        self.assertEqual(rep_res.json()['cast']['status'], 'incomplete')

        # SSE emits named events
        events_res = client.get(f'/runs/{run_id}/events', headers=headers)
        self.assertEqual(events_res.status_code, 200)
        self.assertIn('event: persona.continued', events_res.text)
        self.assertIn('event: persona.stopped', events_res.text)
        self.assertIn(f'id: {ev1}', events_res.text)
        self.assertIn(f'id: {ev2}', events_res.text)

        # Deletion and GET /deletions
        del_res = client.delete(f'/videos/{vid}', headers={**headers, 'Idempotency-Key': 'key_del_list_123'})
        self.assertEqual(del_res.status_code, 202)
        list_res = client.get('/deletions', headers=headers)
        self.assertEqual(list_res.status_code, 200)
        dels = list_res.json()
        self.assertTrue(len(dels) >= 1)
        self.assertEqual(dels[0]['video_id'], vid)
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE video_id=%s", (vid,))


    def test_cross_session_delete_authorization_regression_before_pending_completed(self):
        """Cross-session DELETE isolation: other owner returns 404 before, during (pending), and after (completed) deletion.
        No deletion metadata or operation ID disclosed to other owner. Legitimate owner repeats remain 202."""
        client_a = TestClient(app, base_url='http://127.0.0.1:58000')
        res_a = client_a.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        token_a = client_a.cookies.get('vir_session')
        csrf_a = res_a.json()['csrf']
        headers_a = {'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000', 'X-CSRF-Token': csrf_a}

        client_b = TestClient(app, base_url='http://127.0.0.1:58000')
        res_b = client_b.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        token_b = client_b.cookies.get('vir_session')
        csrf_b = res_b.json()['csrf']
        headers_b = {'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000', 'X-CSRF-Token': csrf_b}

        with connection() as conn:
            owner_a = conn.execute('SELECT id FROM owner_sessions WHERE token_hash=%s', (digest(token_a.encode()),)).fetchone()['id']
            owner_b = conn.execute('SELECT id FROM owner_sessions WHERE token_hash=%s', (digest(token_b.encode()),)).fetchone()['id']
            vid_a = uid()
            conn.execute('INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)', (vid_a, owner_a, 'sha_a_reg', Jsonb({'duration_ms': 33782, 'storage_ready': True, 'original_key': 'a.mp4', 'bytes': 100, 'caveats': []})))

        # 1. Before deletion: Session B DELETE Session A's video -> 404
        b_before = client_b.delete(f'/videos/{vid_a}', headers={**headers_b, 'Idempotency-Key': 'key_b_before_del'})
        self.assertEqual(b_before.status_code, 404)
        self.assertEqual(b_before.json()['code'], 'not_found')

        # 2. Session A initiates DELETE -> 202
        a_del = client_a.delete(f'/videos/{vid_a}', headers={**headers_a, 'Idempotency-Key': 'key_a_init_del'})
        self.assertEqual(a_del.status_code, 202)
        del_id_a = a_del.json()['deletion_id']
        self.assertTrue(a_del.json()['access_revoked'])
        self.assertEqual(a_del.json()['status'], 'pending')

        # 3. During pending: Session B DELETE Session A's video -> 404 (regression check: MUST NOT return 202 or del_id_a!)
        b_pending = client_b.delete(f'/videos/{vid_a}', headers={**headers_b, 'Idempotency-Key': 'key_b_during_del'})
        self.assertEqual(b_pending.status_code, 404)
        self.assertEqual(b_pending.json()['code'], 'not_found')
        self.assertNotIn('deletion_id', b_pending.json())

        # Session B attempts DELETE with Session A's same key -> 404
        b_same_key = client_b.delete(f'/videos/{vid_a}', headers={**headers_b, 'Idempotency-Key': 'key_a_init_del'})
        self.assertEqual(b_same_key.status_code, 404)

        # Session B attempts GET /deletions/{del_id_a} -> 404
        b_get_del = client_b.get(f'/deletions/{del_id_a}', headers=headers_b)
        self.assertEqual(b_get_del.status_code, 404)

        # Session B GET /deletions does not contain del_id_a
        b_list_del = client_b.get('/deletions', headers=headers_b)
        self.assertEqual(b_list_del.status_code, 200)
        self.assertNotIn(del_id_a, [d['id'] for d in b_list_del.json()])

        # Legitimate owner repeats: Session A repeats DELETE with same key -> 202, same del_id_a
        a_repeat_same = client_a.delete(f'/videos/{vid_a}', headers={**headers_a, 'Idempotency-Key': 'key_a_init_del'})
        self.assertEqual(a_repeat_same.status_code, 202)
        self.assertEqual(a_repeat_same.json()['deletion_id'], del_id_a)

        # Session A repeats DELETE with fresh key -> 202, same del_id_a
        a_repeat_fresh = client_a.delete(f'/videos/{vid_a}', headers={**headers_a, 'Idempotency-Key': 'key_a_fresh_del'})
        self.assertEqual(a_repeat_fresh.status_code, 202)
        self.assertEqual(a_repeat_fresh.json()['deletion_id'], del_id_a)

        # 4. Completed deletion: mark all targets complete
        with connection() as conn:
            cur_state = conn.execute('SELECT state FROM deletions WHERE id=%s', (del_id_a,)).fetchone()['state']
            cur_state['status'] = 'complete'
            cur_state['can_claim_complete'] = True
            cur_state['pending_targets'] = []
            for t in cur_state['targets'].values():
                t['status'] = 'complete'
            conn.execute('UPDATE deletions SET state=%s WHERE id=%s', (Jsonb(cur_state), del_id_a))

        # Session B attempts DELETE after completion -> 404
        b_completed = client_b.delete(f'/videos/{vid_a}', headers={**headers_b, 'Idempotency-Key': 'key_b_after_del'})
        self.assertEqual(b_completed.status_code, 404)
        self.assertEqual(b_completed.json()['code'], 'not_found')

        # Session A repeats DELETE after completion -> 202, same del_id_a
        a_repeat_completed = client_a.delete(f'/videos/{vid_a}', headers={**headers_a, 'Idempotency-Key': 'key_a_completed_del'})
        self.assertEqual(a_repeat_completed.status_code, 202)
        self.assertEqual(a_repeat_completed.json()['deletion_id'], del_id_a)
        self.assertEqual(a_repeat_completed.json()['status'], 'complete')

        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE video_id=%s", (vid_a,))

    def test_legacy_persisted_report_compatibility_truthful_projection(self):
        """Authoritative stored facts: legacy persisted reports omitting optional duration_ms, scenes, and
        suppressed_notes truthfully project from video metadata and features without fabricating B scenes."""
        client = TestClient(app, base_url='http://127.0.0.1:58000')
        res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        token = client.cookies.get('vir_session')
        csrf = res.json()['csrf']
        headers = {'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000', 'X-CSRF-Token': csrf}

        # 8 scenes of video A (33782ms)
        scenes_a = [
            {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000},
            {'scene_id': 1, 'start_ms': 3000, 'end_ms': 8000},
            {'scene_id': 2, 'start_ms': 8000, 'end_ms': 12000},
            {'scene_id': 3, 'start_ms': 12000, 'end_ms': 17000},
            {'scene_id': 4, 'start_ms': 17000, 'end_ms': 22000},
            {'scene_id': 5, 'start_ms': 22000, 'end_ms': 26000},
            {'scene_id': 6, 'start_ms': 26000, 'end_ms': 30000},
            {'scene_id': 7, 'start_ms': 30000, 'end_ms': 33782},
        ]
        bundle_a = {
            'schema_version': 'normalized-1',
            'extractor_version': 'ffmpeg-local-v02',
            'timebase': 'milliseconds',
            'scenes': scenes_a,
            'caveats': ['No local transcript or OCR extraction.'],
            'provenance': ['Decoded from uploaded bytes.']
        }
        metadata_a = {
            'duration_ms': 33782,
            'width': 1080,
            'height': 1920,
            'audio_present': True,
            'bytes': 1865999,
            'storage_ready': True,
            'original_key': 'a.mp4',
            'caveats': []
        }
        # Old-shape report: lacks duration_ms, scenes, and suppressed_notes
        legacy_report_a = {
            'schema_version': 'normalized-1',
            'cast': {'profile': 'test', 'requested': 3, 'effective': 3, 'failed': 0, 'pending': 0, 'stopped': 3, 'status': 'complete_test_profile'},
            'notes': [],
            'observations': [],
            'evidence': [],
            'completion': {'kind': 'simulation_range', 'unit': 'percent', 'observed': 0.0, 'denominator': 3, 'range': {'low': 0.0, 'high': 0.0, 'method': 'nearest-rank p10-p90'}, 'evidence_ids': []},
            'trust': {'model_id': 'meta/spark-1.3', 'app_source_sha': 'testsha'},
            'methodology': {'range_kind': 'simulation_resampling_not_confidence', 'ranking': 'heuristic stop fraction', 'assumptions': ['Independent simulated traces.']},
            'caveats': ['1 unsupported note(s) suppressed.', 'Signals unavailable.'],
            'coverage': {'transcript': False, 'ocr': False, 'confused': None, 'cta_understood': None, 'trend_fit': None}
        }

        with connection() as conn:
            owner_id = conn.execute('SELECT id FROM owner_sessions WHERE token_hash=%s', (digest(token.encode()),)).fetchone()['id']
            vid_a = uid()
            conn.execute('INSERT INTO videos(id, owner_id, sha256, metadata, features) VALUES(%s, %s, %s, %s, %s)', (vid_a, owner_id, 'sha_a_legacy', Jsonb(metadata_a), Jsonb(bundle_a)))
            run_id_a = uid()
            conn.execute('INSERT INTO runs(id, video_id, status, stage, sequence, report) VALUES(%s, %s, \'complete\', \'reporting\', 5, %s)', (run_id_a, vid_a, Jsonb(legacy_report_a)))

        res_rep = client.get(f'/runs/{run_id_a}/report', headers=headers)
        self.assertEqual(res_rep.status_code, 200)
        data = res_rep.json()

        # Must project truthful duration, scenes, and suppressed_notes from stored source
        self.assertEqual(data['duration_ms'], 33782)
        self.assertEqual(len(data['scenes']), 8)
        self.assertEqual(data['scenes'][7]['end_ms'], 33782)
        self.assertEqual(data['suppressed_notes'], 1)

        # Invariant: underlying stored record is preserved without destructive mutation
        with connection() as conn:
            raw_report = conn.execute('SELECT report FROM runs WHERE id=%s', (run_id_a,)).fetchone()['report']
            self.assertNotIn('duration_ms', raw_report)
            self.assertNotIn('scenes', raw_report)
            self.assertNotIn('suppressed_notes', raw_report)
            conn.execute('DELETE FROM runs WHERE id=%s', (run_id_a,))
            conn.execute('DELETE FROM videos WHERE id=%s', (vid_a,))


if __name__ == '__main__':
    unittest.main()
