# V03 real Standard-provider connection smoke - 2026-11-02

**LIVE COMPONENT VERIFIED, not integrated/journey acceptance.** One real Meta request executed the unmodified production `StandardProvider.verdict` and `Storage` at clean commit **5f5fe3ac3129521f5efecd66c2ec842b897bda4c**, in the frozen review checkout. The candidate still has four independently reported product defects and is not accepted. This bounded component check used a synthetic scene, no application scheduler/database/browser path or customer media.

Owner authority: current cap-free efficient-credit-use decision `ec26458:docs/decisions-v03-product-priority.md`. Exactly one attempt, maximum output1200, one active request, no retry. An exclusive private attempted marker was written before invocation; rerunning the helper refuses to dispatch again. Existing supplied credential stayed server-side, encrypted with Windows user DPAPI outside Git and decrypted only into the child process environment. No credential value in this evidence.

## Observed result

| Item | Actual observation |
|---|---|
|Component|Production adapter, actual local object storage and actual Meta HTTPS endpoint; no transport double|
|Endpoint/model|`https://api.meta.ai/v1/responses`, `muse-spark-1.3`|
|Request|Current synthetic decoded JPEG, fictional p001 policy, empty own prior; store:false, strict text.format, no tools/history, redirects disabled|
|Result|Completed envelope and valid normalized p001 reaction, still_watching=true; model text retained privately|
|Elapsed provider call|6.297 seconds (one component call, not full app latency or p95)|
|Usage|421 input,0 cached,534 output including462 reasoning,955 total tokens|
|Application cost estimate|0.00279575USD using pinned `meta-spark-standard-2026-10-29` rates; not an invoice/billing-balance claim|
|Request ID|4341de94-8cd1-4df1-9f53-e26df68d59fe|
|Response ID|resp_6ae80458445e85c73bea44ae|
|Response SHA256|248d00ca57e5452c76e3bb5ef7ded02ef5a842461994696f12cce123ab4c34b3|
|Frame SHA256|1fa9cbe265a5a36a5f56c3a0ef85fca40c33d6be7146c735adcc6c6400d02153|

## Reproduction and cleanup evidence

Private root `C:/Users/Shrikar/.codex/private-runs/viralist-v03-live/`: provider_probe.py, provider-probe-01.attempted, provider-probe-01-summary.json, private raw response, synthetic MP4/JPEG and fixture inventory. Python `C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe`. The wrapper loaded the DPAPI credential into MODEL_API_KEY, ran the helper, then removed that environment variable; PYTHONDONTWRITEBYTECODE=1. **Exit0**. Source clean/full SHA verified before inference.

The helper generated four seconds of FFmpeg testsrc2 at320x240/10fps, decoded a JPEG at1s and supplied scene bounds0-4000ms. It created/used only its own local bucket `viralist-v03-live-smoke`, with one named synthetic object, and did not connect to an application database. Stored media/frame hashes and inventory are private. This fixture proves image transport/normalization, not useful-video quality or representative behavior.

The object DELETE completed in the helper. Its first HEAD verification mistakenly used a nonexistent convenience method, so it honestly returned cleanup unverified. A separate cleanup-only invocation used actual `Storage.client.head_object`, verified **HEAD404**, updated the private summary and exited0, with **zero additional provider calls**. Raw response and synthetic local evidence remain private; no upstream provider backup-erasure claim.

Remaining: Antigravity correction2 for the four product findings/mobile gap; independent acceptance/integration; actual real-provider upload→50-instance sequential scene simulation/streamed results→report/evidence/playback→refresh/recovery→deletion. No human calibration, model accuracy, full-app performance, p95, deployment or release is established by this smoke.
