# Mobbs app redesign — author verification, 2026-11-04

## Artifact and authority

The owner requested the approved landing language throughout the actual app, Figma first in the same file, a scattered animated mob space, then local website integration. They explicitly assigned Codex directly and excluded Orca/other agents. This is the task-specific implementation exception. No delegation, deployment, merge, push, public release or submission was performed.

- Baseline: `6c47b220e481befc66a74626d9db76113c31ced3`; its product tree matches accepted V03 rename16a2fe6.
- Implementation: `e85cd2586998e4189a01e003c5f50a4fa3eb364f`.
- Final product correction: **`6837a583cad2b77914e26463d0f7242d10c7637a`**, branch `codex/mobbs-app-redesign`, isolated checkout `C:/Users/Shrikar/mobbs-app-redesign`.
- Production build artifact SHA256: **`16c0f30f3b5a1b360004a804dd4a9695307c9cb4a476c60563332884730759c5`**, defined as SHA256 of the sorted JSON map of relative dist paths to file SHA256. Private `final-build.json` records every file. TypeScript/Vite build passed. Final packaging additionally includes the verbatim font/Anime.js license notices under public/licenses; application JS/CSS matches6837a58 byte-for-byte.
- Backend/API/worker/scheduler/auth/deletion source and migrations are unchanged from the accepted V03 base. Coordinator `C:/Users/Shrikar/viralist` dirty V04/V05 work remains untouched.

## Same-file Figma design

[Editable app board](https://www.figma.com/design/HNAM1otmM0c7FUlsLK72Ub/mobbs.fun?node-id=56-56), live room56:102, in original fileHNAM1otmM0c7FUlsLK72Ub. Eight editable desktop/mobile/supporting-state/roadmap frames were created before implementation. Original full landing motion50:43, header, features and footer remain present. Text/native paths were checked editable. Native editor was used after connected MCP Starter quota prevented additional calls. No file upgrade or video upload was needed.

Self-hosted Space Mono/Patrick Hand, cobalt/lavender/gray palette, original Figma face and phone/laptop vector paths. Current MP4<=60s/200MB contract supersedes MOV/two-minute visual-reference copy. No ElevenLabs work was resumed; the owner dropped that optional insertion.

## Final product checks

All checks below are **author-observed**, not independent acceptance.

| Check | Observed result and boundary |
|---|---|
| TypeScript + Vite build | Pass;81 modules; original dependency architecture retained, pinned Anime.js4.5.0 and local font packages added |
|5 UI checks on production artifact6837a58 | Pass: landing CTA/refresh/sample/roadmap; pause/resume/reduced motion;320px routes/keyboard; actual production MobbsSpace bound to controlled streamed events, escaped quotes, stable targets, pause buffering, mobile focus/scroll; production placement property checks across280 width/seed/cast combinations |
|4 recorded-inference production journeys6837a58 | Pass:17.1s VideoB/Test3 upload, real scheduler/storage/report, supported note seek and quote inspector, refresh, modal focus, deletion; unsupported Flash error/recovery; processing cancellation/deletion;320px app layout. Real PostgreSQL/S3/worker/API; saved provider inference rather than fresh model calls |
| Real Standard inferencee85cd25 | One constructed4s functional MP4,50/50 effective,0 failed/pending,99 live calls; estimated0.23176410USD (not invoice),0 supported notes honestly withheld. Actual streamed reactions observed and paused/resumed. No uncertain call retried |
| Final6837a58 renderer with that real saved report | Pass: authenticated200 and50/50 actual report, decoded4s video/seek near3s, refresh after API/worker restart,375/320 no document overflow, foreign report/media401/404,0 page errors/HTTP5xx. Report retains its originale85cd25 provenance |
| Final live upload deletion6837a58 | Actual UI modal/confirm and completed state; report/media404; all103 owned object HEADs404; related objects/runs/jobs0. Upstream backups are not claimed erased |
| Focused regressions |20 normalized/config tests passed;3 provisional-verdict tests passed on isolated database. Backend source is unchanged. Initial attempts failed due mismatched test Origin, then C: exhaustion; those attempts are not labeled passing |
| browse CLI | Final named local session opened production landing, followed observed drop-a-video link to actual app, inspected Standard mode/limits/profile controls. Owned session stopped. Early daemon-timeout attempts were superseded by this successful check |

The original all-tests recording run was interrupted after C: filled: the long VideoA/Flash50 browser wait timed out although its recorded run later completed. It is not claimed as a successful full browser rehearsal. No paid retry was performed. A stale historical error-path assertion expected Operation failed/Try again; observed Analysis failed/Return to upload was already correct and the test was updated before final4/4 pass.

Visual inspection caught an inherited stage max-height clipping later characters. Final correction makes the stage scrollable, prevents48x66 target overlaps, increases decorative scatter and keeps focused lower characters reachable. Narrow engagement cards use one column. Streamed reasons remain source data, never decorative invented viewer feedback.

## Local services and cleanup

Working local Standard website: **http://127.0.0.1:58020/**; app `/#/app`; sample `/#/sample`; roadmap `/#/roadmap`. Recorded QA58021 was isolated. Private startup helper `C:/Users/Shrikar/.codex/private-runs/mobbs-app-redesign-20261104/start.ps1 -Role api|worker -Mode standard|recorded -ExpectedCommit SHA` checks a clean exact source revision. Provider key is DPAPI-loaded server-only; all runtime configs/owner cookies/media/raw responses remain outside Git.

Docker startup was repaired by reversibly backing up its zero-byte runtime socket directories together while stopped. No factory reset, image pull, volume recreation or deletion. Windows reserved old55432; new `mobbs-redesign-postgres` uses the identical local image/retained pgdata on58032, original PG container stopped, one volume writer. RustFS59000 retains its original volume. New QA database/bucket names isolate this work. Original data remains in its original database/bucket.

C: exhaustion was discovered and the task dependencies moved to D: with a same-path junction. Private decoder temp uses D:. Default npm cache now points through the original-path junction to D: and npm cache verify passed (61 entries). Remaining ephemeral npx package remainders are preserved at AppData/Local/npm-cache.npx-backup-20261104;19 partly copied D: entries were moved out of the active cache to D:/mobbs-redesign-runtime/npx-partial-backups so npx can reinstall them normally. No cleanup process remains active; C: had about1.3GB free at final inspection. Every task-owned live, recorded and unit upload was removed using production deletion jobs; no outstanding QA model job or pending QA deletion remained at cleanup inspection. A later non-QA upload appeared in the live preview and is being left untouched with its running API/worker; it is outside this test-cost/deletion evidence. Private sanitized evidence and screenshots are retained for recovery.

## Acceptance and remaining scope

**WORKER-REPORTED / author-verified** implementation. Independent **REVIEW-ACCEPTED** and formal **JOURNEY-VERIFIED** remain pending because the owner explicitly excluded other agents. The redesign runs locally from its isolated branch; the dirty coordinator was not merged over. **RELEASED: not performed.**

The full V04/V05/Deep/multi-platform/benchmark/accounts/API/calibration roadmap remains. A short synthetic functional check is not prediction accuracy, creator-video performance, maximum-duration revalidation or20-sample p95 evidence. Existing V03 timing/cost targets and historical evidence remain accurately recorded in STATE. Nothing here publishes or submits the project.
