# Current state - 2026-10-29

## V02: integrated and journey-verified locally

- Verified application/integration commit: `1e140dc3db6bd9d052206cb3ae385b771d39c9dd`. Accepted candidate: `1ce2abefdd7780a4fc7fd5080d5bb2d47655d4d6` (Antigravity production behavior independently checked by Codex at parent1b322d5; Codex claim-only repair independently accepted by Antigravity). The current ledger update changes documentation only; running source stays at the exact integration commit.
- [Actual combined journey and command evidence](evidence/v02-integrated-journey.md): real UI B upload -> validation/private storage/PG durable worker -> recorded three-person simulation -> supported3-8s note -> refresh -> actual API restart -> same report -> scoped deletion. A has eight scenes/33.782s/no supported note/one suppressed. Other-session access/deletion denied; actual concurrent run creation/key conflicts checked. All35 registered journey objects HEAD404 and all selected run/object/job/event/reaction/checkpoint/provider-call rows absent after deletion. Historical inputs remain intact.
- Integration checks:28 Python checks, standalone19-reaction saved reconciliation and production build passed; deterministic actual local Chromium journey passed on the integration commit. Supplied six browser executions retain their1b322d5 revision scope; no false attribution to integration. Full accessibility, cross-browser, fresh inference, fifty-person performance and production deployment remain unverified.

| State | Revision / evidence |
|---|---|
| WORKER-REPORTED | Preserved Antigravity submissions576df90, a834fc2,1b322d5 and their original reports |
| REVIEW-ACCEPTED | Final candidate1ce2abe; [functional review/reassessment](evidence/v02-correction-2-review.md) plus [separate claim-repair acceptance](evidence/v02-evidence-record-review.md) |
| INTEGRATED | `1e140dc3db6bd9d052206cb3ae385b771d39c9dd`, local coordinator branch `codex/orchestration-readiness` |
| JOURNEY-VERIFIED | Same exact integration commit, actual local components/Chromium; recorded provider boundary |
| RELEASED | No; no app push, deployment or publication in this milestone |

## Ownership, runtime and preserved history

- No active supervised workers or source editors; all eight supervised worker terminals settled/released. Historical user-owned Codex terminal/worktree is preserved unchanged. Antigravity remains default implementation; Codex orchestration/architecture/integration/quality. The narrow claim-only exception followed two unsuccessful submitted corrections and explicit reassessment; count2 is retained, not reset. Primary quality task `task_16bbdf64e247` and its independent review `task_4a0da4cba911` settled in Run `run_eb62638ed3eb`.
- App is running at http://127.0.0.1:58000 from `C:/Users/Shrikar/orca/workspaces/viralist/codex-v02-integrated-runtime`, branch `codex/v02-integrated-runtime`, exact integration HEAD above. API listener15012/launcher2460; worker12228/launcher10008 at capture. Private runtime/process logs: `C:/Users/Shrikar/.codex/viralist-v02-integrated/`. Verify live process identity before recovery; PIDs can change. Shared PG17/RustFS volumes remain intact. README and journey evidence provide commands; API/worker need separate terminals with the same private runtime override.
- Coordinator checkout: `C:/Users/Shrikar/viralist`, branch `codex/orchestration-readiness`. Preserved author worktree `codex-v02-correction-2` at1b322d5; quality worktree `codex-v02-evidence-record` and read-only review at1ce2abe; all earlier commits/worktrees retained. `git worktree list` gives actual paths. Historical ledger is recoverable as `git show 1e140dc3db6bd9d052206cb3ae385b771d39c9dd:docs/STATE.md`; those old statuses are archival, not current acceptance.
- Paid ledger unchanged: estimate$13.38427320 + uncertain reserve$1.31327 = tracked maximum$14.69754320 against$15. No new provider inference calls. Orca per-worker new/cached/output tokens and actual model spend unavailable; do not invent totals. Correction2 elapsed39m09s; independent claim review6m49s by recorded UTC timestamps. Private media/auth/provider artifacts remain outside Git.

## Next permitted milestone

V02 is complete within its approved local recorded-inference scope. No additional worker is dispatched. V03 depends on separately authorized live Standard-provider smoke and full-Flash cost/latency/60s worst-case/p95 evidence; fifty-instance UX, A/B, thumbnails and releases remain later tasks. No new paid calls, deployment/publication or scope change is authorized by this completion. Existing architecture/upload choices remain settled.

Context map: [approved brief](PROJECT_BRIEF.md), [canonical local tasks/roadmap](../PLAN.md), [interfaces](CONTRACTS.md), [remaining acceptance gates](ACCEPTANCE.md), [design](DESIGN_DIRECTION.md), [accepted schema prerequisite](evidence/v00-correction-review.md). PLAN remains canonical until authorized GitHub tracker migration; no duplicate issue was created.
