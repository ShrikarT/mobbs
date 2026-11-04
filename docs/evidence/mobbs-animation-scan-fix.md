# Landing motion and scan fix — 2026-11-04

Owner asked Codex to fix oversized/glitched landing motion, scan failure and scan time, continuing direct execution without Orca/other agents. Isolated branch `codex/mobbs-app-redesign`, baseline1430548; coordinator dirty V04/V05 drafts preserved. No deployment, merge, push or submission.

## Root causes and implementation

- Nested SVG faces/icons had CSS dimensions but no intrinsic width/height attributes. At1911px the supposed40px faces rendered~700–900px. Added native SVG dimensions. A regression failed with28 oversized descendants, then passed at9 sampled beats including loop wrap. Original illustration/theme preserved.
- Actual failing request was a sanitized HTTPX **ConnectTimeout**, before connection establishment.117 decisions had already committed. The old adapter labeled every transport exception an ambiguous HTTP500, stopped the run and paused further inference.
- A new client was created for every scene/persona and never explicitly closed. The same JPEG was fetched/base64-encoded separately for each viewer. A run now owns one thread-safe8-connection client, lazily caches only frames requested by validated current-scene projections, and closes/clears its resources in the worker’s finally block.
- A single bounded retry is allowed only for ConnectTimeout/ConnectError. Before retry, the adapter rechecks lease/deletion and active-run status. Read/write/protocol/unknown-response failures remain unconfirmed/uncertain and are never automatically resent. No HTTP response status is invented. The global8-slot gate, ordering, call ceiling and no-later-input-after-stop rules remain.
- Worker pool waits for completed futures instead of spinning/re-querying while nothing runnable changed. The header now shows the actual saved reaction count.
- Existing Test3 is labeled **Quick preview (3 personas)** and explicitly described as a smaller diagnostic sample. Full50 remains default. No sample reduction, model change, false ETA or instant-scan claim.

HTTPX documents [client pooling/lifecycle](https://www.python-httpx.org/advanced/clients/) and [connection-only retries](https://www.python-httpx.org/advanced/transports/). [Exception definitions](https://www.python-httpx.org/exceptions/) distinguish connecting from reading/writing. These boundaries informed the implementation; ambiguous requests remain protected.

## Saved-scan continuation

Functional checkpoint **c9371af0eb7651b0242a825e1f84cfa5cd630fb2** safely continued the specific legacy connection failure using the checked [operator procedure](procedures/v03-connect-recovery.py). Dry run validated the original error class, failed checkpoint, absence of any other failed/unknown dispatched call, undeleted video and idle matching worker. The original sanitized receipt was archived as a non-request transport-audit entry; accepted data and immutable manifest were retained. Minimal private backup holds only sanitized receipt/IDs/hashes, not media, impressions or a report copy. A second apply is refused.

**Observed result:** full50/50 complete,0failed/0pending,346accepted calls including notes. All117 original reaction/evidence hashes and the manifest are unchanged. Stopped personas have0 later dispatches. Remaining work took162.8s with229new accepted calls, known incremental token-cost estimate0.59942420USD (not invoice). The old receipt remains in provenance and the report does not invent a known aggregate bill. Original completed report and recovered report/media remain under the owner session.

This was operator-assisted continuation, not a fresh full-path speed benchmark. The preceding identical-input scan completed in242.483s/343calls. Observed request medians were4.422s before failure and4.297s during continuation; these differing scene samples do not establish a universal speedup. Full50 still entails hundreds of provider decisions and can take several minutes. Connection/frame reuse removes avoidable overhead; the3-person diagnostic option offers a smaller/faster check.

Final functional checkpoint **219e0ff0638c24e3ac6993ea3e970c22eb88ce7c** adds the retry cancellation fence; the guarded worker was installed while job admission was table-locked and no analysis was queued/leased/dispatched. No in-flight request was interrupted. API main/auth/report source is unchanged, frontend rebuilt and served on58020. Future startup uses the clean current HEAD guard.

## Observed verification

-26 focused normalized/config/transport checks pass at219e0ff, including parallel client reuse, one fetch per current frame, bounded connect retry, no read-timeout retry, exhausted connection classification and cancellation before retry.
-6 UI checks pass:9 motion beats/loop wrap, pause/reduced motion, navigation,320px/keyboard, streamed saved reactions/pause buffering and bounded mob placement.
-4 actual recorded-provider browser journeys pass: upload/note/evidence/video seek/refresh/modal/deletion, explicit unsupported-profile error/recovery, processing cancellation, mobile. Production API/PostgreSQL/S3/scheduler/report renderer; only provider inference is recorded.
- Initial48-case broad backend run:47passed,1lease-renewal test failed once. That case passed on an isolated frozen rerun and again in the pool suite. The subsequent11-case pool run passed9 and exposed2 test-query isolation failures: pg_locks counted production and QA databases together (16 slots). The test introspection queries were scoped to current_database OID; both cross-process cases then passed, observing aggregate8 slots and no post-deletion dispatch. The production gate was not weakened. No single clean48-case suite run is claimed.
- TypeScript/Vite build passes; no new dependency. Named local browse session checked corrected animation bounds/pause and actual landing-to-app navigation. Saved proof `C:/Users/Shrikar/.codex/tmp/mobbs-app-design/hero-fixed.png`.
- No extra paid scan was created for validation; only remaining work of the authorized failed scan was continued. QA uses isolated runtime/database/bucket; its pause marker parent is separated from live. Customer data is preserved.

## Acceptance and practical limits

WORKER-REPORTED / author-observed local fix. Independent review/formal integration/journey acceptance remain pending under the owner’s no-agent instruction. RELEASED not performed. Working site: http://127.0.0.1:58020/ . Reload the original browser once to load the new bundle and recover its completed report. Its browser/cookie session was not accessible to automation, so customer UI display is not claimed observed; server completion/integrity is verified. Original privacy/session controls remain.

No p95, prediction accuracy, guaranteed provider uptime or universal latency claim. Future ambiguous read/write outcomes still pause rather than risk duplicate inference. V04/V05/full roadmap remain deferred.

Final QA teardown: isolated unit uploads were reconciled through production deletion jobs and direct synthetic fixture frames removed. A concurrent multi-object teardown attempt on that same QA-only bucket timed out; the production deletion workers completed cleanup. No customer bucket was targeted. Recorded QA cleanup also completed. Customer’s two completed reports/media remain preserved. Provider runtime is separate from the unit pause marker. No teardown process remains.

Final frontend artifact SHA256 `5bf404b1886a889e6003611f49ac7e67cff00f67b1b3f852e30ed52548a62bc7`; full per-file manifest is private scan-fix-build.json. Source219e0ff, frontend code identical to checkeda8b3c4a. No further application changes after these checks.
