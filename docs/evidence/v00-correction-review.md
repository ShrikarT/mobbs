# V00-R1 independent correction review — submission 1

**Decision: ACCEPT.** All four original findings from `docs/evidence/v00-readiness-review.md` are resolved in candidate commit `715be0ee31f8ed3229e64b75853aff624c3f449c`. The submitted changes establish corrected saved-adapter and schema prerequisite readiness for local V02 development without introducing new blockers.

- Reviewer: Independent verification engineer (Antigravity default model, no helper agents), separate from author Codex.
- Run: `run_eb62638ed3eb`; Task: `task_436abf78d22b`; Dispatch: `ctx_cb461cd2c9a7`; terminal: `term_fe9cef6d-58e6-4d62-b783-e190e73112c9`.
- Reviewed exact candidate SHA: `715be0ee31f8ed3229e64b75853aff624c3f449c`.
- Base commit: `14cbdb036ea2ef9b8ef62f3e881c0de3d9d93e43`.
- Worktree root: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v00-correction-review`; branch: `codex/v00-correction-review`.
- Worktree status: clean before and after inspection (`git status --short` clean, `git diff --check` clean, 0 tracked edits).
- Environment: Windows 10, PowerShell, Python 3.10.2.
- Scope & isolation: read-only worktree; no tracked edits, commits, remote writes, or pushes. No live provider requests or key access (`MODEL_API_KEY` verified cleared). Private experiment evidence at `C:/Users/Shrikar/.codex/private-runs/viralist-spark13-20261028` inspected strictly through narrow sanitized reconciliation; no private model/transcript/media content was emitted or stored.

---

## Guidance and Startup Receipt

Verified checkout identity and read the following documents:
- Shared policy `C:/Users/Shrikar/AGENTS.md` and assigned `AGENTS.md`
- `docs/STATE.md` and `PLAN.md` (correction and V02 sections)
- Latest owner attachment `C:/Users/Shrikar/.codex/attachments/25e57a37-cc20-45d8-ba71-4cb854eb0d59/pasted-text-1.txt`
- Original review `docs/evidence/v00-readiness-review.md`
- Correction report `docs/evidence/v00-correction-1.md`
- `docs/CONTRACTS.md`
- Corrected fixtures: `docs/contracts/provider-saved.v1.json` and `docs/contracts/vertical-slice.v1.json`
- `contracts/normalized.py` and test suites `tests/test_normalized.py` and `tests/reconcile_saved.py`
- Affected architecture/brief/ADRs: `docs/PROJECT_BRIEF.md`, `docs/ARCHITECTURE.md`, `docs/adr/0001-simulation-evidence-boundary.md`, `docs/adr/0002-durable-worker.md`
- Orca guidance: `C:/Users/Shrikar/.agents/policy/ORCA-HANDOFF.md` and `orchestration` skill / runtime
- `code-review` skill (delegation disabled per assignment instructions)

Environment variables checked by name without value output:
- `ORCA_CLI_COMMAND`: unset
- `ORCA_DEV_REPO_ROOT`: unset
- `MODEL_API_KEY`: cleared

Startup receipt was sent via `orca orchestration ask` from `term_fe9cef6d-58e6-4d62-b783-e190e73112c9` and accepted by coordinator `term_d8e11dfc-625e-47b9-a5a1-dffec67d25cc` prior to test execution.

---

## Observed Verification Checks

| Check / Command | Observed Result | Scope and Boundary |
|---|---|---|
| `git rev-parse --show-toplevel`; `git branch --show-current`; `git rev-parse HEAD` | Exit 0; `C:/Users/Shrikar/orca/workspaces/viralist/codex-v00-correction-review`, branch `codex/v00-correction-review`, HEAD `715be0ee31f8ed3229e64b75853aff624c3f449c` | Exact assigned identity verified |
| `git status --short`; `git diff --check 14cbdb036ea2ef9b8ef62f3e881c0de3d9d93e43 HEAD` | Exit 0; clean tree, no whitespace/formatting defects | Verified before and after review |
| `Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue; python -m unittest discover -s experiments -p 'test_*.py' -v` | Exit 0; **25 passed** in 1.458s | Exercises actual offline scheduler, budget reservation, projection, and behavioral regression logic with external doubles |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | Exit 0; **14 passed** in 0.034s | Positive and negative checks for envelope normalization, strict JSON, verdict normalization, decimal half-up ms rounding, reaction validation, stop triggers, note normalization, anti-fake-proof regex, cast profile semantics, fixture validation, and deletion fencing |
| `python -m tests.reconcile_saved` | Exit 0; `{"result": "PASS", "counts": {"reactions": 19, "supported_notes": 1, "suppressed_notes": 1}}` | Reconciles 19 saved reactions and 2 notes across both test videos from private run `viralist-spark13-20261028` against ledger and response envelopes |
| Fixture hash and validation check (`contracts.normalized.validate_fixture`) | Exit 0; `validate_fixture` passed, byte SHA-256 verified | Structural, content hash, and arithmetic verification |

### Verified Fixture SHA-256 Hashes

- `docs/contracts/provider-saved.v1.json`: `39b2ac1f4488e992e624e9d54322f28639fb3a390ec44c44d1afe6021b69c2fd`
- `docs/contracts/vertical-slice.v1.json`: `17a3fc8168584edae5a1a04c78f64016042a95ae6e61b3264088aa7b49e335b0`

---

## Detailed Finding Resolution

### Finding 1: Provider response mapping and saved evidence reconciliation
- **Status: RESOLVED.**
- **Evidence:** `docs/contracts/provider-saved.v1.json` provides sanitized projections of actual historical provider responses from private runs:
  - Success case from final bounded source `04b852728ae22967f408f71e34f274911ab07578` (call #40).
  - Incomplete generation case from pre-repair source `e8abd1bee0b5706d9166aba4f38985ed6fa6bcff` (call #35, status `incomplete`, reason `max_output_tokens`, usage preserved at 3441 total tokens with 600 output tokens, `output: null`).
  - Transport HTTP 500 error from pre-repair source `e8abd1bee0b5706d9166aba4f38985ed6fa6bcff` (call #16, status `error`, code `provider_http_error`, charge state `uncertain`, ledger-only, no fabricated response body).
- **Semantics:**
  - `reported_version` is explicitly `null` (provider response headers/body do not provide an immutable version string).
  - `cancellation` is explicitly `'unknown'` (unexercised).
  - `refusal` is explicitly `'unobserved'` (all saved responses checked; 0 refusal blocks observed). Refusal discrimination logic is implemented in `normalize_envelope` and covered by synthetic unit tests.
  - All private model text is replaced by synthetic `{}` in public projections; reasoning tokens are tracked in usage while reasoning text is stripped.
  - `provider_request_shape` in `vertical-slice.v1.json` is updated to Spark 1.3 with current-frame image data URL and scene-local observations, marked as an illustrative path.

### Finding 2: Reconciled reaction and note producer/consumer contracts
- **Status: RESOLVED.**
- **Evidence:** `contracts/normalized.py` establishes the shared, production-ready boundary:
  - `normalize_verdict` strictly parses legacy experiment outputs: enforces exact expected persona ID, single verdict item, non-empty reason, legacy action whitelist (`{'like', 'share', 'save', 'comment'}`), and <=30-word impression. Rejects unauthorized string actions (such as `'execute_tool'`) and unexpected actions (such as `'follow'`).
  - Decimal half-up rounding: `milliseconds()` uses `Decimal * 1000` with `ROUND_HALF_UP` to integer ms.
  - `validate_reaction` validates actions in enum `{'like', 'share', 'save', 'comment', 'follow'}`, enforces unique actions, validates `start_ms <= at_ms < end_ms` or `at_ms: None` with `timing: 'unobserved'`, and validates impression bounds (<=60 words).
  - Continued viewer reasons are stored in `evidence` as `simulated_reason` quotes and kept out of `drop_reason` (`drop_reason` is strictly null for continuing viewers, and required text for stopped viewers).
  - Deterministic detector `stop_trigger` requires >=15% stopped viewers among scene entrants and rejects duplicate respondents.
  - `normalize_note` validates notes against deterministic triggers, enforces exact evidence quote matching, verifies time boundaries within trigger and cited scene, and applies anti-fake-proof filters (rejecting suggestions to fabricate mock product UI or testimonials).
  - Across the 19 saved small-cast reactions, 19 converted cleanly; of the 2 notes, 1 supported note converted and 1 unsupported note was suppressed.

### Finding 3: Complete synthetic report/deletion fixtures and small-profile rules
- **Status: RESOLVED.**
- **Evidence:** `docs/contracts/vertical-slice.v1.json` provides a complete synthetic vertical slice:
  - Explicit provenance: `SYNTHETIC_DESIGN_FIXTURE_NOT_PROVIDER_EVIDENCE`.
  - Cast profile semantics: `cast_status` implements explicit rules for `'test'` vs `'flash'`. In the test profile (2 requested), a stopped viewer (p1 at scene 0) is a valid terminal trace; 2 valid traces earn `'complete_test_profile'`. Test runs are cleanly insulated from Flash's 50-person or 40-person completion thresholds.
  - Fixture trust block includes mode `'synthetic'`, explicitly unavailable source SHA, observation timestamp in UTC, all 5 content/config SHA-256 hashes matching canonical `content_hash()`, empty usage ledger, and unobserved model calls.
  - Hand-checkable resampling arithmetic verified: completion count 1, denominator 2, 50% observed, bootstrap indices `[[0, 0], [0, 1], [1, 1]]`, samples `[0, 50, 100]`, nearest-rank range `[0, 100]`.
  - Deletion lifecycle: `validate_deletion` verifies full target inventory (`originals, derivatives, provider_files, runs, events, reports, jobs`), access revocation timestamp, per-target retry on failed provider deletion, completed timestamps, and repeat deletion stability (repeat returns identical deletion ID).
  - Fencing and event discrimination: `may_publish_job` demonstrates atomic lease fence checks (lease generation matching current generation and tombstone check); `event_examples` demonstrates discriminated event types (`persona.stopped`, `run.snapshot` with reset and sequence, and deletion lifecycle events).

### Finding 4: Settled owner authority and prerequisite ownership
- **Status: RESOLVED.**
- **Evidence:**
  - Owner decisions from 2026-10-28 are recorded across `PLAN.md`, `docs/STATE.md`, `docs/PROJECT_BRIEF.md`, `docs/ARCHITECTURE.md`, and ADRs. Approved stack: React + TypeScript frontend, FastAPI/Python API and durable worker, PostgreSQL, private storage, FFmpeg, explicit Meta Standard adapter; MP4 <=60s and <=200MB.
  - Prerequisite ownership is explicit: this review independently accepts candidate commit `715be0ee31f8ed3229e64b75853aff624c3f449c` for corrected adapter/schema feasibility. The candidate commit does not fabricate an acceptance SHA. The coordinator records the accepted SHA and integration baseline upon receiving this report.
  - V02 prerequisites are cleanly bounded: requires only (a) offline scheduler/budget properties observed at `a2c90b5e99109d79a8ebbf2249aab0960838666a` and (b) corrected adapter/schema feasibility observed at `715be0ee31f8ed3229e64b75853aff624c3f449c`. Full-Flash S2 criteria (50-person Flash, <=$0.50, <=90s, 60s worst-case, p95) are recognized as V03 gates and do not block V02.
  - Historical paid provider runs at source `04b852728ae22967f408f71e34f274911ab07578` remain WORKER-REPORTED. No paid runs or live inference are promoted to REVIEW-ACCEPTED based on offline tests. Spend ceiling remains preserved at $14.69754320 / $15 ceiling with $0 new spend.

---

## Acceptance States and Boundaries

| Milestone / Component | State at Reviewed SHA `715be0ee31f8ed3229e64b75853aff624c3f449c` |
|---|---|
| Corrected adapter & schema prerequisite | **REVIEW-ACCEPTED** |
| Bounded offline scheduler & budget logic | **REVIEW-ACCEPTED** (observed previously at `a2c90b5e99109d79a8ebbf2249aab0960838666a` and re-verified here) |
| Historical Spark 1.3 paid stages | **WORKER-REPORTED** (historical evidence read-only; not re-run or accepted as verified live runs) |
| Application integration (HTTP/DB/Worker/S3) | **UNIMPLEMENTED / PENDING** (expected V02 implementation work) |
| Full product user journey | **PENDING** (requires V02 implementation) |
| Full-Flash S2 cost/latency criteria | **PENDING** (V03 milestone gate) |
| Release / Deployment | **INAPPLICABLE** |

---

## Conclusion and Next Action

Candidate commit `715be0ee31f8ed3229e64b75853aff624c3f449c` satisfies all four original correction criteria.
The coordinator should:
1. Record `715be0ee31f8ed3229e64b75853aff624c3f449c` as the accepted V00-R1 prerequisite revision and establish the integration dispatch baseline.
2. Dispatch a single V02 implementation worker to construct the thin real user journey (React/TS, FastAPI/Python durable worker, PostgreSQL, private storage, FFmpeg, Standard Meta adapter) under the approved limits.
