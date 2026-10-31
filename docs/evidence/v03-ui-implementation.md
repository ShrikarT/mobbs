# V03-U1 Flash Evidence Workbench Implementation Report — Corrective Submission 1

## Metadata & Task Context
- **Logical Task:** V03-U1 Flash evidence workbench
- **Role:** Antigravity (Ordinary Implementation Worker)
- **Task ID:** `task_7459c8f8d952`
- **Dispatch ID:** `ctx_dba6e0dd9be6`
- **Run ID:** `run_d3354faa0659`
- **Worker Terminal:** `term_0a32c075-a8b3-4f37-b3e1-e327d2f4e5f8`
- **Coordinator Terminal:** `term_4d9cb728-3dfb-403c-bf6c-4364574d517a`
- **Assigned Workspace:** `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-ui`
- **Assigned Branch:** `codex/v03-ui`
- **Baseline HEAD:** `3dfa20fb708a093ac288db51ff7c303036621250`
- **Accepted Prerequisites:**
  - Backend integration: `5a3025c46c043b7645d935c3831f95d733f19ab5` (`7439b6c` merged)
  - Review round 1 findings: `feaa0b8:docs/evidence/v03-ui-review-r1.md`
  - Corrective assignment: `feaa0b8:docs/evidence/v03-ui-r1-assignment.md`
- **Submission Milestone:** `WORKER-REPORTED` (author-complete, pending independent review)
- **Correction Count:** Corrective submission 1 (prior submitted: 0 before this round, prior unsuccessful: 0)

---

## Executive Summary
In this corrective round, resolved all six independent review findings across `apps/web/src/App.tsx`, `apps/web/src/style.css`, `apps/web/src/api.ts`, `apps/web/src/types.ts`, and test suites without modifying production backend code, database schemas, package manifests, or lockfiles.

1. **Finding 1 (P1 - Narrative Honesty & Gated Disclosure):** Removed hardcoded Scene 2 / 3–8s / 11-persona drop claims and "statistical support threshold" claims from the empty-note banner. Derived narrative dynamically from `report.observations` and the deterministic stop-fraction detector. Gated the 5-archetype Flash 50 disclosure on actual Flash 50 cast/manifest; Video B Test 3 displays a truthful Test 3 disclosure without mentioning Flash 50 or 5 archetypes.
2. **Finding 2 (P2 - Persisted Emitter Reason Binding):** Rendered the actual persisted `payload.reason` emitted by `worker.py:187-195` in both the ordered event sequence log and persona node hover/title tooltips for continued and stopped events. Distinguished quote/persona reason from server stop categories and retained safe React text escaping.
3. **Finding 3 (P2 - Async State Fencing & Request Cancellation):** Eliminated overlapping 1s polling via sequenced timeout scheduling (`isPollBusy` guard). Implemented generation fencing (`runFenceRef`, `evidenceFenceRef`, `delFenceRef`) and native `AbortController` cancellation across run switches, deletions, resets, and unmounts, guaranteeing that delayed responses (401, 404, or late success) cannot alter newer views or seek the player.
4. **Finding 4 (P2 - Accessible Semantic Evidence Controls):** Converted quote citations into focusable semantic `<button type="button" className="quote-button">` controls with accessible `aria-label`. Added event propagation stopping so pressing Enter or Space opens the evidence inspector and seeks the player range without triggering or clearing the parent note card (`e.target === e.currentTarget` guard).
5. **Finding 5 (P2 - Cohort Coverage & Legacy Fallbacks):** Added a prominent cohort coverage card displaying partial/effective/requested/failed/pending counts and excluded traces. Provided explicit denominators for displayed completion rate and metrics. Rendered explicit unavailable explanations for legacy reports missing additive fields (`scores`, `engagement`, `retention`).
6. **Finding 6 (P2 - Text Contrast & Opacity Removal):** Removed opacity compositing on `.persona-node.pending` (0.6 -> 1.0, dashed border), `.score-item.unavailable` (0.8 -> 1.0), and `.engagement-item.unavailable` (0.8 -> 1.0). Verified all text/background pairs exceed WCAG AA 4.5:1 (ranging from 6.59:1 to 16.49:1).

In addition, retained the authorized isolated test setup repair in `tests/test_v03_flash_backend.py` (`TestCorrection1BlockerRegressions.test_migration_003_manifest_integer_type_guard_and_health`), ensuring autonomous owner creation on fresh migrated databases.

---

## Detailed Six-Finding Resolution

### 1. Narrative Honesty & Thin Cast Disclosure (Finding 1)
- **Problem:** Previous UI hardcoded Scene 2 (3.0s–8.0s) with 11 dropped personas and cited a "statistical support threshold" for any empty-note report. It also unconditionally displayed the 50-instance 5-archetype disclosure on Video B Test 3.
- **Resolution:**
  - In `App.tsx`, dynamic observation mapping summarizes observed triggers from `report.observations`, or states that no scene dropout triggers exceeded deterministic thresholds when empty.
  - References the deterministic stop-fraction detector rather than "statistical support".
  - Thin cast disclosure checks `(report.cast.profile === 'flash' || report.manifest?.profile === 'flash') && (report.cast.requested === 50 || report.manifest?.requested === 50)`. Video B Test 3 displays: `The Test 3 cast uses 3 simulated personas. All audience outcomes are simulated models, never real people...`

### 2. Persisted Event Reason Rendering (Finding 2)
- **Problem:** Production emitter (`apps/api/app/worker.py:187-195`) persists `payload.reason = evidence['quote']`, but the UI looked only for nonexistent `payload.drop_reason`.
- **Resolution:**
  - Bound `p.reason` in `personaStateMap` and rendered it in the ordered event sequence log:
    `{isStop ? 'stop quote: ' : 'quote: '}&ldquo;{p.reason}&rdquo;`.
  - Tooltips display `state?.reason ? ' · Quote: "' + state.reason + '"' : ''`.
  - Distinguishes quote reason from server drop categories while maintaining safe JSX escaping.

### 3. Async State Fencing & Request Cancellation (Finding 3)
- **Problem:** Overlapping 1s `setInterval` polling could cause race conditions. Stale poll/report/evidence responses from previous runs or before deletion could overwrite active state or seek the player.
- **Resolution:**
  - Replaced `setInterval` with sequenced recursive `setTimeout` protected by an `isPollBusy` flag.
  - Added `runFenceRef`, `evidenceFenceRef`, `delFenceRef`, and `pollAbortControllerRef`.
  - Any run switch, reset, or deletion triggers `abortCtrl.abort()` and increments `runFenceRef.current`, discarding any pending or delayed HTTP responses.
  - `handleSelectEvidence` checks `evidenceFenceRef` and `runFenceRef`, ensuring stale evidence fetches cannot seek the player on a newer run or after deletion.

### 4. Keyboard Operability on Evidence Quotes (Finding 4)
- **Problem:** Evidence quotes were plain `<div>`s nested inside an interactive note card. Pressing Enter or Space triggered the note card's handler, which called `setSelectedEvidence(null)` and cleared the inspector.
- **Resolution:**
  - Rendered quotes as `<button type="button" className="quote-button" aria-label={'Inspect evidence quote ' + (idx + 1) + ': "' + q.text + '"'} ...>`.
  - `onKeyDown` and `onClick` call `e.stopPropagation()`.
  - The parent note card's `onKeyDown` checks `if (e.target === e.currentTarget)`, preventing bubbled key events from re-selecting or resetting the note.

### 5. Cohort Coverage & Legacy Field Handling (Finding 5)
- **Problem:** Partial cohorts were not clearly distinguished from complete runs. If additive legacy fields (`scores`, `engagement`, `retention`) were absent, the sections were silently omitted without explanation.
- **Resolution:**
  - Added `.cohort-coverage-card` rendering a caution alert for partial runs (`effective < requested` or `failed > 0`), detailing effective, requested, failed, and pending counts.
  - Exposed `report.coverage?.excluded_traces` (failed and pending trace IDs).
  - Explicit denominators displayed on completion rate (`(completed / total)`), stopped viewers, and engagement actions.
  - Added explicit `.section-unavailable-banner` fallbacks when `scores`, `engagement`, or `retention` are absent in legacy reports.

### 6. Text Contrast & Opacity Compositing (Finding 6)
- **Problem:** `.persona-node.pending` had `opacity: 0.6`, causing 11px text to composite to 2.92:1 contrast. `.score-item.unavailable` and `.engagement-item.unavailable` had `opacity: 0.8`, compositing text to 4.29:1. Both failed WCAG AA (4.5:1).
- **Resolution:**
  - Removed `opacity` rules entirely.
  - Styled pending nodes with dashed borders on solid surface backgrounds; text uses `--text-primary` (16.49:1) and indicator uses `--text-subtle` (7.71:1).
  - Styled unavailable score and engagement items with dashed borders on `--bg-subtle`; reason text uses `--text-subtle` (6.59:1).
  - Verified via deterministic contrast regression script (`scripts/v03_ui_regressions.js`).

---

## Isolated Backend Test Repair
- **File:** `tests/test_v03_flash_backend.py`
- **Class / Method:** `TestCorrection1BlockerRegressions.test_migration_003_manifest_integer_type_guard_and_health`
- **Repair:** Autonomous owner creation via `create_session(client)` before querying `owner_sessions LIMIT 1`. Prevents `TypeError` on fresh migrated databases with no preexisting owners.
- **Verification:** Ran isolated against database `viralist_v03_ui`:
  - Command: `python -m unittest tests.test_v03_flash_backend.TestCorrection1BlockerRegressions.test_migration_003_manifest_integer_type_guard_and_health -v`
  - Result: `Ran 1 test in 1.075s. OK` (Exit code: 0).

---

## Verification Results Summary

| Check | Target / Command | Exit Code | Result |
|---|---|---|---|
| Lockfile-Pinned Frontend Build | `npm run build` (Vite 8.3.5 / React 19.3.1) | 0 | PASSED (Clean build in 305ms, 17 modules transformed) |
| Six Review Findings Regressions | `node scripts/v03_ui_regressions.js` | 0 | PASSED (6/6 deterministic tests passed) |
| Backend Test Isolation Repair | `python -m unittest tests.test_v03_flash_backend.TestCorrection1BlockerRegressions...` | 0 | PASSED (1 test, 1.075s) |
| Video B Complete Journey (Test 3) | `npx playwright test -c playwright.v03.config.ts -g "Complete journey for Video B"` | 0 | PASSED (25.1s) |
| Video A Flash 50 Journey (50 personas) | `npx playwright test -c playwright.v03.config.ts -g "Video A journey (Flash 50)"` | 0 | PASSED (3.0m, 256 events) |
| Video B Flash Rejection (Truthful 422) | `npx playwright test -c playwright.v03.config.ts -g "truthful error handling"` | 0 | PASSED (3.6s) |
| Processing Cancellation & Containment | `npx playwright test -c playwright.v03.config.ts -g "Processing cancellation"` | 0 | PASSED (6.2s) |
| Mobile 320px Responsive Viewport | `npx playwright test -c playwright.v03.config.ts -g "Mobile viewport"` | 0 | PASSED (1.6s) |
| Full End-to-End Playwright Suite | `npx playwright test -c playwright.v03.config.ts` (all 5 tests) | 0 | PASSED (5 passed in 3.7m) |

---

## Changed Files & Ownership Boundary
All modifications strictly respect the assigned U1 ownership boundary:
- `apps/web/src/App.tsx`: Resolved findings 1, 2, 3, 4, 5.
- `apps/web/src/style.css`: Resolved finding 6 (opacity removal, contrast enhancement, quote button styles, unavailable banners).
- `apps/web/src/api.ts`: Added optional `signal?: AbortSignal` to fetch functions for native request cancellation.
- `apps/web/src/types.ts`: Made `coverage` optional in `ReportData` for legacy report compatibility.
- `tests/e2e/journey.spec.ts`: Added quote keyboard navigation, Test 3 thin cast assertions, and empty-note honesty assertions.
- `scripts/v03_ui_regressions.js`: Focused deterministic regression suite for contrast and source findings.
- `scripts/v03_ui_capture_checkpoints.js`: Updated timeout to 350s for 50-persona sequential simulation.
- `scripts/v03_ui_test_journey.js`: Updated timeout to 350s for 50-persona sequential simulation.
- `tests/test_v03_flash_backend.py`: Bounded owner creation repair in migration 003 test.
- `docs/evidence/v03-ui-implementation.md`: This updated verification report.

No files outside owned scope were modified. Production backend code (`apps/api/**`), schema migrations, root `playwright.config.ts`, `AGENTS.md`, `PLAN.md`, and `STATE.md` remain completely untouched.

---

## Mocked Boundaries & External Dependencies
- **No Primary API or UI Mocks:** All tests executed against live FastAPI server on port 58003, PostgreSQL database `viralist_v03_ui` (port 55432), and private RustFS S3 storage `viralist-v03-ui` (port 59000).
- **Recorded Provider Mode:** External model inference executed through the hash-bound recorded provider boundary; no external provider network calls or live spend were incurred.
