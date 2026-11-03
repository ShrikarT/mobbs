# V03 Bounded Independent-Persona Execution — Author Evidence Record

Task: **V03-P1** (`task_f42dd28fa84c`, dispatch `ctx_25ac981d707b`, run `run_d3354faa0659`).  
Author: Antigravity (worker terminal `term_94ec81bb-df1d-4a9e-91c6-144de54507c1`).  
Coordinator: Codex (terminal `term_fae0b73c-b257-4674-aa24-b5f6df0ea7aa`).  
Assigned worktree: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-bounded-pool` on branch `codex/v03-bounded-pool`.  
Exact clean baseline: `ecdcdde59fafda223af4374f15704fe953158e26`.  

**Outcome: WORKER-REPORTED.** Submitted for independent review.  
No live provider spend, paid requests, or external network calls to paid model endpoints occurred in this run. All provider verification was conducted using controlled `httpx.MockTransport` doubles and recorded fixtures against production PostgreSQL 16 (`viralist_v03_pool`) and RustFS S3 storage (`viralist-v03-pool`).

---

## Executive Summary of Implementation & Findings

This implementation fulfills the V03-P1 objective: executing independent personas concurrently to complete the 50-instance Flash simulation substantially faster while strictly preserving sequential scene decisions per persona, lease heartbeat renewal, fencing, and truthful provenance:

1. **Additive Manifest Field & Strict Integer Validation (`apps/api/app/reporting.py`):**
   - Added `provider_concurrency` to the server-sealed run manifest:
     - Standard Flash: `8`
     - Standard Test: `1`
     - Recorded Replay: `1`
     - Missing / legacy manifests: defaults cleanly to `1`.
   - Validated strictly in `build_manifest`: rejects booleans (`True`/`False`), floats (`1.0`), strings (`"8"`), and values outside the integer range `1..8` with `ValueError`.
   - Preserves compatibility and report trust provenance (`report.trust.provider_concurrency`).

2. **Bounded Independent-Persona Pool Execution (`apps/api/app/worker.py`):**
   - For `provider_concurrency > 1`, `execute_persona_pool` runs active personas using a `ThreadPoolExecutor(max_workers=provider_concurrency)`.
   - **Per-Persona Sequential Invariant:** Within any individual persona, scenes execute sequentially. A persona's scene $S+1$ is never submitted until scene $S$ completes and updates the database checkpoint (`next_scene`).
   - **Cross-Persona Concurrency:** Independent personas with available scenes at the current scene frontier execute concurrently across available worker threads.
   - For legacy / serial execution (`provider_concurrency == 1`), `execute_persona_serial` executes stepping ordered by scene frontier (`ORDER BY next_scene ASC, persona_id ASC LIMIT 1`).

3. **Global Standard HTTP Concurrency Gate across DB Sessions (`apps/api/app/worker.py`):**
   - Enforced via PostgreSQL advisory locks across 8 dedicated keys: `58004001..58004008`.
   - For `limit == 1`, acquires a blocking lock on `58004001` (`SELECT pg_advisory_lock(58004001)`), ensuring waiting sessions are visible in `pg_locks` (`NOT granted`) for deadlock-free single-slot queueing.
   - For `limit > 1`, iterates non-blocking try-locks across slots `58004001` through `58004001 + limit - 1` (`SELECT pg_try_advisory_lock(...)`) with a 10ms sleep backoff until a slot is acquired.
   - Total aggregate standard provider HTTP calls across any number of OS worker processes sharing the database are strictly bounded at $\le 8$.

4. **Post-Wait Fencing & Zero Post-Fence HTTP:**
   - Immediately after acquiring an advisory slot and before making outbound HTTP calls, `fence(gate_conn, lease)` checks video status, tombstone, job generation, and lease validity.
   - If a video is deleted or job cancelled while waiting in the advisory queue, `LeaseLost` is raised and caught cleanly without issuing any HTTP requests.

5. **Lease Heartbeat Renewal During Pool Execution:**
   - `LeaseRenewalThread` runs concurrently during pool execution, pulsing `renew_lease` every 5 seconds as long as worker threads are active.
   - Prevents lease expiry during long multi-persona batches without extending the base lease TTL.

6. **Partial Failure & Clean In-Flight Drain:**
   - On provider HTTP failure (e.g., 429 rate limit or transport timeout), the pool stops scheduling new scene tasks (`stop_event.set()`), waits for already in-flight HTTP calls to drain cleanly, and marks the run failed with appropriate failure codes (`provider_rate_limited` or `uncertain_provider_charge`).

7. **Recorded Replay Marker Reuse & Video Scope Binding:**
   - In recorded replay mode, existing `dispatched` checkpoints are matched and reused without duplicate `INSERT` constraint collisions or spin loops.
   - Corrected video scope binding in `execute_persona_scene` to bind `video = fence(conn, lease)` unconditionally at the top of the connection block, eliminating `UnboundLocalError` in non-standard execution paths.
   - Wrapped durable notes byte retrieval from S3 Storage in `try...except Exception:` to ensure missing storage objects visibly pause with `error_code='missing_durable_notes_output'` without unhandled crashes.

8. **Frozen Interface Preservation:**
   - Kept exact signature: `process_once(provider_factory=None, before_publish=None)`.
   - No migrations added (001-003 preserved).
   - No dependencies or lockfiles modified.

---

## Verification Evidence

### 1. Bounded Pool Acceptance Suite (`tests.test_v03_bounded_pool`)
- **Command:**
  ```powershell
  $env:VIRALIST_RUNTIME = 'C:\Users\Shrikar\.codex\viralist-v03-pool\runtime.json'
  C:\Users\Shrikar\.codex\viralist-v02-review\venv\Scripts\python.exe -m unittest tests.test_v03_bounded_pool -v
  ```
- **Exit Code:** `0`
- **Output:**
  ```
  Ran 11 tests in 311.445s
  OK
  ```
- **Test Inventory & Verified Results:**
  1. `test_checkpoint1_compilation_and_real_pg_concurrent_path_proof`:
     - Result: `CP1 PROOF: max_observed_concurrency=3, total_calls=400, duration=72.282s`
     - Validates: Real 50-persona 8-scene run with concurrent execution across real PostgreSQL 16 database.
  2. `test_compatibility_and_provenance`:
     - Validates: Missing `provider_concurrency` defaults to 1, report trust block retains `provider_concurrency=1`, and report structure is intact.
  3. `test_cross_process_concurrency_bound_and_slot_waiter`:
     - Validates: Child 1 holding all 8 slots causes Child 2 to queue visibly in `pg_stat_activity` / `pg_locks`. When deleted, Child 2 exits with 0 outbound HTTP calls.
  4. `test_cross_process_normal_release_aggregate_concurrency_bounded_at_8`:
     - Validates: Two independent OS worker processes executing Flash 400 calls concurrently against PostgreSQL never exceed aggregate concurrency of 8 (`max_aggregate_locks_observed=8`).
  5. `test_isolation_and_no_future_or_peer_leakage`:
     - Validates: Personas maintain strict isolation. No scene $S$ receives data from scene $S+1$, and peer personas do not leak decisions into other personas.
  6. `test_kill_child_with_unresolved_units_does_not_resend_and_marks_failed`:
     - Validates: Killing a child worker with in-flight unresolved units leaves them marked uncertain; a subsequent worker run does not blindly re-dispatch them and fails with `uncertain_provider_charge`.
  7. `test_lease_renewal_during_pool_execution`:
     - Validates: Background lease heartbeat renews lease TTL during active pool processing.
  8. `test_manifest_integer_validation`:
     - Validates: Strict validation for integer `1..8`. Rejects `True`, `False`, `1.5`, `"8"`, `0`, and `9`.
  9. `test_partial_failure_stops_admission_and_in_flight_drains`:
     - Validates: Provider 429 stops admission of new tasks and drains running calls cleanly.
  10. `test_pool_helps_wall_time_lower_than_serial_and_events_stream_early`:
      - Result: `Concurrency 8: 12.312s vs Serial: 29.406s -> 2.39x speedup`
      - Validates: Significant wall-clock speedup for bounded pool vs serial stepping while streaming progress events early.
  11. `test_recorded_replay_reuses_dispatched_marker_without_duplicate_insert`:
      - Validates: Replaying recorded runs reuses existing dispatched markers without unique key violation or endless loop.

### 2. Standard App Regression Suite (`tests.test_v03_standard_app`)
- **Command:**
  ```powershell
  $env:VIRALIST_RUNTIME = 'C:\Users\Shrikar\.codex\viralist-v03-pool\runtime.json'
  C:\Users\Shrikar\.codex\viralist-v02-review\venv\Scripts\python.exe -m unittest tests.test_v03_standard_app
  ```
- **Exit Code:** `0`
- **Output:**
  ```
  Ran 18 tests in 155.409s
  OK
  ```
- **Verified Regressions:** All 18 existing Standard app tests pass cleanly, including:
  - Post-wait deletion zero second HTTP test (`test_post_wait_deletion_yields_zero_second_http`).
  - Safe malformed usage receipt and canary redaction.
  - Registered notes recovery across restarts.
  - Immutable manifest sealing and mode isolation.

### 3. Flash Backend Suite in Recorded Mode (`tests.test_v03_flash_backend`)
- **Command:**
  ```powershell
  $env:VIRALIST_RUNTIME = 'C:\Users\Shrikar\.codex\viralist-v03-pool\runtime.json'
  $env:VIRALIST_PROVIDER_MODE = 'recorded'
  C:\Users\Shrikar\.codex\viralist-v02-review\venv\Scripts\python.exe -m unittest tests.test_v03_flash_backend
  ```
- **Exit Code:** `0`
- **Output:**
  ```
  Ran 14 tests in 126.618s
  OK
  ```
- **Verified Compatibility:** Zero regression in recorded 50-persona Flash simulation, archetype derivation, and reporting.

### 4. Frontend Assets Build
- **Command:**
  ```powershell
  pnpm run build
  ```
- **Exit Code:** `0`
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
  apps/web/dist/assets/index-Bg0LEYay.js   264.27 kB │ gzip: 79.79 kB
  ✓ built in 364ms
  ```

### 5. Python Syntax Compilation
- **Command:**
  ```powershell
  python -m py_compile apps/api/app/reporting.py apps/api/app/worker.py tests/test_v03_bounded_pool.py tests/v03_pool_worker.py
  ```
- **Exit Code:** `0`

---

## Mock Boundaries vs. Production Components

- **Production Components Exercised:**
  - Real PostgreSQL 16 database running on `127.0.0.1:55432` with transactional tables, advisory locking (`pg_advisory_lock`, `pg_try_advisory_lock`, `pg_locks`, `pg_stat_activity`), schema migrations 001-003.
  - Real RustFS S3 storage on `127.0.0.1:59000` (`viralist-v03-pool` bucket) for notes bytes and report uploads.
  - Real multi-threaded and multi-process OS execution using `subprocess.Popen` and `ThreadPoolExecutor`.
- **Mocked Boundaries:**
  - External Google Gemini API HTTP endpoints are mocked with deterministic `httpx.MockTransport` test doubles simulating latency (e.g., 30ms-50ms), token counts, and structured JSON responses.
  - No real network egress or API charges were incurred.

---

## Files Modified

- `apps/api/app/reporting.py`: Added `provider_concurrency` to run manifest with strict integer validation (`1..8`).
- `apps/api/app/worker.py`: Added bounded thread pool execution for independent personas, global PostgreSQL advisory lock slots (`58004001..58004008`), background lease renewal thread, safe video scope binding, and scene-frontier ordering.
- `tests/test_v03_bounded_pool.py`: 11 comprehensive acceptance tests verifying compilation, pool speedup, aggregate cross-process concurrency bounds, slot waiter observability, partial failure draining, lease renewal, isolation, and recorded replay marker reuse.
- `tests/v03_pool_worker.py`: Subprocess worker helper for cross-process concurrency verification.
- `docs/evidence/v03-bounded-pool.md`: Durable author evidence record.
