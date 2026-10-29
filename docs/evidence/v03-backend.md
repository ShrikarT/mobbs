# V03-B1 durable fifty-instance Flash and inspectable report data

Task: **V03-B1** (`task_9d01d4520634`, dispatch `ctx_4da38f5feed2`, run `run_d3354faa0659`).
Author: Antigravity (worker terminal `term_b9d7cff5-120c-4f2e-b340-76c578b637a5`).
Coordinator: Codex (terminal `term_0aecb9de-e52d-4a29-b1aa-42df8fdd8be6`).
Assigned worktree: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-backend` on branch `codex/v03-backend`.
Accepted application prerequisite: `1e140dc3db6bd9d052206cb3ae385b771d39c9dd`; starting coordinator baseline: `dcb8172f700965aa329a6d154a473173276e0fb8`.

**Outcome: WORKER-REPORTED.** Submitted for independent review. No deployment, publication, or live provider spend performed.

---

## Observable behavior on the candidate revision

### Criterion 1: Manifest and Profile (`POST /runs`, `GET /runs/{id}`)
- Migration `002_run_manifest.sql` executes under advisory lock and defines table check constraint `runs_manifest_shape`, default `run-manifest-1` (`requested: 3`, `persona_ids: ['p001', 'p002', 'p003']`, `profile: 'test'`, `provider_mode: 'recorded'`, `resample_seed: 20261028`), and PL/pgSQL trigger `protect_run_manifest()`.
- Immutability trigger verified: direct SQL `UPDATE runs SET manifest = ...` raises `psycopg.errors.CheckViolation: run_manifest_immutable`.
- Video A uploaded once: `POST /runs` with `profile='test'` creates `run_1` (`requested: 3`); `POST /runs` with `profile='flash'` creates distinct `run_2` (`requested: 50`).
- Inspected `GET /runs/{run_2}` before worker preparation returns: `status: 'queued'`, `requested: 50`, `pending: 50`, `effective: 0`, `failed: 0`, `stopped: 0`.
- Idempotency repeat is stable (returns same `run_id`). Reusing key with altered payload returns `409` (`idempotency_body_changed`). Invalid profile returns `422` (`profile_must_be_test_or_flash`).
- Pre-enqueue validation: requesting `profile='flash'` on media lacking stage2 evidence (e.g. video B) immediately fails pre-enqueue with `422` (`recorded_evidence_unavailable_for_this_upload`).

### Criterion 2: Full Flash Run
- Original Video A (SHA256 `c76b510a43b6aaaf90dc152e8be358f0e6efb64a95ebc785c8cd51af7713975a`, duration `33782ms`, 8 scenes) uploaded and executed under `profile='flash'`.
- Production worker `process_once()` stepped across all checkpoints to completion.
- Exact database counts observed:
  - `checkpoints`: 50 rows, all 50 reached status `'stopped'`.
  - `reactions`: 256 mapped rows (matching the 256 stage2 archive decisions).
  - `events`: 256 rows, monotonic sequence 1..256.
  - Final status: `status: 'complete'`, `stage: 'report'`, `requested: 50`, `effective: 50`, `failed: 0`, `stopped: 50`, `pending: 0`.
- Post-stop invariant verified: no persona receives any reaction or dispatch for scenes following their terminal stop. Calling `validate_projection` on a stopped checkpoint raises `ValueError: post-stop or out-of-order dispatch`.

### Criterion 3: Evidence and Events
- Events endpoint `GET /runs/{run_id}/events`:
  - Returns 256 SSE frames with strictly monotonic integer sequence 1..256 and no duplicates.
  - Reconnecting with `Last-Event-ID: {event_100_id}` resumes monotonically from sequence 101 to 256 (156 events returned).
  - Additive event fields present: `payload.actions` and `payload.reason` (quoted justification).
- Owner-scoped evidence endpoint `GET /runs/{run_id}/evidence/{evidence_id}`:
  - Returns validated evidence unit: `id`, `persona_id`, `scene_id`, `start_ms`, `end_ms`, `quote`, `still_watching`.
  - A distinct browser session requesting the same evidence ID receives `404` (`Denied`).
  - Requesting an unknown evidence ID returns `404`.

### Criterion 4: Report Math and Notes
- Report endpoint `GET /runs/{run_id}/report` verified against production database and private RustFS storage:
  - **Retention Table (8 scenes):**
    - Scene 0 (0-3000ms): 50 entrants, 11 stopped, 39 continued, survival 78.0% [70.0, 86.0], drop rate 22.0% [14.0, 30.0].
    - Scene 1 (3000-8000ms): 39 entrants, 0 stopped, 39 continued, survival 78.0% [70.0, 86.0], drop rate 0.0% [0.0, 0.0].
    - Scene 2 (8000-13000ms): 39 entrants, 0 stopped, 39 continued, survival 78.0% [70.0, 86.0], drop rate 0.0% [0.0, 0.0].
    - Scene 3 (13000-18000ms): 39 entrants, 9 stopped, 30 continued, survival 60.0% [50.0, 70.0], drop rate ~23.1% [15.4, 30.8].
    - Scene 4 (18000-23000ms): 30 entrants, 0 stopped, 30 continued, survival 60.0% [50.0, 70.0], drop rate 0.0% [0.0, 0.0].
    - Scene 5 (23000-28000ms): 30 entrants, 1 stopped, 29 continued, survival 58.0% [48.0, 68.0], drop rate ~3.3% [0.0, 6.7].
    - Scene 6 (28000-33000ms): 29 entrants, 29 stopped, 0 continued, survival 0.0% [0.0, 0.0], drop rate 100.0% [100.0, 100.0].
    - Scene 7 (33000-33782ms): 0 entrants, 0 stopped, 0 continued, survival 0.0% [0.0, 0.0], drop rate `observed: None`, `unavailable_reason: 'no_scene_entrants'`.
  - **Engagement:**
    - `save`: observed 50.0%, denominator 50, range [42.0, 58.0] (200 whole-persona resamples, seed 20261028).
    - `follow`: observed `None`, denominator 50, range `None`, `unavailable_reason: 'action_not_observed_by_legacy_provider'`.
    - `like`, `share`, `comment`: observed rates with resampled intervals.
  - **Scores:**
    - `hook`: survival at scene 0 (covering 3s): observed 78.0%, range [70.0, 86.0].
    - `pacing`: survival at scene 5 (covering 80% duration): observed 58.0%, range [48.0, 68.0].
    - `clarity`, `cta`, `trend`: observed `None` with truthful missing-signal reasons (`confusion_signal_unobserved`, `cta_signal_unobserved`, `grounded_trend_rules_unavailable`).
  - **Notes & Grounded Injection:**
    - Stage 2 historical note candidate for scene 5 (23-28s) has no compatible stop trigger (scene 5 stop rate was 3.3% < 15% threshold) and is properly suppressed: 0 reported notes, `suppressed_notes: 1`.
    - Grounded note injection test verifies that providing a candidate note matching an active trigger (`stop_0`, scene 0, 22% stop rate) normalizes to open status with quotes, fix, interpretation, evidence_refs, and ranking.
  - **Golden Trace Math:**
    - Hand-calculated 4-persona 2-scene fixture unit test verifies exact sample arithmetic, conditional denominators, and percentile ranking.

### Criterion 5: Failure and Recovery
- Cast status edge cases:
  - 49 stopped/complete, 1 failed -> `incomplete` status.
  - 39 stopped/complete, 11 failed -> `incomplete` status.
  - 0 valid terminal traces (50 failed) -> `failed` status.
- Worker crash simulation:
  - Active leased job left unreleased; lease expires in past.
  - Second worker invokes `claim()` and acquires expired job with incremented generation.
  - First worker attempting to fence with stale lease generation raises `LeaseLost`.
  - Checkpoint and reactions resume seamlessly without duplication or event resurrection.

### Criterion 6: Privacy and Deletion
- Two browser sessions: Session 1 (owner) and Session 2 (unrelated).
- Session 2 denied access to Session 1's video, media, run, report, and analysis (`404` on all routes); Session 2's video list returns `[]`.
- Session 1 calls `DELETE /videos/{video_id}`:
  - Returns `202` with `access_revoked: True`.
  - Immediate access revocation: Session 1 itself immediately receives `404` on `/videos/{id}/analysis`, `/videos/{id}/media`, `/runs/{id}`, and `/runs/{id}/report`. Session 1's `/videos` list immediately excludes the video.
  - Asynchronous wipe: worker `process_once()` executes deletion steps until completion.
  - Deletion record state verifies `status: 'complete'`, `can_claim_complete: True`.
  - Object storage verification: all registered object keys in `objects` table return `404` via private S3 client `head_object`.

---

## Commands and verification evidence

Environment: Windows; Python 3.10.2, PostgreSQL 17 on port 55432, RustFS S3 on port 59000, FFmpeg. Configuration via `test_runtime.json` (`VIRALIST_RUNTIME`).

| Command | Exit Code | Observed Result |
|---|---|---|
| `python -m unittest tests.test_v03_flash_backend` | Exit 0 | 9 tests passed (87.352s): Criteria 1-6 verified against real DB & private S3 |
| `python -m unittest discover tests` | Exit 0 | 37 tests passed (96.475s): Full repo test suite including baseline V02 regression |
| `python -m tests.reconcile_saved` | Exit 0 | Standalone evidence reconciliation: PASS (19 reactions, 1 supported note, 1 suppressed note) |
| `python -m unittest tests.test_v03_flash_backend.TestGoldenTraceMathFixture` | Exit 0 | 1 test passed (0.003s): Hand-checkable synthetic trace math |

---

## Invariants and boundaries preserved

1. **Zero Provider Spend / Inference:** `MetaStandardAdapter` remains fail-closed. No live external inference was performed; all 50-persona Flash traces were served from verified private stage 2 bounded evidence (`apps/api/recorded-50-index.json`). Provider spend remains at the tracked $14.69754320 maximum, well within the authorized $30 cap.
2. **Post-Stop Invariant:** Simulated viewers receive zero later media frames, summaries, or reactions once stopped.
3. **Additive Schema & Backward Compatibility:** Existing V02 3-person test runs and endpoints remain fully supported; run manifests are immutable once sealed.
4. **Data Isolation & Deletion Truthfulness:** Immediate access revocation precedes asynchronous storage wipe. Controlled object storage deletion verified via S3 HEAD 404 for all registered video keys.
