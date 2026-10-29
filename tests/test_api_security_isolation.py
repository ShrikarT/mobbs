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
            conn.execute('INSERT INTO events(run_id, sequence, event_id, type, payload) VALUES(%s, 1, \'ev1\', \'persona.continued\', %s)', (run_id, Jsonb({'persona_id': 'p1', 'scene_id': 0, 'at_ms': 3000})))
            conn.execute('INSERT INTO events(run_id, sequence, event_id, type, payload) VALUES(%s, 2, \'ev2\', \'persona.stopped\', %s)', (run_id, Jsonb({'persona_id': 'p2', 'scene_id': 1, 'drop_reason': 'pacing'})))

        # Incomplete report returns HTTP 200
        rep_res = client.get(f'/runs/{run_id}/report', headers=headers)
        self.assertEqual(rep_res.status_code, 200)
        self.assertEqual(rep_res.json()['cast']['status'], 'incomplete')

        # SSE emits named events
        events_res = client.get(f'/runs/{run_id}/events', headers=headers)
        self.assertEqual(events_res.status_code, 200)
        self.assertIn('event: persona.continued', events_res.text)
        self.assertIn('event: persona.stopped', events_res.text)
        self.assertIn('id: ev1', events_res.text)
        self.assertIn('id: ev2', events_res.text)

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


if __name__ == '__main__':
    unittest.main()
