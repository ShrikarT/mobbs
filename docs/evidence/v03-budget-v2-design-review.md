# Independent review of V03 budget guard redesign contract v2

Decision: **ACCEPT** for proposed redesign contract `docs/contracts/budget-guard.v2.md` and `docs/adr/0003-budget-guard-redesign.md` at committed revision `a7d0354424276fb2106c3fd9dadb068053619e5e`.

**Qualification:** This ACCEPT decision certifies contract and design specification completeness only. It does NOT constitute acceptance of candidate code (`48c0a8398086e94320f34fbe575834957d022cab` or any other), database persistence/concurrency behavior, provider integration, journey verification, or release authority. The candidate code remains WORKER-REPORTED. A real PostgreSQL fixture is an explicit future READY gate for any implementation dispatch, not something this document review can satisfy.

Independent Antigravity verifier; Orca Task `task_26f757315c91`, Dispatch `ctx_bdc27a19a571`, Run `run_d3354faa0659`; parent product Task `task_2ffdc9f26a08`. No implementation, no helpers, no tracked source edits, no commits, no database actions, and no network/provider calls.

---

## 1. Verified Workspace, Authority, and Source Audit

- **Actual Workspace Root:** `C:/Users/Shrikar/orca/workspaces/viralist/viralist-v03-budget-v2-design-review`
- **Actual Branch:** `ShrikarT/viralist-v03-budget-v2-design-review` (Orca-managed unique child branch branched from `codex/orchestration-readiness`)
- **Committed Baseline HEAD:** `a7d0354424276fb2106c3fd9dadb068053619e5e`
- **Working Tree Status:** Clean (`git status --porcelain=v1` returns empty; no tracked or untracked file changes)
- **Startup Receipt & Authority:** Startup receipt sent via `orca orchestration ask` and approved by coordinator (`Approved. Proceed with the read-only contract/ADR review against the exact sources named. Record that SQL004 is absent from the review branch but available at c58fd52 and inspect it via that commit. No DB, service, code, provider, credential, push or deployment work. Write only the sanitized private report and submit one decision.`).
- **Private Artifact Location:** Sanitized report written only under `C:/Users/Shrikar/.codex/viralist-v03-budget-v2-design-review/report.md`.
- **Documents Read:**
  1. `C:/Users/Shrikar/AGENTS.md` (shared engineering policy)
  2. project `AGENTS.md` (`C:/Users/Shrikar/orca/workspaces/viralist/viralist-v03-budget-v2-design-review/AGENTS.md`)
  3. `docs/STATE.md`
  4. `PLAN.md`
  5. `docs/adr/0003-budget-guard-redesign.md`
  6. `docs/contracts/budget-guard.v2.md`
  7. `docs/evidence/v03-budget-correction-2-review.md` (sanitized report of C2 review)
  8. `docs/evidence/v03-budget-correction-1-review.md` (sanitized report of C1 review)
  9. `docs/evidence/v03-budget-review-r1.md` (sanitized report of Round 1 review)
  10. `docs/contracts/budget-guard.v1.md`
- **Document Gaps Recorded:**
  - `migrations/004_provider_budget.sql` is absent from current branch HEAD `a7d0354424276fb2106c3fd9dadb068053619e5e` (the branch contains migrations 001–003). As authorized by the coordinator, the exact migration was inspected via commit `c58fd52f2153b75e84a8a7ca819b3ecffe46b2b3` on branch `codex/v03-budget-schema`.
  - Candidate implementation files `apps/api/app/budget.py`, `apps/api/app/budget_types.py`, and `tests/test_v03_budget.py` are at candidate commit `48c0a8398086e94320f34fbe575834957d022cab` and were inspected via git.

---

## 2. Review Questions Detailed Analysis

### Question 1: Coverage of Original Eleven Findings and Correction-2 Criteria

Contract v2 addresses each of the eleven original findings and both correction-2 criteria with explicit, testable rules rather than relying on author assertions or green suite claims:

1. **Finding 1 — Underquote & Helper Price/Margin Overrides (P2 source defect):**
   - *Problem in Candidate `48c0a83`:* Pure helpers `calculate_cost` and `compute_reservation` accepted arbitrary caller-supplied price schedules, negative prices, and zero margins, permitting arbitrary underquotes.
   - *v2 Rule:* Lines 24–27 mandate strict JSON request validation (object only, no duplicate keys, no NaN/Infinity, no trailing data). Actual `model` and strict integer `max_output_tokens` must equal pinned Spark 1.3 profile and `RequestBound`. Public price and margin parameters are completely removed from all helpers; helpers and the guard must share the same constants and validator. Guard derives the reservation internally using a fixed 10% input margin and upward rounding (100k input + 20k output costs USD 0.2100000000 and reserves USD 0.2225000000). Context is strictly bounded by 1,048,576.
   - *Testable Rule:* Fully testable via unit tests and Fixture Criterion 1.

2. **Finding 2 — Canonical Identity & Paid Policy Omission (P1 source defect):**
   - *Problem in Candidate `48c0a83`:* Constructor accepted paid identity with arbitrary non-canonical values (cap 1, opening 0, source digest 0) because `_verify_binding_and_lock_account` only checked equality between configuration and persisted database row.
   - *v2 Rule:* Lines 17–20 define `BudgetIdentity` binding database name, account ID, ledger instance, environment, canonical source-ledger digest, cap, and opening amounts. Paid identity fails closed unless its exact digest (`8b7929c67cda1d8cf81efea387eef98afaf384989c14fab6ed14ba1aefd293bc`), cap ($30.00), opening settled ($13.38427320), and opening uncertain ($1.31327) match authorized constants. Test identity cannot select or create a paid row. Equality between two misconfigured values is explicitly rejected.
   - *Testable Rule:* Testable via Fixture Criterion 2 without requiring a live paid account.

3. **Finding 3 — Analysis Job Lease Tuple & Domain Binding (P1 source defect / runtime blocked):**
   - *Problem in Candidate `48c0a83`:* Joint validation was present in source (`_verify_lease_tuple`), but unverified on PostgreSQL due to timeout; first-run fallback was previously problematic.
   - *v2 Rule:* Lines 31 and 59–60 require persisting a canonical fingerprint over the complete tuple (video, run, job, generation, lease, stage, unit, attempt ordinal). Valid current unexpired lease is accepted; expired, missing, deleted, or mismatched generation retains debt and pauses admission. First-run fallback is prohibited.
   - *Testable Rule:* Testable via Fixture Criterion 3 & 6.

4. **Finding 4 — Immutable Replay & Receipt/Evidence Identity (P2 source defect):**
   - *Problem in Candidate `48c0a83`:* Reserve replay omitted job/video/generation; settle replay compared only receipt hash and cost, treating differing usages with equal costs (e.g. 1000/200 vs 320/400 at $0.0021) as identical idempotent replays; receipt hash replay ignored changed billing evidence.
   - *v2 Rule:* Lines 31–34 specify two distinct canonical fingerprints: (a) reserve/retry fingerprint over account/ledger identity, full lease tuple, stage, unit, attempt, request hash, count hash, model/pricing/context, and derived quote; (b) settlement fingerprint over received receipt hash, normalized usage counts, model/version, status, calculated charge, and validated billing IDs. Any changed usage/evidence conflicts even if cost is identical. Exact identical replay is idempotent.
   - *Testable Rule:* Testable via Fixture Criterion 4.

5. **Finding 5 — Transaction Boundary & Arithmetic Overflow Rollback (P1 source defect):**
   - *Problem in Candidate `48c0a83`:* Exception exit previously rolled back uncertainty/pause; candidate caught `BudgetUsageError` outside transaction, but counts lacked pre-arithmetic upper bounds. Large counts (e.g. `10**40`) raised uncaught `decimal.InvalidOperation` before `with connection()`, preventing the transaction from ever executing and leaving pause uncommitted.
   - *v2 Rule:* Lines 13, 27, and 49–61 establish that the public guard is a façade over private storage transitions. Every mutating transition runs in its own transaction and commits outcomes (including pause and uncertainty) before the façade raises typed exceptions outside the transaction. All counts are bounded by model context before Decimal arithmetic, non-finite decimals are rejected, and excessive usage durably transitions to uncertain with maximum representable debt before returning/raising.
   - *Testable Rule:* Testable via Fixture Criterion 5.

6. **Finding 6 — Lifecycle Gates, Pause Serialization & Stale Debt (P1 source defect / runtime blocked):**
   - *Problem in Candidate `48c0a83`:* In C1, dispatch read pre-update pause and granted sibling sends; reserve raised inside transaction rolling back pause. In C2, source changes were made, but persistence and concurrency were BLOCKED by DB downtime.
   - *v2 Rule:* Lines 59–61 mandate that discovering stale dispatched/received debt commits pause before returning a denial. Dispatch must evaluate pause state post-update. Reserve does not raise inside the transaction. A valid current unexpired lease is not stale. Stage closure blocks dispatch.
   - *Testable Rule:* Testable via Fixture Criterion 6 covering reserve-first discovery, sibling dispatch, and received-state debt.

7. **Finding 7 — Monotonic Uncertainty Exposure (P1 source defect / runtime blocked):**
   - *Problem in Candidate `48c0a83`:* Repeating uncertainty with omitted or lower partial charge erased prior higher partial charge or receipt.
   - *v2 Rule:* Lines 27, 55, and 67 require monotonic exposure: usage above reserved bound becomes durable uncertainty with at least the maximum representable known charge; repeated uncertainty cannot reduce partial charge, rewrite a receipt, or clear pause while uncertain or stale debt remains.
   - *Testable Rule:* Testable via Fixture Criterion 7.

8. **Finding 8 — Explicit Reconciliation & Total Usage (P1/P2 source defect):**
   - *Problem in Candidate `48c0a83`:* Reconciliation omitted `total_tokens` check, appended raw string `evidence.reason` after sanitization, failed to check stale dispatched/received debt before clearing pause, and replay conflicted instead of succeeding idempotently.
   - *v2 Rule:* Lines 46, 57, and 67–68 require `reconciliation_reason` to be a typed enum (not prose). Reconciliation requires a nonempty typed set of unresolved attempts, exact request and durable receipt hashes, canonical validated usage, and allowlisted receipt metadata. Shared settlement/reconciliation validation is enforced. Idempotent on exact replay. Pause is cleared only when all uncertain and stale debt is resolved.
   - *Testable Rule:* Testable via Fixture Criterion 8.

9. **Finding 9 — Retry & Refund Constraints (P1 source defect):**
   - *Problem in Candidate `48c0a83`:* Reserve path accepted any rejected state without verifying `rate_limit_429` category; 400 allowed immediate retry; Retry-After checked only `>0` without checking bool, fractional, or max bound (1–3600s); rejection replay did not recheck `request_sha256`.
   - *v2 Rule:* Lines 65–66 mandate that Attempt 1 is reservable ONLY after attempt 0 is a recorded `rate_limit_429` rejection with matching request hash, model, stage, full immutable basis, strict integer Retry-After in 1–3600 seconds, and the delay has elapsed. Attempt 2 is always denied. Other uncharged categories (400/403/account denial) never retry. Ambiguous failures become uncertain.
   - *Testable Rule:* Testable via Fixture Criterion 9.

10. **Finding 10 — Canonical Usage / Total / Cost Bound (P1/P2 source defect):**
    - *Problem in Candidate `48c0a83`:* Settle validated total, but reconciliation did not; counts had no upper bound before Decimal arithmetic.
    - *v2 Rule:* Lines 27 and 67 unify canonical usage validation across settle and reconciliation: strict integers, non-negative, booleans rejected, cached <= input, reasoning <= output, supplied total == input + output, bounded by model context limit.
    - *Testable Rule:* Testable via Fixture Criteria 5, 8, and 10.

11. **Finding 11 — Bounded Privacy-Safe Financial JSON (P1 source defect):**
    - *Problem in Candidate `48c0a83`:* Sanitizer allowlisted keys but permitted prose strings in `request_id`, negative token counts, NaN money, trailing newline in cancellation reason (`user_cancelled\n`), raw strings in reconciliation, and bypasses in alternate writers.
    - *v2 Rule:* Lines 37–46 establish `encode_financial_evidence` as the single mandatory gate for all writers (reserve, receive, settle, uncertainty, rejection, cancellation, reconciliation, recovery). It enforces ASCII grammar `[A-Za-z0-9_-]{1,128}` for opaque IDs, exact model allowlist, enumerated constants for status/pause/cancel/rejection/reconciliation, strict finite integers for counts/HTTP status, finite non-negative decimal strings (<=10 decimal places) for USD, and lowercase 64-char hex for hashes. Complete object validated; stripping invalid fields is rejected. Raw text, notes, prompts, transcripts, error messages, and exceptions are strictly forbidden.
    - *Testable Rule:* Testable via Fixture Criterion 10.

- **Correction-2 Criteria:**
  - *C2-1 (Stale debt race & sibling send grant):* Addressed in Lines 59–61 and Fixture Criterion 6.
  - *C2-2 (Privacy bounding across all writers):* Addressed in Lines 37–46 and Fixture Criterion 10.

---

### Question 2: Implementability against Existing SQL004 and Domain APIs

1. **Public Data Types:**
   - `BudgetIdentity`, `RequestBound`, `CanonicalUsage`, `RejectionEvidence`, and `ReconciliationEvidence` map cleanly to the required parameters.
   - In `apps/api/app/budget_types.py`, the existing dataclasses need straightforward adjustments: adding pre-arithmetic bound checks to `CanonicalUsage`, removing price/margin arguments from helper signatures, and adding an explicit enum for `reconciliation_reason`.

2. **Database Schema (SQL004 at `c58fd52f2153b75e84a8a7ca819b3ecffe46b2b3`):**
   - `budget_accounts`: Contains `id`, `ledger_instance_id`, `environment` (`CHECK in ('test','paid')`), `owner_cap_usd`, `opening_settled_usd`, `opening_uncertain_usd`, `source_ledger_sha256`, and `pause_reason` (`CHECK in ('ambiguous_charge','invalid_usage','over_bound_usage','reconciliation_required')`).
   - `budget_stages`: Keyed on `(account_id, id)` with `cap_usd` and `closed_at`.
   - `budget_attempts`: Keyed on `id`, unique on `(account_id, run_id, unit, attempt)`, partial unique index on non-terminal states. Contains `bound_basis` (JSONB), `billing_receipt` (JSONB), `reserved_usd`, `charged_usd`, `state`, `receipt_sha256`, and `error_code`.
   - All proposed v2 constructs (`encode_financial_evidence` output, immutable fingerprints, pause reasons, attempt limits 0..1) map directly into these tables without requiring schema modifications.

3. **Transaction Boundary & Lock Order:**
   - The façade pattern (private storage mutations in `with connection() as conn: ...` returning internal outcomes, committing upon context manager exit, and raising typed exceptions outside) directly matches psycopg transaction semantics and eliminates rollback vulnerabilities.
   - Lock order `video → current job → account/stage → attempt` aligns exactly with `domain.py:fence()`, which locks `videos` then `jobs`.
   - Stale recovery scans across other jobs avoid lock inversion by performing read-only queries on `jobs` without taking domain locks after account locks.

4. **Interfaces to Clarify during Implementation:**
   - *`reconciliation_reason` enum set:* Contract v2 mandates that `reconciliation_reason` become a typed enum (not prose), matching `cancelled_reason`. While candidate `budget_types.py` already had `VALID_CANCELLATION_REASONS`, it lacked `VALID_RECONCILIATION_REASONS`. The implementation must define this set explicitly (e.g. `{'provider_receipt_verified', 'stale_debt_reconciled', 'administrative_audit'}`). This is an implementation-level constant definition that does not block contract acceptance.
   - *Fingerprint storage representation:* Contract v2 requires canonical fingerprints for reserve and settlement. In implementation, storing this as a canonical SHA-256 digest (`fingerprint_sha256`) or as an immutable sub-object inside `bound_basis` and `billing_receipt` must be standardized.

---

### Question 3: Field-Level Financial JSON Rules

1. **Coverage Across Writers:**
   - `encode_financial_evidence` covers every writing path: reserve, receive, settle, uncertainty, rejection, cancellation, reconciliation, and recovery.
   - Alternate paths that previously bypassed sanitization in candidate `48c0a83` are unified under this single validator.

2. **Rejection of Content / Prose:**
   - Opaque IDs are constrained to ASCII `[A-Za-z0-9_-]{1,128}`. This regex rejects spaces, tabs, newlines, quotes, and punctuation, completely preventing transcript sentences (e.g. Canary sentences observed in C2 review) and newline injection (`user_cancelled\n`).
   - Notes, error messages, exception strings, prompts, transcripts, and arbitrary nested dictionaries are explicitly forbidden.

3. **Coherence with Legitimate Provider IDs:**
   - Provider request and response IDs across OpenAI, Anthropic, Meta, Google, and standard UUID/hex identifiers match `[A-Za-z0-9_-]{1,128}`. Legitimate IDs will not be rejected.

4. **Coherence of Bounds:**
   - Hashes: Lowercase 64-character SHA-256 hex (`^[0-9a-f]{64}$`), matching SQL004 regex check constraints.
   - USD values: Finite, non-negative decimal strings with <= 10 decimal places (`numeric(20,10)`).
   - Token counts: Strict non-negative finite integers bounded by model context (1,048,576); booleans strictly rejected.
   - HTTP status: Strict finite integers (100–599).
   - Fail-closed validation: Stripping invalid keys is rejected; any invalid or unexpected key causes rejection of the transition.

---

### Question 4: Acceptance Fixture Definition

Section "Real fixture and acceptance gate" (lines 70–94) provides a concrete, reproducible test specification:

1. **Preservation of Pre-Existing Rows:**
   - Requires unique test namespaces for test identities, accounts, stages, videos, runs, and jobs.
   - Captures created IDs; explicitly forbids table truncation, DB drop/recreation, or deleting pre-existing rows.
   - Cleanup is restricted to fixture-owned rows and only when no unsettled debt remains; crash/recovery debt is preserved as evidence.

2. **Fresh-Connection Verification:**
   - Mandates that after each mutation or exception, verification queries run on a fresh, independent database connection.

3. **Reproducible Triggers & Outcomes (Criteria 1–11):**
   - Criterion 1: Pinned 100k/20k fixture costs $0.2100000000, reserves $0.2225000000; non-canonical prices/margins rejected.
   - Criterion 2: Paid identity mismatch rejected before mutation; isolated test identity works without paid account.
   - Criterion 3: Forged tuple rejected; valid current lease accepted.
   - Criterion 4: Changed inputs on same request yield Conflict; identical replay is idempotent.
   - Criterion 5: Invalid/overflow usage transitions to uncertain, preserves debt, commits pause, and raises outside API.
   - Criterion 6: Stale debt discovered by reserve or sibling dispatch commits pause; sibling send withheld.
   - Criterion 7: Monotonic uncertainty preserves maximum known debt and receipt.
   - Criterion 8: Reconciliation rejects mismatched totals, raw reasons, absent receipts; clears pause only when all stale/uncertain debt is resolved.
   - Criterion 9: Attempt 1 allows retry only on rate_limit_429 after delay; attempt 2 denied.
   - Criterion 10: Private marker verified absent across fresh-connection queries of all tables/columns.
   - Criterion 11: Two-process concurrency against shared cap; child kill after dispatch commit and after receive commit; verified no resend.

4. **External Double & Commands:**
   - Allowed double is strictly limited to a local fsynced file marker double; provider network calls are strictly forbidden.
   - Commands specified: `python -m unittest tests.test_v03_budget -v` on existing PostgreSQL, bounded fixture driver for criteria 2–11, and `git diff --check`.
   - Clear limitation: DB timeout blocks READY state and is not counted as a code correction failure.

---

### Question 5: Invariants, Staged Authority, and Task Lineage

1. **Cumulative Provider Cap & Ledger Balance:**
   - Explicitly preserves $30.00 cumulative cap.
   - Binds opening settled ($13.38427320) and uncertain reserve ($1.31327000), total opening exposure $14.69754320, and source ledger digest `8b7929c67cda1d8cf81efea387eef98afaf384989c14fab6ed14ba1aefd293bc`.

2. **Privacy, Provenance, and Deletion Invariants:**
   - Financial ledger is completely decoupled from content/media tables (no foreign keys to content tables).
   - Domain deletion removes content, but debt rows survive without leaking media, prompts, notes, or transcripts.

3. **Staged Spending Authority:**
   - Explicitly forbids creating paid accounts, connecting guard to transport, calling external provider endpoints, running network smoke, or deploying.
   - Test identities are barred from paid transport.

4. **Task Lineage and Correction Limits:**
   - Adheres to Orca / shared engineering policy: preserves parent task `task_2ffdc9f26a08` and records that two correction rounds failed review.
   - Explicitly designates the next implementation task as a **redesign**, prohibiting task renaming or resetting correction history.

---

## 3. Single Numbered Decision Batch

1. **DECISION: ACCEPT.**
   - *Rationale:* Contract redesign `docs/contracts/budget-guard.v2.md` and `docs/adr/0003-budget-guard-redesign.md` provide a complete, sound, and implementable specification. They systematically resolve all 11 original review findings and both correction-2 criteria. The transaction boundary pattern (façade over private storage transitions), strict single financial encoder (`encode_financial_evidence`), dual canonical replay fingerprints, pre-arithmetic bound checks, lock order preservation, and explicit 11-point acceptance fixture establish an unambiguous blueprint for the redesign implementation.
   - *Implementation Note:* The implementing engineer should explicitly define the enum set `VALID_RECONCILIATION_REASONS` in `budget_types.py` alongside the existing `VALID_CANCELLATION_REASONS`, and specify whether the replay fingerprint is stored as a canonical SHA-256 field or sub-object in JSONB.
   - *Evidence Limits:* This decision certifies design and contract completeness only. It does not accept candidate code `48c0a83`, run tests, or authorize provider calls, paid accounts, database mutations, service restarts, integrations, or deployments. Execution of the real PostgreSQL fixture remains a mandatory READY gate before any future implementation acceptance.

---

## 4. Verification Check and Settlement

- Working tree remains clean at `a7d0354424276fb2106c3fd9dadb068053619e5e` on branch `ShrikarT/viralist-v03-budget-v2-design-review`.
- No tracked files created or modified.
- Sanitized private report written to `C:/Users/Shrikar/.codex/viralist-v03-budget-v2-design-review/report.md`.
- No database connections, health checks, or services invoked.
