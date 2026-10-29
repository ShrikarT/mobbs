"""End-to-end journey test using real owned video B, real PostgreSQL, and private S3.
Upload -> validation -> durable worker -> small test cast -> supported note -> report -> deletion.
"""
import unittest
from pathlib import Path
from starlette.testclient import TestClient
from apps.api.app.main import app
from apps.api.app.worker import process_once
from apps.api.app.storage import Storage
from apps.api.app.db import connection

VIDEO_B_PATH = Path(r"D:\UserFolders\Downloads\WhatsApp Video 2026-10-28 at 9.06.27 AM.mp4")


class TestFullJourney(unittest.TestCase):
    def test_complete_owned_journey_and_deletion(self):
        self.assertTrue(VIDEO_B_PATH.is_file(), f"Missing required test asset: {VIDEO_B_PATH}")
        video_bytes = VIDEO_B_PATH.read_bytes()

        client = TestClient(app, base_url='http://127.0.0.1:58000')

        # 1. Initialize session
        res = client.post('/sessions', headers={'Host': '127.0.0.1:58000', 'Origin': 'http://127.0.0.1:58000'})
        self.assertEqual(res.status_code, 201)
        csrf = res.json()['csrf']
        headers = {
            'Host': '127.0.0.1:58000',
            'Origin': 'http://127.0.0.1:58000',
            'X-CSRF-Token': csrf,
        }

        # 2. Upload original video B
        up_res = client.post(
            '/videos',
            headers={**headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': 'up_journey_b_001'},
            content=video_bytes
        )
        self.assertEqual(up_res.status_code, 201)
        video_id = up_res.json()['video_id']
        self.assertEqual(up_res.json()['status'], 'uploaded')

        # 3. Start analysis run
        run_res = client.post(
            '/runs',
            headers={**headers, 'Content-Type': 'application/json', 'Idempotency-Key': 'run_journey_b_001'},
            json={'video_id': video_id, 'profile': 'test'}
        )
        self.assertEqual(run_res.status_code, 202)
        run_id = run_res.json()['run_id']
        self.assertEqual(run_res.json()['status'], 'queued')

        # 4. Durable worker processing loop
        # Step through decoder, simulation of 3 personas across 4 scenes, and report generation
        steps = 0
        while steps < 25:
            worked = process_once()
            steps += 1
            if not worked:
                break

        # 5. Check run state
        state_res = client.get(f'/runs/{run_id}', headers=headers)
        self.assertEqual(state_res.status_code, 200)
        state = state_res.json()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['stage'], 'report')
        self.assertEqual(state['requested'], 3)
        self.assertEqual(state['effective'], 3)
        self.assertEqual(state['failed'], 0)
        self.assertEqual(state['pending'], 0)

        # 6. Check report
        rep_res = client.get(f'/runs/{run_id}/report', headers=headers)
        self.assertEqual(rep_res.status_code, 200)
        report = rep_res.json()

        self.assertEqual(report['schema_version'], 'normalized-1')
        self.assertEqual(report['cast']['profile'], 'test')
        self.assertEqual(report['cast']['requested'], 3)
        self.assertEqual(report['cast']['effective'], 3)
        self.assertEqual(report['cast']['status'], 'complete_test_profile')

        # Notes: exactly 1 supported note for 3000ms - 8000ms citing trigger stop_1
        self.assertEqual(len(report['notes']), 1)
        note = report['notes'][0]
        self.assertEqual(note['start_ms'], 3000)
        self.assertEqual(note['end_ms'], 8000)
        self.assertEqual(note['trigger_id'], 'stop_1')
        self.assertTrue(len(note['quotes']) > 0)
        self.assertTrue(len(note['fix']) > 0)
        self.assertIn('real screen capture', note['fix'])

        # Observations include stop trigger
        self.assertTrue(any(obs['kind'] == 'stop_fraction' for obs in report['observations']))

        # Trust manifest verifies recorded mode and hash binding
        self.assertEqual(report['trust']['mode'], 'recorded')
        self.assertEqual(report['trust']['model_ids'], ['muse-spark-1.3'])
        self.assertEqual(report['trust']['media_sha256'], 'b0b43397f99e31467cf89827336d8ee5c69c33719a28f086ecebca6ba0d9ec9f')

        # Caveats include suppressed note disclosure
        self.assertTrue(any('suppressed' in c for c in report['caveats']))

        # 7. Check media streaming with Range request
        media_res = client.get(f'/videos/{video_id}/media', headers={**headers, 'Range': 'bytes=0-1023'})
        self.assertEqual(media_res.status_code, 206)
        self.assertEqual(len(media_res.content), 1024)

        # 8. Check events stream
        ev_res = client.get(f'/runs/{run_id}/events?after=0', headers=headers)
        self.assertEqual(ev_res.status_code, 200)
        self.assertIn('event: persona.', ev_res.text)

        # 9. Request deletion
        del_res = client.delete(
            f'/videos/{video_id}',
            headers={**headers, 'Idempotency-Key': 'del_journey_b_001'}
        )
        self.assertEqual(del_res.status_code, 202)
        del_id = del_res.json()['deletion_id']
        self.assertTrue(del_res.json()['access_revoked'])

        # Immediate access revocation: video and run return 404
        self.assertEqual(client.get(f'/videos/{video_id}/analysis', headers=headers).status_code, 404)
        self.assertEqual(client.get(f'/runs/{run_id}', headers=headers).status_code, 404)

        # Run worker to execute deletion job
        del_steps = 0
        while del_steps < 5:
            worked = process_once()
            del_steps += 1
            if not worked:
                break

        # Deletion state must be complete
        cur_del_res = client.get(f'/deletions/{del_id}', headers=headers)
        self.assertEqual(cur_del_res.status_code, 200)
        cur_del = cur_del_res.json()
        self.assertEqual(cur_del['status'], 'complete')
        self.assertTrue(cur_del['can_claim_complete'])
        self.assertEqual(cur_del['pending_targets'], [])

        # Verify DB object records removed
        with connection() as conn:
            obj_count = conn.execute("SELECT count(*) as c FROM objects WHERE video_id=%s", (video_id,)).fetchone()['c']
            self.assertEqual(obj_count, 0)


if __name__ == '__main__':
    unittest.main()
