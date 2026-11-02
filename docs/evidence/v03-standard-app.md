# V03 Standard provider to app — author evidence record

Task: **V03-LIVE-APP** (`task_3a9951dd9175`, dispatch `ctx_718343708607`, run `run_d3354faa0659`).  
Author: Antigravity (worker terminal `term_1c943b2a-06cc-4933-a359-7345f146639d`).  
Coordinator: Codex (terminal `term_2f6e85a0-2d3d-4864-a150-7278685a21f3`).  
Assigned worktree: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-standard-app` on branch `codex/v03-standard-app`.  
Baseline commit: `ea6959aca0e999c71f4f1fb0eb24e372699076df`.  

**Outcome: WORKER-REPORTED.** Submitted for independent review.  
No live provider spend, API key leakage, or network calls to external endpoints performed; all provider interactions were verified via controlled `httpx.MockTransport` test doubles with fail-closed server defaults.

---

## Executive Summary

1. **Configured and Wired Standard Provider:** Added `StandardProvider` targeting fixed `https://api.meta.ai/v1/responses` with model `muse-spark-1.3`, `store: false`, minimal reasoning effort, and strict JSON schema (`text.format`) for verdicts and editing notes. Bound server-only `MODEL_API_KEY` with fail-closed validation when live without key or transport.
2. **Immutable Manifest Sealing & Mode Isolation:** Updated `POST /runs` and `GET /runs` to seal `provider_mode` (`recorded` vs `standard`), `model_id`, `cast_hash`, and `prompt_version` in the run manifest. Repeat lookups isolate runs by `(video_id, profile, provider_mode)`. Standard mode accepts fresh uploads absent historical stage2 fixture data.
3. **Sequential 50-Persona Simulation & Honest Reporting:** Wired `fifty-policies.json` (`66d9649bf11e24fda80bddb721e0783f5c7ef72c0c203f448e70b5a744118ffd`) mapping `p01..p50` to `p001..p050`. Enforced call ceiling (`requested * scenes + 1`, max 651 for Flash, <=40 for test), sequential single-active-generation ticks, pre-send `dispatched` markers committed under fence, fail-closed handling of unresolved dispatched markers after crashes without reissue, and honest report trust reflecting actual receipts and costs.

---

## Observable Behavior & Verified Criteria

### 1. Configuration & Manifest Sealing (`config.py`, `main.py`)
- `provider_mode`: configured via `VIRALIST_PROVIDER_MODE` (defaults to `'recorded'`).
- `model_api_key`: server-only setting via `VIRALIST_MODEL_API_KEY`, only read in `'standard'` mode; never exposed via browser, endpoints, or client-side config.
- `POST /runs`:
  - Enforces valid mode in `('recorded', 'standard')`.
  - Seals `manifest`: `schema_version='run-manifest-1'`, `profile`, `provider_mode`, `model_id`, `cast_hash`, `prompt_version`, `requested`, `persona_ids`, `resample_seed`.
  - Standard mode allows fresh video uploads (e.g., Video B) without stage2 fixture prerequisites (`test_standard_mode_accepts_upload_without_stage2_fixture`).
  - Repeat run lookup key is scoped by `(video_id, profile, provider_mode)` (`test_standard_manifest_sealing_and_mode_isolation`).
- `/health`: reports accurate inference capabilities:
  - `standard_available: True` when `MODEL_API_KEY` is present.
  - `active_mode`: current configured mode.
  - `standard_model`: `'muse-spark-1.3'`.

### 2. Standard Provider Implementation (`standard_provider.py`, `providers.py`)
- Target endpoint: fixed `https://api.meta.ai/v1/responses`, standard `muse-spark-1.3`.
- Strict format: `text.format` uses JSON Schema with `additionalProperties: False`.
- Frame input: scene-local decoded JPEG frame from object storage encoded as inline base64 image; scene bounds and persona card included; no whole-summary or peer reaction leakage.
- Cost calculation: pinned rates ($1.25 / $0.15 / $4.25 per 1M tokens) matching `2026-10-28-standard-v1` pricing version.
- Note generation: accepts `note-context-1` built from reactions; filters out failed personas; identifies stop triggers (>=15% drop-off); omits provider call deterministically (0 HTTP calls) when no triggers are present (`test_notes_omission_emits_zero_calls`).

### 3. Worker Execution & Lifecycle Protection (`worker.py`)
- Dynamic Provider Selection: picks `StandardProvider` when `manifest.provider_mode == 'standard'`, otherwise `RecordedProvider`.
- Call Ceiling Enforcement: stops admissions and marks run failed (`run_call_ceiling_exceeded`) when `provider_calls >= min(40 if test else 651, requested * scenes + 1)` (`test_call_ceiling_enforcement`).
- Fence & Pre-Send Dispatched Marker: inserts `provider_calls(run_id, unit, 'dispatched', ...)` committed under DB fence prior to network call.
- Crash Recovery Without Reissue: an unresolved `dispatched` call encountered upon worker restart halts the run with `error_code='uncertain_provider_charge'`, marks the call failed with `charge_state='uncertain'`, and never blindly reissues the request (`test_unresolved_dispatched_marker_halts_without_reissue`).
- Once-Only Publishing: accepted calls in `provider_calls` allow idempotent re-tick without duplicate generations.
- Reporting Notes Marker: `unit='notes'` is tracked under the same dispatched fence, call ceiling, and receipt updating mechanism.

### 4. 50-Candidate Cast Management (`cast.py`)
- Loads `experiments/behavior/fifty-policies.json` verified against canonical hash `66d9649bf11e24fda80bddb721e0783f5c7ef72c0c203f448e70b5a744118ffd`.
- Maps 50 policies in exact order to `p001..p050`.
- Provides `get_persona_ids(profile)`, `get_persona_card(persona_id)`, and `get_cast_hash(profile)`.

### 5. Honest Reporting (`reporting.py`)
- Report `trust` block aggregates directly from `provider_calls` receipts:
  - `total_cost_usd`: sum of `cost_usd` across all receipts, rounded to 8 decimal places.
  - `live_calls`: count of calls with `mode == 'standard'`.
  - `pricing_version`: matches receipt pricing version (`2026-10-28-standard-v1`).
  - `app_source_sha`, `cast_sha256`, `feature_sha256`.

---

## Verification Evidence & Test Commands

All checks were executed in the assigned worktree against the local PostgreSQL (`viralist_v03_standard_app`, port 55432) and RustFS S3 store (`http://127.0.0.1:59000`).

### 1. Standard Provider & App Lifecycle Test Suite
Command:
```powershell
$env:VIRALIST_RUNTIME = "C:\Users\Shrikar\.codex\viralist-v03-standard-app\runtime.json"
& "C:\Users\Shrikar\.codex\viralist-v02-review\venv\Scripts\python.exe" -m unittest tests.test_v03_standard_app
```
Result: **OK (12 tests in 132.036s)**
Tests verified:
- `test_cast_loading_and_hash_integrity`: `fifty-policies.json` hash integrity, 50 persona ordering `p001..p050`.
- `test_verdict_request_serialization_and_response_validation`: strict Meta schema, inline base64 image, cost calculation.
- `test_provider_fail_closed_without_credentials`: `ProviderUnavailable` raised when live without key or transport double.
- `test_transport_timeout_sets_uncertain_charge`: timeout maps to `uncertain_provider_charge`.
- `test_notes_omission_emits_zero_calls`: no triggers -> 0 HTTP calls.
- `test_build_note_context_filters_failed_and_unsupported_triggers`: failed personas excluded, >=15% stop triggers extracted.
- `test_standard_manifest_sealing_and_mode_isolation`: manifest sealing, repeat isolation by mode.
- `test_standard_mode_accepts_upload_without_stage2_fixture`: unknown uploads accepted in standard mode.
- `test_health_reflects_inference_mode`: `/health` inference details.
- `test_standard_worker_end_to_end_test_profile`: 3 personas across 8 scenes + notes, receipts recorded with costs.
- `test_unresolved_dispatched_marker_halts_without_reissue`: zero blind reissue on crash recovery.
- `test_call_ceiling_enforcement`: fails closed on call ceiling limit.
- `test_standard_worker_50_persona_flash_full_journey`: full 50-persona Flash journey (10 stopped at scene 0, 40 completed all 8 scenes, 331 calls dispatched, receipts matched, trust verified).

### 2. Regression Suites
- `test_normalized.py`:
  ```powershell
  & "C:\Users\Shrikar\.codex\viralist-v02-review\venv\Scripts\python.exe" -m unittest tests.test_normalized
  ```
  Result: **OK (14 tests in 0.026s)**
- `test_v03_flash_backend.py` (Recorded mode regression):
  ```powershell
  $env:VIRALIST_RUNTIME = "C:\Users\Shrikar\.codex\viralist-v03-standard-app\runtime.json"
  $env:VIRALIST_PROVIDER_MODE = "recorded"
  & "C:\Users\Shrikar\.codex\viralist-v02-review\venv\Scripts\python.exe" -m unittest tests.test_v03_flash_backend
  ```
  Result: **OK (14 tests in 98.955s)**

---

## Limitations & Non-Goals

1. **Deferred Accounting:** All custom accounting, ledgers, reservations, `budget.py`, `_budget_core.py`, and `SQL004` remain strictly deferred per owner priority directive (`docs/decisions-v03-product-priority.md`).
2. **Provider Doubles Only:** Zero live provider credits spent; all tests ran via controlled `httpx.MockTransport` doubles. Live execution with real `MODEL_API_KEY` remains a subsequent authorized coordinator step within the $30 cap.
3. **Frontend & Schemas:** No UI styles, DB migrations, or lockfiles modified.
