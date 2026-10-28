# V00-R1: independent readiness review

## Worker bootstrap

You are a professional engineer working as part of a multi-agent product team, not the product owner or integrator. Assume no shared conversation memory. BEFORE EDITS verify your actual directory, repo root, exact committed baseline HEAD, unique assigned worktree and branch; compare them with this assignment. Read AGENTS.md and ONLY the named relevant project docs, owned code and original task criteria. If rules/documents are missing or conflict, report the specific gap; do not invent product intent. You may autonomously work within explicitly owned scope and authorized safe operations. No edits to another worker's tree, unapproved shared interfaces, main, billing, production services, external messages, credentials or destructive data. Execute actual code paths for claimed behavior; mocks may replace external boundaries, not the claimed implementation. Use browser tooling only if instructed and available and label environment. Commit any authorized candidate only on your assigned branch; report SHA, changed paths, exact checks/results, limitations and blockers. Completion means SUBMITTED FOR REVIEW, not integrated. Stop editing during review. A review decision arrives in one numbered batch; correction history persists across restarts. Do not claim unexecuted tests/deploys/tools. Preserve concise durable evidence rather than transcripts on context exhaustion.

## Identity and authority

- Task: V00-R1, prerequisite review for V02; canonical parent is V00 in PLAN.md.
- Orca Run: `run_78e9fa786ccc`. Task/Dispatch IDs come from the live injected preamble and must be included in the startup receipt and final report.
- Agent: Codex, configured default model (no model override).
- Checkout: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v00-readiness-review`.
- Branch: `codex/v00-readiness-review`.
- Frozen baseline: `a2c90b5e99109d79a8ebbf2249aab0960838666a`.
- Independent read-only review; no accepted prerequisite needed to inspect this candidate. The baseline has NOT already earned acceptance.
- Owned output: a sanitized Markdown report outside Git at `C:/Users/Shrikar/.codex/viralist-v00-review/report.md`. No tracked edits, commits, provider requests, package installation, remote writes, merges or credential access. Tests may write disposable local output. Coordinator will preserve the review report in the repository.
- The user now requested engineering orchestration. Review readiness; do not infer approval of all material proposals. No additional paid-provider authority is granted by this task.

## Receipt gate

First read the named guidance and send an Orca question with task/dispatch IDs, cwd/root/branch/HEAD, explicitly named documents read, owned output, checks and blockers. WAIT for the coordinator's receipt acceptance before executing tests or drafting the review. Read-only discovery is allowed before this gate. This task-specific checkout supersedes the historical root-checkout sentence in project AGENTS for read-only review only; Git writes are forbidden.

Read `C:/Users/Shrikar/AGENTS.md`, assigned checkout `AGENTS.md`, `README.md`, `docs/STATE.md`, V00/V01/V02 in `PLAN.md`, `docs/PROJECT_BRIEF.md`, `docs/ACCEPTANCE.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/contracts/vertical-slice.v1.json`, both ADRs, and `docs/evidence/spark13-rerun.md`. Read the installed `C:/Users/Shrikar/.agents/skills/code-review/SKILL.md` and `orchestration/SKILL.md`, then the version-matched `orca skills get orchestration`. Inspect related experiment production functions/tests as needed; do not read raw private media/transcripts or credentials. If source review requires historical provider source, use `git show 04b852728ae22967f408f71e34f274911ab07578:<path>` without changing HEAD.

## Outcome and bounded scope

Determine whether the actual frozen code, synthetic contract fixture and evidence support starting V02: owned upload -> durable analysis -> small explicitly simulated cast -> supported note -> deletion. The app does not exist; do not claim a user journey. Distinguish independent offline verification from author-reported historical paid evidence. List blocking contract inconsistencies with concrete locations and smallest remedies. Identify decisions that really require owner input separately from routine engineering choices and deferred release decisions.

Producer/consumer boundary: C1-C5/C8 in CONTRACTS; canonical synthetic fixture `docs/contracts/vertical-slice.v1.json`; existing `experiments/meta_pipeline.py` and imported production modules are experimental adapter evidence, not the future HTTP/DB implementation. Verify actual signatures by reading code. Do not freeze an invented interface or approve unsupported provider shapes.

| Criterion | Trigger | Expected result / actual path | Verification | Limit |
|---|---|---|---|---|
| Frozen source | Git identity checks before and after review | Exact baseline, clean tracked tree | git rev-parse HEAD; git status --short; git diff --check | Local checkout only |
| Existing behavior | Offline regression inputs | Existing experiment implementations execute | python -m unittest discover -s experiments -p 'test_*.py' -v | External provider doubles; not app integration |
| Contract readiness | Compare C1-C5/C8 and fixture with implementation/evidence | Enumerate incompatible or missing guarantees | Targeted source reads; JSON parse/structural inspection; cite paths/lines | Synthetic fixture is not live evidence |
| Claims and gates | Compare PLAN/STATE/brief/evidence | ACCEPT, REVISE or REDESIGN with bounded reasons; explicit pending prerequisites | Report exact reviewed SHA and observed checks/exit codes | Historical paid results remain author-reported unless independently reconciled |

Risk: medium/high dependency significance, no product changes. First checkpoint is verified startup receipt; next checkpoint is offline suite result. One initial review; at most two correction submissions later, tracked under V00-R1 without reset. Stop for contradictory baseline, unsafe side effects, missing essential capability, unresolved material requirements or impossible checks. Routine inspection choices proceed autonomously. No spawning additional workers.

Submission: report includes full reviewed SHA, reviewer identity, exact commands/exit codes and environment, findings numbered by severity with source locations/reproduction, acceptance by component, mocked/live boundaries, unknowns, minimal V02 prerequisites and next action. Distinguish review task completion from product acceptance. Send worker_done exactly once using live Orca lifecycle IDs, report path and succeeded/failed outcome; then idle. No production integration, browser journey or release claims.
