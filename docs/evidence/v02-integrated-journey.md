# V02 local integrated journey verification

Verified application/integration commit: **`1e140dc3db6bd9d052206cb3ae385b771d39c9dd`**. Candidate `1ce2abefdd7780a4fc7fd5080d5bb2d47655d4d6` combines Antigravity's functional fixes with the independently accepted claim reconciliation. Coordinator branch: `codex/orchestration-readiness`. The final ledger update changes documentation only; the running artifact stays at the exact integration commit in `codex/v02-integrated-runtime`.

**Outcome: INTEGRATED and JOURNEY-VERIFIED locally. RELEASED: no.** No push, deployment, publication or new paid provider inference was performed for this milestone.

## Observable behavior on the integration commit

1. A real browser uploads original B through the UI. Production validation, private S3 storage, PostgreSQL job queue, worker, hash-bound recorded provider adapter and report renderer run. The report has three effective simulated personas, duration17108ms/four scenes, one supported note at3000-8000ms and zero suppressed candidates. Displayed quote text matches the report's evidence-linked quotes. Keyboard activation seeks the actual player; a full authenticated media stream hashes to the original B bytes.
2. Browser reload restores the same report/run. The coordinator then stops the actual owned Uvicorn process9444 and starts a new API process15012. A browser retaining its real session cookies restores that same durable report after the restart. This is an actual process restart, not a generation-field edit.
3. A genuinely separate browser session cannot read the owned video/run/report/events or delete it. The server returns404. Origin/CSRF checks remain active.
4. Original A is uploaded through the real API. Six simultaneous same-key HTTP POSTs create exactly one new A run. It produces33782ms/eight scenes/no supported note/one suppressed candidate. A fresh key first used on an existing B run cannot be reused for A:409.
5. B is deleted through the actual UI. Completion is app-owned-copy scope, with the historical-source/upstream-backup caveat visible. Owner repeats return the same deletion operation. Reusing a successful deletion key for A returns409. A is then cleaned through its real deletion lifecycle. The other session cannot DELETE B after completed deletion:404. Owner resource reads return404 while its session remains valid and its video list is empty.
6. The inventory captured before deletion contains35 object keys for these two journey videos. **All35 actual S3 HEAD requests return404 afterward.** Database objects/runs/jobs and run dependents (events, checkpoints, reactions, provider_calls) are all zero for these journey IDs. Original historical media hashes remain unchanged. This does not claim the entire test database/bucket, historical archives or upstream backups were erased.

The two deterministic browser phases recorded zero page exceptions. Deliberate negative HTTP404/409 probes are expected; no blanket network-error or accessibility certification is claimed.

## Commands and revision-specific evidence

Environment: Windows; Python3.10.2, Node26.7.0, PostgreSQL17, private RustFS S3, FFmpeg and local Chromium. No cloud/production/cross-browser test claim. Actual runtime paths and configuration remain private.

| Check on exact integration commit | Result |
|---|---|
| `python -m apps.api.app.db`, `python -m scripts.check_services` | Exit0; real migration and private S3 put/get/delete |
| `python -m unittest tests.test_normalized tests.test_domain_integration tests.test_api_security_isolation tests.test_full_journey` | Exit0;28 checks,15.287s, real local services with scoped external fault fixtures |
| `python -m tests.reconcile_saved` | Exit0; standalone19 saved reactions/one supported and one suppressed note |
| `npm ci --ignore-scripts`, `npm run build` | Exit0; bundle `index-BF9vQwJF.js`, CSS `index-BjoDrqkn.css` |
| Private deterministic `journey.mjs before-restart`, actual API stop/start, `journey.mjs after-restart` | Exit0; UI journey, media hash, durable report, ownership, concurrency/key binding and deletion above |
| Private `storage-proof.py after` plus run-dependent SQL check | Exit0;35/35 S3 HEAD404 and all selected journey rows absent; archives preserved |
| `browse --local --session viralist-v02-integrated` | Actual integrated app reachable; final landing snapshot captured; owned browser session stopped |

The six supplied Playwright executions passed independently at `1b322d53555a71d98a9743ddb709701eed599278` (1.2m). They were not rerun for totals on this integration. The new deterministic integration journey and28 Python checks above ran on the combined commit. Production files match the accepted candidate; only claim/test-label documentation differed from1b. Actual old-shape browser rendering, pending-deletion reload, incomplete/error cleanup, event delivery and dialog containment were separately exercised at1b; the [second review](v02-correction-2-review.md) preserves those exact limits. The API old-shape regression also runs in the28-check integration suite.

Private evidence: `C:/Users/Shrikar/.codex/viralist-v02-integrated/` contains the replayable local drivers, runtime/media receipts, before/after restart logs, saved browser auth (private), registered-key inventory, `b-report.png`, `deletion-complete.png` and final browse snapshot. No raw auth, footage or provider output is committed. Reproduction requires the private original A/B and saved provider archive; this is not a public self-contained fixture package.

## Acceptance and operating handoff

- Functional implementation author: Antigravity. Independent functional verifier/integrator: Codex coordinator. The coordinator-authored claim-only repair received separate Antigravity exact-commit acceptance with focused real API/PG checks: [review](v02-evidence-record-review.md). Neither author automatically approved their own changes.
- Two submitted corrections failed blocking criteria. The recorded [reassessment](v02-correction-2-review.md) froze production behavior and split out factual claim reconciliation; the parent count stayed two. No third broad application patch iteration or budget reset occurred. All named commits/worktrees are retained.
- Antigravity remains the permanent default implementation worker. The bounded Codex claim-repair exception and justification are in [its assignment](v02-evidence-record-assignment.md). No substitute was launched for an Antigravity quota limit. All supervised workers are settled/released; the historical user-owned terminal/worktree remains untouched.
- Orca correction2 ran07:47:33-08:26:42UTC; independent claim review08:42:43-08:49:32UTC on2026-10-29. Per-worker new/cached/output token counts and actual Orca model spend are unavailable. Paid experiment ledger unchanged: estimate$13.38427320 plus$1.31327 uncertain reserve = tracked maximum$14.69754320 against$15.
- Verified application controls include owner/CSRF/origin/host checks, request-key binding, PostgreSQL transaction/lease fences, server media limits, private inventory-backed cleanup and accurate scope disclosure. Worktree/ownership receipts were checked. GitHub required checks/protection, full secret/dependency scanning, full accessibility and production hardening were not established by this local milestone.

The app is left running at **http://127.0.0.1:58000** from the frozen integration checkout `C:/Users/Shrikar/orca/workspaces/viralist/codex-v02-integrated-runtime`. API launcher2460/listener15012; worker launcher10008/process12228 at capture. Private config: `C:/Users/Shrikar/.codex/viralist-v02-integrated/runtime.json` via `VIRALIST_RUNTIME`; process records/logs are beside it. Verify current process identity/listener before stopping or restarting; PIDs can change. Shared PostgreSQL/S3 volumes remain intact. README gives standard setup commands; use separate API/worker terminals and the private runtime override for this instance.

V02 is the local recorded-inference three-person slice. V03 still needs separately authorized live Standard-provider smoke, full-Flash50-instance cost/latency/60s-worst-case/p95 evidence and subsequent product work. No50-distinct-human-persona, real-world accuracy, paid cost target, public demo or release claim is earned here.
