# V03 Standard provider to app — Correction 2 author evidence record

Task: **V03-LIVE-APP Correction 2** (`task_e952bf64a6cc`, dispatch `ctx_f64ce39b3cb2`, run `run_d3354faa0659`).  
Parent original task: `task_3a9951dd9175`, previous author `task_091b0d0a88c4` (`ctx_1d206fe9da4f`, candidate `5f5fe3a`).  
Review: `task_5279a12a6e25` / `ctx_f36ef6765e84` returned REVISE.  
Author: Antigravity (worker terminal `term_ff5ea1aa-2b4c-4f74-8046-881a18ed0c42`).  
Coordinator: Codex (terminal `term_fae0b73c-b257-4674-aa24-b5f6df0ea7aa`).  
Assigned worktree: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-standard-app` on branch `codex/v03-standard-app-r2`.  
Exact clean baseline: `5f5fe3ac3129521f5efecd66c2ec842b897bda4c`.  

**Outcome: WORKER-REPORTED.** Submitted for independent review.  
No live provider spend, paid requests, or network access to external model endpoints performed in this worker run; all provider interactions were verified via controlled `httpx.MockTransport` test doubles with fail-closed server defaults. Owner course correction `ec26458:docs/decisions-v03-product-priority.md` applied: the 30 USD monetary cap and balance gate are removed; custom accounting remains deferred; credit efficiency is preserved via bounded per-run calls, concurrency 1, no blind retry of uncertain units, and honest usage reporting.

---

## Executive Summary of Corrections

This correction submission resolves all four numbered product blockers and the mobile layout limitation identified in the independent review of candidate `5f5fe3ac3129521f5efecd66c2ec842b897bda4c`:

1. **Finding 1 (P1) — Post-Wait Deletion and Stale Dispatch Fence (`apps/api/app/worker.py`):**
   - In both `verdict` and `notes` worker paths, an atomic `fence(gate_conn, lease)` check is executed immediately after acquiring `standard_concurrency_gate()`, before any outbound HTTP dispatch.
   - The fence validates the current video row status, tombstone, job generation, and lease; if the video was deleted or the job cancelled while waiting in the PostgreSQL advisory lock queue, `LeaseLost` is raised.
   - `process_once` catches `LeaseLost` cleanly without dispatching provider HTTP, publishing results, or persisting error receipts.
   - Verified via dedicated multi-process regression helper `tests/v03_standard_r2_worker.py` and test `test_post_wait_deletion_yields_zero_second_http` in `tests/test_v03_standard_app.py`: second worker waiting at gate yields exactly ZERO outbound HTTP requests when deleted via the owner API before gate acquisition. First checkpoint commit `909f34722b73b42a531df018b5028fcd5fdd7fb0` reviewed and approved by coordinator.

2. **Finding 2 (P2) — Safe Malformed Usage Receipt & Response Identity Preservation (`apps/api/app/standard_provider.py`, `apps/api/app/worker.py`):**
   - Implemented `sanitize_usage()` in `standard_provider.py` to filter arbitrary provider prose and diagnostic keys (e.g., `SYNTHETIC_USAGE_PROSE_CANARY_R2`) while preserving primitive numeric token counts (`input_tokens`, `output_tokens`, `total_tokens`, `cached_tokens`, `reasoning_tokens`).
   - In `worker.py` and `standard_provider.py`, verified that `sanitize_error_receipt()` preserves `response_id` alongside `request_id`, `requested_model`, and HTTP status.
   - Regression test `test_missing_and_inconsistent_usage` updated to assert that canaries are redacted from persisted receipts while `response_id` is retained.

3. **Finding 3 (P2) — Registered Notes Bytes & Hash Recovery Across Restart (`apps/api/app/worker.py`):**
   - On notes generation, raw payload bytes are registered in `Storage` via `reserve_object` / `put_reserved`, and `response_sha256` is recorded in both `provider_calls.receipt` and `audit`.
   - On worker recovery across process restart, the worker verifies that an accepted notes call has `object_key` and `response_sha256`.
   - The raw bytes are read directly from `Storage().get(object_key)['Body'].read()`, their SHA-256 is computed and matched against stored `response_sha256`, and the envelope is re-normalized with receipt metadata (`http_status=200`, `latency_sec`).
   - If storage is missing or corrupt, the run fails visibly with `error_code='missing_durable_notes_output'` without reissuing HTTP requests.
   - Verified via `test_notes_recovery_across_restart_no_generation` with injected storage fault.

4. **Finding 4 (P2) — Saved Provenance & Truthful Persona Library Disclosures (`apps/web/src/App.tsx`):**
   - Replaced fragile OR logic with `effectiveMode` memo:
     1. Saved report provenance first (`report?.trust?.mode`).
     2. Sealed manifest second (`runState?.manifest?.provider_mode`).
     3. Session fallback only for initial empty state (`session?.provider_mode || 'recorded'`).
   - Header badge, upload desk notice, trust block, and thin-cast library notice derive strictly from `effectiveMode`:
     - Standard Flash: 50 fictional candidate persona policies from `fifty-policies.json`.
     - Standard Test: 3 fictional candidate persona policies.
     - Recorded Flash: 50 simulated personas derived from 5 archetypes.
     - Recorded Test: 3 simulated viewers.
   - Trust block renders `Recorded replay` / `Standard inference` matching actual mode.
   - Verified in `test_ui_disclosures_truthful` and automated Playwright config-switch refresh check (reloaded recorded report preserves Recorded mode badge and Recorded replay text even when backend settings switch to standard).

5. **Finding 5 (Mobile Addendum) — Mobile Layout Responsiveness & Zero Document Overflow (`apps/web/src/style.css`):**
   - Resolved grid and flex auto-min-width overflow by setting `min-width: 0; width: 100%` across `.workbench-grid > *`, `.player-column`, `.evidence-column`, `.timeline-segment`, and cards.
   - Added `overflow-wrap: anywhere; word-break: break-word` for monospace and alert containers.
   - Added media queries for `@media (max-width: 639px)` and `@media (max-width: 360px)`.
   - Built frontend assets via `cmd /c pnpm run build` (tsc + vite, 325ms, 0 errors).
   - Verified in Playwright across both Standard and Recorded journeys:
     - 375px viewport: `document.documentElement.scrollWidth` = 375px (`overflow375: false`).
     - 320px viewport: `document.documentElement.scrollWidth` = 320px (`overflow320: false`).
     - Note cards, trust manifest, and delete controls remain fully reachable and functional at 320px.

---

## Verification Evidence

### 1. Build and Frontend Assets
- **Command:** `cmd /c pnpm run build`
- **Output:**
  ```
  $ tsc -p apps/web/tsconfig.json && vite build --config apps/web/vite.config.ts
  vite v8.3.5 building client environment for production...
  transforming...
  ✓ 17 modules transformed.
  rendering chunks...
  computing gzip size...
  apps/web/dist/index.html                   0.40 kB │ gzip:  0.29 kB
  apps/web/dist/assets/index-DlpWRBPX.css   20.12 kB │ gzip:  4.27 kB
  apps/web/dist/assets/index-4vxDW0gL.js   264.07 kB │ gzip: 79.73 kB
  ✓ built in 325ms
  ```
- **Exit Code:** 0

### 2. Full Standard App Unit Test Suite
- **Command:** `$env:VIRALIST_RUNTIME = 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json'; python -m unittest tests.test_v03_standard_app`
- **Output:**
  ```
  Ran 18 tests in 218.061s
  OK
  ```
- **Exit Code:** 0
- **Exact Executed Unittest Method Inventory (18 tests):**
  1. `tests.test_v03_standard_app.TestNotesContextAndOmission.test_build_note_context_filters_failed_and_unsupported_triggers`: Validates note context filters out failed personas and unsupported triggers.
  2. `tests.test_v03_standard_app.TestNotesContextAndOmission.test_deterministic_omission_when_no_supported_triggers`: Confirms deterministic omission when no supported triggers are present.
  3. `tests.test_v03_standard_app.TestStandardAppRoutesAndManifest.test_standard_manifest_sealing_and_mode_isolation`: Asserts immutable manifest sealing in standard mode.
  4. `tests.test_v03_standard_app.TestStandardAppRoutesAndManifest.test_standard_mode_accepts_upload_without_historical_fixtures`: Ensures standard mode accepts uploads without requiring historical recorded fixture hashes.
  5. `tests.test_v03_standard_app.TestStandardProviderUnit.test_50_persona_cards_in_order`: Verifies ordered 50-persona policy cards.
  6. `tests.test_v03_standard_app.TestStandardProviderUnit.test_pricing_calculation`: Exercises token pricing calculation and pricing version propagation.
  7. `tests.test_v03_standard_app.TestStandardProviderUnit.test_verdict_request_capture_and_normalization`: Checks payload structure, schema strictness, and normalization.
  8. `tests.test_v03_standard_app.TestStandardProviderUnit.test_verdict_timeout_uncertain_charge_fails_closed`: Verifies timeout handling fails closed with uncertain charge state.
  9. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_call_ceiling_enforcement`: Confirms ceiling bounds prevent extra calls.
  10. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_canary_redaction_transport_error`: Asserts synthetic canaries are excluded from durable error receipts.
  11. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_concurrency_gate_enforces_single_active_generation`: Enforces PG advisory semaphore limits active generation to 1.
  12. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_missing_and_inconsistent_usage`: Finding 2 verification; confirms prose canaries are redacted from persisted receipts, response_id is retained, and inconsistent usage triggers operational pause.
  13. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_notes_recovery_across_restart_no_generation`: Finding 3 verification; tests restart recovery reading durable bytes, validating hash, and handling storage failure with visible error without reissuing HTTP.
  14. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_post_wait_deletion_yields_zero_second_http`: Finding 1 verification; multi-process test where second worker waiting at gate yields ZERO outbound HTTP requests when deleted before gate acquisition.
  15. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_standard_worker_50_persona_flash_full_journey`: Executes full Flash 50 journey with mock transport.
  16. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_standard_worker_end_to_end_test_profile`: Executes complete Test profile journey.
  17. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_ui_disclosures_truthful`: Finding 4 verification; tests session mode negotiation, candidate policy limitations, and archetype distinctions.
  18. `tests.test_v03_standard_app.TestStandardWorkerAndLifecycle.test_unresolved_dispatched_marker_halts_without_reissue`: Confirms crash-recovery halts without blind re-execution.

### 3. Normalized Envelope Contract Suite
- **Command:** `python -m unittest tests.test_normalized`
- **Output:**
  ```
  Ran 14 tests in 0.016s
  OK
  ```
- **Exit Code:** 0

### 4. Domain Integration Suite
- **Command:** `$env:VIRALIST_RUNTIME = 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json'; python -m unittest tests.test_domain_integration`
- **Output:**
  ```
  Ran 4 tests in 1.759s
  OK
  ```
- **Exit Code:** 0

### 5. Automated Playwright Browser Journeys (Standard & Recorded)
Executed against running production FastAPI server with built frontend mounted at `/` and live background worker thread:

#### Standard Mode Journey (`node browser_check.cjs standard`)
- **HTTP Transport Double:** Standard inferences in the runner were served via `httpx.MockTransport` in `browser_runner.py` with strict schema validation against Meta Spark 1.3 prompt and response contracts.
- **Initial badge:** `Standard mode · Meta muse-spark-1.3`
- **Video playback:** 83 decoded frames, 5 callback presented frames, seek 3.06s, zero media errors
- **Keyboard navigation:** Enter on note card opens evidence quote and inspects without bubbled selection clearing
- **Mobile responsiveness:**
  - Viewport 375px: document scrollWidth 375px (`overflow375: false`)
  - Viewport 320px: document scrollWidth 320px (`overflow320: false`)
  - Note cards, trust manifest, and delete controls fully visible at 320px
- **Foreign isolation:** HTTP 401 Unauthorized for unauthenticated requests
- **Deletion:** Complete (`App-owned copies removed`)
- **Result:** `PASS`, saved to `browser-standard-results.json`

#### Recorded Mode Journey (`node browser_check.cjs recorded`)
- **Harness Failure & Resolution:** Initial recorded test attempt failed with `Trust mode text mismatch` in `browser-recorded-results.json` because `App.tsx` rendered `"recorded (Standard Meta Spark 1.3)"` instead of `"Recorded replay"`. After updating `App.tsx:1270` to render `{report.trust.mode === 'standard' ? 'Standard inference' : 'Recorded replay'}` and rebuilding, the recheck passed completely.
- **Initial badge:** `Recorded mode · Standard Meta Spark 1.3`
- **Video playback:** 168 decoded frames, 4 callback presented frames, seek 3.00s, zero media errors
- **Keyboard navigation:** Evidence opened by keyboard = true
- **Mobile responsiveness:**
  - Viewport 375px: document scrollWidth 375px (`overflow375: false`)
  - Viewport 320px: document scrollWidth 320px (`overflow320: false`)
- **Config-switch persistence check:**
  - Server runtime switched to `provider_mode = "standard"`
  - Page reloaded with saved recorded report
  - Badge preserved: `Recorded mode · Standard Meta Spark 1.3`
  - Trust details preserved: `Recorded replay (Recorded inference · exact original media)`, `0 live calls / $0.00 (Recorded replay)`
  - Persona library notice preserved: 3 simulated viewers / synthetic persona library / not representative audience
- **Foreign isolation:** HTTP 401 Unauthorized
- **Deletion:** Complete
- **Result:** `PASS`, saved to `browser-recorded-results.json`

---

## Test Doubles and Production Boundaries
- **Mocked Boundaries:** External Meta inference HTTP endpoint (`https://api.meta.ai/v1/responses`) mocked using `httpx.MockTransport` in tests and browser runner to prevent unauthorized spend or live network access.
- **Production Components Exercised:** Production FastAPI routes (`/videos`, `/runs`, `/events`, `/reports`, `/deletions`, `/sessions`), production database layer (`db.py`, PostgreSQL connection pool, session advisory locks), production private storage (`Storage` class with S3/RustFS backend), production worker loop (`process_once`, `fence`, `reserve_object`, `put_reserved`), production report builder (`build_report`), production React 19 frontend bundle (`apps/web/dist`).
- **Limitations:** No live provider keys or paid inference executed. Upstream provider backup erasure cannot be verified without provider-side API support. Mobile layout verified at 375px and 320px viewport widths with zero horizontal document overflow; full WCAG AAA audit not performed.
