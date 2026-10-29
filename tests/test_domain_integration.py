"""Integration tests for domain recovery, idempotency, lease fencing, and deletion lifecycle.
Exercises real PostgreSQL 17 and private RustFS S3 with exact production paths.
"""
import unittest
from pathlib import Path
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.domain import (
    idem, owned_video, reserve_object, put_reserved, request_deletion,
    delete_step, fence, Conflict, LeaseLost
)
from apps.api.app.storage import Storage
from apps.api.app.worker import claim, release, process_once
from apps.api.app.providers import digest


class TestDomainIntegration(unittest.TestCase):
    def setUp(self):
        self.store = Storage()
        self.store.check()
        self.owner_id = uid()
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")
            conn.execute(
                "INSERT INTO owner_sessions(id, token_hash, csrf_hash, expires_at) "
                "VALUES(%s, %s, %s, now() + interval '24 hours')",
                (self.owner_id, digest(b'token_' + self.owner_id.encode()), digest(b'csrf_' + self.owner_id.encode()))
            )

    def _create_video(self, sha256='test_hash'):
        vid = uid()
        with connection() as conn:
            conn.execute(
                "INSERT INTO videos(id, owner_id, sha256, metadata) VALUES(%s, %s, %s, %s)",
                (vid, self.owner_id, sha256, Jsonb({'duration_ms': 17108, 'storage_ready': True, 'original_key': f'test/{vid}.mp4', 'bytes': 100, 'caveats': []}))
            )
        return vid

    def test_concurrent_idempotent_run_requests(self):
        """(1) Concurrent same-owner idempotent run requests."""
        vid = self._create_video()
        req_key = 'idem_key_12345678'
        body_hash_1 = digest(b'{"video_id":"' + vid.encode() + b'","profile":"test"}')
        body_hash_changed = digest(b'{"video_id":"' + vid.encode() + b'","profile":"different"}')

        with connection() as conn:
            # First request records result
            initial = dict(run_id=uid(), status='queued')
            res1 = idem(conn, self.owner_id, 'run', req_key, body_hash_1, initial)
            self.assertIsNone(res1)

            # Same key, same body returns recorded result
            res2 = idem(conn, self.owner_id, 'run', req_key, body_hash_1)
            self.assertEqual(res2, initial)

            # Same key, changed body raises Conflict 409
            with self.assertRaises(Conflict) as ctx:
                idem(conn, self.owner_id, 'run', req_key, body_hash_changed)
            self.assertEqual(str(ctx.exception), 'idempotency_body_changed')

    def test_lost_expired_worker_lease_fencing(self):
        """(2) Lost/expired worker lease before publish prevents duplicate verdicts/events."""
        vid = self._create_video()
        run_id = uid()
        job_id = uid()
        with connection() as conn:
            conn.execute("INSERT INTO runs(id, video_id, status) VALUES(%s, %s, 'queued')", (run_id, vid))
            conn.execute("INSERT INTO jobs(id, video_id, run_id, kind, status) VALUES(%s, %s, %s, 'analysis', 'queued')", (job_id, vid, run_id))

        lease = claim()
        self.assertIsNotNone(lease)
        self.assertEqual(lease['id'], job_id)

        # Simulate another process or timeout incrementing generation and taking lease
        with connection() as conn:
            conn.execute(
                "UPDATE jobs SET generation = generation + 1, lease_until = now() + interval '120 seconds' WHERE id = %s",
                (job_id,)
            )

        # Stale worker attempts to fence; must raise LeaseLost
        with connection() as conn:
            with self.assertRaises(LeaseLost):
                fence(conn, lease)

        # Verify no reactions or events were recorded under the stale lease
        with connection() as conn:
            reactions = conn.execute("SELECT count(*) as c FROM reactions WHERE run_id=%s", (run_id,)).fetchone()['c']
            events = conn.execute("SELECT count(*) as c FROM events WHERE run_id=%s", (run_id,)).fetchone()['c']
            self.assertEqual(reactions, 0)
            self.assertEqual(events, 0)

    def test_deletion_between_object_reservation_and_publish(self):
        """(3) Deletion between object reservation and publish fences writes and cleans storage."""
        vid = self._create_video()
        run_id = uid()
        job_id = uid()
        with connection() as conn:
            conn.execute("INSERT INTO runs(id, video_id) VALUES(%s, %s)", (run_id, vid))
            conn.execute("INSERT INTO jobs(id, video_id, run_id, kind) VALUES(%s, %s, %s, 'analysis')", (job_id, vid, run_id))

        lease = claim()

        # Worker reserves an object key
        objkey = reserve_object(vid, 'derivatives', 'jpg', lease)
        self.assertTrue(objkey.startswith(f'v02/{vid}/'))

        # Put bytes in S3 for the reserved key
        self.store.put(objkey, b'test-derivative-frame')

        # Owner requests deletion before worker publishes
        with connection() as conn:
            del_state = request_deletion(conn, self.owner_id, vid)
            self.assertTrue(del_state['access_revoked'])

        # Now worker tries to fence; must fail with LeaseLost because video is tombstoned
        with connection() as conn:
            with self.assertRaises(LeaseLost):
                fence(conn, lease)

        # Run deletion job to execute cleanup
        del_lease = claim()
        self.assertEqual(del_lease['kind'], 'deletion')
        final_del = delete_step(del_lease, self.store)

        # Deletion must claim complete
        self.assertTrue(final_del['can_claim_complete'])
        self.assertEqual(final_del['status'], 'complete')

        # S3 object must be deleted
        with self.assertRaises(Exception):
            self.store.get(objkey)

        # DB object row must be removed
        with connection() as conn:
            obj_row = conn.execute("SELECT 1 FROM objects WHERE key=%s", (objkey,)).fetchone()
            self.assertIsNone(obj_row)

    def test_storage_cleanup_failure_pending_and_retry(self):
        """(4) Storage cleanup failure retains pending status and succeeds on retry."""
        vid = self._create_video()
        objkey = reserve_object(vid, 'originals', 'mp4')
        self.store.put(objkey, b'fake-video-bytes')

        with connection() as conn:
            request_deletion(conn, self.owner_id, vid)

        del_lease = claim()

        # Create a mock storage that fails on delete to simulate provider outage
        class FailingStorage:
            def delete(self, key):
                raise RuntimeError("simulated_storage_outage")

        failing_state = delete_step(del_lease, FailingStorage())
        self.assertFalse(failing_state['can_claim_complete'])
        self.assertEqual(failing_state['status'], 'pending')
        self.assertIn('originals', failing_state['pending_targets'])
        self.assertEqual(failing_state['targets']['originals']['error_code'], 'storage_cleanup_unavailable')
        self.assertIsNotNone(failing_state['targets']['originals']['retry_at'])

        # Ensure the job was not deleted and is queued for retry
        with connection() as conn:
            job = conn.execute("SELECT status, available_at FROM jobs WHERE id=%s", (del_lease['id'],)).fetchone()
            self.assertEqual(job['status'], 'queued')
            # Reset available_at so we can immediately claim for retry test
            conn.execute("UPDATE jobs SET available_at = now() WHERE id=%s", (del_lease['id'],))

        # Re-claim and run with working storage
        retry_lease = claim()
        self.assertIsNotNone(retry_lease)
        success_state = delete_step(retry_lease, self.store)

        self.assertTrue(success_state['can_claim_complete'])
        self.assertEqual(success_state['status'], 'complete')
        self.assertEqual(success_state['pending_targets'], [])
        self.assertEqual(success_state['targets']['originals']['status'], 'complete')

        # Cleaned up in S3
        with self.assertRaises(Exception):
            self.store.get(objkey)


if __name__ == '__main__':
    unittest.main()
