# V03-U1 corrective submission 2

Antigravity implements this ordinary UI correction. No helpers. Same product task lineage as `task_7459c8f8d952`. This is the last allowed submission: correction 1 at `33596a6` received one unsuccessful review. A second unsuccessful review stops the task for redesign.

## Baseline

Worktree `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-ui`, branch `codex/v03-ui`, clean base `33596a615872e36e1e39a1aee43950bec35397d6`. Do not touch the coordinator checkout, the review worktree, the budget branch, backend, SQL, contracts, manifests, or lockfiles.

Read `docs/evidence/v03-ui-correction-1-review.md` from the coordinator commit named in the dispatch. The two items below are the whole batch.

## Fixes

1. When a report has no observations, the empty-note banner must say observed dropout triggers are unavailable. It must not claim that triggers were checked or that none exceeded a threshold. Keep the existing per-observation sentence when observations exist.
2. Render each present hook and pacing `denominator` beside the score. If that stored denominator is absent, say the denominator is unavailable. Do not substitute cast size.

## Checks

Add a behavioral assertion for both cases. A source-string grep is not sufficient. Run `npm run build` from this worktree. Do not start Docker, Postgres, RustFS, or the API, and do not make a provider call. Commit one correction on `codex/v03-ui` and stop. Report the SHA, commands, and exit codes. Claim WORKER-REPORTED only.
