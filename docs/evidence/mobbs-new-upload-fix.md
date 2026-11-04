# Fresh upload navigation — 2026-11-04

Task: MOBBS-NEW-UPLOAD-FIX. Owner requested that landing “drop a video” allow a new video instead of restoring the last upload. Owner explicitly authorized direct Codex implementation without Orca or other agents. Functional revision **9dc2e26a6d912dd6447ae0ec00729fd74f10d6b1**, isolated branch `codex/mobbs-app-redesign`; coordinator drafts preserved.

## Cause and change

The CTA entered the same route used for durable recovery. App bootstrap unconditionally selected the first owned video, and a delayed bootstrap could also replace an upload started while session initialization was pending.

Upload CTAs now open `/#/app/new`. This stays fresh across reload and exposes a collapsed previous-scans list with explicit owned-run links. Started runs use `/#/app/run/{run_id}` so refresh restores that run. Legacy `/#/app` recovery remains supported. Bootstrap/upload generation checks ignore stale responses after navigation or a new upload; session initialization is shared within a mount to avoid duplicate session creation. Returning to upload also resets the route. Existing API authorization remains the authority for owned media/runs. No backend, provider, dependency, media limit or visual theme changes.

## Observed author verification

- Regression reproduced against the old app before the fix. The two new browser tests cover an existing owned scan and a slow session/previous-video response racing a fresh upload. They assert a fresh chooser through reload, explicit prior-scan selection, correct new video/run after reload, one upload/run creation, and no old-run lookup.
- TypeScript and production Vite build passed for the committed source bytes before the checkpoint. At exact revision9dc2e26, all **8** presentation/regression browser tests passed against the served production build (30.3s). HTTP fixtures control external API responses for this suite.
- At9dc2e26, the real production-component recorded-inference journey passed (**1** test,53.2s): upload, scheduler/report, supported evidence seek, refresh, landing CTA with an existing saved report, fresh chooser after reload, explicit reopen of that same report, modal focus and durable deletion. API startup backend source remains6837a58; its production backend code is unchanged by this frontend-only revision. Recorded worker started at9dc2e26. This tests saved provider inference, not a new paid provider call.
- First recorded attempt reached queued but timed out because its isolated QA worker had exited on a database connection timeout. Removed only that attempt’s isolated QA video through the production deletion path, restarted the recorded worker, and reran successfully. An auxiliary cleanup count initially used a nonexistent objects.deleted_at column; corrected read-only verification confirms QA live videos0, runs0, jobs0 and objects0 after the successful journey.
- `browse --local --session mobbs-new-upload` on http://127.0.0.1:58020/: clicked observed landing CTA, verified URL `/#/app/new`, visible upload input and both profile buttons; stopped only that owned browser session. Original user browser cookies are outside automation access. Reload the existing browser tab to load the new bundle.
- Private13-file build manifest `new-upload-build.json`; artifact mapping SHA256 **0f1cecd80e4aa05ec4dd77bc93b00c84580b5c26adb1ef03357847a345837670**. Served index matches disk. No original customer media/report mutation or inference retry was performed for this fix.

**WORKER-REPORTED / author-verified.** Independent REVIEW-ACCEPTED, formal INTEGRATED and JOURNEY-VERIFIED remain pending because the owner excluded other agents. RELEASED not performed. No merge, push, deployment or submission.
