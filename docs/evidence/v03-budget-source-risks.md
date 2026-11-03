# V03 budget guard: coordinator source inspection

Frozen candidate: `8edc79b097695a806f8c07038a6cf79ef8f4d546`.
Author task: `task_2ffdc9f26a08`; independent runtime review task: `task_ca196433bd63`.

This is engineering-lead analysis of Antigravity's guard implementation, not independent acceptance of coordinator-authored migration004. It does not change the candidate, submit a correction, or advance its WORKER-REPORTED state. PostgreSQL/process/deletion tests remain unverified. Existing independent infrastructure report remains authoritative for that limitation.

## Observed checks

The review tree `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-budget-review` was clean at exact candidate HEAD before and after inspection. Read all of `budget.py`, `budget_types.py`, relevant original live-standard contract, `db.connection`, and the invalid/over-bound test assertions. No provider/config secrets, network calls, DB writes, or service startup.

Private probe: `C:/Users/Shrikar/.codex/viralist-v03-coordination/guard-source-probe.py`, run with the existing v02-review Python venv. Initial import failed because the repository root was absent from `sys.path`; after adding both frozen root and `apps/api`, the actual production imports executed, exit0. No fake database or replacement production component was used.

- `compute_reservation({input_tokens:100000,max_output_tokens:20000})` returned `0.2225000000` USD, including the default input margin.
- `sanitize_billing_receipt({note:{transcript:'SYNTHETIC_PROBE'}})` returned the nested content unchanged.
- `compute_reservation({input_tokens:1500000,max_output_tokens:20000,context_limit:2000000})` returned `2.1475000000` instead of rejecting the pinned-model context overflow.

## Spec findings to reproduce with PostgreSQL

1. **P1 — reservation bound is not enforced at admission** (`budget.py:358,483`). `reserve` validates a positive caller amount but never calls `compute_reservation` or validates the bound fields. With a valid isolated account/lease, supply the 100k/20k bound above and `reserved_usd=Decimal('0.0000000001')`; the source permits admission against that amount. `compute_reservation` also trusts an oversized caller `context_limit` (executed above). Enforce the pinned complete request bound and conservative quote at the public admission boundary; reject an under-quote or malformed/oversized basis. Do not depend on every future transport caller voluntarily checking this.

2. **P1 — invalid-usage pause is rolled back on ordinary exception exit** (`budget.py:687-707`, `db.py:14-17`). `settle` writes uncertainty and account pause, then raises `BudgetUsageError`. A caller using `with connection() as conn: settle(...)` lets that exception reach psycopg's connection context, which rolls back the transaction. Existing invalid/over-bound tests catch the exception *inside* the open connection and inspect the same transaction (`test_v03_budget.py:399-414,431-445`); they do not prove durability under ordinary exception exit. Reproduce from a previously committed dispatched attempt, catch outside the connection, and inspect with a fresh connection. Preserve uncertainty/known charge durably before propagating failure, without committing unrelated caller work. SQL execution was unavailable here; this conclusion is from source transaction flow, not an observed DB rollback.

3. **P1 — existing reservations can dispatch after an account pause or stage closure** (`budget.py:516-575`). `dispatch` checks the lease and attempt state but never checks account pause or stage closure. Reserve two units; make one uncertain and commit; dispatch the other under a valid lease. The source grants it. Recheck/serialize the applicable account and stage gates at the committed send authorization boundary, including races, so newly ambiguous calls stop subsequent paid sends.

4. **P1 — reconciliation can clear a pause without resolving anything** (`budget.py:878-901`). `reconcile_account(conn, account, {}, clear_pause=True)` only requires a dictionary, unconditionally clears the account pause, and stores no reconciliation evidence. Bind reconciliation to explicit attempt/receipt evidence and validated state transitions; reject empty/unrelated evidence and unresolved new uncertainty. Prove this with a fresh-connection admission attempt after the empty reconciliation call.

5. **P1 — repeated uncertainty can reduce known debt** (`budget.py:790-830`). `record_uncertain` accepts an already-uncertain row and replaces `charged_usd` with the new optional value, including `None`. A first call with a known charge above the reservation followed by a default replay loses that known charge and reduces aggregated exposure to the reservation. Keep the maximum known charge and original receipt/evidence across idempotent recovery. Verify from fresh connections after both calls; also reject conflicting receipt identities rather than overwriting them.

## Standards/privacy finding

6. **P1 — billing evidence is not content-free** (`budget.py:164-181`, `budget_types.py:38-56`). The sanitizer filters top-level keys but accepts arbitrary nested values and unbounded text under `note`, `request_id`, and other allowed keys. The nested transcript probe above executes this behavior. Such data reaches `billing_receipt`, intended to survive content deletion. Enforce per-field scalar types, bounded identifiers/enums/numbers and content-free values; remove unrestricted note text. Audit alternate writers (`record_rejection`, `record_uncertain`, `cancel_unspent`) too, since they bypass this sanitizer. Use synthetic content in regression checks, never private payloads.

## Next permitted action

Keep the frozen guard unaccepted and paid stages closed. When independent review can resume, give the verifier this source analysis alongside the original unchanged G1–G6 criteria; require real PostgreSQL, fresh-connection durability and process controls. Consolidate verified blockers into one numbered author correction batch through the original Antigravity task lineage. No correction count is consumed by this source inspection. Coordinator must not self-approve migration004. Antigravity availability and local runtime restoration remain separate blockers.
