"""Focused regression and verification test suite for V03-RUNTIME-INCOMPLETE.
Covers:
1. StandardProvider adapter handling of HTTP 200 status=incomplete with reason=max_output_tokens.
   Preservation of response_id, request_id, allowlisted incomplete_reason, canonical numeric usage,
   cost estimate, and request output limit context through adapter and sanitize_error_receipt.
2. Bounded response headroom of 4096 tokens on outbound HTTP bodies for both verdict and notes.
3. Worker per-persona failure isolation for confirmed max_output_tokens:
   persona marked failed, no subsequent scene dispatches, independent personas continue,
   and honest incomplete report generated with failed persona exclusion / effective denominator.
4. Conservative failure for malformed usage, unknown incomplete reasons, and ambiguous transport.
5. All-failed behavior resulting in honest failed report/run.
"""
import copy
import json
import os
import unittest
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import httpx
import psycopg
from starlette.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.config import settings
from apps.api.app.db import connection, uid, Jsonb
from apps.api.app.providers import (
    StandardProvider,
    ProviderUnavailable,
    digest,
)
from apps.api.app.standard_provider import (
    compute_cost_usd,
    sanitize_usage,
    MODEL_ID,
    PRICING_VERSION,
)
from apps.api.app.storage import Storage
from apps.api.app.worker import (
    sanitize_error_receipt,
    process_once,
    clear_operational_pause,
)
from contracts.normalized import require
from tests.test_v03_standard_app import get_video_a_bytes


def create_test_session(client):
    origin = settings().origin
    host = urlparse(origin).netloc
    res = client.post('/sessions', headers={'Host': host, 'Origin': origin})
    require(res.status_code == 201, f'failed to create session: {res.status_code}')
    csrf = res.json()['csrf']
    return {
        'Host': host,
        'Origin': origin,
        'X-CSRF-Token': csrf,
    }


def make_incomplete_fixture(
    response_id="resp_inc_test_001",
    reason="max_output_tokens",
    input_tokens=100,
    output_tokens=1200,
    cached_tokens=0,
    reasoning_tokens=1200,
):
    return {
        "id": response_id,
        "model": MODEL_ID,
        "status": "incomplete",
        "incomplete_details": {"reason": reason},
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_tokens_details": {"cached_tokens": cached_tokens},
            "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
        },
        "output": [],
    }


def make_verdict_payload(persona_id, still_watching=True, reason="Looks great", impression="Good start"):
    return {
        "id": f"resp_{uid()[:12]}",
        "model": MODEL_ID,
        "status": "completed",
        "usage": {
            "input_tokens": 150,
            "output_tokens": 80,
            "total_tokens": 230,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 30},
        },
        "output": [
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
                                    "actions": ["save"],
                                }
                            ]
                        }),
                    }
                ],
            }
        ],
    }


class TestV03IncompleteRegression(unittest.TestCase):
    def setUp(self):
        clear_operational_pause()
        self.client = TestClient(app, base_url=settings().origin)
        self.headers = create_test_session(self.client)
        self.storage = Storage()
        self.dummy_frame_key = f"test_frame_{uid()[:8]}.jpg"
        self.dummy_jpeg_bytes = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
            b"\xff\xdb\x00C\x00\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01"
            b"\x22\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00"
            b"\xbf\x00\xff\xd9"
        )
        self.storage.put(self.dummy_frame_key, self.dummy_jpeg_bytes, "image/jpeg")
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")

    def tearDown(self):
        clear_operational_pause()
        with connection() as conn:
            conn.execute("DELETE FROM jobs WHERE status IN ('queued', 'leased')")

    def _create_test_run(self, profile="test", concurrency=None):
        up = self.client.post(
            "/videos",
            headers={**self.headers, "Content-Type": "video/mp4", "Idempotency-Key": f"inc_vid_{uid()[:8]}"},
            content=get_video_a_bytes(),
        )
        self.assertEqual(up.status_code, 201)
        vid = up.json()["video_id"]

        run_res = self.client.post(
            "/runs",
            headers={**self.headers, "Content-Type": "application/json", "Idempotency-Key": f"inc_run_{uid()[:8]}"},
            json={"video_id": vid, "profile": profile},
        )
        self.assertEqual(run_res.status_code, 202)
        run_id = run_res.json()["run_id"]
        return vid, run_id

    def test_repro_criterion_1_adapter_incomplete_metadata_loss(self):
        """Criterion 1: Adapter with HTTP 200 incomplete (reason=max_output_tokens) must preserve
        response_id, incomplete_reason, canonical numeric usage, calculable cost, and request limit context.
        """
        fixture = make_incomplete_fixture(
            response_id="resp_inc_test_100",
            reason="max_output_tokens",
            input_tokens=100,
            output_tokens=1200,
            cached_tokens=0,
            reasoning_tokens=1200,
        )

        def handler(request: httpx.Request):
            return httpx.Response(200, json=fixture, headers={"x-request-id": "req_inc_test_100"})

        transport = httpx.MockTransport(handler)
        provider = StandardProvider(
            media_hash="dummy_media_hash",
            duration_ms=6000,
            profile="test",
            transport=transport,
        )

        projection = {
            "persona_id": "p001",
            "scene": {"scene_id": 0, "start_ms": 0, "end_ms": 3000},
            "allowed_media_refs": [self.dummy_frame_key],
            "max_visible_ms": 3000,
            "own_impression": "",
        }

        with self.assertRaises(ProviderUnavailable) as ctx:
            provider.verdict(projection)

        exc = ctx.exception
        # Must retain metadata on exception receipt
        receipt = exc.receipt
        self.assertEqual(receipt.get("response_id"), "resp_inc_test_100", "Lost response_id in adapter receipt")
        self.assertEqual(receipt.get("incomplete_reason"), "max_output_tokens", "Lost incomplete_reason in adapter receipt")
        self.assertEqual(receipt.get("status"), "incomplete", "Lost status in adapter receipt")

        expected_usage = {
            "input_tokens": 100,
            "output_tokens": 1200,
            "total_tokens": 1300,
            "cached_tokens": 0,
            "reasoning_tokens": 1200,
        }
        self.assertEqual(receipt.get("usage"), expected_usage, "Lost usage in adapter receipt")

        # Calculable cost: 100 * 1.25/1e6 + 1200 * 4.25/1e6 = 0.000125 + 0.0051 = 0.005225
        self.assertAlmostEqual(receipt.get("cost_usd"), 0.005225, places=6, msg="Missing calculable cost in receipt")
        self.assertEqual(receipt.get("max_output_tokens"), 4096, "Missing request max_output_tokens context in receipt")

        # Verify sanitize_error_receipt preserves all allowlisted metadata
        clean_receipt = sanitize_error_receipt(exc, mode="standard", model_id=MODEL_ID, req_id="req_inc_test_100")
        self.assertEqual(clean_receipt.get("response_id"), "resp_inc_test_100")
        self.assertEqual(clean_receipt.get("incomplete_reason"), "max_output_tokens")
        self.assertEqual(clean_receipt.get("usage"), expected_usage)
        self.assertAlmostEqual(clean_receipt.get("cost_usd"), 0.005225, places=6)
        self.assertEqual(clean_receipt.get("max_output_tokens"), 4096)
        self.assertEqual(clean_receipt.get("error", {}).get("charge_state"), "unconfirmed")

    def test_repro_criterion_2_outbound_headroom_4096(self):
        """Criterion 2: Bounded response headroom for verdict and notes must be 4096 tokens."""
        captured_requests = []

        def handler(request: httpx.Request):
            captured_requests.append(request)
            body = json.loads(request.read().decode("utf-8"))
            if "verdicts" in body["text"]["format"]["schema"]["required"]:
                return httpx.Response(200, json=make_verdict_payload("p001"))
            else:
                return httpx.Response(200, json={
                    "id": f"resp_{uid()[:12]}",
                    "model": MODEL_ID,
                    "status": "completed",
                    "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"notes": []})}]}],
                })

        transport = httpx.MockTransport(handler)
        provider = StandardProvider(
            media_hash="dummy_media_hash",
            duration_ms=6000,
            profile="test",
            transport=transport,
        )

        # 1. Verdict request headroom
        projection = {
            "persona_id": "p001",
            "scene": {"scene_id": 0, "start_ms": 0, "end_ms": 3000},
            "allowed_media_refs": [self.dummy_frame_key],
            "max_visible_ms": 3000,
            "own_impression": "",
        }
        provider.verdict(projection)
        verdict_body = json.loads(captured_requests[-1].read().decode("utf-8"))
        self.assertEqual(verdict_body.get("max_output_tokens"), 4096, "Verdict request max_output_tokens must be 4096")

        # 2. Notes request headroom
        note_ctx = {
            "schema_version": "note-context-1",
            "duration_ms": 6000,
            "cohort": {"requested": 3, "effective": 3, "failed": 0, "pending": 0},
            "supported_triggers": [{
                "id": "stop_0",
                "scene_id": 0,
                "start_ms": 0,
                "end_ms": 3000,
                "start_sec": 0.0,
                "end_sec": 3.0,
                "stop_fraction": 0.33,
                "evidence": [],
            }],
        }
        provider.notes(note_ctx)
        notes_body = json.loads(captured_requests[-1].read().decode("utf-8"))
        self.assertEqual(notes_body.get("max_output_tokens"), 4096, "Notes request max_output_tokens must be 4096")

    def test_repro_criterion_3_worker_incomplete_persona_isolation(self):
        """Criterion 3: One persona receives HTTP 200 max_output_tokens; worker marks it failed,
        never dispatches later scenes to it, independent personas continue, and honest incomplete
        report is rendered with failed exclusion and valid usage in totals.
        """
        vid, run_id = self._create_test_run(profile="test", concurrency=1)

        dispatched_scenes = []

        def handler(request: httpx.Request):
            body = json.loads(request.read().decode("utf-8"))
            if "verdicts" in body["text"]["format"]["schema"]["required"]:
                prompt = body["input"][0]["content"][0]["text"]
                data = json.loads(prompt[prompt.index("{"):])
                pid = data["viewer"]["persona_id"]
                sid = data["current_segment"]["scene_id"]
                dispatched_scenes.append((pid, sid))

                # p001 gets HTTP 200 incomplete with max_output_tokens
                if pid == "p001" and sid == 0:
                    inc_resp = make_incomplete_fixture(
                        response_id="resp_inc_p001_s0",
                        reason="max_output_tokens",
                        input_tokens=100,
                        output_tokens=1200,
                        cached_tokens=0,
                        reasoning_tokens=1200,
                    )
                    return httpx.Response(200, json=inc_resp, headers={"x-request-id": "req_inc_p001_s0"})
                # p002 continues, p003 stops
                still_watching = (pid == "p002")
                return httpx.Response(200, json=make_verdict_payload(pid, still_watching=still_watching))
            else:
                return httpx.Response(200, json={
                    "id": f"resp_{uid()[:12]}",
                    "model": MODEL_ID,
                    "status": "completed",
                    "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"notes": []})}]}],
                })

        mock_transport = httpx.MockTransport(handler)

        def mock_factory(vhash, dur, profile="test", lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=mock_transport)

        # Run worker loop
        steps = 0
        while steps < 50:
            worked = process_once(provider_factory=mock_factory)
            steps += 1
            if not worked:
                break

        # Check DB state
        with connection() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id=%s", (run_id,)).fetchone()
            checkpoints = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id", (run_id,)).fetchall()
            calls = conn.execute("SELECT * FROM provider_calls WHERE run_id=%s ORDER BY unit", (run_id,)).fetchall()

        # The run MUST NOT fail due to one incomplete persona! It should finish with incomplete status.
        self.assertNotEqual(run["status"], "failed", f"Run failed prematurely with error: {run.get('error_code')}")
        self.assertEqual(run["status"], "incomplete", "Run status should be 'incomplete'")

        # Verify checkpoints
        cp_map = {c["persona_id"]: c["status"] for c in checkpoints}
        self.assertEqual(cp_map.get("p001"), "failed", "p001 should be marked failed")
        self.assertIn(cp_map.get("p002"), ("complete", "stopped"))
        self.assertEqual(cp_map.get("p003"), "stopped")

        # Verify p001 was NEVER dispatched scene 1
        p001_scenes = [sid for pid, sid in dispatched_scenes if pid == "p001"]
        self.assertEqual(p001_scenes, [0], "p001 must never receive another scene dispatch after failure")

        # Verify provider_calls for p001:0 has persisted receipt with incomplete metadata
        p001_call = next((c for c in calls if c["unit"] == "p001:0"), None)
        self.assertIsNotNone(p001_call)
        self.assertEqual(p001_call["status"], "failed")
        p001_receipt = p001_call["receipt"]
        self.assertEqual(p001_receipt.get("response_id"), "resp_inc_p001_s0")
        self.assertEqual(p001_receipt.get("incomplete_reason"), "max_output_tokens")
        self.assertAlmostEqual(p001_receipt.get("cost_usd"), 0.005225, places=6)

        # Verify report
        report = run["report"]
        self.assertIsNotNone(report, "Report must be generated")
        self.assertEqual(report["cast"]["requested"], 3)
        self.assertEqual(report["cast"]["effective"], 2)
        self.assertEqual(report["cast"]["failed"], 1)
        self.assertEqual(report["cast"]["status"], "incomplete")

        # Verify failed p001's usage and cost are included in total_cost_usd
        self.assertGreater(report["trust"]["total_cost_usd"], 0.005225)
        self.assertIn("p001", report["coverage"]["excluded_traces"]["failed"])

    def test_repro_criterion_3_all_failed_behavior(self):
        """When all personas encounter max_output_tokens incomplete, worker marks all failed,
        renders honest all-failed report (cast status failed, run status failed) with usage included.
        """
        vid, run_id = self._create_test_run(profile="test", concurrency=1)

        def handler(request: httpx.Request):
            body = json.loads(request.read().decode("utf-8"))
            if "verdicts" in body["text"]["format"]["schema"]["required"]:
                inc_resp = make_incomplete_fixture(
                    response_id=f"resp_inc_{uid()[:8]}",
                    reason="max_output_tokens",
                    input_tokens=100,
                    output_tokens=1200,
                )
                return httpx.Response(200, json=inc_resp)
            return httpx.Response(200, json={"output": {"notes": []}})

        mock_transport = httpx.MockTransport(handler)

        def mock_factory(vhash, dur, profile="test", lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=mock_transport)

        steps = 0
        while steps < 50:
            worked = process_once(provider_factory=mock_factory)
            steps += 1
            if not worked:
                break

        with connection() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id=%s", (run_id,)).fetchone()
            checkpoints = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s", (run_id,)).fetchall()

        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["stage"], "report")
        for cp in checkpoints:
            self.assertEqual(cp["status"], "failed")

        report = run["report"]
        self.assertIsNotNone(report)
        self.assertEqual(report["cast"]["effective"], 0)
        self.assertEqual(report["cast"]["failed"], 3)
        self.assertEqual(report["cast"]["status"], "failed")

    def test_repro_malformed_usage_or_unknown_reason_fails_closed(self):
        """Unknown reason or malformed usage must remain conservative failure, never isolated as incomplete."""
        vid, run_id = self._create_test_run(profile="test", concurrency=1)

        def handler(request: httpx.Request):
            # Unknown reason
            resp = make_incomplete_fixture(reason="content_filter")
            return httpx.Response(200, json=resp)

        mock_transport = httpx.MockTransport(handler)

        def mock_factory(vhash, dur, profile="test", lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=mock_transport)

        steps = 0
        while steps < 50:
            worked = process_once(provider_factory=mock_factory)
            steps += 1
            if not worked:
                break

        with connection() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id=%s", (run_id,)).fetchone()

        # Unknown reason must fail the run conservatively
        self.assertEqual(run["status"], "failed")
        self.assertNotEqual(run["stage"], "report")

    def test_repro_criterion_3_pool_concurrency_incomplete_persona_isolation(self):
        """Bounded pool concurrency path: incomplete persona terminates nonfatally, pool continues,
        honest incomplete report is rendered without halting pool admission.
        """
        vid, run_id = self._create_test_run(profile="flash")

        dispatched_scenes = []

        def handler(request: httpx.Request):
            body = json.loads(request.read().decode("utf-8"))
            if "verdicts" in body["text"]["format"]["schema"]["required"]:
                prompt = body["input"][0]["content"][0]["text"]
                data = json.loads(prompt[prompt.index("{"):])
                pid = data["viewer"]["persona_id"]
                sid = data["current_segment"]["scene_id"]
                dispatched_scenes.append((pid, sid))

                # p001 gets HTTP 200 incomplete with max_output_tokens on scene 0
                if pid == "p001" and sid == 0:
                    inc_resp = make_incomplete_fixture(
                        response_id="resp_inc_pool_p001_s0",
                        reason="max_output_tokens",
                        input_tokens=100,
                        output_tokens=1200,
                        cached_tokens=0,
                        reasoning_tokens=1200,
                    )
                    return httpx.Response(200, json=inc_resp, headers={"x-request-id": "req_inc_pool_p001_s0"})
                # All other personas stop on scene 0 to make test fast
                return httpx.Response(200, json=make_verdict_payload(pid, still_watching=False))
            else:
                return httpx.Response(200, json={
                    "id": f"resp_{uid()[:12]}",
                    "model": MODEL_ID,
                    "status": "completed",
                    "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"notes": []})}]}],
                })

        mock_transport = httpx.MockTransport(handler)

        def mock_factory(vhash, dur, profile="flash", lease=None):
            return StandardProvider(vhash, dur, profile=profile, lease=lease, transport=mock_transport)

        steps = 0
        while steps < 50:
            worked = process_once(provider_factory=mock_factory)
            steps += 1
            if not worked:
                break

        with connection() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id=%s", (run_id,)).fetchone()
            checkpoints = conn.execute("SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id", (run_id,)).fetchall()

        self.assertNotEqual(run["status"], "failed", f"Run failed prematurely: {run.get('error_code')}")
        self.assertEqual(run["status"], "incomplete")

        cp_map = {c["persona_id"]: c["status"] for c in checkpoints}
        self.assertEqual(cp_map.get("p001"), "failed")
        self.assertEqual(sum(1 for s in cp_map.values() if s == "stopped"), 49)

        # p001 was never dispatched scene 1
        p001_scenes = [sid for pid, sid in dispatched_scenes if pid == "p001"]
        self.assertEqual(p001_scenes, [0])

        report = run["report"]
        self.assertIsNotNone(report)
        self.assertEqual(report["cast"]["requested"], 50)
        self.assertEqual(report["cast"]["effective"], 49)
        self.assertEqual(report["cast"]["failed"], 1)
        self.assertEqual(report["cast"]["status"], "incomplete")
        self.assertGreater(report["trust"]["total_cost_usd"], 0.005225)


if __name__ == "__main__":
    unittest.main()
