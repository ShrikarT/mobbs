# V03-B1 correction submission 1: report cohorts, metric contracts and rejection reasons

Task: **V03-B1 correction submission 1** (`task_ec3e6a6f91f6`, dispatch `ctx_cdfd6213b2a9`, run `run_d3354faa0659`).
Canonical original task: `task_9d01d4520634` / dispatch `ctx_4da38f5feed2`.
Review task: `task_190031ae9b43` / dispatch `ctx_04be79a61d66` (independently REVISEd `cf71ac85cc88630bdc18d397564dd62c3f9679fa`).
Author: Antigravity (worker terminal `term_837cc8b3-a318-459d-be27-5c925b91d88d`).
Coordinator: Codex (terminal `term_0aecb9de-e52d-4a29-b1aa-42df8fdd8be6`).
Assigned worktree: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-backend-correction-1` on branch `codex/v03-backend-correction-1`.
Assigned base commit: `5e50dababc291190b8b93d039746c70ea3914b04` (direct descendant of `cf71ac8` adding only integrator migration `003_manifest_integer_fields.sql`).
Accepted application prerequisite: `1e140dc3db6bd9d052206cb3ae385b771d39c9dd`.

**Outcome: WORKER-REPORTED.** Submitted for independent review. Correction count: submission 1 under original V03-B1; 0 prior submitted corrections, 0 unsuccessful corrections. No deployment, publication, or live provider spend performed.

---

## One numbered blocker batch: observed resolution evidence

### 1. Blocker 1: Partial-trace evidence and detector cohorts are reconciled with effective cast
- **Decision:** One single effective terminal-trace cohort (`valid_pids = [c['persona_id'] for c in checkpoints if c['status'] in ('stopped', 'complete')]`) governs all final metrics, evidence IDs, stop trigger inputs, and note references.
- **Implementation in `apps/api/app/reporting.py`:**
  - Metrics calculate rates from terminal persona traces (`traces`), and all metric `evidence_ids` (retention survival/drop-rate, engagement actions, hook/pacing scores, completion) select only from `terminal_reactions`.
  - Deterministic detector `stop_trigger` receives only `terminal_reactions`, ensuring its entrant denominator and numerator reflect the effective terminal cohort rather than uncompleted prefixes.
  - Additive `coverage.excluded_traces = {'failed': failed_pids, 'pending': pending_pids}` explicitly identifies excluded persona IDs while preserving existing coverage fields.
  - Candidate notes citing evidence from excluded traces fail validation with `invalid_reference`.
- **Observed Evidence:**
  - `TestCorrection1BlockerRegressions.test_cohort_isolation_three_trace_controlled_fixture`: Controlled 3-persona fixture with p001 stopped, p002 complete, and p003 failed after a scene 0 prefix. Scene 0 retention has 2 entrants, 1 stop, survival 50.0% and drop rate 50.0% (denominator 2, not 3). `stop_0` observation trigger has denominator 2 and numerator 1 (value 0.50 >= 0.15 threshold). `engagement.like` observed is 50.0% (1/2, p002) without citing p003's evidence. `engagement.share` (taken only by p003 in its excluded prefix) is 0.0% with `evidence_ids: []`. `coverage.excluded_traces` reports `failed: ['p003']`, `pending: []`. Note candidate citing p003's excluded evidence is rejected as `invalid_reference`.
  - `TestCorrection1BlockerRegressions.test_real_scheduler_fault_incomplete_run_and_report`: Real database run executed by production `process_once()`. Checkpoint p003 fails during execution; worker completes reporting. API run state returns `status: 'incomplete'`, `requested: 3`, `effective: 2`, `failed: 1`. Persisted report returns `cast.status: 'incomplete'`, `coverage.excluded_traces: {'failed': ['p003'], 'pending': []}`, and scene 0 entrants: 2.

### 2. Blocker 2: Manifest integer type guard and health compatibility
- **Decision:** Enforce JSON numeric integer count and seed types in schema guard and require schema version 3 in health endpoint without rewriting migration 002.
- **Implementation:**
  - Integrator supplied additive `migrations/003_manifest_integer_fields.sql` at base `5e50dab`, adding check constraint `runs_manifest_integer_fields` checking `jsonb_typeof(manifest->'requested')='number'` and regex `^(0|[1-9][0-9]*)$`, plus same for `resample_seed`, inserting version 3.
  - Updated `apps/api/app/main.py` health endpoint to require version 3: `assert 1 in rows and 2 in rows and 3 in rows`.
- **Observed Evidence:**
  - `TestCorrection1BlockerRegressions.test_migration_003_manifest_integer_type_guard_and_health`:
    - Health endpoint `GET /health` returns HTTP 200 `{'status': 'ok', 'database': 'postgresql', 'storage': 'private_s3', 'inference': 'recorded_only'}`.
    - Verified `schema_migrations` contains `{1, 2, 3}`.
    - Verified valid integer manifests accepted on real PostgreSQL: `requested: 3, resample_seed: 20261028` and `requested: 50, resample_seed: 0`.
    - Verified invalid manifests rejected by PostgreSQL `CheckViolation`: string count (`'3'`), string seed (`'20261028'`), fractional count (`3.5`), fractional seed (`1.5`), null count (`None`), null seed (`None`), bool count (`True`), bool seed (`False`), negative count (`-1`), and negative seed (`-5`).
    - Verified idempotent repeat application of `003_manifest_integer_fields.sql` text without error.

### 3. Blocker 3: Metric kinds strictly in frozen C5 enum and explicit unavailable reasons
- **Decision:** Eliminate unsupported `observed_rate` discriminant in favor of `simulation_range`. Ensure every zero-effective or zero-respondent metric provides explicit safe `unavailable_reason`, truthful denominator, and null observed/range.
- **Implementation in `apps/api/app/reporting.py`:**
  - Changed `engagement` metrics from `kind: 'observed_rate'` to `kind: 'simulation_range'`.
  - When `effective == 0`, metrics report `observed: None`, `range: None`, `denominator: 0`, and explicit `unavailable_reason: 'no_effective_traces'`:
    - `completion`
    - Scene `survival` in `retention`
    - Engagement metrics `like`, `share`, `save`, `comment`
    - Scores `hook`, `pacing`
  - Preserved existing signal-specific unavailable reasons:
    - `engagement.follow`: `unavailable_reason: 'action_not_observed_by_legacy_provider'`
    - Retention `drop_rate` with 0 entrants: `unavailable_reason: 'no_scene_entrants'`
    - Scores `clarity`: `unavailable_reason: 'confusion_signal_unobserved'`
    - Scores `cta`: `unavailable_reason: 'cta_understanding_signal_unobserved'`
    - Scores `trend`: `unavailable_reason: 'grounded_trend_rules_unavailable'`
- **Observed Evidence:**
  - `TestCorrection1BlockerRegressions.test_zero_effective_metrics_contract_and_frozen_kinds`: Controlled fixture with all 3 personas failed (effective: 0). Verified all metrics in retention, engagement, scores, and completion have `kind` in frozen set `{'observed_count', 'simulation_range', 'heuristic_index', 'hypothetical_reach'}` with no `observed_rate`. Verified all 8 zero-effective metrics report `unavailable_reason: 'no_effective_traces'`, null observed, null range, and denominator 0.

### 4. Blocker 4: Additive note_rejections vocabulary and aggregator validation
- **Decision:** Retain rejected note reasons in additive `note_rejections: Record<safe_reason_code, int>` alongside `suppressed_notes`, with bounded safe vocabulary whose category counts sum to `suppressed_notes`. Exercise via production aggregator `build_report`.
- **Implementation in `apps/api/app/reporting.py`:**
  - Defined bounded safe vocabulary: `unsupported_trigger`, `quote_mismatch`, `invalid_time`, `invalid_reference`, `malformed_candidate`.
  - Each note candidate in `note_envelope` is validated using shared `normalize_note` and terminal evidence:
    - Missing trigger or note outside trigger -> `unsupported_trigger`
    - Unmatched quote -> `quote_mismatch`
    - Unsupported note time or invalid range -> `invalid_time`
    - Non-terminal evidence reference or note does not cite trigger -> `invalid_reference`
    - Missing fields, non-dict, or type error -> `malformed_candidate`
  - Persisted `note_rejections` in returned report dictionary; `suppressed_notes` set to `sum(note_rejections.values())`.
  - No raw provider exceptions, prompt text, or quotes leaked in rejection counts.
- **Observed Evidence:**
  - `TestCorrection1BlockerRegressions.test_aggregator_note_rejections_and_ranking`: 6 controlled candidates passed through production `build_report`: 1 valid note accepted into `notes`; 5 suppressed candidates categorized into `unsupported_trigger: 1`, `quote_mismatch: 1`, `invalid_time: 1`, `invalid_reference: 1`, `malformed_candidate: 1`. `suppressed_notes: 5` equals sum of `note_rejections.values()`.
  - `TestCriteria234FullRunEvidenceAndReporting.test_criterion4_report_math_and_notes`: Stage 2 historical note candidate for scene 5 correctly categorized with `note_rejections: {'unsupported_trigger': 1, 'quote_mismatch': 0, 'invalid_time': 0, 'invalid_reference': 0, 'malformed_candidate': 0}` and `suppressed_notes: 1`. Calling production `build_report` with grounded valid candidate matching `stop_0` produces `notes: 1`, `trigger_id: 'stop_0'`, `suppressed_notes: 0`.

---

## Report shapes and observed counts

### 1. Complete 50-Person Flash Run
- `status`: `'complete'`, `stage`: `'report'`
- `manifest`: `profile: 'flash'`, `requested: 50`, `resample_seed: 20261028`, 50 unique ordered `persona_ids` (`p001`..`p050`).
- `cast`: `requested: 50`, `effective: 50`, `stopped: 50`, `failed: 0`, `pending: 0`, `status: 'complete'`.
- `coverage.excluded_traces`: `{'failed': [], 'pending': []}`.
- `retention` (8 scenes):
  - Scene 0: 50 entrants, 11 stopped, survival 78.0% [70.0, 86.0], drop rate 22.0% [14.0, 30.0].
  - Scene 6: 29 entrants, 29 stopped, continued 0, survival 0.0%, drop rate 100.0%.
  - Scene 7: 0 entrants, 0 stopped, survival 0.0%, drop rate `observed: None, unavailable_reason: 'no_scene_entrants'`.
- `engagement`:
  - `save`: observed 50.0% [42.0, 58.0], denominator 50, `kind: 'simulation_range'`.
  - `follow`: observed `None`, denominator 50, `kind: 'simulation_range'`, `unavailable_reason: 'action_not_observed_by_legacy_provider'`.
- `scores`:
  - `hook`: observed 78.0% [70.0, 86.0], denominator 50, `kind: 'heuristic_index'`.
  - `pacing`: observed 58.0% [48.0, 68.0], denominator 50, `kind: 'heuristic_index'`.
  - `clarity`, `cta`, `trend`: observed `None`, `kind: 'heuristic_index'`, truthful unavailable reasons preserved.
- `notes`: `[]` (0 reported notes; stage 2 candidate for scene 5 is unsupported).
- `suppressed_notes`: 1.
- `note_rejections`: `{'unsupported_trigger': 1, 'quote_mismatch': 0, 'invalid_time': 0, 'invalid_reference': 0, 'malformed_candidate': 0}`.

### 2. Incomplete Faulted Run (Real Scheduler / DB Fault)
- `status`: `'incomplete'`, `stage`: `'report'`
- `cast`: `requested: 3`, `effective: 2`, `stopped: 2`, `failed: 1`, `pending: 0`, `status: 'incomplete'`.
- `coverage.excluded_traces`: `{'failed': ['p003'], 'pending': []}`.
- Scene 0 entrants: 2 (failed persona p003 excluded from terminal cohort).

### 3. Failed Run (Zero-Effective Controlled Fixture)
- `status`: `'failed'`
- `cast`: `requested: 3`, `effective: 0`, `failed: 3`, `pending: 0`, `status: 'failed'`.
- `coverage.excluded_traces`: `{'failed': ['p001', 'p002', 'p003'], 'pending': []}`.
- All 8 metrics (completion, retention survival, like, share, save, comment, hook, pacing) emit `observed: None`, `range: None`, `denominator: 0`, `unavailable_reason: 'no_effective_traces'`.
- All metric kinds strictly in frozen C5 set.

---

## Verification commands and exit codes

Environment: Windows; Python 3.10.2 venv `C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe`, PostgreSQL 17 on port 55432, RustFS S3 on port 59000, isolated database `viralist_v03_backend_correction1`, isolated bucket `viralist-v03-backend-correction1`. `VIRALIST_RUNTIME=C:/Users/Shrikar/.codex/viralist-v03-backend-correction-1/runtime.json`.

| Command | Exit Code | Observed Result |
|---|---|---|
| `python -m unittest tests.test_v03_flash_backend -v` | 0 | 14 tests passed (107.364s): Criteria 1-6 + 5 correction blocker regressions |
| `python -m unittest tests.test_v03_flash_backend.TestCorrection1BlockerRegressions -v` | 0 | 5 tests passed (9.388s): Blocker 1-4 regressions + real scheduler fault |
| `python -m unittest tests.test_normalized tests.test_domain_integration tests.test_api_security_isolation tests.test_full_journey -v` | 0 | 28 tests passed (12.035s): Baseline V02 suites preserved |
| `python -m tests.reconcile_saved` | 0 | Evidence reconciliation: PASS (19 reactions, 1 supported note, 1 suppressed note) |

---

## Invariants preserved

1. **Zero Provider Spend / Live Inference:** Provider adapter remains fail-closed. All 50-persona Flash traces were served from verified private stage 2 bounded evidence (`apps/api/recorded-50-index.json`). No API keys accessed or paid provider calls made. Provider spend remains within authorized $30 cap.
2. **Post-Stop Invariant:** Simulated viewers receive zero later media frames, summaries, or reactions once stopped.
3. **Data Isolation and Truthful Deletion:** Immediate session-revocation precedes asynchronous deletion; S3 HEAD 404 verified for all registered objects after deletion.
4. **Frozen Schema & Interfaces:** SQL migrations 002 and 003 untouched. Shared normalizer and metric kinds enum untouched.
