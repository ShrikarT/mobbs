# V03-B2G corrective submission 2

Antigravity implements this ordinary guard correction. No helpers. Same product task lineage as `task_2ffdc9f26a08`. This is the last allowed submission: correction 1 at `58c10aa` received one unsuccessful review. A second unsuccessful review stops the task for redesign.

## Baseline

Worktree `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-budget`, branch `codex/v03-budget`, clean base `58c10aa1d9969afbd84eeb541a1ce87741996c3e`. Own only `apps/api/app/budget.py`, `apps/api/app/budget_types.py`, `tests/test_v03_budget.py`, existing budget test helpers, and `docs/evidence/v03-budget-implementation.md`. Do not change SQL, domain, API, UI, manifests, or the coordinator tree.

Read `docs/contracts/budget-guard.v1.md` and `docs/evidence/v03-budget-correction-1-review.md` from the coordinator commit named in the dispatch. The two items below are the whole batch. Keep the public `BudgetGuard(identity)` methods and the fixes that already commit invalid-usage uncertainty before raising.

## Fixes

1. Stale dispatched or received debt must commit `pause_reason` before the call returns or raises. `dispatch` must decide from the pause state after that update, not from the account row loaded before it. A sibling reserved attempt on a still-valid lease must not be granted while that pause is required. A currently leased, unexpired, generation-matched job is not stale. `reserve` must not roll the pause back by raising inside `db.connection()`.
2. `cancel_unspent` must not persist arbitrary caller text. Use a fixed reason enum or a bounded identifier. `record_uncertain` must sanitize receipt fields before writing them back. A synthetic transcript marker must be absent from committed financial JSON.

## Checks

Add regressions that perform the review's reproduction on real PostgreSQL and read pause, state, and receipt JSON from a fresh connection. Use only the existing database `viralist_v03_budget`, port 55432, and the existing venv `C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe`. If Postgres is down, stop and report that blocker. Do not start Docker, reset data, or call a provider. Run `python -m unittest tests.test_v03_budget -v`. Commit one correction on `codex/v03-budget` and stop. Report the SHA, command, and exit code. Claim WORKER-REPORTED only.
