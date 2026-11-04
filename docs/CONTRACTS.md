# Local contract v1 — V00-R1 correction candidate

The shared schema/saved-adapter correction was accepted at `715be0ee31f8ed3229e64b75853aff624c3f449c`; local V02 runtime scope and exact integration evidence are in [the journey record](evidence/v02-integrated-journey.md). Owner approved the local architecture and MP4 limits on 2026-10-28. The app and tests use [contracts/normalized.py](../contracts/normalized.py). [vertical-slice.v1.json](contracts/vertical-slice.v1.json) remains a synthetic `normalized-1` fixture, not runtime evidence. [provider-saved.v1.json](contracts/provider-saved.v1.json) projects saved receipts with private output text replaced by synthetic empty JSON; that substitution proves parser structure only. The tables include future roadmap contracts; current API code and the journey record identify the implemented V02 subset.

## Cross-module contracts

| ID | Producer → consumer | Required shape / invariant | Failure |
|---|---|---|---|
| C1 Media accepted | HTTP/storage → feature worker | `video_id, owner_id, media_ref, sha256, duration_ms, width, height, audio_present, bytes`; private references; ≤60,000ms and ≤200,000,000 bytes | 413 size; 422 format/duration; cleanup quarantine; no model call |
| C2 Feature bundle | extractor → scheduler/detectors | `schema_version, video_id, extractor_version, timebase, scenes[], caveats[], provenance[]`; each scene has ordered `[start_ms,end_ms)`, frame/clip refs, scene-local transcript/OCR/measurements and timestamp granularity | Missing audio is a caveat; missing media/timebase is fatal; missing optional observation is null, not zero |
| C3 Persona batch | scheduler → provider adapter → scheduler | Current scene, active persona IDs/cards/checkpoints, allowed past state; verdict for each ID with `still_watching, actions[], impression_update, drop_reason, signals` | Reject unknown IDs, duplicate blocks, invalid times, >60-word impression, unallowed actions; skip requires reason |
| C4 Event/checkpoint | scheduler transaction → event store → SSE/UI | `run_id, sequence, event_id, type, payload`; verdict/checkpoint/event committed atomically, unique accepted persona/scene verdict | Reconnect after sequence; duplicates ignored by event ID; no speculative UI events |
| C5 Report | aggregation/notes → API/UI | effective/requested cast, methodology, ranges, evidence references, ≤3 ranked notes, trust manifest, coverage/caveats | Unsupported note suppressed; unavailable metric null with reason; incomplete cast labeled |
| C6 Comparison | two owned complete/partial runs → compare/UI | base/revised IDs, compatibility reasons, same cast/settings hashes, paired-delta method, note match confidence | Different owner 404; incompatible settings 409; uncertain mapping not marked addressed |
| C7 Thumbnail | owned media → permitted image provider or layout fallback → vote adapter → UI | original + 3 variants; source type/provenance; same 30-person panel per variant; vote/reason/evidence | Muse Image playground owner-confirmed; API/policy discrepancy must be resolved for app use; fallback/failed votes labeled, no inferred winner on tie |
| C8 Deletion | API tombstone → worker/stores/provider adapters → UI | deletion ID, pending targets, access revoked time, completion times; repeat request same operation | Provider failure retains pending target; workers fenced; report never says “fully deleted” early |

## Wire and domain conventions

New Standard run manifests select `media_pipeline: scene-av-v1`. Preparation cuts native silent MP4 and WAV per authoritative scene interval before external interpretation/transcription. Each paid preparation unit is marked dispatched before sending; accepted output and its source hash are persisted and reused, while ambiguous/failed units are not resent. Files are sent inline/multipart, without Files API IDs. A persona projection may add `scene_features` containing only that scene's observations, model-read text and transcript; projection validation and post-skip fencing apply unchanged. Voice timestamps remain approximate turn boundaries. Historical manifests/reports retain their original path. Report model IDs/coverage/usage reflect the performed preparation; call ceilings add at most two preparation calls per scene.

Server-generated opaque identifiers; milliseconds as nonnegative integers; UTC ISO timestamps; bounded strings; discriminated event/error types; unknown schema versions fail validation. Reject NaN/Infinity and invalid ranges. Ownership stays server-side and is never trusted from a request body. `impression_update` is a bounded summary of past/current content only.

Scenes are contiguous over accepted duration, max five seconds for Flash, with a 0–3s hook boundary (or the video end when shorter). Decoder scene cuts can create shorter intervals. Regular actions are within `[start_ms,end_ms)`; stop decisions may occur exactly at `end_ms`. Transcript overlap is clipped by time. When a segment's semantics span a boundary, do not leak later words into the earlier prompt; flag coarse timing instead.

Action enum: `like, share, save, comment, follow`. Each action has `type`, `at_ms: integer|null` and `timing: observed|unobserved`; null must accompany unobserved. The legacy provider shape supports only the first four actions, with no timestamps. Conversion never fabricates timestamps; canonical richer producers may supply validated observed times. Watching/stopping uses `still_watching`. Optional comment text needs separate evidence/filtering before a later producer adds it; legacy `comment` supplies intent only. Signals: `confused: boolean|null`, `cta_understood: boolean|null`, `matched_trend_rule_ids: string[]`; null means unobserved. Legacy conversion sets both signals null and trend IDs empty. Nonempty trend IDs are unsupported by this v1 local validator until evidence-bound rules exist.

FeatureBundle is a storage contract, **not** permission to send the whole bundle to personas. Construct a separate `SceneInput` projection; include an `allowed_media_refs` list and `max_visible_ms` in dispatch audit. Provider caches must never bind a persona to an earlier whole-video request.

## Internal HTTP proposal

All routes are same-origin, session-authorized and rate-limited. Unowned IDs return 404; absent/expired sessions require recovery without revealing object existence. Mutating routes require origin/CSRF validation. `Idempotency-Key` is scoped by owner + route and binds a request hash; reuse with changed input returns 409. Default routes do not expose a public share URL.

| Route | Request | Success / other state |
|---|---|---|
| `POST /sessions` | no signup; server issues opaque capability cookie | 201 expiry/retention disclosure; never return credential in URLs |
| `POST /videos` | multipart owned MP4; validated metadata | 201 `{video_id,status:"uploaded"}`; stream to private quarantine |
| `GET /videos/{id}/analysis` | owned video | 200 stage, completed observations, caveats |
| `POST /runs` | `{video_id,platform:"reels",tier:"flash",audience_preset_id,comparison_group_id?}` | 202 `{run_id,status,events_url}`; duplicate key returns original run |
| `GET /runs/{id}` | owned run | 200 durable status/sequence; poll fallback |
| `GET /runs/{id}/events` | `Last-Event-ID` or `after` cursor | SSE persisted events; heartbeat has no reaction semantics; expired cursor returns snapshot/reset marker |
| `GET /runs/{id}/report` | owned run | 200 report if ready; 202 current stage; 410 deleted |
| `GET /runs/{base}/compare/{revised}` | two owned runs | 200 comparison or 409 incompatible/not-ready with reason |
| `POST /runs/{id}/thumbnails` | owned source frame choice + title | 202 operation; idempotent, bounded to original + 3 variants |
| `GET /runs/{id}/thumbnails` | owned run | 200 pending/result with vote denominators/provenance |
| `GET /videos` | current owner | 200 session history, never other sessions' videos |
| `DELETE /videos/{id}` | confirmation in client, idempotency key | 202 `{deletion_id,status:"pending"}`; immediate access revocation |
| `GET /deletions/{id}` | owned operation | 200 pending targets or complete; redacted target classes only |

Error envelope: `{code,stage,message,retryable,request_id}`. Safe user text only. Raw provider errors may be retained in restricted redacted diagnostics; no authorization headers or content excerpts. Later what-if/PDF/share endpoints are defined by V08 before coding; they are not part of the first slice interface.

## Provider boundary — observed saved mapping

Historical implementation boundary: `PipelineClient.text` calls `Client.call(POST /responses)` then `output_json`; the latter discards the envelope and rejects non-completed responses. Client.call stores request header ID/latency/usage in a ledger and saves successful HTTP JSON separately. Transport `success` can therefore contain generation `incomplete`. Existing final persona path is Spark 1.3 Standard, current real frame plus scene-local observations/local transcript and own past impression, `store:false`, strict JSON schema, minimal reasoning. Native scene files are used for shared extraction, not attached as whole-video persona context. The fixture request is explicitly illustrative of this selected path. No endpoint verification or paid rerun occurred in this correction.

`normalize_envelope(raw, receipt)` returns our `{request_id,response_id,model_id,reported_version,output,usage,latency_ms,status,error,incomplete_reason,cancellation}`:

| Normalized field | Observed source / rule |
|---|---|
| request_id / response_id | ledger `x-request-id` capture / body `id`; never substitute one for the other |
| model_id / reported_version | body `model`, fallback ledger requested_model / null (immutable backend revision unavailable) |
| output | completed `output[type=message].content[type=output_text].text`, concatenate then strict JSON parse; reasoning/encrypted content never enters output |
| usage | input/output/total tokens plus nested cached/reasoning counts; retained on incomplete generation; missing usage remains null, never zero or free |
| latency_ms | ledger latency_sec converted decimal half-up to integer milliseconds; excludes preparation, not end-to-end latency |
| status | completed, incomplete, refused, error; unknown generation status fails closed |
| incomplete_reason | observed `incomplete_details.reason=max_output_tokens`; no partial JSON accepted |
| error | safe local code/HTTP status only; observed HTTP500 is ledger-only, body absent and usage unknown; charge uncertain, no automatic retry |
| cancellation | unknown; not exercised, no cancellation guarantee |

Saved success source is `04b852728ae22967f408f71e34f274911ab07578`. Incomplete/HTTP500 are pre-repair `e8abd1bee0b5706d9166aba4f38985ed6fa6bcff`, not relabeled as final paid runs. Every example records original response (when present), ledger and revision-record SHA-256 plus call number. No refusal was found in inspected saved envelopes; refusal parser handling is synthetic-test coverage only. `tests/reconcile_saved.py` re-extracts allowlisted projections and reconciles original envelopes to the 19 saved small-cast reactions and both notes without exposing content.

New network/provider calls are outside this correction's authority. Saved evidence demonstrates historical adapter/schema feasibility only. Fresh inference, provider deletion/cancellation and full-Flash performance need separately authorized applicable evidence. Replay must be labeled recorded evidence, bound to exact original media SHA-256; unmatched uploads cannot inherit saved observations/findings.

### Reaction and note conversion

`normalize_verdict` requires one exact expected persona ID, a boolean watch decision, nonempty reason, <=30-word legacy impression, and unique whitelisted legacy action strings. It maps `impression` to `impression_update` (canonical maximum 60 words), scene seconds to integer ms, and takes a server-assigned evidence ID. Continued reasons are stored as `simulated_reason` evidence; only stopped viewers get `drop_reason`. Evidence preserves exact quote, persona/scene identity and source scene range. Inputs never execute tools or render HTML.

`stop_trigger` computes segment stops / valid respondents, threshold >=0.15, rejecting duplicate respondents. V02 supports only this detector initially. `normalize_note` converts `start_sec/end_sec`, `finding/suggested_edit` and `evidence_ids/quotes` to the C5 note; a known deterministic trigger and at least one of its evidence IDs are required. Quotes must exactly match a selected stored reason and note range must lie within trigger and cited scene. Missing trigger suppresses the note; unsupported quotes/ranges/actions reject it. This intentionally suppresses one historical small-cast note instead of treating all paid prose as supported product advice. No causal/real audience claim follows from the trigger.

### Small profile, report and recovery semantics

Requested cast is immutable. Effective cast counts valid terminal traces (stopped or reached final scene); stopped is a successful terminal outcome, not failure. Requested = effective + failed + pending. Any pending unit means processing; terminal zero effective means failed; any missing terminal trace means incomplete. All requested valid traces yield `complete_test_profile` for explicit test profiles and `complete` only for Flash requesting 50. Flash <40 is necessarily incomplete; 40–49 also cannot claim full-cast completion. This rule resolves the old unqualified <40 text for V02 without weakening V03.

The synthetic fixture includes complete report provenance, all five content/config hashes, source revision explicitly unavailable because no execution occurred, synthetic observation timestamp, model/version/usage absence, methodology, coverage, caveats, requested/effective/failed/pending/stopped counts, and exact completion/resample arithmetic. Canonical JSON hashes use sorted keys, compact separators, UTF-8 and no nonfinite values. Media zero hash is a disclosed synthetic placeholder. Three hand-checkable resamples are not the production 200.

C4 cursor is a positive per-run sequence; SSE ID is the persisted event_id, resolved under owner+run scope. Conflicting run/ID or invalid cursor is rejected; reconnect sends sequence > cursor, duplicate event IDs are ignored. Heartbeats have no domain sequence or reaction semantics. Retention-expired cursor produces `run.snapshot` with `reset:true` and `through_sequence`, then resumes after that sequence. Discriminated fixtures cover persona, snapshot and deletion events. DB uniqueness/transaction/SSE enforcement remains V02 implementation, not proved by schema validation.

C8 first delete transaction tombstones media, revokes access, increments fence generation and creates one owner+video deletion operation; repeat delete returns that same deletion ID, including after completion. Idempotency is owner+route+key bound to request hash, changed input 409; deletion identity additionally remains stable across different keys. Targets enumerate originals, derivatives, provider files, runs, events, reports and outstanding jobs. Operation stays pending while any target is pending/failed. Failed provider target retains error code/next retry; complete requires all target completion timestamps and final operation timestamp. Upstream backups remain unverified. Every write checks current lease generation and tombstone in its transaction; late response after deletion enters cleanup without report/bytes resurrection. Pending/retry/complete/repeat/stale-job fixtures and pure fence predicate are contract checks only; actual persistence/recovery is V02 work.

## Metric and evidence contracts

Each metric has `kind` (`observed_count`, `simulation_range`, `heuristic_index`, `hypothetical_reach`), unit, optional observed value, range/method, denominator and evidence IDs. Count and derived range are different fields. Notes cite both a trigger observation and persona evidence; absence of a supported fix means no negative note. Comparison can legitimately show no supported difference.

Ranges: 200 resamples of whole persona traces; nearest-rank p10/p90 (`ceil(p*n)`, one-based). Fixture supplies three explicit resamples only to make arithmetic hand-checkable; production uses 200 and records seed/method. For paired A/B resample the same indices across cuts. Never subtract independent endpoint bounds and call that a paired interval.

Trend-fit output is unavailable when rules or evidence are missing. A static pack date is distinct from the provider model's training cutoff. Every report carries source Git SHA, media/feature/cast/config/prompt hashes, model IDs/reported versions, observed time, call-usage ledger, replay/live flag and limitations.

## Required negative fixture mutations

- Add a scene-1 request for skipped `p1`: scheduler/audit test must fail; do not replace production scheduler with fixture logic.
- Insert full-video media reference or future transcript in scene 0: projection validator rejects dispatch.
- Duplicate accepted persona verdict/event: persistent result and streamed counts remain unchanged.
- Change a note evidence reference to `missing`: report validator rejects it.
- Change another owner's video ID: no object/report/event/thumbnail/delete access.
- Replay deleted media job with old lease: no new bytes/report created; late provider output enters cleanup.
- Give A/B mismatched model/pack hashes: incompatible comparison, no winner.
- Mark a synthetic fixture as live: provenance validator rejects it.
