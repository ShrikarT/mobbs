# Real Standard Flash50 bounded-pool journey — 2026-11-02

## Revision and environment

Coordinator independently exercised the integrated V03-P1 bounded pool implementation on clean integrated source **d38ad2826816a294fb0070261505b41de2e6afc5**, merge commit **799a8b3881456506cf24942659b51f6ebf937d91**, accepted candidate **4ae71179a71d4b1f675e406a896b7dce33879c53**. Integrated product source contains the bounded concurrency pool (8 session slots, leader-driven scene-frontier execution). Frontend was served from `apps/web/dist` built cleanly from integrated source.

Windows / Python 3.10.2 / Node 26.7.0 / Chromium 1243; actual FastAPI, durable worker, PostgreSQL 55432 (`viralist-v02-postgres`), RustFS 59000 (`viralist-v02-objectstore`). Owned API 58006, database `viralist_v03_live_journey_20261102`, bucket `viralist-v03-live-journey-20261102`. Actual Meta Responses Standard model `muse-spark-1.3`, store:false; **no provider, worker, decoder, storage or browser doubles**. Server-only DPAPI credential remained private. No deployment or release.

## Input and observed result

Owned canonical B derived portrait input: SHA256 `9f1685a58c2328c8f3d8eb28e6473c0765985194f34f87a94d76a34a47e810a9`, 1,334,306 bytes, 17,003 ms, 720x1280 H.264/AAC. Entire original frame scaled into portrait black canvas; re-encoded derivative, not a spatial crop. Source B SHA `b0b43397f99e31467cf89827336d8ee5c69c33719a28f086ecebca6ba0d9ec9f`. Media/screenshots/quotes/raw responses stay private.

One upload and one Flash run `4ff88f8a3b314b7b8ce6f2de9cf94d2d` completed, all 50 fictional policy instances effective, 0 failed / 0 pending / 6 stopped:
- Scene 1: `std-flash-p013-s1` stopped (1/50, 2.0% drop, 98% survival)
- Scene 2: `std-flash-p027-s2`, `std-flash-p030-s2` stopped (2/49, 4.08% drop, 94% survival)
- Scene 3: `std-flash-p005-s3`, `std-flash-p041-s3`, `std-flash-p042-s3` stopped (3/47, 6.38% drop, 88% survival)
196 actual new provider calls; application estimate **0.45438985 USD** (within the $1.50 authorized hard cap and ~$0.44–$0.46 estimate), not a provider invoice. Concurrency bounded pool (concurrency 8), no retry/reupload, 0 uncertain calls observed.

| Scene | Entrants | Stopped | Continued |
|---|---:|---:|---:|
|0|50|0|50|
|1|50|1|49|
|2|49|2|47|
|3|47|3|44|

Simulated completion 88%, p10–p90 internal resampling 82–92%, denominator 50. No human-audience or accuracy claim. Zero supported notes because no scene crossed the existing 15% drop trigger; honest "No supported edit found" rendered.

## Actual browser and recovery checks

- Private `node live_journey.cjs`: exit 0, upload -> real reactions -> persisted report. Attempt marker `live-journey-02.attempted` recorded.
- `node check-report.cjs inspect`: exit 0. Report verified against tested source SHA `d38ad2826816a294fb0070261505b41de2e6afc5`. Decoded video playback verified (`currentTime > 0.2s`, decoded frames > 0, error null), four retention rows, five engagement items, honest empty notes banner, desktop and mobile 375/320 viewports document width <= viewport width (no horizontal overflow). Page reload persisted report without new run creation.
- `python check-deletion.py snapshot`: exit 0, 202 registered objects preserved in private inventory before deletion.
- `node check-report.cjs delete`: exit 0. Actual UI confirmation -> complete, report access revoked HTTP 404.
- `python check-deletion.py verify`: exit 0, all 202 actual object HEADs returned HTTP 404, owned bucket empty, runs/objects/reactions/events/provider_calls/checkpoints count strictly 0; video tombstone content stripped. No upstream-backup erasure claim. Owned API and durable worker processes stopped; shared containers and volumes retained.

## Timing resolution and performance comparison

- Upload duration: 7.129s
- First SSE decision tick: 11.239s after upload completion
- Scene 0 completion (~50 decisions): ~36.5s after upload completion (satisfies < 60s first-finding target)
- Report visible: **103.031s after upload completion** (110.160s total from upload start)
- Prior serial run duration (Journey 01 on `6ebafa5`): 637.669s
- Observed speedup: **6.19x** wall-clock reduction (103.031s vs 637.669s)
- A01 full report delivery (< 300s): **RESOLVED / PASS** (103.031s is well below the 300s gate)
- A01 rehearsal verdict gate (<= 90s): Because executive verdict is rendered with the report workbench, delivery occurred at 103.031s (+13.031s above target). Remains an active architectural focus (e.g. streaming early provisional verdict).
- Provider latencies across 196 accepted calls: min 1828 ms, max 5469 ms, mean 3001.3 ms

Functional upload -> real 50 simulation / stream -> report -> decoded playback -> reload persistence -> ownership -> deletion is **JOURNEY-VERIFIED on d38ad2826816a294fb0070261505b41de2e6afc5 (integration 799a8b3881456506cf24942659b51f6ebf937d91)** for Video B portrait.
