# Viralist current handoff — 2026-11-02

This is the current snapshot. The complete prior state/history is preserved at **4394bf5bde767a9d0da97bbdad6154a489e22847**: `git show 4394bf5:docs/STATE.md`. Older active-task and budget-gate statements there are historical, not current authority.

## Scope and authority

Continue local V03 on the accepted V02 architecture: 50 fictional scene-aware instances, real provider/streaming, transparent retention/engagement, supported notes and video evidence, ownership/recovery/deletion, responsive UI. No V04/V05, marketing, deployment or release. Antigravity is the default implementation worker; Codex coordinates architecture, integration and independent quality checks.

Owner removed monetary caps and balance/dashboard gates on 2026-11-02. Use existing provider credits efficiently; retain bounded calls, limited concurrency, no blind uncertain-unit resend and honest usage. Custom accounting implementation/reviews/fixtures remain **DEFERRED**. See [current scope decision](decisions-v03-product-priority.md). Credential is private/server-only; never put it in Git, messages or browser code. No new paid calls since the real Flash50 below.

GitHub Issues is the selected destination, but no canonical issue is published; **PLAN.md remains canonical locally**. No implementation PR/push/CI/deployment is claimed. Owner-selected origin is `https://github.com/ShrikarT/viralist.git`.

## Active work and next action

V03-P1 bounded independent-persona execution is **INTEGRATED at 799a8b3881456506cf24942659b51f6ebf937d91**. Candidate **4ae71179a71d4b1f675e406a896b7dce33879c53** from Antigravity (`task_f42dd28fa84c`, `ctx_25ac981d707b`, worktree `codex-v03-bounded-pool`) was independently reviewed and accepted against clean baseline `ecdcdde59fafda223af4374f15704fe953158e26`:
- 11 bounded pool tests passed (308.903s, exit 0, CP1 proof 67.922s, 2.44x speedup, 8 aggregate locks).
- 18 Standard app regression tests passed (142.762s, exit 0).
- Frontend assets built cleanly (exit 0, 384ms).
Candidate merged cleanly into coordinator branch `codex/orchestration-readiness` via merge commit `799a8b3881456506cf24942659b51f6ebf937d91`. Combined checks re-verified: all 11 bounded pool tests passed (329.814s, exit 0, 2.64x speedup, 4 concurrent workers in real PG proof, max 8 aggregate locks); frontend built cleanly (exit 0, 785ms). Supervised worker dispatch `ctx_25ac981d707b` is completed and settled.

**Next:** Execute real journey verification for the integrated bounded pool application on `799a8b3881456506cf24942659b51f6ebf937d91` using the prepared Flash 50 journey, recording the updated end-to-end latency to verify resolution of the A01 timing failure.

| Owner/state | Exact identity and scope |
|---|---|
| Coordinator | `C:/Users/Shrikar/viralist`, branch `codex/orchestration-readiness`; integrated commit **799a8b3881456506cf24942659b51f6ebf937d91**. |
| Antigravity — SETTLED | V03-P1, Task `task_f42dd28fa84c`, Dispatch `ctx_25ac981d707b`, terminal `term_94ec81bb-df1d-4a9e-91c6-144de54507c1`, Run `run_d3354faa0659`. Status: `completed` / `settled`. |
| Implementation worktree | `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-bounded-pool`, branch `codex/v03-bounded-pool`, candidate commit **4ae71179a71d4b1f675e406a896b7dce33879c53** independently REVIEW-ACCEPTED. |
| Review queue | Empty. Bounded pool candidate 4ae7117 independently reviewed and accepted (11 bounded pool tests, 18 standard app tests, frontend build passing exit 0). |

[Full V03-P1 assignment](evidence/v03-bounded-pool-assignment.md) is frozen at89d9974 and was delivered in the actual dispatch. Startup receipt msg_6035f6a7d563 verified; reply msg_2a29aab0c121 approved implementation, delivery848b9026b97d acknowledged. Worker mislabeled its gitdir as repo root; coordinator verified the actual assigned top-level and corrected it. Excluded manifests means dependency files, not the authorized run-manifest field.

**Next:** verify acknowledgment of the numbered checkpoint batch, finish the same task's missing original fault/lease/cross-process/regression/browser evidence, then independent exact-commit review and integration. Do not duplicate/reassign a live worker. Recent observed edits: owned API/worker/reporting/App/types and new pool tests/helper. Generated own pnpm-lock.yaml was removed after scope warning msg_9328ecb77791; latest status contains only seven owned source/test paths, no dependency-file changes. First-feedback scope msg_def208b0d0d6 and exact checkpoint/failing-trace request msg_a7ae2d266846 were enqueued; checkpoint report received at cc332c7; six passing tests/controlled speedup are author claims qualified by the technical batch. Conditional job-identity diagnostic msg_52a0968e9391 advises checking own leftover fixture jobs before changing production fairness. Do not infer read/ack from enqueue.

Frozen pool contract at ecdcdde (`docs/contracts/live-standard.v1.md`, bounded-concurrency section): new Standard Flash manifest concurrency8; test/recorded1; historical missing1. Global HTTP max8 through PG session slots, one job leader, per-persona ordered next scene/own prior only, no later hints after stop, generation/lease heartbeat and post-slot fence. Stream each completed unit once; unresolved dispatches never resend; preserve notes byte/hash recovery/privacy and call ceilings. Prefer scene-frontier ordering. No schema/service/financial subsystem or real-key/model access by the worker. Own DB `viralist_v03_pool`, bucket `viralist-v03-pool`, port58007, private `.codex/viralist-v03-pool/`.

## Preserved acceptance and current gaps

- V02 was INTEGRATED/JOURNEY-VERIFIED at1e140dc. Recorded V03 backend accepted7439b6c/integrated5a3025c; UI accepted52a0968/integratedd9d3ed5. Later Standard integration below supersedes the old infrastructure-blocked browser attempt; do not rerun V02 wholesale.
- Standard correction2 **REVIEW-ACCEPTED c714c2c0e2f0e1f0ef8c618b22bc05004551f556**, merged **ae643ffe96b4d0e16ae57fde41a8a629b969b2bb**, tested integration source **6ebafa53c6d2dccd0a7f698f0a209935431710fb**. [Independent review](evidence/v03-standard-app-r2-independent-review.md):46 tests/build,12 fault controls, Standard/recorded browser journeys, mobile/keyboard/playback. External model transport doubled. Four privacy/recovery/deletion/provenance blockers and mobile overflow accepted resolved. Corrections submitted2/unsuccessful1, then accepted; V03-P1 is a new performance task, not a renamed failed correction.
- [Real Flash50 journey](evidence/v03-real-flash50-journey.md) on6ebafa5: actual Standard model,50/50 complete,195 real calls, estimated0.43857825USD (not invoice),88% simulated completion. Streaming, report, decoded playback, refresh/API restart, foreign401/404 and320/375 layouts verified. Zero supported notes because no scene crossed the existing trigger; honest empty state. UI deletion followed by201 actual HEAD404s, empty bucket, content tables0 and stripped tombstone. No upstream-backup erasure claim.
- **A01 timing FAIL:** report637.669s from completed upload; final verdict exceeds90s. First visible reaction10.289s is not the defined first useful finding. One sample is not p95. V03 still needs bounded-pool performance, positive live-provider supported-note/evidence coverage,60s maximum input, applicable rehearsals and >=20 valid full-path samples before claiming p95. Preserve failed observations; do not relabel/replay them as fast or live success.
- [Native zoom/motion/text check](evidence/v03-accessibility-zoom-motion.md) at26fc644 (same accepted product source): actual recorded3 path, native200% zoom,631px viewport/document, keyboard evidence/deletion, reduced motion,164 direct-text elements0contrast failures. No full WCAG/cross-browser/assistive-technology claim. Changed integration needs affected re-verification.
- **RELEASED: not authorized/not performed.** New pool code is REVIEW-ACCEPTED (4ae7117) and INTEGRATED (799a8b3); JOURNEY-VERIFIED is next.

## Runtime and recovery

Existing PG55432 (`viralist-v02-postgres`, retained pgdata volume) and RustFS59000 (`viralist-v02-objectstore`, retained objectdata volume). Do not reset/recreate/pull/delete shared volumes. Prior objectstore contention/exit137 was observed, not proven OOM or permanently fixed. Inspect actual health on a concrete failure; sequence heavy tests.

Coordinator real-journey DB `viralist_v03_live_journey_20261102` and bucket `viralist-v03-live-journey-20261102` are retained but content-empty after verified deletion. Its API58006, durable worker and browse sessions are stopped. No paid run is currently live. Private `.codex/private-runs/viralist-v03-live/` contains frozen build/manifests, scripts, receipts/media/results; `journey-01-as-executed/manifest.json` preserves15 executed scripts/results with hashes, no credentials/media copies. One-attempt paid markers must not be rerun. `active-journey-handoff.json` records old sessions only; they are now stopped, not active identities.

Approved next input A is privately prepared via the committed named helper: SHA c76b510a43b6aaaf90dc152e8be358f0e6efb64a95ebc785c8cd51af7713975a,1,865,999bytes,33.782s,720x1280H264/AAC. B portrait/hash and input rights/construction are in the real-journey evidence. Private user-DPAPI credential and fixtures stay outside Git; current pool worker is excluded from the live-key directory. Reusable Python `.codex/viralist-v02-review/venv/Scripts/python.exe`; PYTHONDONTWRITEBYTECODE=1. Apply001-003 only to new owned runtime databases.

Deferred accounting safe checkpoint **ba6af92c429c126e51da515816432d34a81ef33c**, branch codex/v03-budget-senior-reassessment, remains preserved, unaccepted/unintegrated. Original task_d8317ec85c90/ctx_e0819319664e settled, terminal retained/user_takeover. Old correction/review/DDL records remain history. Do not resume, import, review or redesign them. Original Codex review quota interruption and retained/unknown old terminal resources are recorded in the prior state commit; do not broad-close or spawn replacements for them.

## Authority map

Start with [AGENTS](../AGENTS.md), [PLAN](../PLAN.md) and [approved brief](PROJECT_BRIEF.md); use [architecture](ARCHITECTURE.md)/[contracts](CONTRACTS.md) for interfaces, [acceptance](ACCEPTANCE.md) for exact gates, [design direction](DESIGN_DIRECTION.md) for UI. Task-specific frozen contract and revision-linked evidence above govern current execution. Recover actual Git/Orca identities rather than treating this handoff or an author report as implementation proof.
