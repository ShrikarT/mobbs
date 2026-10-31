# V03-B2G correction 1 review — REVISE

**Decision: REVISE** at `58c10aa1d9969afbd84eeb541a1ce87741996c3e`. Reviewer: Grok, acting coordinator, independent of Antigravity author task `task_2ffdc9f26a08`. Codex was not invoked. This is correction submission 1. It becomes unsuccessful review 1. One further submission is allowed.

Source review against `docs/contracts/budget-guard.v1.md` and the original eleven findings. The author's 26 PostgreSQL tests were not rerun: Docker's Linux engine pipe was down, so port 55432 was closed. `test_regression_finding_6_lifecycle_gates_and_stale_debt` only closes a stage and expects `BudgetDenied`. It never creates stale debt or reads pause from a fresh connection after the exception. A green author log would not cover finding 1 below.

Most of the public `BudgetGuard` surface now derives the quote, checks identity and the analysis lease, rejects forged replay, commits invalid-usage uncertainty before raising, keeps uncertain debt monotonic, requires reconciliation evidence, and restricts uncharged rejection to the typed categories. Those paths are not accepted by this review.

## Remaining batch

1. **P1 — stale debt does not durably pause, and a sibling send is still granted.** `BudgetGuard.dispatch` loads the account row, then `_check_and_pause_stale_debt` may set `pause_reason`, then the send decision reads the pre-update `acc['pause_reason']`. A reserved sibling on a still-valid lease is granted and the transaction commits both the pause and `state='dispatched'`. `BudgetGuard.reserve` does re-read status and raises `BudgetPaused`, but that raise is inside `db.connection()`. psycopg rolls the transaction back, so a fresh connection still shows `pause_reason` NULL. Contract: mutating methods commit the financial transition, then raise; unresolved dispatched/received debt with a missing, deleted, generation-mismatched, or expired job pauses admission and dispatch; a valid current in-flight job is not itself classified stale. Expected reproduction: persist one dispatched attempt, move that job's generation, leave a second attempt reserved on a current leased job, call `dispatch` for the second attempt. Expected: no send grant, and a new connection observes the pause. Also call `reserve` for a new unit and, after the typed pause error, observe the same committed pause.

2. **P1 — cancellation still stores arbitrary text in the financial row.** `cancel_unspent` writes the caller `reason` into `error_code` and `billing_receipt.cancelled_reason` with no enum or identifier bound. `record_uncertain` copies the existing `billing_receipt` object forward and does not run it through `sanitize_billing_receipt`. Contract: never store raw or private text, and every surviving financial writer accepts only bounded scalars. Expected: cancellation reason is a fixed enum or a bounded identifier; uncertainty rewrites only sanitized scalar receipt fields; a synthetic transcript marker in either input is absent from the committed JSON.

## Milestones

WORKER-REPORTED correction remains. REVIEW-ACCEPTED, INTEGRATED, JOURNEY-VERIFIED, and RELEASED are not earned. No paid call and no schema change is authorized by this review.
