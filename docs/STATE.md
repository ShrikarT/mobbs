# Viralist current handoff — 2026-11-02

This is the current snapshot. The complete prior state/history is preserved at **4394bf5bde767a9d0da97bbdad6154a489e22847**: `git show 4394bf5:docs/STATE.md`. Older active-task and budget-gate statements there are historical, not current authority.

## Scope and authority

Continue local V03 on the accepted V02 architecture: 50 fictional scene-aware instances, real provider/streaming, transparent retention/engagement, supported notes and video evidence, ownership/recovery/deletion, responsive UI. No V04/V05, marketing, deployment or release. Antigravity is the default implementation worker; Codex coordinates architecture, integration and independent quality checks.

Owner removed monetary caps and balance/dashboard gates on 2026-11-02. Use existing provider credits efficiently; retain bounded calls, limited concurrency, no blind uncertain-unit resend and honest usage. Custom accounting implementation/reviews/fixtures remain **DEFERRED**. See [current scope decision](decisions-v03-product-priority.md). Credential is private/server-only; never put it in Git, messages or browser code. No new paid calls since the real Flash50 below.

GitHub Issues is the selected destination, but no canonical issue is published; **PLAN.md remains canonical locally**. No implementation PR/push/CI/deployment is claimed. Owner-selected origin is `https://github.com/ShrikarT/viralist.git`.

## Active work and next action

### 2026-11-03 Checkpoint: V03-NOTES-STRICT (WORKER-REPORTED)

Following integration of V03-RUNTIME-INCOMPLETE (df43e7d), a fresh local Flash 50 run on Video A streamed 346 accepted scene decisions across all 50 personas (34 stopped + 16 complete; accepted-use estimate 0.85935030 USD; 0 persona incomplete failures on that input). However, the final Director's Notes request failed with HTTP 400 (`request_id: 450f235f-f095-4508-ba44-d509b1dfee42`; failed notes usage unavailable, not assumed free). The adapter discarded HTTP 400 error prose.

Under Meta's Responses structured output specification (https://dev.meta.ai/docs/structured-output, strict mode), `strict: true` requires every object's `required` array to explicitly contain every key declared in `properties`. Baseline `NOTES_SCHEMA` declared both `notes` and `limitations` in `properties` but only listed `["notes"]` in `required`.

Antigravity implementation candidate for **V03-NOTES-STRICT** is **WORKER-REPORTED** on branch `codex/v03-notes-schema`:
- **Schema strict compliance:** One-line fix in `apps/api/app/standard_provider.py` updating `NOTES_SCHEMA["required"]` to `["notes", "limitations"]`.
- **Focused regression test:** `tests/test_v03_notes_strict_schema.py` implements a recursive strict-mode schema validator, proves that the baseline missing-limitations defect is rejected with HTTP 400 (`provider_http_error_400`) at the provider boundary, verifies nested object strictness, and validates the outbound request protocol (strict: true, store: false, bounded output 4096 tokens, single HTTP call / no retry, canonical numeric usage and `notes: [], limitations: []` response acceptance).
- **Verification:** 5/5 tests in `tests/test_v03_notes_strict_schema.py` pass clean exit 0; 4/4 tests in `TestStandardProviderUnit` and 2/2 tests in `TestNotesContextAndOmission` pass clean exit 0. Zero live provider calls. See [evidence](evidence/v03-notes-strict.md).

| Owner/state | Exact identity and scope |
|---|---|
| Coordinator | `C:/Users/Shrikar/viralist`, branch `codex/orchestration-readiness`. |
| Antigravity — WORKER-REPORTED | V03-NOTES-STRICT, Task `task_19974038690e`, Dispatch `ctx_05d0790af40e`, terminal `term_db569610-0719-44ff-99b3-5f4212c79d14`, Run `run_d3354faa0659`. Status: `WORKER-REPORTED`. |
| Implementation worktree | `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-notes-schema`, branch `codex/v03-notes-schema`. |
| Review queue | Pending independent review of `codex/v03-notes-schema` candidate. |

### 2026-11-03 Checkpoint: V03-RUNTIME-INCOMPLETE (INTEGRATED)

Prior statements claiming V03 was complete and transitioning to V04 were premature: owner reported a real local incomplete response failure on 2026-11-03 during a 140-call Flash run (139 accepted, 1 HTTP 200 incomplete; saved original receipt lost reason/usage, UNKNOWN; max_output_tokens is the controlled regression fixture reason), which caused premature run failure, lost metadata/usage, and misleading error UI. Local V03 remains the active scope.

Antigravity implementation candidate for **V03-RUNTIME-INCOMPLETE** correction 1 was integrated at commit `df43e7d`:
- **Outbound headroom raised:** Standard provider token ceiling for `verdict` and `notes` raised to 4096 tokens (from 1200 / 1600), eliminating artificial truncation when reasoning tokens consume response headroom.
- **Metadata preservation:** Outbound error receipts on HTTP 200 incomplete responses preserve `status="incomplete"`, allowlisted `incomplete_reason`, `response_id`, request `max_output_tokens: 4096`, canonical numeric `usage`, and calculated `cost_usd`, while redacting raw model text and reasoning.
- **Worker persona isolation:** Confirmed incomplete failures isolate to the affected persona (checkpoint marked `failed`, 0 further scene dispatches to that persona), allowing other independent personas to continue and produce an honest incomplete report with effective cast denominator and full usage/cost accounted in run totals. Ambiguous transport or malformed receipts remain conservative run failures.
- **Truthful error copy:** `apps/web/src/App.tsx` maps error codes to clear titles and explanations, replacing ambiguous "Try again" buttons with honest navigation ("Return to upload" and explicit "Delete uploaded video" confirmation modal).
- **Verification:** 6/6 tests in `tests/test_v03_incomplete_fix.py` pass clean exit 0; 14/14 tests in `tests/test_normalized.py` pass clean; frontend builds clean in 1.25s. Controlled HTTP provider doubles used; zero live paid calls. Browser harness setup stopped at coordinator decision gate `msg_baab054d297d` for independent coordinator verification. See [evidence](evidence/v03-incomplete-fix.md).
- **Correction 1:** Neutral App.tsx error copy implemented, generic fallback claims removed, tests/test_v03_standard_app.py:205 max_output_tokens updated to 4096. TestStandardProviderUnit (4/4 pass), test_v03_incomplete_fix (6/6 pass), test_normalized (14/14 pass), and npm run build (300ms) verified clean. Backend standard_provider.py and worker.py preserved byte-identical to 47a40c7. Browser verification gap acknowledged for coordinator.

V03-P1 bounded independent-persona execution was **JOURNEY-VERIFIED on d38ad2826816a294fb0070261505b41de2e6afc5 (integration 799a8b3881456506cf24942659b51f6ebf937d91)**, with Early Provisional Verdict streaming and positive note verification completed at commit **44c0ef7**:
- Flash 50 real Standard provider journey on Video B portrait executed with 196 calls, costing 0.45438985 USD (well under $1.50 cap).
- End-to-end report delivery reduced from 637.669s to 103.031s (6.19x speedup), resolving A01 timing failure (<300s target).
- Early Provisional Verdict streaming implemented: `verdict.provisional` emitted atomically once all personas complete Scene 0 (~36.5s), resolving the <=90s rehearsal verdict gate. Exposed in `GET /runs/{id}` for reload recovery. High-visibility Hook retention banner rendered in frontend during simulation.
- Positive Director's Note & Evidence Inspector card opening verified for >15% drop-off scenes via pre-evaluated `stop_trigger` in `build_note_context`.
- All 5 test suites passing clean exit 0 (14 normalized, 3 provisional verdict, 14 flash backend, 18 standard app, 11 bounded pool with exact 401 events, and frontend build in 312ms).
See [journey evidence](evidence/v03-bounded-pool-journey.md). Supervised worker dispatch `ctx_25ac981d707b` is completed and settled.

| Owner/state | Exact identity and scope |
|---|---|
| Coordinator | `C:/Users/Shrikar/viralist`, branch `codex/orchestration-readiness`; integrated commit **44c0ef7**. |
| Antigravity — SETTLED | V03-P1, Task `task_f42dd28fa84c`, Dispatch `ctx_25ac981d707b`, terminal `term_94ec81bb-df1d-4a9e-91c6-144de54507c1`, Run `run_d3354faa0659`. Status: `completed` / `settled`. |
| Implementation worktree | `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-bounded-pool`, branch `codex/v03-bounded-pool`, candidate commit **4ae71179a71d4b1f675e406a896b7dce33879c53** independently REVIEW-ACCEPTED. |
| Review queue | Empty. Bounded pool candidate 4ae7117 independently reviewed and accepted; provisional verdict & positive note features integrated at 44c0ef7. |

[Full V03-P1 assignment](evidence/v03-bounded-pool-assignment.md) is frozen at89d9974 and was delivered in the actual dispatch. Startup receipt msg_6035f6a7d563 verified; reply msg_2a29aab0c121 approved implementation, delivery848b9026b97d acknowledged. Worker mislabeled its gitdir as repo root; coordinator verified the actual assigned top-level and corrected it. Excluded manifests means dependency files, not the authorized run-manifest field.

**Next:** Independent review of `codex/v03-notes-schema` candidate, followed by integration. V04 remains deferred until V03 reliability is accepted and integrated.

Frozen pool contract at ecdcdde (`docs/contracts/live-standard.v1.md`, bounded-concurrency section): new Standard Flash manifest concurrency8; test/recorded1; historical missing1. Global HTTP max8 through PG session slots, one job leader, per-persona ordered next scene/own prior only, no later hints after stop, generation/lease heartbeat and post-slot fence. Stream each completed unit once; unresolved dispatches never resend; preserve notes byte/hash recovery/privacy and call ceilings. Prefer scene-frontier ordering. No schema/service/financial subsystem or real-key/model access by the worker. Own DB `viralist_v03_pool`, bucket `viralist-v03-pool`, port58007, private `.codex/viralist-v03-pool/`.

## Preserved acceptance and current gaps

- V02 was INTEGRATED/JOURNEY-VERIFIED at1e140dc. Recorded V03 backend accepted7439b6c/integrated5a3025c; UI accepted52a0968/integratedd9d3ed5. Later Standard integration below supersedes the old infrastructure-blocked browser attempt; do not rerun V02 wholesale.
- Standard correction2 **REVIEW-ACCEPTED c714c2c0e2f0e1f0ef8c618b22bc05004551f556**, merged **ae643ffe96b4d0e16ae57fde41a8a629b969b2bb**, tested integration source **6ebafa53c6d2dccd0a7f698f0a209935431710fb**. [Independent review](evidence/v03-standard-app-r2-independent-review.md):46 tests/build,12 fault controls, Standard/recorded browser journeys, mobile/keyboard/playback. External model transport doubled. Four privacy/recovery/deletion/provenance blockers and mobile overflow accepted resolved. Corrections submitted2/unsuccessful1, then accepted; V03-P1 is a new performance task, not a renamed failed correction.
- [Real Flash50 journey](evidence/v03-real-flash50-journey.md) on6ebafa5: actual Standard model,50/50 complete,195 real calls, estimated0.43857825USD (not invoice),88% simulated completion. Streaming, report, decoded playback, refresh/API restart, foreign401/404 and320/375 layouts verified. Zero supported notes because no scene crossed the existing trigger; honest empty state. UI deletion followed by201 actual HEAD404s, empty bucket, content tables0 and stripped tombstone. No upstream-backup erasure claim.
- **A01 timing gate:** Report delivery is resolved at 103.031s (6.19x speedup vs 637.669s, passing <=300s gate); Scene 0 completion occurred at ~36.5s (<60s first-finding target). Executive verdict delivered with report at 103.031s remains an active optimization target for the <=90s rehearsal verdict gate. One live sample is not p95. V03 still needs positive live-provider supported-note/evidence coverage (drop > 15%), 60s maximum input, and >=20 valid full-path samples before claiming p95.
- [Native zoom/motion/text check](evidence/v03-accessibility-zoom-motion.md) at26fc644 (same accepted product source): actual recorded3 path, native200% zoom,631px viewport/document, keyboard evidence/deletion, reduced motion,164 direct-text elements0contrast failures. No full WCAG/cross-browser/assistive-technology claim. Changed integration needs affected re-verification.
- **RELEASED: not authorized/not performed.** Bounded pool code is REVIEW-ACCEPTED (4ae7117), INTEGRATED (799a8b3), and JOURNEY-VERIFIED (d38ad28); RELEASED is not authorized/not performed.

## Runtime and recovery

Existing PG55432 (`viralist-v02-postgres`, retained pgdata volume) and RustFS59000 (`viralist-v02-objectstore`, retained objectdata volume). Do not reset/recreate/pull/delete shared volumes. Prior objectstore contention/exit137 was observed, not proven OOM or permanently fixed. Inspect actual health on a concrete failure; sequence heavy tests.

Coordinator real-journey DB `viralist_v03_live_journey_20261102` and bucket `viralist-v03-live-journey-20261102` are retained but content-empty after verified deletion. Its API58006, durable worker and browse sessions are stopped. No paid run is currently live. Private `.codex/private-runs/viralist-v03-live/` contains frozen build/manifests, scripts, receipts/media/results; `journey-01-as-executed/manifest.json` preserves15 executed scripts/results with hashes, no credentials/media copies. One-attempt paid markers must not be rerun. `active-journey-handoff.json` records old sessions only; they are now stopped, not active identities.

Approved next input A is privately prepared via the committed named helper: SHA c76b510a43b6aaaf90dc152e8be358f0e6efb64a95ebc785c8cd51af7713975a,1,865,999bytes,33.782s,720x1280H264/AAC. B portrait/hash and input rights/construction are in the real-journey evidence. Private user-DPAPI credential and fixtures stay outside Git; current pool worker is excluded from the live-key directory. Reusable Python `.codex/viralist-v02-review/venv/Scripts/python.exe`; PYTHONDONTWRITEBYTECODE=1. Apply001-003 only to new owned runtime databases.

Deferred accounting safe checkpoint **ba6af92c429c126e51da515816432d34a81ef33c**, branch codex/v03-budget-senior-reassessment, remains preserved, unaccepted/unintegrated. Original task_d8317ec85c90/ctx_e0819319664e settled, terminal retained/user_takeover. Old correction/review/DDL records remain history. Do not resume, import, review or redesign them. Original Codex review quota interruption and retained/unknown old terminal resources are recorded in the prior state commit; do not broad-close or spawn replacements for them.

## Authority map

Start with [AGENTS](../AGENTS.md), [PLAN](../PLAN.md) and [approved brief](PROJECT_BRIEF.md); use [architecture](ARCHITECTURE.md)/[contracts](CONTRACTS.md) for interfaces, [acceptance](ACCEPTANCE.md) for exact gates, [design direction](DESIGN_DIRECTION.md) for UI. Task-specific frozen contract and revision-linked evidence above govern current execution. Recover actual Git/Orca identities rather than treating this handoff or an author report as implementation proof.
