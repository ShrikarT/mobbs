# V03-RUNTIME-INCOMPLETE Evidence — Incomplete Response Reliability

- Task ID: `task_416dfe1a4d64`
- Dispatch ID: `ctx_d98dbfd50ef5`
- Run ID: `run_d3354faa0659`
- Author: Antigravity (Implementation Worker)
- Branch: `codex/v03-incomplete-fix`
- Baseline Commit: `affebcedae5a92d1f877113adfda104eee6a7c7f`
- Dedicated Test Runtime: `C:/Users/Shrikar/.codex/private-runs/viralist-v03-incomplete-20261103/runtime.json`
- Dedicated Test Database: `viralist_v03_incomplete_20261103` on PostgreSQL port 55432
- Dedicated Test S3 Bucket: `viralist-v03-incomplete-20261103` on port 59000
- Acceptance State: WORKER-REPORTED (submitted for independent exact-commit review)

---

## 1. Defect Analysis and Reproduction

### The Problem
During the local Standard Flash run, 139 persona decisions completed normally, followed by one HTTP 200 response with `status="incomplete"`.
Under the baseline code:
1. `StandardProvider.verdict` and `notes` raised `ProviderUnavailable('provider_incomplete', receipt=receipt)`, but `receipt` only contained basic HTTP headers (`status_code`, `request_id`, `requested_model`, `latency_sec`). The `response_id`, `incomplete_reason` (`max_output_tokens`), parsed `usage`, and calculable `cost_usd` present in `normalized` were lost.
2. `worker.sanitize_error_receipt` lacked fields for `incomplete_reason`, `status`, `cost_usd`, and `max_output_tokens`, stripping them from persisted provider call receipts.
3. `worker.execute_persona_scene` caught `ProviderUnavailable` and unconditionally updated the entire run to `status='failed'`, `stage='failed'`, and set `halt_event`, prematurely killing the run and halting all other independent personas.
4. Request output limits were set tightly at 1200 tokens for `verdict` and 1600 tokens for `notes`.
5. Frontend error state displayed raw error codes (e.g. `provider_incomplete`) with ambiguous "Try again" wording that did not clarify whether charges would be reissued or uploads deleted.

### Deterministic Red Reproduction
Prior to modifying production code, `tests/test_v03_incomplete_fix.py` was created and executed against baseline:
- `test_repro_criterion_1_adapter_incomplete_metadata_loss`: FAILED (`None != 'resp_inc_test_100'`, lost response_id and usage in receipt).
- `test_repro_criterion_2_outbound_headroom_4096`: FAILED (`1200 != 4096`, verdict request output limit was 1200).
- `test_repro_criterion_3_worker_incomplete_persona_isolation`: FAILED (`'failed' == 'failed'`, run aborted prematurely with `error_code='provider_incomplete'` on first incomplete persona).
- `test_repro_criterion_3_all_failed_behavior`: FAILED (`'failed' != 'report'`, run failed at scene level instead of rendering honest all-failed report).
- `test_repro_malformed_usage_or_unknown_reason_fails_closed`: PASSED (conservative failure intact).

Status `msg_180539ef2997` reported the red checkpoint to the coordinator.

---

## 2. Implementation Seams

### (A) Adapter Headroom and Metadata Preservation (`apps/api/app/standard_provider.py`)
- Increased bounded output headroom for `verdict` from 1200 to 4096 tokens, and `notes` from 1600 to 4096 tokens, preserving `store: False`, minimal reasoning effort, strict schema, and pricing version.
- In `verdict` and `notes`, updated exception receipt with `status`, allowlisted `incomplete_reason`, `response_id`, canonical numeric `usage`, calculable `cost_usd` via `compute_cost_usd(usage)`, and request limit context (`max_output_tokens: 4096`).
- Rejected malformed usage and unknown reasons conservatively with `charge_state='uncertain'`.

### (B) Worker Per-Persona Failure Isolation and Accurate Reporting (`apps/api/app/worker.py`)
- In `sanitize_error_receipt`, preserved allowlisted `incomplete_reason` (`max_output_tokens`, `unknown`), `status`, `cost_usd`, and `max_output_tokens`.
- In `maybe_emit_provisional_verdict`, updated condition to verify no active personas remain on Scene 0 (`active_s0 is None and rows`), allowing provisional verdict emission when surviving personas finish Scene 0 even if one persona failed.
- In `execute_persona_scene`, detected confirmed `max_output_tokens` incomplete response with valid usage:
  - Persona checkpoint marked `failed`.
  - Provider call recorded with `status='failed'` and sanitized receipt containing usage and cost.
  - Run is NOT marked failed; `halt_event` is NOT set; operational pause is NOT triggered.
  - Returns `True` (nonfatal persona termination) so the bounded pool or serial worker continues executing remaining independent personas.
  - Persona is excluded from future scene queries because `checkpoints.status == 'failed'`.
- When all active personas finish, worker advances to reporting:
  - Builds report via `build_report` where failed personas are excluded from traces, retention, and scores.
  - If some personas succeeded: `cast['status'] == 'incomplete'`, `runs.status == 'incomplete'`, `runs.stage == 'report'`.
  - If all personas failed: `cast['status'] == 'failed'`, `runs.status == 'failed'`, `runs.stage == 'report'`.
  - Failed attempt's valid usage and cost are included in report `trust['total_cost_usd']` and `trust['live_calls']`.

### (C) Frontend Truthful Navigation and Error Copy (`apps/web/src/App.tsx`)
- Added `formatRunErrorMessage(code)` helper providing clear, honest explanations and user guidance for error codes (`uncertain_provider_charge`, `provider_incomplete`, `run_call_ceiling_exceeded`, `missing_durable_notes_output`, `corrupted_durable_notes_output`, `provider_timeout`, `provider_transport_error`, `provider_response_rejected`).
- Replaced ambiguous "Try again" button with "Return to upload", which safely resets view to idle without resending charges or deleting the uploaded video.
- Preserved "Delete uploaded video" with explicit confirmation modal.

---

## 3. Verification and Observed Results

### Focused Test Suite (`tests/test_v03_incomplete_fix.py`)
Command:
```powershell
$env:VIRALIST_RUNTIME = "C:/Users/Shrikar/.codex/private-runs/viralist-v03-incomplete-20261103/runtime.json"
C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe -m unittest tests/test_v03_incomplete_fix.py -v
```
Result:
```
test_repro_criterion_1_adapter_incomplete_metadata_loss ... ok
test_repro_criterion_2_outbound_headroom_4096 ... ok
test_repro_criterion_3_all_failed_behavior ... ok
test_repro_criterion_3_pool_concurrency_incomplete_persona_isolation ... ok
test_repro_criterion_3_worker_incomplete_persona_isolation ... ok
test_repro_malformed_usage_or_unknown_reason_fails_closed ... ok

Ran 6 tests in 39.468s
OK (exit code 0)
```

### Core Normalized Contract Suite (`tests/test_normalized.py`)
Command:
```powershell
C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe -m unittest tests/test_normalized.py
```
Result:
```
Ran 14 tests in 0.017s
OK (exit code 0)
```

### Frontend Build
Command:
```cmd
cmd.exe /c "npm run build"
```
Result:
```
> tsc -p apps/web/tsconfig.json && vite build --config apps/web/vite.config.ts
vite v8.3.2 building client environment for production...
transforming...
✓ 17 modules transformed.
rendering chunks...
computing gzip size...
apps/web/dist/index.html                   0.40 kB │ gzip:  0.29 kB
apps/web/dist/assets/index-DlpWRBPX.css   20.12 kB │ gzip:  4.27 kB
apps/web/dist/assets/index-CB_7kx4_.js   270.63 kB │ gzip: 81.54 kB
✓ built in 1.25s (exit code 0)
```

---

## 4. Verification Limits and Gaps

1. **Browser Verification Gap:**
   Per coordinator messages `msg_baab054d297d` and `msg_9944103df6a4`, worker browser setup attempts were stopped under coordinator decision gate. Live local browser testing via `browse --local` encountered process launch timeout on Windows local Chrome. Coordinator takes independent verification of browser flows.
2. **Zero Paid Calls:**
   No live Meta API calls or charges were incurred by the worker. All provider boundary interactions were exercised via `httpx.MockTransport` fixtures.
3. **User Data Integrity:**
   The original failed user run and upload from 2026-11-03 were left strictly unmodified in the user database; no retroactive receipts were invented.

---

## 5. Review Correction 1 (2026-11-03)

- Task ID: `task_85789c335894`
- Dispatch ID: `ctx_a16a63bb9c6e`
- Run ID: `run_d3354faa0659`
- Preserved Lineage: Task `task_416dfe1a4d64`, Dispatch `ctx_d98dbfd50ef5`, candidate `47a40c76a3c5a7f35966f77f478cc814070ac470`, baseline `c015c42dc63f04f208c2ba145a5cd5fdfb210098`
- Submitted Corrections: 1 (0 unsuccessful)
- Acceptance State: WORKER-REPORTED

### Resolved Review Findings (`docs/evidence/v03-incomplete-review-r1.md`):
1. **App.tsx Error Copy:**
   - Updated `provider_incomplete` in `formatRunErrorMessage` to exact neutral copy: `"The provider returned an unfinished response, so this run stopped."`
   - Removed unsupported charges and video preservation claims from generic/fallback errors (`!code` and unknown code fallback), replacing with honest fallback guidance: `"Return to upload to start a new analysis. No automatic resend was dispatched."`
   - Retained explicit "Return to upload" navigation and confirmed "Delete uploaded video" modal without broader UI changes.
2. **Request Shape Regression Assertion (`tests/test_v03_standard_app.py:205`):**
   - Updated obsolete outbound request ceiling assertion from `1200` to `4096` matching intended bounded headroom.
   - Preserved 1200-token incomplete response fixtures intact.
   - Backend source `apps/api/app/standard_provider.py` and `apps/api/app/worker.py` remain byte-identical to `47a40c7`.

### Verification Results:
- `tests.test_v03_standard_app.TestStandardProviderUnit`: 4 tests PASS in 0.604s (exit code 0) using dedicated test runtime `unit-runtime.json` (origin 58000).
- `npm run build`: PASS, 17 modules transformed, Vite built in 300ms (exit code 0).
- `tests.test_v03_incomplete_fix`: 6 tests PASS in 38.008s (exit code 0).
- `tests.test_normalized`: 14 tests PASS in 0.017s (exit code 0).
- Browser verification gap: coordinator explicitly owns independent browser and combined verification.

