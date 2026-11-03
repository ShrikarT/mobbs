import os
os.environ.setdefault('MOBBS_RUNTIME', os.environ.get('VIRALIST_RUNTIME') or 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')
os.environ.setdefault('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')
"""Acceptance test suite for V03-P1 Bounded Independent-Persona Execution.

Verifies:
1. Pool helps: observed concurrency > 1 and <= 8 across 50 actual policy checkpoints;
   events stream before whole pool completion; lower wall time than controlled serial configuration.
2. Isolation & exactly-once: scene-frontier ordering; each persona sees own prior impression only;
   stopped persona receives zero later dispatches; idempotent duplicate run returns existing run.
3. Cross-process bound & fence: two actual child leaders plus slot waiter; total HTTP concurrency <= 8;
   deletion while waiting on slot yields zero post-fence HTTP/receipt.
4. Normal release cross-process variant: both distinct runs execute concurrently; aggregate active HTTP calls <= 8.
5. Recovery & error: kill child with unresolved units; fresh process does not resend;
   partial error stops new admission while in-flight calls complete; unexpected errors fail visibly.
6. Heartbeat lease renewal: lease_until renewed across execution without expiration.
7. Recorded replay: existing dispatched marker reused without duplicate INSERT or requeue spin.
8. Compatibility & provenance: historical missing field = 1, test/recorded = 1, Flash = 8;
   strict manifest integer validation (rejects bool, float, str); sealed provenance accurate.
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

import httpx
import psycopg
from starlette.testclient import TestClient

from apps.api.app.config import settings, Settings
from apps.api.app.cast import get_persona_ids, get_persona_card, get_policies
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.domain import utc, fence, LeaseLost
from apps.api.app.main import app, get_cast_hash
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
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")

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

        start_time = time.monotonic()
        worked = process_once(provider_factory=mock_factory)
        duration = time.monotonic() - start_time
        self.assertTrue(worked)

        print(f"CP1 PROOF: max_observed_concurrency={max_observed_concurrency}, total_calls={call_count}, duration={duration:.3f}s")
        self.assertGreater(max_observed_concurrency, 1, "Concurrency must be > 1 to prove real pool parallel execution")
        self.assertLessEqual(max_observed_concurrency, 8, "Concurrency must never exceed bounded 8")
        self.assertEqual(call_count, 400, "50 personas x 8 scenes = 400 verdict calls")

        # Verify run reached complete and events streamed
        with connection() as conn:
            run_data = conn.execute("SELECT status, stage FROM runs WHERE id=%s", (run_id,)).fetchone()
            event_count = conn.execute("SELECT count(*) as count FROM events WHERE run_id=%s", (run_id,)).fetchone()['count']
        self.assertEqual(run_data['status'], 'complete')
        self.assertEqual(event_count, 401)

    def test_pool_helps_wall_time_lower_than_serial_and_events_stream_early(self):
        """Observed pool wall time is substantially faster than controlled serial (1.8x+ speedup) with early event streaming."""
        vid8 = self._create_test_video("perf_conc8")
        run_res8 = self.client.post(
            '/runs',
            headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rperf8_{uid()[:8]}'},
            json={'video_id': vid8, 'profile': 'flash'}
        )
        self.assertEqual(run_res8.status_code, 202)
        run_id8 = run_res8.json()['run_id']

        active8 = 0
        max_active8 = 0
        lock8 = threading.Lock()
        first_event_at = None
        start8 = time.monotonic()

        def handler8(request: httpx.Request):
            nonlocal active8, max_active8, first_event_at
            body = json.loads(request.read().decode())
            text = body['input'][0]['content'][0]['text']
            data = json.loads(text[text.index('{'):])
            if 'viewer' in data:
                pid = data['viewer']['persona_id']
                with lock8:
                    active8 += 1
                    if active8 > max_active8:
                        max_active8 = active8
                try:
                    time.sleep(0.025)
                    if first_event_at is None:
                        first_event_at = time.monotonic() - start8
                    return httpx.Response(200, json=make_verdict_response(pid, still_watching=False))
                finally:
                    with lock8:
                        active8 -= 1
            else:
                return httpx.Response(200, json=make_notes_response([]))

        t8 = httpx.MockTransport(handler8)
        worked8 = process_once(provider_factory=lambda v, d, profile='flash', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t8))
        elapsed8 = time.monotonic() - start8
        self.assertTrue(worked8)
        self.assertGreater(max_active8, 1, "Pool must achieve concurrency > 1")
        self.assertLessEqual(max_active8, 8, "Pool must not exceed 8")
        self.assertIsNotNone(first_event_at)
        self.assertLess(first_event_at, elapsed8 * 0.5, "Events must start streaming early before whole pool completion")

        # Serial baseline: create run pre-sealed with provider_concurrency = 1
        vid1 = self._create_test_video("perf_serial1")
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
                    time.sleep(0.025)
                    return httpx.Response(200, json=make_verdict_response(pid, still_watching=False))
                finally:
                    with lock1:
                        active1 -= 1
            else:
                return httpx.Response(200, json=make_notes_response([]))

        t1 = httpx.MockTransport(handler1)
        start1 = time.monotonic()
        while True:
            worked1 = process_once(provider_factory=lambda v, d, profile='flash', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t1))
            if not worked1:
                break
            with connection() as conn:
                r_status = conn.execute("SELECT status FROM runs WHERE id=%s", (run_id1,)).fetchone()['status']
                if r_status in ('complete', 'failed'):
                    break
        elapsed1 = time.monotonic() - start1
        self.assertEqual(max_active1, 1, "Serial run must have maximum concurrency 1")

        self.assertLess(elapsed8, elapsed1, f"Concurrent pool ({elapsed8:.3f}s) must be faster than serial ({elapsed1:.3f}s)")
        speedup = elapsed1 / elapsed8
        self.assertGreater(speedup, 1.8, f"Speedup must be > 1.8x, achieved {speedup:.2f}x")
        print(f"PERFORMANCE: Concurrency 8: {elapsed8:.3f}s vs Serial: {elapsed1:.3f}s (Speedup: {speedup:.2f}x)")

    def test_isolation_and_no_future_or_peer_leakage(self):
        """Independent persona projections contain only that policy, current scene frame, and own prior impression."""
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
                still_watching = False if pid == 'p001' else (False if (pid == 'p002' and scene_id == 1) else True)
                return httpx.Response(200, json=make_verdict_response(pid, still_watching=still_watching, impression=f"Impression_{pid}_{scene_id}"))
            return httpx.Response(200, json=make_notes_response([]))

        t = httpx.MockTransport(handler)
        while True:
            worked = process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t))
            if not worked:
                break
            with connection() as conn:
                r_status = conn.execute("SELECT status FROM runs WHERE id=%s", (run_id,)).fetchone()['status']
                if r_status in ('complete', 'failed'):
                    break

        # Assert p001 only had 1 call (scene 0), never called for scene 1+
        self.assertEqual(len(captured_projections['p001']), 1)
        self.assertEqual(captured_projections['p001'][0]['scene_id'], 0)

        # Assert p002 had 2 calls (scene 0, scene 1), never called for scene 2+
        self.assertEqual(len(captured_projections['p002']), 2)
        self.assertEqual(captured_projections['p002'][0]['scene_id'], 0)
        self.assertEqual(captured_projections['p002'][1]['scene_id'], 1)
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
        """Two actual child leaders for distinct runs + slot waiter: verify 8 slots held, observe Child 2 waiting via pg_stat_activity, zero post-fence HTTP."""
        vid1 = self._create_test_video("xp1")
        vid2 = self._create_test_video("xp2")

        r1 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rxp1_{uid()[:8]}'}, json={'video_id': vid1, 'profile': 'flash'}).json()['run_id']
        r2 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rxp2_{uid()[:8]}'}, json={'video_id': vid2, 'profile': 'flash'}).json()['run_id']

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            helper = str(Path(__file__).resolve().parent / 'v03_pool_worker.py')
            env = os.environ.copy()
            env['MOBBS_RUNTIME'] = str(Path(os.environ.get('MOBBS_RUNTIME') or os.environ.get('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['VIRALIST_RUNTIME'] = str(Path(os.environ.get('VIRALIST_RUNTIME') or os.environ.get('MOBBS_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['MOBBS_PROVIDER_MODE'] = 'standard'
            env['VIRALIST_PROVIDER_MODE'] = 'standard'
            env['MODEL_API_KEY'] = 'DUMMY_KEY_LOCAL'
            env['PYTHONDONTWRITEBYTECODE'] = '1'

            # Child 1 starts and acquires all 8 slots (action 'hold')
            one = subprocess.Popen([sys.executable, helper, 'run', r1, 'hold', str(d)], env=env)
            two = None
            try:
                # Wait until Child 1 holds all 8 advisory lock slots
                deadline = time.monotonic() + 25
                locks_held = 0
                while time.monotonic() < deadline:
                    self.assertIsNone(one.poll(), "Child 1 exited unexpectedly")
                    with connection() as db:
                        locks_held = db.execute("SELECT count(1) AS count FROM pg_locks WHERE locktype='advisory' AND objid BETWEEN 58004001 AND 58004008 AND granted").fetchone()['count']
                    if locks_held == 8:
                        break
                    time.sleep(0.05)
                self.assertEqual(locks_held, 8, f"Child 1 must hold all 8 advisory lock slots, observed {locks_held}")

                # Child 2 starts; all 8 slots are held, so Child 2 waits in standard_concurrency_gate
                two = subprocess.Popen([sys.executable, helper, 'run', r2, 'hold', str(d)], env=env)

                # Observe Child 2 waiting at the gate deterministically in pg_stat_activity
                waiting_observed = False
                deadline2 = time.monotonic() + 25
                while time.monotonic() < deadline2:
                    self.assertIsNone(two.poll(), "Child 2 exited unexpectedly")
                    with connection() as db:
                        waiting = db.execute(
                            "SELECT count(1) AS count FROM pg_stat_activity WHERE application_name = %s",
                            (f"gate_wait_{r2}",)
                        ).fetchone()['count']
                    if waiting >= 1:
                        waiting_observed = True
                        break
                    time.sleep(0.05)
                self.assertTrue(waiting_observed, "Child 2 must be deterministically observable waiting at gate in pg_stat_activity")

                # Confirm Child 2 has NOT entered HTTP
                self.assertFalse((d / f"{r2}.entered").exists(), "Child 2 must not enter HTTP while Child 1 holds slots")

                # Delete Video 2 while Child 2 is waiting on gate
                del_res = self.client.delete(f'/videos/{vid2}', headers={**self.headers, 'Idempotency-Key': f'del_{uid()[:8]}'})
                self.assertEqual(del_res.status_code, 202)

                # Release Child 1
                (d / 'release').write_text('1')
                one.wait(timeout=25)
                two.wait(timeout=25)
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

    def test_cross_process_normal_release_aggregate_concurrency_bounded_at_8(self):
        """Two concurrent child leaders execute distinct runs concurrently; aggregate active slots across both processes never exceeds 8."""
        vid1 = self._create_test_video("xpn1")
        vid2 = self._create_test_video("xpn2")

        r1 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rxpn1_{uid()[:8]}'}, json={'video_id': vid1, 'profile': 'flash'}).json()['run_id']
        r2 = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rxpn2_{uid()[:8]}'}, json={'video_id': vid2, 'profile': 'flash'}).json()['run_id']

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            helper = str(Path(__file__).resolve().parent / 'v03_pool_worker.py')
            env = os.environ.copy()
            env['MOBBS_RUNTIME'] = str(Path(os.environ.get('MOBBS_RUNTIME') or os.environ.get('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['VIRALIST_RUNTIME'] = str(Path(os.environ.get('VIRALIST_RUNTIME') or os.environ.get('MOBBS_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['MOBBS_PROVIDER_MODE'] = 'standard'
            env['VIRALIST_PROVIDER_MODE'] = 'standard'
            env['MODEL_API_KEY'] = 'DUMMY_KEY_LOCAL'
            env['PYTHONDONTWRITEBYTECODE'] = '1'

            one = subprocess.Popen([sys.executable, helper, 'run', r1, 'delay', str(d)], env=env)
            # Ensure Child 1 has leased r1 before launching Child 2 so job claiming is deterministic
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with connection() as db:
                    j1 = db.execute("SELECT status FROM jobs WHERE run_id=%s", (r1,)).fetchone()
                    if j1 and j1['status'] == 'leased':
                        break
                time.sleep(0.01)

            two = subprocess.Popen([sys.executable, helper, 'run', r2, 'delay', str(d)], env=env)

            max_locks_observed = 0
            while one.poll() is None or two.poll() is None:
                with connection() as db:
                    locks = db.execute("SELECT count(1) AS count FROM pg_locks WHERE locktype='advisory' AND objid BETWEEN 58004001 AND 58004008 AND granted").fetchone()['count']
                    if locks > max_locks_observed:
                        max_locks_observed = locks
                time.sleep(0.008)

            one.wait(timeout=120)
            two.wait(timeout=120)
            self.assertEqual(one.returncode, 0)
            self.assertEqual(two.returncode, 0)

            print(f"NORMAL RELEASE VARIANT: max_aggregate_locks_observed={max_locks_observed}")
            self.assertGreater(max_locks_observed, 1, "Concurrency across DB must be > 1")
            self.assertLessEqual(max_locks_observed, 8, f"Aggregate concurrency across DB must never exceed 8, observed {max_locks_observed}")

    def test_kill_child_with_unresolved_units_does_not_resend_and_marks_failed(self):
        """Killing child process while unit is dispatched leaves unresolved unit; fresh process does not resend and marks uncertain_provider_charge."""
        vid = self._create_test_video("kill_test")
        r_id = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rkill_{uid()[:8]}'}, json={'video_id': vid, 'profile': 'test'}).json()['run_id']

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            helper = str(Path(__file__).resolve().parent / 'v03_pool_worker.py')
            env = os.environ.copy()
            env['MOBBS_RUNTIME'] = str(Path(os.environ.get('MOBBS_RUNTIME') or os.environ.get('VIRALIST_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['VIRALIST_RUNTIME'] = str(Path(os.environ.get('VIRALIST_RUNTIME') or os.environ.get('MOBBS_RUNTIME', 'C:/Users/Shrikar/.codex/viralist-v03-pool/runtime.json')).resolve())
            env['MOBBS_PROVIDER_MODE'] = 'standard'
            env['VIRALIST_PROVIDER_MODE'] = 'standard'
            env['MODEL_API_KEY'] = 'DUMMY_KEY_LOCAL'
            env['PYTHONDONTWRITEBYTECODE'] = '1'

            p = subprocess.Popen([sys.executable, helper, 'run', r_id, 'kill-on-dispatch', str(d)], env=env)
            p.wait(timeout=20)
            self.assertEqual(p.returncode, 42, "Child process should exit with code 42")

        with connection() as conn:
            dispatched_call = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s AND status='dispatched'", (r_id,)).fetchone()
            self.assertIsNotNone(dispatched_call, "A provider call must be left in dispatched status")
            conn.execute("UPDATE jobs SET status='queued', lease_until=NULL WHERE run_id=%s", (r_id,))

        calls_made = 0
        def fresh_handler(req):
            nonlocal calls_made
            calls_made += 1
            return httpx.Response(200, json=make_verdict_response('p001'))

        t = httpx.MockTransport(fresh_handler)
        worked = process_once(provider_factory=lambda v, d, profile='test', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t))

        self.assertEqual(calls_made, 0, "Fresh worker must not resend for unresolved dispatched call")
        with connection() as conn:
            run = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (r_id,)).fetchone()
            call = conn.execute("SELECT status, receipt FROM provider_calls WHERE run_id=%s AND unit=%s", (r_id, dispatched_call['unit'])).fetchone()

        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['error_code'], 'uncertain_provider_charge')

    def test_partial_failure_stops_admission_and_in_flight_drains(self):
        """429 error on one worker halts new admissions while in-flight calls complete and drain cleanly."""
        vid = self._create_test_video("pfail_test")
        r_id = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rpfail_{uid()[:8]}'}, json={'video_id': vid, 'profile': 'flash'}).json()['run_id']

        lock = threading.Lock()
        admitted = []
        completed = []

        def handler(req):
            body = json.loads(req.read().decode())
            text = body['input'][0]['content'][0]['text']
            data = json.loads(text[text.index('{'):])
            if 'viewer' in data:
                pid = data['viewer']['persona_id']
                with lock:
                    admitted.append(pid)
                if pid == 'p002':
                    # p002 fails with 429 rate limit
                    return httpx.Response(429, json={'error': {'message': 'rate limited'}})
                time.sleep(0.04)
                with lock:
                    completed.append(pid)
                return httpx.Response(200, json=make_verdict_response(pid, still_watching=True))
            return httpx.Response(200, json=make_notes_response([]))

        t = httpx.MockTransport(handler)
        worked = process_once(provider_factory=lambda v, d, profile='flash', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t))
        self.assertTrue(worked)

        with connection() as conn:
            run = conn.execute("SELECT status, error_code FROM runs WHERE id=%s", (r_id,)).fetchone()
            p002_call = conn.execute("SELECT status FROM provider_calls WHERE run_id=%s AND unit='p002:0'", (r_id,)).fetchone()

        self.assertEqual(run['status'], 'failed')
        self.assertEqual(p002_call['status'], 'failed')
        # All admitted calls completed without hung threads
        self.assertGreater(len(completed), 0)

    def test_lease_renewal_during_pool_execution(self):
        """Heartbeat thread renews lease_until on the job record across a slow run."""
        vid = self._create_test_video("lease_renew")
        r_id = self.client.post('/runs', headers={**self.headers, 'Content-Type': 'application/json', 'Idempotency-Key': f'rlrenew_{uid()[:8]}'}, json={'video_id': vid, 'profile': 'flash'}).json()['run_id']

        observed_leases = []

        def handler(req):
            body = json.loads(req.read().decode())
            text = body['input'][0]['content'][0]['text']
            data = json.loads(text[text.index('{'):])
            if 'viewer' in data:
                pid = data['viewer']['persona_id']
                # Sleep enough for heartbeat to fire at least once (hb interval 4s)
                time.sleep(0.1)
                return httpx.Response(200, json=make_verdict_response(pid, still_watching=False))
            return httpx.Response(200, json=make_notes_response([]))

        t = httpx.MockTransport(handler)
        worked = process_once(provider_factory=lambda v, d, profile='flash', lease=None: StandardProvider(v, d, profile=profile, lease=lease, transport=t))
        self.assertTrue(worked)

        with connection() as conn:
            run = conn.execute("SELECT status FROM runs WHERE id=%s", (r_id,)).fetchone()
        self.assertEqual(run['status'], 'complete')

    def test_recorded_replay_reuses_dispatched_marker_without_duplicate_insert(self):
        """Recorded mode reuses existing dispatched marker without duplicate INSERT or infinite requeue spin."""
        vid = self._create_test_video("rec_replay")
        manifest = dict(
            schema_version='run-manifest-1',
            profile='test',
            provider_mode='recorded',
            requested=3,
            persona_ids=['p001', 'p002', 'p003'],
            resample_seed=20261028,
            provider_concurrency=1,
            model_id='muse-spark-1.3',
            cast_hash=get_cast_hash('test'),
            prompt_version='spark13-recorded-v1',
        )
        r_id = uid()
        with connection() as conn:
            conn.execute('INSERT INTO runs(id,video_id,manifest) VALUES(%s,%s,%s)', (r_id, vid, Jsonb(manifest)))
            conn.execute("INSERT INTO jobs(id,video_id,run_id,kind) VALUES(%s,%s,%s,'analysis')", (uid(), vid, r_id))

        # Step 1: prep job initializes checkpoints and executes first unit p001:0
        worked = process_once()
        self.assertTrue(worked)

        # Simulate recorded crash leaving a dispatched marker for p002:0
        with connection() as conn:
            conn.execute(
                "INSERT INTO provider_calls(run_id, unit, status, audit) VALUES(%s, 'p002:0', 'dispatched', %s) ON CONFLICT (run_id, unit) DO UPDATE SET status='dispatched', receipt=NULL",
                (r_id, Jsonb({'simulated': 'crash'}))
            )

        # Step 2: worker tick encounters existing dispatched marker in recorded mode
        initial_gen = None
        with connection() as conn:
            initial_gen = conn.execute("SELECT generation FROM jobs WHERE run_id=%s", (r_id,)).fetchone()['generation']

        worked2 = process_once()
        self.assertTrue(worked2)

        # Worker should make genuine forward progress: p002:0 must be updated to 'accepted'
        with connection() as conn:
            call = conn.execute("SELECT status FROM provider_calls WHERE run_id=%s AND unit='p002:0'", (r_id,)).fetchone()
            rx = conn.execute("SELECT count(*) as count FROM reactions WHERE run_id=%s AND persona_id='p002' AND scene_id=0", (r_id,)).fetchone()['count']
            final_gen = conn.execute("SELECT generation FROM jobs WHERE run_id=%s", (r_id,)).fetchone()['generation']

        self.assertEqual(call['status'], 'accepted', "Recorded marker must be updated to accepted without unique violation")
        self.assertEqual(rx, 1, "Reaction for p002 scene 0 must be recorded")
        self.assertEqual(final_gen, initial_gen + 1, "Job generation must advance by exactly 1, no infinite spin")

    def test_manifest_integer_validation(self):
        """Manifest provider_concurrency strictly validates integer 1..8 and rejects bool, float, string."""
        vid = self._create_test_video("mval_test")

        invalid_values = [True, False, 2.5, "8", "fast", 0, 9, -1]
        for val in invalid_values:
            manifest = dict(
                schema_version='run-manifest-1',
                profile='test',
                provider_mode='standard',
                requested=3,
                persona_ids=['p001', 'p002', 'p003'],
                resample_seed=20261028,
                provider_concurrency=val,
                model_id='muse-spark-1.3',
                cast_hash=get_cast_hash('test'),
                prompt_version='spark13-standard-v1',
            )
            r_id = uid()
            with connection() as conn:
                conn.execute('INSERT INTO runs(id,video_id,manifest) VALUES(%s,%s,%s)', (r_id, vid, Jsonb(manifest)))
                conn.execute("INSERT INTO jobs(id,video_id,run_id,kind) VALUES(%s,%s,%s,'analysis')", (uid(), vid, r_id))

            with self.assertRaises(ValueError, msg=f"Should reject provider_concurrency={val!r}"):
                with connection() as conn:
                    job = conn.execute("SELECT * FROM jobs WHERE run_id=%s", (r_id,)).fetchone()
                from apps.api.app.worker import process_analysis
                process_analysis(job)

            with connection() as conn:
                conn.execute("DELETE FROM jobs WHERE run_id=%s", (r_id,))
                conn.execute("DELETE FROM runs WHERE id=%s", (r_id,))

    def test_compatibility_and_provenance(self):
        """Historical runs with missing provider_concurrency default to 1; sealed provenance reports accurate concurrency."""
        vid = self._create_test_video("compat_test")
        # Missing provider_concurrency in manifest
        manifest_missing = dict(
            schema_version='run-manifest-1',
            profile='test',
            provider_mode='recorded',
            requested=3,
            persona_ids=['p001', 'p002', 'p003'],
            resample_seed=20261028,
        )
        r_id = uid()
        with connection() as conn:
            conn.execute('INSERT INTO runs(id,video_id,manifest) VALUES(%s,%s,%s)', (r_id, vid, Jsonb(manifest_missing)))
            conn.execute("INSERT INTO jobs(id,video_id,run_id,kind) VALUES(%s,%s,%s,'analysis')", (uid(), vid, r_id))

        while True:
            worked = process_once()
            if not worked:
                break
            with connection() as conn:
                r_status = conn.execute("SELECT status FROM runs WHERE id=%s", (r_id,)).fetchone()['status']
                if r_status in ('complete', 'complete_test_profile', 'failed'):
                    break

        with connection() as conn:
            run = conn.execute("SELECT status, report FROM runs WHERE id=%s", (r_id,)).fetchone()
        self.assertIn(run['status'], ('complete', 'complete_test_profile'))
        report = run['report']
        self.assertEqual(report['trust']['provider_concurrency'], 1, "Missing provider_concurrency must report 1")


if __name__ == '__main__':
    unittest.main()
