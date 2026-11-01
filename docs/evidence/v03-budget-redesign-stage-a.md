# Budget redesign fixture checkpoint

Frozen test-only commit: `c0b2ab0a06243569c6a01d2f8d25ab4b6ab11bee`, base `48c0a83`, branch `codex/v03-budget-redesign`. Same Task `task_78ff6c14c403` / Dispatch `ctx_bb6e7b063d8e`. Author reports real PostgreSQL execution of 20 tests in21.871s:7 pass,13 product assertion failures,0 harness errors,exit1. Coordinator inspected the committed tests/helpers/evidence and clean scope; did not rerun under degraded shared runtime. Production modules are unchanged.

Coordinator accepted fixture readiness only via reply `msg_d12af234bb9c` to checkpoint `msg_42f4a3b30443`. This is not complete v2 coverage, production acceptance, or reset of the original two failed correction submissions. Source Stage B is permitted after worker acknowledges the following single qualification batch. Further heavy DB/process tests are held while UI runtime degrades.

1. Use the exact contract ID grammar `[A-Za-z0-9_-]{1,128}`, cancellation/reconciliation enums, and pinned fingerprint names/serialization. Correct author evidence's narrower regex. Never cap/reduce known exposure; retain max reservation/known charge.
2. Huge-usage test must require `BudgetUsageError`, not swallow arbitrary exceptions, and independently read preserved exposure/debt.
3. Total/stale reconciliation controls must use valid v2 reason `provider_receipt_verified` so an invalid enum cannot mask the target. Cover exact/conflicting reconciliation replay and same-hash changed receipt metadata and equal-cost changed usage.
4. Add focused bool/NaN/oversized metadata/privacy controls across all writers and deletion, received-state stale debt,403/account-denial, and invalid bool/fractional/oversized Retry-After. Current20 cases do not prove these.
5. Concurrency must read persisted total exposure and child exit codes; receipt-crash case must recover settlement without resend. Ensure bounded joins/owned child cleanup and actual marker evidence support process-boundary claims.

Final redesigned candidate needs full v2 evidence and independent exact-commit review. No provider call, paid account, schema change or integration is authorized by this checkpoint.
