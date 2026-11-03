# V03 UI runtime diagnostic checkpoint

Read-only observation on2026-11-01 while the senior accounting worker owns implementation; no runtime/source changes or browser journey executed. Existing integrated UI report at cffd9e8 remains authoritative for observed158Adecisions/30finished and production PostgreSQL connection timeouts. The cause is unresolved.

Current Docker observations:

- viralist-v02-postgres running, exit0, OOMKilled=false, restart=no, no explicit container CPU/memory cap. One no-stream sample:4.80%CPU,66.25MiB of3.766GiB available Docker memory,6PIDs. A point sample does not characterize the prior outage.
- viralist-v02-objectstore exited137, OOMKilled=false, empty State.Error, FinishedAt2026-11-01T05:06:11.768221559Z. Retained mount viralist-v02-objectdata at/data. Existing documentation records a coordinator stop command, but calling the resulting shutdown graceful is unsupported by exit137. There is no OOM or data-loss proof in this observation. Do not recreate/delete the container/volume.
- Earlier936.23%RustFSCPU sample and DB timeouts suggest a resource question but do not establish causality. No runtime setting was changed on that inference.

The diagnosing-bugs workflow requires an actual symptom-catching reproduction before choosing a cause or applying a fix. No such new reproduction was run here because the guard worker owns serialized DB verification and the recorded source already has an infrastructure-blocked journey. This checkpoint is inventory/evidence reconciliation only, not root-cause diagnosis or recovery acceptance.

Next after the guard runtime window settles: preserve original UI database/bucket/unfinished jobs; establish a bounded simultaneous actual db.connection SELECT and private S3 health/known-object-read probe on the same frozen UI source. Capture latency/errors and resource samples during the smallest A-path workload that reproduces the timeout; inspect and minimize before changing one runtime variable. Keep owned processes/ports/data separate, no paid provider, fake storage, reset or whole-journey repetition before that signal. Full UI acceptance still requires independently observed remaining criteria, including decoded playback/events/privacy/deletion and responsive report states. Existing services may be started only within established local development authority; coordinate timing first. Do not claim that the healthy idle PG sample resolves the prior failure.

## Actual local service restoration for the app task

Coordinator started only the existing viralist-v02-objectstore container, same image sha256:ed9210d6411d77ffceb70d94b964a3cb7d225983368bc25bebe01e995293dcc2 and retained viralist-v02-objectdata at/data; no config/pull/reset/recreate/migration. Loopback59000 health returned200 in815ms; actual existing PostgreSQL SELECT1 succeeded in16ms. One no-stream sample: RustFS16.14%CPU/212.9MiB/33PIDs, PostgreSQL0.15%CPU/77.74MiB/6PIDs, Docker memory3.766GiB. These idle observations restore prerequisites but do not reproduce/fix the earlier A50 failure. App workerctx_718343708607 was notified in msg_3c2d853ba714 and may exercise only assigned DB/bucket/API58004. No paid call or original-data cleanup performed.
