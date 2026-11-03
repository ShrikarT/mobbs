# V03 Standard correction 2 independent review: ACCEPT

- **Task ID:** `task_26ddf5d5a867`
- **Dispatch ID:** `ctx_2c29ac03ada8` (continuation from `ctx_0b8054e5d203`)
- **Terminal ID:** `term_01374029-5881-4e28-b2f2-eebe511aea8d`
- **Run ID:** `run_d3354faa0659`
- **Reviewer:** Independent Antigravity verification engineer (continuation authorized under `175bba6` and `msg_179fe6687aaf`)
- **Author:** Antigravity implementation (`task_e952bf64a6cc` / `ctx_f64ce39b3cb2`, worker_done `msg_68b9baea87b9`)
- **Worktree:** `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-standard-review`
- **Branch:** `codex/v03-standard-r2-review`
- **Exact Clean Reviewed Revision:** `c714c2c0e2f0e1f0ef8c618b22bc05004551f556`
- **Base Revision:** `5f5fe3ac3129521f5efecd66c2ec842b897bda4c` (correction 1 candidate, REVISE)
- **Diff:** `5f5fe3ac3129521f5efecd66c2ec842b897bda4c..c714c2c0e2f0e1f0ef8c618b22bc05004551f556` (7 paths)
- **Review Date:** 2026-11-02

---

## Decision

**ACCEPT.**

Candidate revision `c714c2c0e2f0e1f0ef8c618b22bc05004551f556` advances from **WORKER-REPORTED** to **REVIEW-ACCEPTED**.

All four numbered product blockers from correction 1 review (`v03-standard-app-r1-independent-review.md`) and the mobile responsive layout addendum are independently verified resolved at the exact committed revision without product regressions:
1. **Finding 1 (P1 Gate wait/deletion):** Post-semaphore atomic fence (`domain.fence(gate_conn, lease)`) validates video and lease state after advisory lock acquisition and closes the transaction before HTTP. Cancelled, deleted, or stale waiters dispatch ZERO HTTP requests and leave no receipt.
2. **Finding 2 (P2 Malformed receipt privacy):** `sanitize_usage()` allowlists strictly primitive numeric token fields; arbitrary diagnostic prose, extra keys, and canaries are completely redacted from durable receipts, audits, and public API envelopes. `response_id` is preserved. Missing/invalid usage fails honestly as `uncertain_provider_charge`.
3. **Finding 3 (P2 Notes restart integrity):** Raw notes response bytes are registered in `Storage` alongside `response_sha256`. A recovering child loads registered bytes via production `Storage.get()`, verifies SHA-256 match, and normalizes the envelope with ZERO duplicate HTTP calls. Storage faults or hash mismatches fail visibly with `error_code='missing_durable_notes_output'`.
4. **Finding 4 (P2 Saved provenance):** `effectiveMode` strictly enforces precedence: saved report provenance (`report.trust.mode`) first, sealed manifest (`runState.manifest.provider_mode`) second, session config only for initial empty state. A recorded report reloaded after server configuration switches to Standard preserves `"Recorded mode"`, `"Recorded replay"`, `0 live calls / $0.00`, and 5-archetype disclosure.
5. **Finding 5 (Mobile Layout Addendum):** Setting `min-width: 0; width: 100%` on grid/flex items and applying `overflow-wrap: anywhere; word-break: break-word` resolves the historical 610px document overflow without hiding content. Viewports at 375px and 320px fit document scrollWidth exactly (0px overflow), controls and evidence remain reachable and operational by keyboard, and 1280px desktop hierarchy is preserved.

---

## Continuation Lineage & Evidence Attribution

In accordance with continuation contract `175bba6:docs/evidence/v03-standard-app-r2-review-assignment.md` and coordinator directive `msg_179fe6687aaf`:
- **Original Partial Verification (Codex reviewer, dispatch `ctx_0b8054e5d203`):**
  - Executed candidate test suites: 18 Standard tests in `tests/test_v03_standard_app.py` (222.627s, exit 0) and 28 normalized/Flash tests in `tests/test_v03_flash_backend.py` (112.415s, exit 0). Total 46 tests passed exit 0.
  - Executed frontend production build: `cmd /c pnpm run build` (`tsc -p apps/web/tsconfig.json && vite build --config apps/web/vite.config.ts`, 198ms, exit 0).
  - Verified lockfile/source byte equality across 17 source files matching committed dependencies (`build-source-files.json`).
  - Verified `git diff --check`: zero code whitespace issues; harmless markdown trailing whitespace in author evidence.
  - The dispatch was interrupted by provider quota limits and fenced without code rejection.
- **Continuation Verification (Antigravity reviewer, dispatch `ctx_2c29ac03ada8`):**
  - Verified repository and resource quiescence: clean working tree on `codex/v03-standard-r2-review`, port 58005 free, database `viralist_v03_standard_r2_review` (schema version 3) and RustFS bucket `viralist-v03-standard-r2-review` healthy.
  - Preserved the 46 passing suite results with explicit attribution.
  - Executed independent fault and boundary controls across 12 distinct scenarios in `controls.py`, saving observable results to `controls-results.json` (exit 0).
  - Executed live browser inspection via `browse` CLI and full Playwright test journeys in both Standard and Recorded modes via `browser_check.cjs`, saving results to `browser-standard-results.json` and `browser-recorded-results.json` (exit 0).
  - Captured 7 full-page screenshots across desktop, 375px, 320px, and config-switch states.

---

## Detailed Item Verification

### 1. Gate Wait Deletion & Stale Fence (Finding 1)
- **Component Under Test:** `apps/api/app/worker.py:313-317, 465-470` (`process_analysis` verdict and notes paths).
- **Mechanism:**
  - In both verdict and notes blocks under Standard mode, worker acquires `standard_concurrency_gate()` (PostgreSQL advisory lock `58004001`).
  - Immediately following acquisition, a dedicated autocommit transaction runs `video = fence(gate_conn, lease)`, revalidating video deletion tombstone, job status, generation, and lease expiry.
  - If video was deleted or job cancelled/rescheduled, `LeaseLost` is raised and caught by `process_once` (exiting cleanly without outbound HTTP, without publication, and without persisting error receipts).
- **Independent Control Evidence (`controls-results.json`):**
  - `gate-verdict-normal`: Child 1 holds first HTTP; Child 2 enters gate queue and is observed in PG `pg_locks` (`waiting: true`). On normal release, Child 2 proceeds, dispatches 1 HTTP request (`second_http: 1`), receives accepted receipt, child exits `[0, 0]`.
  - `gate-verdict-delete`: Child 2 waiting on gate; video deleted via owner API `DELETE /videos/{id}` (status 202). Child 1 released. Child 2 executes fence, raises `LeaseLost`, dispatches ZERO HTTP requests (`second_http: 0`), persists NO receipt (`receipt: null`), marker remains `dispatched`, child exits `[0, 0]`.
  - `gate-verdict-stale`: Child 2 waiting on gate; job generation bumped in DB (`update jobs set generation=generation+1`). Child 2 dispatches ZERO HTTP requests (`second_http: 0`), child exits `[0, 0]`.
  - `gate-notes-delete`: Child 2 waiting at notes gate; video deleted. Child 2 dispatches ZERO HTTP requests (`second_http: 0`), child exits `[0, 0]`.
  - `gate-notes-stale`: Child 2 waiting at notes gate; job generation bumped. Child 2 dispatches ZERO HTTP requests (`second_http: 0`), child exits `[0, 0]`.

### 2. Malformed Receipt Privacy & Response Identity (Finding 2)
- **Component Under Test:** `apps/api/app/standard_provider.py:119-136, 306, 438`, `apps/api/app/worker.py:202-204`.
- **Mechanism:**
  - `sanitize_usage(raw)` filters raw usage dictionaries, allowlisting only `input_tokens`, `output_tokens`, `total_tokens`, `cached_tokens`, and `reasoning_tokens` (with validation that values are numeric and not boolean).
  - Nested details (`input_tokens_details.cached_tokens`, `output_tokens_details.reasoning_tokens`) are safely extracted if present.
  - In `sanitize_error_receipt()`, `response_id` is explicitly preserved alongside `request_id`, `requested_model`, and `http_status`.
- **Independent Control Evidence (`controls-results.json`):**
  - `privacy-verdict`: Injected synthetic canary `SYNTHETIC_PRIVATE_PROSE_CANARY` in `usage.diagnostic`, `usage.extra`, and `input_tokens_details.prose` with inconsistent `total_tokens`.
    - Canary completely absent from persisted row (`receipt` and `audit`) and from public API (`/runs/{id}` and `/runs/{id}/report`).
    - `response_id` preserved (`resp_safe_independent_verdict`).
    - Numeric usage fields preserved (`input_tokens: 1500, total_tokens: 1701`).
    - Run status failed with `error_code='uncertain_provider_charge'`.
  - `privacy-notes`: Injected canary in notes malformed envelope.
    - Canary completely absent.
    - `response_id` preserved (`resp_safe_independent_notes`).
    - Status failed with `uncertain_provider_charge`.

### 3. Notes Integrity Across Restart (Finding 3)
- **Component Under Test:** `apps/api/app/worker.py:408-448, 492-501`.
- **Mechanism:**
  - On accepted notes generation, raw response bytes are stored in `Storage` via `put_reserved`, and `response_sha256` is recorded in both `receipt` and `audit`.
  - On restart recovery, the worker checks for `object_key` and `stored_sha`. It reads raw bytes via `Storage.get(object_key)['Body'].read()`, verifies `hashlib.sha256(raw_bytes).hexdigest() == stored_sha`, and calls `normalize_envelope(raw_json, rec_input)` with `http_status=200`.
  - If object is missing, unreadable, or hash fails to match, worker records `error_code='missing_durable_notes_output'` and marks the run failed without reissuing provider HTTP.
- **Independent Control Evidence (`controls-results.json`):**
  - `notes-success`: Worker crashed via injected fault (exit 72) after notes receipt. Fresh child started. Production `Storage.get()` executed (`notes_reads: 1`), SHA-256 matched, output normalized, report completed with 1 note and `live_calls: 4`. Before/after HTTP dispatches were identical (`http_before: 4, http_after: 4`, ZERO duplicate calls).
  - `notes-read`: Injected `OSError` on `Storage.get()`. Fresh child executed, failed visibly with `status='failed'`, `error_code='missing_durable_notes_output'`, ZERO extra HTTP (`http_before: 4, http_after: 4`).
  - `notes-missing`: Injected `NoSuchKey` on `Storage.get()`. Failed visibly with `status='failed'`, `error_code='missing_durable_notes_output'`, ZERO extra HTTP.
  - `notes-hash`: Injected corrupted payload bytes on `Storage.get()`. Failed visibly with `error_code='missing_durable_notes_output'`, ZERO extra HTTP.
  - `notes-legacy`: Legacy row with empty audit/missing object key. Failed visibly with `error_code='missing_durable_notes_output'`, ZERO extra HTTP (`notes_reads: 0`).

### 4. Saved Provenance Precedence & Truthful Library Disclosures (Finding 4)
- **Component Under Test:** `apps/web/src/App.tsx:578-583, 590, 675, 1270, 1305, 1324-1342`.
- **Mechanism:**
  - `effectiveMode = useMemo(() => { if (report?.trust?.mode) return report.trust.mode; if (runState?.manifest?.provider_mode) return runState.manifest.provider_mode; return session?.provider_mode || 'recorded'; }, ...)`
  - Persona library disclosures:
    - Standard Flash: 50 fictional candidate persona policies from `fifty-policies.json`.
    - Standard Test: 3 fictional candidate persona policies.
    - Recorded Flash: 50 simulated personas derived from 5 archetypes.
    - Recorded Test: 3 simulated viewers.
  - All disclosures clearly identify that audience outcomes are simulated and uncalibrated against human viewers.
- **Browser Verification Evidence (`browser-recorded-results.json`):**
  - Replayed recorded report with server configuration switched to Standard (`provider_mode='standard'`).
  - On page reload under Standard server:
    - Header badge retained: `"Recorded mode · Standard Meta Spark 1.3"`.
    - Trust block retained: `"Inference mode: Recorded replay (Recorded inference · exact original media)"`.
    - Spend disclosure retained: `"0 live calls / $0.00 (Recorded replay)"`.
    - Library disclosure retained: 3 simulated viewers (not 50 candidate policies).
    - Screenshot verified: `browser-recorded-config-switch.png`.

### 5. Mobile Responsive Layout & Reachability (Finding 5)
- **Component Under Test:** `apps/web/src/style.css:50-65, 319-335, 391-397, 426-430, 987-992, 1246-1355`.
- **Mechanism:**
  - Grid and flex columns configured with `min-width: 0; width: 100%` on `.workbench-grid > *`, `.player-column`, `.evidence-column`, `.timeline-segment`, and cards.
  - Long text and monospace containers configured with `overflow-wrap: anywhere; word-break: break-word`.
  - Responsive padding, single-column wrapping, and font scaling at `@media (max-width: 639px)` and `@media (max-width: 360px)`.
- **Browser Journey Evidence (`browser-standard-results.json`, `browser-recorded-results.json`):**
  - **375px Viewport:**
    - Standard: `viewport: 375, document: 375` (0px overflow).
    - Recorded: `viewport: 375, document: 375` (0px overflow).
  - **320px Viewport:**
    - Standard: `viewport: 320, document: 320` (`mobileOverflow: false`).
    - Recorded: `viewport: 320, document: 320` (`mobileOverflow: false`).
    - Clipped/overflowing elements check: `mobileControls: []` (0 elements with `left < -1` or `right > innerWidth + 1`).
    - Timeline segments fit within bounds without breaking layout (`overflow: hidden; text-overflow: ellipsis`).
  - **Interaction & Reachability at 320px:**
    - Keyboard note selection: Focus note card, press `Enter` -> player seeks to timestamp (`3.02s` in Standard, `3.00s` in Recorded).
    - Keyboard evidence expansion: Focus quote button, press `Enter` -> `.evidence-inspector-card` opens with full simulated reason.
    - Deletion reachable: Button `Delete video & report` and modal `Confirm deletion` accessible and clickable at 320px; completed with `"App-owned copies removed"`.
  - **Real Video Playback:**
    - Video playback verified via `requestVideoFrameCallback` and `getVideoPlaybackQuality().totalVideoFrames`:
      - Standard: 79 decoded frames, 4 presented callbacks, `readyState: 4`, `error: null`.
      - Recorded: 169 decoded frames, 4 presented callbacks, `readyState: 4`, `error: null`.
  - **Cross-Session Isolation:**
    - Requesting `/videos/{id}/analysis` from unauthenticated context returns HTTP 401.

---

## Artifact Inventory & Verification Environment

- **Screenshots:**
  - `browser-standard-desktop.png` (1280x900 full page, 304 KB)
  - `browser-standard-375.png` (375x900 full page, 244 KB)
  - `browser-standard-mobile.png` (320x900 full page, 243 KB)
  - `browser-recorded-desktop.png` (1280x900 full page, 256 KB)
  - `browser-recorded-375.png` (375x900 full page, 221 KB)
  - `browser-recorded-mobile.png` (320x900 full page, 219 KB)
  - `browser-recorded-config-switch.png` (1280x900 full page, 255 KB)
- **JSON Results:**
  - `controls-results.json` (12 passing scenarios)
  - `browser-standard-results.json` (`status: "PASS"`)
  - `browser-recorded-results.json` (`status: "PASS"`)
  - `suite-results.json` (Codex attribution: 46 passing tests)
- **Runtime Environment:**
  - Windows 11, Node v26.7.0, Python 3.10.2 (`C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe`)
  - Headless Chromium (`C:/Users/Shrikar/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe`)
  - PostgreSQL port 55432 (`dbname=viralist_v03_standard_r2_review`)
  - RustFS S3 port 59000 (`bucket=viralist-v03-standard-r2-review`)
  - Local API port 58005 (quiescent)
  - Browse CLI 0.11.3 (`session=viralist-v03-standard-r2-review`, stopped)

---

## Limitations

1. **Test Doubles:** Model interactions in this review were verified using deterministic `httpx.MockTransport` doubles and synthetic envelopes. No live provider credentials or external network requests were made; live provider latency, p95 performance, and live model quality remain for the coordinator's post-integration smoke/50-instance run.
2. **Provider Upstream Erasure:** Deletion verification confirms immediate access revocation and app-owned database and S3 storage erasure. External provider retention and upstream backup purging cannot be guaranteed or observed by local application code.
3. **Accessibility Scope:** Keyboard navigation, note expansion, seek, and deletion were verified at 320px, 375px, and 1280px viewports. Full WCAG AA contrast audit and 200% browser zoom testing were not formally certified.

---

## Conclusion & Next Steps

Candidate `c714c2c0e2f0e1f0ef8c618b22bc05004551f556` completely resolves the four numbered product blockers and the mobile layout overflow. All tests, builds, independent fault controls, and browser journeys pass cleanly.

- **Current Milestone:** **REVIEW-ACCEPTED** (exact revision `c714c2c0e2f0e1f0ef8c618b22bc05004551f556`).
- **Next Action:** Coordinator may integrate `c714c2c0e2f0e1f0ef8c618b22bc05004551f556` into the integration branch and proceed to live-provider journey verification.
