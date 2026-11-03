# V03-NOTES-STRICT — Director's Notes Strict Schema Verification

## Summary

- **Task ID:** `task_19974038690e`
- **Dispatch ID:** `ctx_05d0790af40e`
- **Run ID:** `run_d3354faa0659`
- **Branch:** `codex/v03-notes-schema`
- **Assigned Worktree:** `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-notes-schema`
- **Baseline HEAD:** `7de04c01f4c2ab1c5dd79d00a9e9ebba6d700cc7` (docs-only assignment atop `df43e7d1077928756263c34ca1dd0036898d3070`)
- **Status:** WORKER-REPORTED (0 corrections submitted)

## Background & Defect Reproduction

During a fresh 50-instance local Flash run on `df43e7d` (Video A), all 50 personas reached terminal checkpoints (34 stopped + 16 complete) across 346 accepted scene decisions (accepted-use estimate 0.85935030 USD; 0 persona incomplete failures on that input). However, the subsequent Director's Notes request failed with HTTP 400 (`request_id: 450f235f-f095-4508-ba44-d509b1dfee42`; failed notes usage unavailable, not assumed free). The adapter discarded HTTP 400 error prose.

Under Meta's structured output specification (https://dev.meta.ai/docs/structured-output, strict mode section), when `strict: true` is enabled on `/responses`, every object schema in the JSON schema definition must explicitly list all declared keys from `properties` in its `required` array.

In baseline `apps/api/app/standard_provider.py`:
- `NOTES_SCHEMA["properties"]` declared both `"notes"` and `"limitations"`.
- `NOTES_SCHEMA["required"]` only listed `["notes"]`.
- Static check: `set(NOTES_SCHEMA['properties'].keys()) - set(NOTES_SCHEMA['required']) == {'limitations'}`.
- Runtime check: In `tests/test_v03_notes_strict_schema.py`, a `MockTransport` enforcing strict schema validation returned HTTP 400 on the baseline request, raising `ProviderUnavailable('provider_http_error_400')`.

## Implementation

1. **One-line production fix (`apps/api/app/standard_provider.py`):**
   Updated `NOTES_SCHEMA["required"]` from `["notes"]` to `["notes", "limitations"]`.
   Preserved all existing properties, nested schemas, `additionalProperties: False`, `strict: True`, bounded output (`max_output_tokens: 4096`), `reasoning: {"effort": "minimal"}`, `store: False`, and model `muse-spark-1.3`.
2. **Focused regression suite (`tests/test_v03_notes_strict_schema.py`):**
   - Recursive schema validator checking that every object schema has all properties in required and `additionalProperties: False`.
   - Verified that `VERDICTS_SCHEMA` and `NOTES_SCHEMA` both comply with strict schema rules.
   - Tested that `MockTransport` rejects schemas missing required properties (simulating baseline defect and nested defect) with HTTP 400.
   - Verified that `StandardProvider.notes` sends valid request to `/responses`, executes exactly 1 HTTP request with no retry (`live_calls == 1`), and normalizes canonical completed response containing `notes: []` and `limitations: []` with valid token usage and calculated cost.

## Checks & Verification

Executed with Python `C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe`, using `VIRALIST_RUNTIME=C:/Users/Shrikar/.codex/private-runs/viralist-v03-incomplete-20261103/unit-runtime.json`, `MODEL_API_KEY=DUMMY_KEY`, and `PYTHONDONTWRITEBYTECODE=1`:

1. **Focused regression tests:**
   ```powershell
   python.exe -m unittest tests.test_v03_notes_strict_schema -v
   ```
   - `test_baseline_request_missing_required_limitations_fails_mock_transport_boundary`: ok
   - `test_fixed_notes_outbound_request_and_response_acceptance`: ok
   - `test_nested_object_missing_required_property_fails_mock_transport_boundary`: ok
   - `test_notes_schema_strict_subset`: ok
   - `test_verdicts_schema_strict_subset`: ok
   *Result:* 5/5 passed in 0.006s (exit code 0).

2. **Standard Provider Unit & Notes Context tests:**
   ```powershell
   python.exe -m unittest tests.test_v03_standard_app.TestStandardProviderUnit tests.test_v03_standard_app.TestNotesContextAndOmission -v
   ```
   - `test_50_persona_cards_in_order`: ok
   - `test_pricing_calculation`: ok
   - `test_verdict_request_capture_and_normalization`: ok
   - `test_verdict_timeout_uncertain_charge_fails_closed`: ok
   - `test_build_note_context_filters_failed_and_unsupported_triggers`: ok
   - `test_deterministic_omission_when_no_supported_triggers`: ok
   *Result:* 6/6 passed in 0.977s (exit code 0).

Total: 11/11 tests pass clean exit 0.

## Scope & Limitations

- Excluded: worker, scheduler, UI, accounting, retry/recovery subsystem, manifests, migrations.
- Controlled MockTransport HTTP boundary used; zero live provider keys or paid calls used.
- Coordinator owns live functional fixture verification (short synthetic-video Flash 50) after integration.
