# V03-U1 independent review contract — candidate `3dfa20f`

## Role and decision

Read-only independent reviewer for Antigravity's V03-U1 Flash evidence workbench. Inspect the exact committed candidate and verify meaningful checks independently. Return **ACCEPT**, **REVISE**, **REDESIGN**, or **BLOCKED** with observed evidence. A worker completion only submits the report; it does not accept, integrate, journey-verify, or release U1. This review does not accept the whole V03 milestone.

Codex reviewer justification: this is a substantial frontend state, accessibility, streaming, and media-playback change; a separate Codex review provides an independent architecture and difficult-UI assessment. This is read-only verification, not reassignment of Antigravity implementation work.

## Frozen source and ownership

- Candidate: `3dfa20fb708a093ac288db51ff7c303036621250` on `codex/v03-ui`.
- Exact prerequisite: integrated backend `5a3025c46c043b7645d935c3831f95d733f19ab5`.
- Original implementation contract: `docs/evidence/v03-ui-assignment.md`, frozen at `e3ad1cf91801a92bd096cf248dc52db166ebb748`.
- Candidate report: `docs/evidence/v03-ui-implementation.md` (author claims are evidence to check, not acceptance).
- Review worktree must be distinct from the author's tree `C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-ui`; check out the exact candidate SHA and verify a clean status before review.
- Reviewer owns no product files. Do not commit or edit candidate/source. Write only a sanitized report and transient check artifacts under the assigned private review directory. No helpers.
- No provider key, paid call, external publication, deployment, database reset, service restart, or other V03 implementation is authorized.

## Required sources

Read shared `C:/Users/Shrikar/AGENTS.md`, project `AGENTS.md`, current `docs/STATE.md`, `docs/PROJECT_BRIEF.md`, `docs/ARCHITECTURE.md`, `docs/ACCEPTANCE.md`, `docs/DESIGN_DIRECTION.md`, `docs/CONTRACTS.md`, `docs/contracts/flash.v1.md`, `docs/evidence/v03-backend-integrated.md`, the full U1 assignment above, the candidate diff, relevant UI/API types and tests, and author evidence. Read the `browse` skill at `C:/Users/Shrikar/.agents/skills/browse/SKILL.md` and relevant `code-review` guidance. Report missing/conflicting instructions rather than inventing product intent.

## Acceptance table

| Criterion | Required evidence | Limit / disposition |
|---|---|---|
| Exact scope and source | Verify tree, branch, clean HEAD, diff from `5a3025c`; inspect every changed path and ownership boundary. | Any unowned production/schema/contract edit is a blocker. |
| Profile truthfulness | Inspect/run the actual UI request path for Flash 50 vs Test 3, available-profile detection, explicit incompatibility and no silent fallback. | Backend/API doubles cannot replace the production UI/API path. |
| Live event view | Inspect/run persisted finite SSE consumption, sequence/event dedupe, reconnect/terminal drain, run-switch/delete cancellation, stable 50-persona IDs and presentation pause/resume. | Do not count speculative UI nodes as persisted events. If service is unavailable, say not verified. |
| Report correctness | Verify retained/drop math and ranges, empty/legacy unavailable signals, 0-supported/1-withheld Video A note behavior, bounded rejection reasons, simulated-cast and thin-library disclosure. | Never display missing observations as zero or unsupported notes as findings. |
| Playback and evidence | In an actual browser, wait for decoded playable media, verify controls/playback advances and a supported note seeks to the exact evidence time. | A screenshot of a loading spinner or `currentTime` assignment alone is not playback proof. |
| Errors, privacy and deletion | Verify incompatibility/network recovery, confirmation behavior, owner-scoped error/deletion state, and that UI does not claim upstream erasure/session invalidation without evidence. | Use existing isolated synthetic data; do not reset shared data or run destructive cleanup beyond the dedicated fixture. |
| Design/accessibility | Compare hierarchy with `docs/DESIGN_DIRECTION.md`; check desktop and 320px views, keyboard/focus, contrast, reduced motion and real control behavior. | Distinguish author screenshots from independently captured browser evidence. |
| Reproducible checks | Run `npm run build`; execute the dedicated Playwright suite against the exact frozen artifact if its required existing services are available. Review the scoped backend-test repair. | Do not restart Docker/PostgreSQL. If unavailable, record the actual failure and make the review BLOCKED for that criterion, not a code rejection. |

## Procedure and bounded scope

1. Before checks, send a startup receipt with task/dispatch/run IDs, actual repo/worktree/branch/HEAD/status, required docs read, exact files reviewed, browser session, available services, commands and blockers. Wait for coordinator acknowledgement.
2. Inspect the exact candidate diff and run `npm run build`. Attempt one bounded health check of the assigned local runtime; if PostgreSQL/Docker is unavailable, do not retry connections or start/restart services. Do not run the provider or use remote Browserbase credentials.
3. If the current assigned API at `127.0.0.1:58003` serves the exact `app_source_sha`, use the named local browse session `viralist-v03-ui-review` to exercise one real upload-to-report path and inspect browser console/network. Run the existing V03 Playwright suite only if its required services are already healthy. Otherwise preserve the exact infrastructure blocker and continue static source review without overstating browser evidence.
4. Review only U1 criteria above and provide one numbered blocker batch. Do not make speculative polish requests. Correction history is coordinator-owned and survives restarts; after two unsuccessful submitted corrections, redesign/reassess.
5. Write a sanitized report under the assigned private review directory. Include exact candidate SHA; decision and criterion mapping; commands, exits, environment; browser screenshots/traces if actually captured; positive and negative findings; mocked boundaries and evidence limitations. Submit once through Orca with task and current dispatch IDs, then stop editing.

## Verification identity

Run: `run_d3354faa0659`. Implementation Task: `task_7459c8f8d952`, Dispatch: `ctx_7764cee17741`. Review Task/Dispatch/worktree/session are assigned by Orca; populate them in the dispatch and report. No Codex implementation exception or Antigravity reassignment is requested.
