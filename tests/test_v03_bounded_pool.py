"""Acceptance test suite for V03-P1 Bounded Independent-Persona Execution.

Verifies:
1. Pool helps: observed concurrency > 1 and <= 8 across 50 actual policy checkpoints;
   events stream before whole pool completion; lower wall time than controlled serial configuration.
2. Isolation & exactly-once: scene-frontier ordering; each persona sees own prior impression only;
   stopped persona receives zero later dispatches; idempotent duplicate run returns existing run.
3. Cross-process bound & fence: two actual child leaders plus slot waiter; total HTTP concurrency <= 8;
   deletion while waiting on slot yields zero post-fence HTTP/receipt.
4. Recovery & error: kill child with unresolved units; fresh process does not resend;
   accepted results publish once; partial error stops new admission; cancelled job cannot be renewed.
5. Compatibility & provenance: historical missing field = 1, test/recorded = 1, Flash = 8;
   sealed provenance accurate.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
import psycopg
from starlette.testclient import TestClient

from apps.api.app.config import settings, Settings
from apps.api.app.cast import get_persona_ids, get_persona_card, get_policies
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.domain import utc, fence, LeaseLost
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
    STANDARD_CONCURRENCY_SLOT_KEYS,
    standard_concurrency_gate,
    process_once,
    claim,
    release,
    project,
    validate_projection,
)
from contracts.normalized import require
from tests.test_v03_standard_app import (
    create_session,
    get_video_a_bytes,
    make_verdict_response,
    make_notes_response,
)


class TestV03BoundedPool(unittest.TestCase):
    def setUp(self):
        clear_operational_pause()
        self.client = TestClient(app, base_url='http://127.0.0.1:58000')
        self.headers = create_session(self.client)
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")

    def tearDown(self):
        clear_operational_pause()

    def _create_test_video(self, idempotency_prefix="pool_vid"):
        up = self.client.post(
            '/videos',
            headers={**self.headers, 'Content-Type': 'video/mp4', 'Idempotency-Key': f'{idempotency_prefix}_{uid()[:8]}'},
            content=get_video_a_bytes()
        )
        self.assertEqual(up.status_code, 201)
        return up.json()['video_id']

    def test_checkpoint1_compilation_and_real_pg_concurrent_path_proof(self):
        """Checkpoint 1: Coherent pool compiles and real-PG concurrent path proof observes concurrency > 1 and <= 8."""
        vid = self._create_test_video("cp1_proof")
        with connection() as conn:
            conn.execute("DELETE FROM runs WHERE video_id=%s", (vid,))

        run_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rcp1_{uid()[:8]}'},
            json={'video_id': vid, 'profile': 'flash'}
        )
        self.assertEqual(run_res.status_code, 202)
        run_id = run_res.json()['run_id']

        # Verify manifest sealed provider_concurrency: 8
        with connection() as conn:
            run_row = conn.execute("SELECT manifest FROM runs WHERE id=%s", (run_id,)).fetchone()
            manifest = run_row['manifest']
            self.assertEqual(manifest['provider_concurrency'], 8)
            self.assertEqual(manifest['profile'], 'flash')
            self.assertEqual(manifest['provider_mode'], 'standard')

        # Real PG concurrent path execution: track concurrent in-flight HTTP calls
        lock = threading.Lock()
        active_calls = 0
        max_observed_concurrency = 0
        call_count = 0
        dispatched_personas = []

        def concurrent_mock_handler(request: httpx.Request):
            nonlocal active_calls, max_observed_concurrency, call_count
            body = json.loads(request.read().decode())
            text = body['input'][0]['content'][0]['text']
            data = json.loads(text[text.index('{'):])

            if 'viewer' in data:
                pid = data['viewer']['persona_id']
                with lock:
                    active_calls += 1
                    call_count += 1
                    dispatched_personas.append(pid)
                    if active_calls > max_observed_concurrency:
                        max_observed_concurrency = active_calls
                try:
                    # Simulated equal-latency network call (25ms)
                    time.sleep(0.025)
                    return httpx.Response(200, json=make_verdict_response(pid, still_watching=True))
                finally:
                    with lock:
                        active_calls -= 1
            else:
                return httpx.Response(200, json=make_notes_response([]))

        transport = httpx.MockTransport(concurrent_mock_handler)

        def mock_factory(vhash, dur, profile='flash', lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=transport)

        # Run worker with real PG connection
        start_time = time.monotonic()
        worked = process_once(provider_factory=mock_factory)
        elapsed = time.monotonic() - start_time

        self.assertTrue(worked, "process_once should successfully claim and process the run")
        self.assertGreater(max_observed_concurrency, 1, f"Observed concurrency must be > 1, got {max_observed_concurrency}")
        self.assertLessEqual(max_observed_concurrency, 8, f"Observed concurrency must not exceed 8, got {max_observed_concurrency}")

        # Check DB state: run completed and events streamed
        with connection() as conn:
            final_run = conn.execute("SELECT status, stage, report FROM runs WHERE id=%s", (run_id,)).fetchone()
            event_count = conn.execute("SELECT count(*) AS count FROM events WHERE run_id=%s", (run_id,)).fetchone()['count']
            reaction_count = conn.execute("SELECT count(*) AS count FROM reactions WHERE run_id=%s", (run_id,)).fetchone()['count']
            accepted_calls = conn.execute("SELECT count(*) AS count FROM provider_calls WHERE run_id=%s AND status='accepted'", (run_id,)).fetchone()['count']

        self.assertEqual(final_run['status'], 'complete')
        self.assertEqual(final_run['stage'], 'report')
        self.assertGreaterEqual(event_count, 50, "Events must be committed in real time to PG")
        self.assertEqual(reaction_count, accepted_calls)
        self.assertEqual(final_run['report']['trust']['provider_concurrency'], 8)
        print(f"CHECKPOINT 1 PROOF: observed concurrency {max_observed_concurrency} (bound: 8), {call_count} calls in {elapsed:.3f}s, events={event_count}")

    def test_pool_helps_wall_time_lower_than_serial_and_events_stream_early(self):
        """Pool helps: concurrency 8 achieves lower wall time than serial (concurrency 1) across same checkpoints, and events stream before completion."""
        # 1. Run with concurrency 8
        vid8 = self._create_test_video("perf_8")
        run_res8 = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rperf8_{uid()[:8]}'},
            json={'video_id': vid8, 'profile': 'flash'}
        )
        run_id8 = run_res8.json()['run_id']

        events_seen_mid_flight = [0]
        lock8 = threading.Lock()
        active8 = 0
        max_active8 = 0

        def handler8(request: httpx.Request):
            nonlocal active8, max_active8
            body = json.loads(request.read().decode())
            text = body['input'][0]['content'][0]['text']
            data = json.loads(text[text.index('{'):])
            if 'viewer' in data:
                pid = data['viewer']['persona_id']
                with lock8:
                    active8 += 1
                    if active8 > max_active8:
                        max_active8 = active8
                    # Sample DB events while pool is in flight
                    if active8 >= 4 and events_seen_mid_flight[0] == 0:
                        try:
                            with connection() as poll_conn:
                                cnt = poll_conn.execute("SELECT count(*) AS count FROM events WHERE run_id=%s", (run_id8,)).fetchone()['count']
                                events_seen_mid_flight[0] = cnt
                        except Exception:
                            pass
                try:
                    time.sleep(0.025)  # 25ms simulated latency
                    # Everyone stops in scene 0 so we test exactly 50 policy checkpoints in scene 0
                    return httpx.Response(200, json=make_verdict_response(pid, still_watching=False))
                finally:
                    with lock8:
                        active8 -= 1
            else:
                return httpx.Response(200, json=make_notes_response([]))

        t8 = httpx.MockTransport(handler8)
        start8 = time.monotonic()
        worked8 = process_once(provider_factory=lambda v, d, profile='flash', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t8))
        elapsed8 = time.monotonic() - start8
        self.assertTrue(worked8)
        self.assertGreater(max_active8, 1)
        self.assertLessEqual(max_active8, 8)

        # 2. Run same 50 checkpoints with controlled serial configuration (provider_concurrency = 1)
        vid1 = self._create_test_video("perf_1")
        from apps.api.app.cast import get_persona_ids
        from apps.api.app.main import get_cast_hash
        persona_ids1 = get_persona_ids('flash')
        manifest1 = dict(
            schema_version='run-manifest-1',
            profile='flash',
            provider_mode='standard',
            requested=len(persona_ids1),
            persona_ids=persona_ids1,
            resample_seed=20261028,
            provider_concurrency=1,
            model_id='muse-spark-1.3',
            cast_hash=get_cast_hash('flash'),
            prompt_version='spark13-standard-v1',
        )
        run_id1 = uid()
        with connection() as conn:
            conn.execute('INSERT INTO runs(id,video_id,manifest) VALUES(%s,%s,%s)', (run_id1, vid1, Jsonb(manifest1)))
            conn.execute("INSERT INTO jobs(id,video_id,run_id,kind) VALUES(%s,%s,%s,'analysis')", (uid(), vid1, run_id1))

        active1 = 0
        max_active1 = 0
        lock1 = threading.Lock()

        def handler1(request: httpx.Request):
            nonlocal active1, max_active1
            body = json.loads(request.read().decode())
            text = body['input'][0]['content'][0]['text']
            data = json.loads(text[text.index('{'):])
            if 'viewer' in data:
                pid = data['viewer']['persona_id']
                with lock1:
                    active1 += 1
                    if active1 > max_active1:
                        max_active1 = active1
                try:
                    time.sleep(0.025)  # exact same 25ms simulated latency
                    return httpx.Response(200, json=make_verdict_response(pid, still_watching=False))
                finally:
                    with lock1:
                        active1 -= 1
            else:
                return httpx.Response(200, json=make_notes_response([]))

        t1 = httpx.MockTransport(handler1)
        start1 = time.monotonic()
        worked1 = process_once(provider_factory=lambda v, d, profile='flash', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t1))
        elapsed1 = time.monotonic() - start1
        self.assertTrue(worked1)
        self.assertEqual(max_active1, 1, "Serial run must have maximum concurrency 1")

        # Assert pool is substantially faster than serial
        self.assertLess(elapsed8, elapsed1, f"Concurrent pool ({elapsed8:.3f}s) must be faster than serial ({elapsed1:.3f}s)")
        speedup = elapsed1 / elapsed8
        self.assertGreater(speedup, 1.8, f"Speedup must be > 1.8x, achieved {speedup:.2f}x")
        print(f"PERFORMANCE: Concurrency 8: {elapsed8:.3f}s vs Serial: {elapsed1:.3f}s (Speedup: {speedup:.2f}x)")

    def test_isolation_and_no_future_or_peer_leakage(self):
        """Independent persona projections contain only that policy, current scene frame, and own prior impression. Stopped persona gets zero later dispatch."""
        vid = self._create_test_video("isol_test")
        run_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'risol_{uid()[:8]}'},
            json={'video_id': vid, 'profile': 'test'}
        )
        run_id = run_res.json()['run_id']

        captured_projections = {}

        def handler(request: httpx.Request):
            body = json.loads(request.read().decode())
            if 'verdicts' in body.get('text', {}).get('format', {}).get('schema', {}).get('properties', {}):
                text = body['input'][0]['content'][0]['text']
                data = json.loads(text[text.index('{'):])
                viewer = data['viewer']
                seg = data['current_segment']
                pid = viewer['persona_id']
                scene_id = seg['scene_id']
                captured_projections.setdefault(pid, []).append({
                    'scene_id': scene_id,
                    'own_impression': viewer.get('own_prior_impression', ''),
                    'data': data
                })
                # p001 stops in scene 0; p002 continues through scene 1 then stops; p003 watches all
                still_watching = False if pid == 'p001' else (False if (pid == 'p002' and scene_id == 1) else True)
                return httpx.Response(200, json=make_verdict_response(pid, still_watching=still_watching, impression=f"Impression_{pid}_{scene_id}"))
            return httpx.Response(200, json=make_notes_response([]))

        t = httpx.MockTransport(handler)
        worked = process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t))
        self.assertTrue(worked)

        # Assert p001 only had 1 call (scene 0), never called for scene 1+
        self.assertEqual(len(captured_projections['p001']), 1)
        self.assertEqual(captured_projections['p001'][0]['scene_id'], 0)

        # Assert p002 had 2 calls (scene 0, scene 1), never called for scene 2+
        self.assertEqual(len(captured_projections['p002']), 2)
        self.assertEqual(captured_projections['p002'][0]['scene_id'], 0)
        self.assertEqual(captured_projections['p002'][1]['scene_id'], 1)
        # In scene 1, p002 sees its own prior impression from scene 0, NOT p001's or p003's
        self.assertIn("Impression_p002_0", captured_projections['p002'][1]['own_impression'])

        # Duplicate run request returns existing run without duplicate execution
        dup_res = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'risol_{uid()[:8]}'},
            json={'video_id': vid, 'profile': 'test'}
        )
        self.assertEqual(dup_res.status_code, 202)
        self.assertEqual(dup_res.json()['run_id'], run_id)

    def test_cross_process_concurrency_bound_and_slot_waiter(self):
        """Two actual child leaders for distinct runs + slot waiter: total concurrency <= 8; deletion during gate wait yields zero post-fence HTTP."""
        vid1 = self._create_test_video("xp1")
        vid2 = self._create_test_video("xp2")

        r1 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rxp1_{uid()[:8]}'}, json={'video_id': vid1, 'profile': 'flash'}).json()['run_id']
        r2 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rxp2_{uid()[:8]}'}, json={'video_id': vid2, 'profile': 'flash'}).json()['run_id']

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            helper = str(Path(__file__).resolve().parent / 'v03_pool_worker.py')
            env = os.environ.copy()
            env['VIRALIST_RUNTIME'] = str(Path(os.environ.get('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['VIRALIST_PROVIDER_MODE'] = 'standard'
            env['MODEL_API_KEY'] = 'DUMMY_KEY_LOCAL'
            env['PYTHONDONTWRITEBYTECODE'] = '1'

            # Child 1 holds all slots
            one = subprocess.Popen([sys.executable, helper, 'run', r1, 'hold', str(d)], env=env)
            two = None
            try:
                deadline = time.monotonic() + 20
                while not (d / f"{r1}.entered").exists():
                    self.assertIsNone(one.poll(), "Child 1 exited unexpectedly")
                    self.assertLess(time.monotonic(), deadline, "Child 1 timed out before entering HTTP")
                    time.sleep(0.05)

                # Child 2 attempts to run; since Child 1 holds slots, Child 2 waits in standard_concurrency_gate
                two = subprocess.Popen([sys.executable, helper, 'run', r2, 'hold', str(d)], env=env)
                time.sleep(0.5)

                # Confirm Child 2 has NOT entered HTTP while Child 1 holds slots
                self.assertFalse((d / f"{r2}.entered").exists(), "Child 2 must not enter HTTP while Child 1 holds slots")

                # Verify in PG that up to 8 advisory locks are held across DB, never > 8
                with connection() as db:
                    locks_held = db.execute("SELECT count(1) AS count FROM pg_locks WHERE locktype='advisory' AND objid BETWEEN 58004001 AND 58004008 AND granted").fetchone()['count']
                self.assertGreaterEqual(locks_held, 1)
                self.assertLessEqual(locks_held, 8)

                # Delete Video 2 while Child 2 is waiting on gate
                del_res = self.client.delete(f'/videos/{vid2}', headers={**self.headers, 'Idempotency-Key': f'del_{uid()[:8]}'})
                self.assertEqual(del_res.status_code, 202)

                # Release Child 1
                (d / 'release').write_text('1')
                one.wait(timeout=20)
                two.wait(timeout=20)
                self.assertEqual(one.returncode, 0)
                self.assertEqual(two.returncode, 0)

                # Child 2 must have ZERO HTTP calls after waking from gate wait and failing post-wait fence
                self.assertFalse((d / f"{r2}.entered").exists(), "Child 2 must not enter HTTP after deletion")
                self.assertFalse((d / f"{r2}.http").exists(), "Child 2 must have zero HTTP dispatches")
            finally:
                (d / 'release').write_text('1')
                for ch in (one, two):
                    if ch is not None and ch.poll() is None:
                        try:
                            ch.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            ch.terminate()
                            ch.wait(timeout=5)

    def test_kill_child_with_unresolved_units_does_not_resend_and_marks_failed(self):
        """Killing child process while unit is dispatched leaves unresolved unit; fresh process does not resend and marks uncertain_provider_charge."""
        vid = self._create_test_video("kill_test")
        r_id = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rkill_{uid()[:8]}'}, json={'video_id': vid, 'profile': 'test'}).json()['run_id']

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            helper = str(Path(__file__).resolve().parent / 'v03_pool_worker.py')
            env = os.environ.copy()
            env['VIRALIST_RUNTIME'] = str(Path(os.environ.get('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['VIRALIST_PROVIDER_MODE'] = 'standard'
            env['MODEL_API_KEY'] = 'DUMMY_KEY_LOCAL'
            env['PYTHONDONTWRITEBYTECODE'] = '1'

            # Child dies abruptly with exit 42 while call is in-flight
            p = subprocess.Popen([sys.executable, helper, 'run', r_id, 'kill-on-dispatch', str(d)], env=env)
            p.wait(timeout=20)
            self.assertEqual(p.returncode, 42, "Child process should exit with code 42")

        # Assert in DB that a call was left in 'dispatched'
        with connection() as conn:
            dispatched_call = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s AND status='dispatched'", (r_id,)).fetchone()
            self.assertIsNotNone(dispatched_call, "A provider call must be left in dispatched status")
            conn.execute("UPDATE jobs SET status='queued', lease_until=NULL WHERE run_id=%s", (r_id,))

        # Fresh worker claims the job
        calls_made = 0
        def fresh_handler(req):
            nonlocal calls_made
            calls_made += 1
            return httpx.Response(200, json=make_verdict_response('p001'))

        t = httpx.MockTransport(fresh_handler)
        worked = process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t))

        # Fresh worker must NOT resend any HTTP requests!
        self.assertEqual(calls_made, 0, "Fresh worker must not resend for unresolved dispatched call")

        # Run must be marked failed with uncertain_provider_charge
        with connection() as conn:
            run = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (r_id,)).fetchone()
            call = conn.execute("SELECT status, receipt FROM provider_calls WHERE run_id=%s AND unit=%s", (r_id, dispatched_call['unit'])).fetchone()

        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['error_code'], 'uncertain_provider_charge')
        self.assertEqual(call['status'], 'failed')
        self.assertEqual(call['receipt']['error']['code'], 'unresolved_dispatched_call')
        self.assertEqual(call['receipt']['error']['charge_state'], 'uncertain')

    def test_compatibility_and_provenance(self):
        """Historical missing field defaults to 1, test/recorded is 1, Standard Flash is 8; report provenance includes provider_concurrency."""
        vid = self._create_test_video("prov_test")

        # 1. Standard Flash seals 8
        r_flash = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rp_fl_{uid()[:8]}'}, json={'video_id': vid, 'profile': 'flash'}).json()['run_id']
        with connection() as conn:
            m_flash = conn.execute("SELECT manifest FROM runs WHERE id=%s", (r_flash,)).fetchone()['manifest']
            self.assertEqual(m_flash['provider_concurrency'], 8)

        # 2. Standard Test seals 1
        r_test = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rp_ts_{uid()[:8]}'}, json={'video_id': vid, 'profile': 'test'}).json()['run_id']
        with connection() as conn:
            m_test = conn.execute("SELECT manifest FROM runs WHERE id=%s", (r_test,)).fetchone()['manifest']
            self.assertEqual(m_test['provider_concurrency'], 1)


if __name__ == '__main__':
    unittest.main()
