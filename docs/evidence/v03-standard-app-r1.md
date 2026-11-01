# V03 Standard provider to app — Correction 1 author evidence record

Task: **V03-LIVE-APP Correction 1** (`task_091b0d0a88c4`, dispatch `ctx_1d206fe9da4f`, run `run_d3354faa0659`).  
Parent original task: `task_3a9951dd9175` (author `ctx_718343708607`, candidate `9c4e07c`).  
Review: `task_4f7cb3e4da43` / `ctx_57ac41c1d5bd` REVISE.  
Author: Antigravity (worker terminal `term_b87aa961-ce0e-497b-9472-cb743528d4f2`).  
Coordinator: Codex (terminal `term_8353d8d9-3f50-4105-a0d0-cca9af044f66`).  
Assigned worktree: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-standard-app` on branch `codex/v03-standard-app-r1`.  
Exact clean baseline: `9c4e07c2ebe0462fcb17c05a6bf1e6675e154a9a`.  

**Outcome: WORKER-REPORTED.** Submitted for independent review.  
No live provider spend, paid requests, or network access to external endpoints performed; all provider interactions were verified via controlled `httpx.MockTransport` test doubles with fail-closed server defaults. Custom accounting remains deferred at `ba6af92`—no financial subsystem or SQL004 schema introduced.

---

## Executive Summary of Corrections

1. **Finding 1 — Notes Recovery Across Process Restart (`worker.py`):**
   - On new notes generation, the raw JSON response is registered via `reserve_object` / `put_reserved`, and durable normalized output (`audit['normalized']`, `object_key`, `response_sha256`) and safe receipt are persisted in `provider_calls` before publication and before the `before_publish` fault boundary.
   - On process restart, worker checks for an existing `accepted` notes call before new call ceiling or admission checks.
   - Identical durable output is recovered from `audit['normalized']` and published without a 2nd HTTP request (HTTP count unchanged, e.g. 18→18).
   - Recovery at ceiling equality (`call_count == max_calls`) succeeds without triggering `run_call_ceiling_exceeded`.
   - The recovered receipt is not appended twice to `usage_ledger`, preserving honest live calls and total cost.
   - If an accepted notes call row lacks durable output, the run fails visibly with `error_code='missing_durable_notes_output'` with no resend.

2. **Finding 2 — Missing & Inconsistent Usage Handling (`standard_provider.py`, `reporting.py`, `worker.py`):**
   - Completed provider envelopes with `usage is None` are accepted with `cost_usd=None` and surface in reports as `trust.total_cost_usd = 'unavailable'` (never numeric $0.0).
   - Inconsistent token counts (`total_tokens != input_tokens + output_tokens`) fail normalization with `ProviderUnavailable('provider_response_rejected', charge_state='uncertain')`.
   - Error receipts preserve safe allowlisted IDs (`request_id`, `response_id`, `requested_model`), HTTP status, and returned raw `usage` structure without prose or raw error text.
   - Uncertain outcomes trigger `set_operational_pause()`, which durably stops subsequent Standard admissions across runs without making any new provider HTTP requests (`next_run_http_calls == 0`).
   - Historical carried fixtures are isolated from new unresolved calls.

3. **Finding 3 — Enforced Concurrency Gate (`worker.py`):**
   - Implemented `standard_concurrency_gate()` utilizing PostgreSQL session advisory lock `pg_advisory_lock(58004001)` on a dedicated autocommit connection.
   - The gate wraps verdict and notes inference execution across worker processes, strictly enforcing at most 1 active Standard generation simultaneously without holding video or job row transactions across inference.
   - Verified with concurrent worker threads against real PostgreSQL with mock transport: maximum active concurrent requests was exactly 1.

4. **Finding 4 — Error & Transport Sanitization (`standard_provider.py`, `worker.py`):**
   - `sanitize_error_receipt()` extracts only fixed allowlisted codes (`provider_timeout`, `provider_transport_error`, `provider_http_error`, `provider_response_rejected`), exception class name, and allowlisted IDs/status/usage.
   - Synthetic secrets/canaries embedded in `httpx.ReadTimeout` or transport exceptions are never copied into database `receipt` or `audit` fields.

5. **Finding 5 — UI & API Truthful Disclosures (`App.tsx`, `types.ts`, `main.py`):**
   - `POST /sessions` returns `provider_mode = settings().provider_mode`.
   - `App.tsx` derives operating mode from report trust, run manifest, or session.
   - Header badge renders `Standard mode · Meta muse-spark-1.3` when in standard mode.
   - Upload desk operating disclosure honestly distinguishes live Standard inference (`Meta muse-spark-1.3`, bounded calls, concurrency 1, sequential scene simulation without calibration or whole-video understanding) from Recorded replay (`exact hash-bound recorded inference`).
   - Report trust block renders `Live provider calls` and `Estimated cost (USD)` for Standard mode, displaying numeric costs or strings (`unavailable` / `uncertain`), never false $0.00.
   - Flash 50 cast disclosure accurately cites 50 candidate persona policies from `fifty-policies.json` without claims of 5 archetypes or human calibration.

---

## Verification Evidence

### 1. Project Build & Typecheck
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
  apps/web/dist/assets/index-D0k30bS2.css   18.90 kB │ gzip:  4.06 kB
  apps/web/dist/assets/index-DdHy-JBA.js   262.79 kB │ gzip: 79.61 kB
  ✓ built in 272ms
  ```
- **Exit code:** 0.

### 2. Unit and Subsystem Tests
- **Normalized Contract Suite (`tests.test_normalized`):**
  - Command: `python -m unittest tests.test_normalized`
  - Result: `Ran 14 tests in 0.019s OK` (Exit code 0).
- **API Security Isolation Suite (`tests.test_api_security_isolation`):**
  - Command: `python -m unittest tests.test_api_security_isolation`
  - Result: `Ran 9 tests in 3.016s OK` (Exit code 0).
- **Domain Integration Suite (`tests.test_domain_integration`):**
  - Command: `python -m unittest tests.test_domain_integration`
  - Result: `Ran 4 tests in 1.657s OK` (Exit code 0).

### 3. V03 Standard App Suite (`tests.test_v03_standard_app`)
- **Command:**
  `powershell -Command "$env:VIRALIST_RUNTIME = 'C:/Users/Shrikar/.codex/viralist-v03-standard-app/runtime.json'; $env:MODEL_API_KEY = 'DUMMY_KEY'; $env:PYTHONDONTWRITEBYTECODE = '1'; python -m unittest tests.test_v03_standard_app"`
- **Result:**
  ```
  .................
  ----------------------------------------------------------------------
  Ran 17 tests in 186.748s

  OK
  ```
- **Exit code:** 0.
- **Specific Regression Tests Exercised:**
  1. `test_notes_recovery_across_restart_no_generation`:
     - Injected child exit 72 at `before_publish` hook after notes call was accepted.
     - Fresh child reclaimed expired lease and finished run.
     - Total notes HTTP requests remained 1 (did NOT increase 1→2).
     - Total verdicts HTTP requests remained 17.
     - Report completed with 0 duplicate receipts, live calls 18.
     - Ceiling check equality (`call_count == 18 == max_calls`) verified.
     - Accepted notes row with missing durable output verified to fail visibly with `missing_durable_notes_output` with 0 HTTP calls.
  2. `test_missing_and_inconsistent_usage`:
     - Null usage (`usage=None`) verified: report trust returned `total_cost_usd='unavailable'` (never 0.0).
     - Inconsistent usage (`total_tokens != input + output`) verified: call marked failed with `charge_state='uncertain'`, safe usage and `response_id` preserved, run failed with `uncertain_provider_charge`.
     - Operational pause verified: subsequent Standard run stopped admissions with 0 provider calls (`next_run_http_calls == 0`).
  3. `test_concurrency_gate_enforces_single_active_generation`:
     - Two concurrent worker threads executing `process_once` against real PostgreSQL verified: `max_active == 1` across all provider requests.
  4. `test_canary_redaction_transport_error`:
     - Sensitive canary `SYNTHETIC_SECRET_CANARY_X998877` in `httpx.ReadTimeout` verified absent from DB receipt and audit; allowlisted code `provider_transport_error` and `charge_state='uncertain'` recorded.
  5. `test_ui_disclosures_truthful`:
     - `/sessions` returns `provider_mode='standard'`.
     - Standard provenance verified: 50 candidate persona policies without false calibration or archetype claims.
  6. `test_standard_worker_end_to_end_test_profile`:
     - 3-persona sequential execution with mock transport doubles verified complete.
  7. `test_standard_worker_50_persona_flash_full_journey`:
     - 50-persona Flash journey verified: 10 stopped at scene 0, 40 completed 8 scenes, 331 total calls with honest report trust.

---

## Changed Files
- `apps/api/app/main.py`: Updated `/sessions` to return `provider_mode`.
- `apps/api/app/reporting.py`: Honest `total_cost_usd` classification (`unavailable`, `uncertain`, or numeric cost).
- `apps/api/app/standard_provider.py`: Safe exception handling, `charge_state='uncertain'` for HTTP >= 500 and malformed usage, safe receipt preservation.
- `apps/api/app/worker.py`: Concurrency gate (`pg_advisory_lock`), error receipt sanitization, operational pause helpers, notes recovery before ceiling check with durable response reuse, and visible failure on missing durable output.
- `apps/web/src/types.ts`: `SessionResponse.provider_mode` and `TrustManifest.total_cost_usd` / `pricing_version`.
- `apps/web/src/App.tsx`: Truthful mode derivation, header badge, operating disclosure, trust metrics (live calls and estimated cost), and Flash 50 candidate policies disclosure.
- `tests/test_v03_standard_app.py`: Comprehensive regressions for findings 1 through 5.
- `docs/evidence/v03-standard-app-r1.md`: This evidence document.
