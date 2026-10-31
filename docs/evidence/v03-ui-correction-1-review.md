# V03-U1 correction 1 review — REVISE

**Decision: REVISE** at `33596a615872e36e1e39a1aee43950bec35397d6`. Reviewer: Grok, acting coordinator, independent of Antigravity author task `task_7459c8f8d952`. Codex was not invoked. This is correction submission 1. It becomes unsuccessful review 1. One further submission is allowed.

The six original findings are mostly addressed in source. Two residuals remain. Browser, Playwright, and API checks were not rerun: ports 5432, 55432, 59000, 58003, and 58004 were closed, and the Docker engine pipe was absent at review start. That infrastructure gap is not itself a code finding. `scripts/v03_ui_regressions.js` checks source strings and hardcoded color pairs. It does not render a report.

## What the source now does

- Empty-note copy no longer hardcodes Scene 2, 3–8s, or 11 personas. When `report.observations` is present, the banner lists stored scene, time, numerator, denominator, and threshold.
- Flash 50 disclosure is gated on profile `flash` and requested 50. That matches `docs/contracts/flash.v1.md` line 23. Test 3 no longer claims five archetypes and 50 instances.
- The ordered event log renders `payload.reason` for continued and stopped events.
- Run polling uses an AbortController, a generation fence, and an `isMounted` check before applying 401/404.
- Evidence quotes are `<button type="button">` controls. The parent note ignores keyboard activation whose target is not the note itself.
- Partial cast, excluded traces, and missing retention, scores, and engagement sections have explicit unavailable copy. Pending nodes no longer use opacity 0.6.

## Remaining batch

1. **P2 — finding 1 is still open when observations are absent.** `apps/web/src/App.tsx` empty-note branch, observations-missing arm, says all candidate findings were checked and no dropout trigger exceeded the deterministic support threshold. That sentence is not bound to stored observations. Expected: say that observed dropout triggers are unavailable for this report, and do not claim a threshold result. Keep the data-bound sentence when observations exist. Add a fixture assertion for the absent-observations report, not only a source-string check.

2. **P2 — finding 5 still omits score denominators.** Hook and pacing values render observed percent and range, not `MetricItem.denominator`. Expected: when a stored denominator is present, show it next to the score; when it is absent, show that the denominator is unavailable. Do not invent a denominator from cast size for these indices.

## Not charged as findings

The poll `finally` block still schedules the next poll after a terminal `return`. Effect cleanup on the view change clears that timer. No separate failure is claimed. The five-archetype Flash 50 sentence is the frozen contract disclosure.

## Milestones

WORKER-REPORTED correction remains. REVIEW-ACCEPTED, INTEGRATED, JOURNEY-VERIFIED, and RELEASED are not earned. No paid call.
