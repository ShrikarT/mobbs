"""Focused regression tests for Meta Responses strict JSON schema compliance in StandardProvider.notes.

Contract reference: https://dev.meta.ai/docs/structured-output (2026-11-03, strict mode section)
Under strict: true, every object schema must have all keys in `properties` explicitly listed in `required`.
"""
import copy
import json
import unittest
from typing import Any, List

import httpx

import apps.api.app.standard_provider as standard_provider_module
from apps.api.app.standard_provider import (
    StandardProvider,
    NOTES_SCHEMA,
    VERDICTS_SCHEMA,
    ProviderUnavailable,
    MODEL_ID,
    PRICING_VERSION,
)


def find_strict_schema_violations(schema: Any, path: str = "root") -> List[str]:
    """Recursively validates that all object schemas in a strict JSON schema
    have every key in `properties` explicitly listed in `required`.
    Returns a list of violation messages.
    """
    violations = []
    if not isinstance(schema, dict):
        return violations

    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        for prop in properties:
            if prop not in required:
                violations.append(
                    f"{path}: property '{prop}' declared in properties but missing from required {sorted(list(required))}"
                )
        for prop, subschema in properties.items():
            violations.extend(find_strict_schema_violations(subschema, f"{path}.properties.{prop}"))

    if schema.get("type") == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            violations.extend(find_strict_schema_violations(items, f"{path}.items"))
        elif isinstance(items, list):
            for idx, item in enumerate(items):
                violations.extend(find_strict_schema_violations(item, f"{path}.items[{idx}]"))

    return violations


def make_canonical_notes_response(notes_list=None, limitations_list=None, input_tokens=1500, output_tokens=250):
    if notes_list is None:
        notes_list = []
    if limitations_list is None:
        limitations_list = []
    return {
        "id": "resp_notes_strict_test_12345",
        "model": MODEL_ID,
        "status": "completed",
        "usage": {
            "input_tokens": input_tokens,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": output_tokens,
            "output_tokens_details": {"reasoning_tokens": 100},
            "total_tokens": input_tokens + output_tokens,
        },
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps({"notes": notes_list, "limitations": limitations_list})
                    }
                ]
            }
        ]
    }


class TestStrictJsonSchemaCompliance(unittest.TestCase):
    """Test suite ensuring outbound request schemas strictly comply with Meta structured output rules."""

    def setUp(self):
        self.supported_context = {
            "schema_version": "note-context-1",
            "duration_ms": 6000,
            "cohort": {
                "requested": 3,
                "effective": 2,
                "failed": 1,
                "pending": 0,
                "included_persona_ids": ["p001", "p002"],
                "excluded_persona_ids": ["p003"],
            },
            "supported_triggers": [
                {
                    "id": "stop_1",
                    "scene_id": 1,
                    "start_ms": 3000,
                    "end_ms": 6000,
                    "start_sec": 3.0,
                    "end_sec": 6.0,
                    "stop_fraction": 0.5,
                    "evidence": [
                        {
                            "evidence_id": "ev_2_1",
                            "quote": "Confusing section",
                            "persona_id": "p002",
                            "start_sec": 3.0,
                            "end_sec": 6.0,
                        }
                    ],
                }
            ],
        }

    def test_verdicts_schema_strict_subset(self):
        """VERDICTS_SCHEMA must satisfy strict structured output rules (all properties in required)."""
        violations = find_strict_schema_violations(VERDICTS_SCHEMA)
        self.assertEqual(violations, [], f"VERDICTS_SCHEMA has strict violations: {violations}")
        self.assertFalse(VERDICTS_SCHEMA.get("additionalProperties", True))
        self.assertFalse(VERDICTS_SCHEMA["properties"]["verdicts"]["items"].get("additionalProperties", True))
        # Ensure all verdict item properties are required
        item_props = VERDICTS_SCHEMA["properties"]["verdicts"]["items"]["properties"]
        item_req = VERDICTS_SCHEMA["properties"]["verdicts"]["items"]["required"]
        self.assertEqual(set(item_props.keys()), set(item_req))

    def test_notes_schema_strict_subset(self):
        """NOTES_SCHEMA must satisfy strict structured output rules (all properties in required, including nested)."""
        violations = find_strict_schema_violations(NOTES_SCHEMA)
        self.assertEqual(violations, [], f"NOTES_SCHEMA has strict violations: {violations}")

        # Top-level properties match required
        self.assertEqual(set(NOTES_SCHEMA["properties"].keys()), set(NOTES_SCHEMA["required"]))
        self.assertIn("notes", NOTES_SCHEMA["required"])
        self.assertIn("limitations", NOTES_SCHEMA["required"])
        self.assertFalse(NOTES_SCHEMA.get("additionalProperties", True))

        # Nested note object properties match required
        note_item = NOTES_SCHEMA["properties"]["notes"]["items"]
        self.assertEqual(set(note_item["properties"].keys()), set(note_item["required"]))
        self.assertFalse(note_item.get("additionalProperties", True))

    def test_baseline_request_missing_required_limitations_fails_mock_transport_boundary(self):
        """Baseline schema missing 'limitations' in required causes external provider boundary to reject with HTTP 400."""
        captured_requests = []

        def strict_meta_boundary(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            body = json.loads(request.read().decode())
            outbound_schema = body.get("text", {}).get("format", {}).get("schema", {})
            violations = find_strict_schema_violations(outbound_schema)
            if violations:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": f"Strict JSON schema violation: {violations}",
                            "type": "invalid_request_error",
                            "code": "invalid_json_schema",
                        }
                    },
                    headers={"x-request-id": "req_strict_fail_400"},
                )
            return httpx.Response(
                200,
                json=make_canonical_notes_response(),
                headers={"x-request-id": "req_strict_pass_200"},
            )

        transport = httpx.MockTransport(strict_meta_boundary)
        provider = StandardProvider("media_test_hash", 6000, profile="test", transport=transport)

        # Recreate baseline defect: NOTES_SCHEMA with required: ["notes"] (missing "limitations")
        baseline_defective_schema = copy.deepcopy(NOTES_SCHEMA)
        baseline_defective_schema["required"] = ["notes"]

        original_schema = standard_provider_module.NOTES_SCHEMA
        try:
            standard_provider_module.NOTES_SCHEMA = baseline_defective_schema
            with self.assertRaises(ProviderUnavailable) as cm:
                provider.notes(self.supported_context)
            self.assertEqual(cm.exception.code, "provider_http_error_400")
            self.assertEqual(cm.exception.charge_state, "unconfirmed")
            self.assertEqual(cm.exception.receipt["http_status"], 400)
            self.assertEqual(cm.exception.receipt["request_id"], "req_strict_fail_400")
            self.assertEqual(len(captured_requests), 1)
        finally:
            standard_provider_module.NOTES_SCHEMA = original_schema

    def test_nested_object_missing_required_property_fails_mock_transport_boundary(self):
        """A schema with a nested object missing a required property is also rejected with HTTP 400."""
        captured_requests = []

        def strict_meta_boundary(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            body = json.loads(request.read().decode())
            outbound_schema = body.get("text", {}).get("format", {}).get("schema", {})
            violations = find_strict_schema_violations(outbound_schema)
            if violations:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": f"Strict JSON schema violation: {violations}",
                            "type": "invalid_request_error",
                        }
                    },
                    headers={"x-request-id": "req_nested_fail_400"},
                )
            return httpx.Response(200, json=make_canonical_notes_response())

        transport = httpx.MockTransport(strict_meta_boundary)
        provider = StandardProvider("media_test_hash", 6000, profile="test", transport=transport)

        defective_nested_schema = copy.deepcopy(NOTES_SCHEMA)
        # Remove 'quotes' from required in nested items
        defective_nested_schema["properties"]["notes"]["items"]["required"] = [
            "start_sec", "end_sec", "finding", "suggested_edit", "evidence_ids"
        ]

        original_schema = standard_provider_module.NOTES_SCHEMA
        try:
            standard_provider_module.NOTES_SCHEMA = defective_nested_schema
            with self.assertRaises(ProviderUnavailable) as cm:
                provider.notes(self.supported_context)
            self.assertEqual(cm.exception.code, "provider_http_error_400")
        finally:
            standard_provider_module.NOTES_SCHEMA = original_schema

    def test_fixed_notes_outbound_request_and_response_acceptance(self):
        """StandardProvider.notes sends valid strict:true schema and receives canonical completed notes."""
        captured_requests = []

        def strict_meta_boundary(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            body = json.loads(request.read().decode())

            # Verify protocol requirements
            self.assertEqual(body.get("model"), "muse-spark-1.3")
            self.assertIs(body.get("store"), False)
            self.assertEqual(body.get("reasoning"), {"effort": "minimal"})
            self.assertEqual(body.get("max_output_tokens"), 4096)

            text_fmt = body.get("text", {}).get("format", {})
            self.assertEqual(text_fmt.get("type"), "json_schema")
            self.assertEqual(text_fmt.get("name"), "result")
            self.assertIs(text_fmt.get("strict"), True)

            outbound_schema = text_fmt.get("schema", {})
            violations = find_strict_schema_violations(outbound_schema)
            if violations:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": f"Strict violation: {violations}",
                            "type": "invalid_request_error",
                        }
                    },
                    headers={"x-request-id": "req_err_400"},
                )

            return httpx.Response(
                200,
                json=make_canonical_notes_response(notes_list=[], limitations_list=[]),
                headers={"x-request-id": "req_notes_valid"},
            )

        transport = httpx.MockTransport(strict_meta_boundary)
        provider = StandardProvider("media_test_hash", 6000, profile="test", transport=transport)

        normalized, raw_bytes, sha = provider.notes(self.supported_context)

        # Assert exactly one HTTP request was sent and no blind retry
        self.assertEqual(len(captured_requests), 1)
        self.assertEqual(provider.live_calls, 1)

        req = captured_requests[0]
        self.assertEqual(str(req.url), "https://api.meta.ai/v1/responses")
        self.assertEqual(req.headers["authorization"], "Bearer DUMMY_KEY")

        # Assert normalized output and canonical response properties
        self.assertEqual(normalized["status"], "completed")
        self.assertEqual(normalized["mode"], "standard")
        self.assertEqual(normalized["output"], {"notes": [], "limitations": []})
        self.assertEqual(normalized["pricing_version"], PRICING_VERSION)
        self.assertGreater(normalized["cost_usd"], 0.0)
        self.assertEqual(normalized["usage"]["input_tokens"], 1500)
        self.assertEqual(normalized["usage"]["output_tokens"], 250)
        self.assertEqual(normalized["usage"]["total_tokens"], 1750)
        self.assertIsNotNone(sha)
        self.assertEqual(len(sha), 64)


if __name__ == "__main__":
    unittest.main()
