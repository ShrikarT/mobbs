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


if __name__ == '__main__':
    unittest.main()
