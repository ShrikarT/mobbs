# Evidence and research — 2026-10-27, updated 2026-10-28

## Owner update — 2026-10-28

Shrikar reports successful Muse Image generation in the playground and receipt of $150 Meta credits. Treat both as owner-confirmed facts; no repeat proof request is needed. Direct API behavior, remaining balance and permitted app deployment are separate, untested questions. The geographic policy was re-read on 2026-10-28 and still explicitly lists Muse Image: India. This conflicts with observed playground availability; neither account-specific exemption nor changed terms have been established. Preserve the discrepancy rather than conclude the playground cannot work or that it grants deployment permission.

Owner selected [ShrikarT/mobbs](https://github.com/ShrikarT/mobbs). GitHub connector metadata verified public visibility, default branch main, size 0 and repository ID 1436533420; `git ls-remote` succeeded with no refs. Local `origin` was configured to its clone URL; no push or GitHub issue write occurred. TokenTree is excluded by owner instruction; replacement demo subject is unresolved. Earlier observations below describe the initial planning baseline, not the updated account/repository state.

Research was read-only. Public documentation describes capabilities; it does **not** verify this account's access or an implemented integration. No paid call, billing inspection, credential read, account mutation, external message or publication occurred.

## Local baseline and source provenance

The workspace was empty: no README, manifest, source, schema, tests, CI, deployment configuration, nested instructions, tracker documents, ADRs or handoff. Initially Git resolved to `C:/Users/Shrikar`, branch `master`, commit `f8d430c6e694af8ad4b3a9483423db579896f0b3`, with unrelated changes. That is **not a Mobbs baseline**. It was left untouched. A fresh local repository was initialized at `C:/Users/Shrikar/viralist`, branch `main`, initially without a remote (configured on 2026-10-28 above).

| Local input | SHA-256 | Treatment |
|---|---|---|
| `D:\UserFolders\Downloads\viralist-prd-spec-complete (2).md` | `D7C0592F9C9E168D21782C6E5902B6B325EF7EB0725C68AE2F7764EC5FADB95C` | Product intent; internal conflicts reconciled in PROJECT_BRIEF |
| `D:\UserFolders\Downloads\hackathon (1).md` | `D66957BAFAB14740D1B48DEBED7FE713B0008205EC3087F554CD173F239BEF09` | Participant summary, not verified official rules or authorization |
| Goal objective attachment, `506048c9-5361-4faa-a3fa-905280dd4d77/goal-objective.md` | `94C161F78B70FD6AA617A8072451F27DE01EEF85B8EDC4DAF12CB68FFFA008ED` | Requested planning scope; no product code |

Original inputs remain unchanged outside this repository. Their operative product requirements are captured here; private participant material is not copied into a future public repository. Referenced smoke-test scripts, demo kit and earlier PRDs were not supplied and were not inspected.

Read instructions: supplied project policy; `C:\Users\Shrikar\AGENTS.md`; research, writing-for-agents, domain-modeling and orchestration skills; PROJECT-AGENTS template; ORCA-HANDOFF policy. `orca skills get orchestration` failed: “The term 'orca' is not recognized as a name of a cmdlet, function, script file, or executable program.” Background research/independent Orca verification was unavailable; research and cold-start checks are author-performed.

## Verified public facts and implications

| Source | Observed fact | Consequence / limit |
|---|---|---|
| [Meta event](https://dev.meta.ai/events/global-hackathon) | Oct 26 kickoff, Nov 4 21:00 ET submissions, Indie/startup tracks and two themes; page mentions Spark, Image and SAM | Deadline verified; individual selection, credits and detailed judging rules remain supplied-only. Public page says Nov 4–8 judging, guide says Nov 5–8: use deadline, confirm participant schedule. |
| [Meta models](https://dev.meta.ai/docs/models) | `muse-wonder-1.0` is documented on the API; Wonder Full is subscription-only in Muse Code. Spark versions 1.1/1.2/1.3 are listed, not a hosted “small/distilled Spark” SKU | Wonder model ID is no longer merely third-party reporting. Choose actual model from account catalog; no invented small-model identifier. |
| [Video/audio guide](https://dev.meta.ai/docs/video-understanding) | MP4 video; Responses supports uploaded `input_file`/`file_id` and `input_video`/`video_url`; embedded audio is supported. 1.3 audio-quality caveat persists | Propose Standard Spark 1.2 for audio-bearing slice until controlled 1.3 test. Native clips and timestamp fidelity still need smoke tests. |
| [Image guide](https://dev.meta.ai/docs/image-understanding) | Vision input supports text extraction and image content blocks | Useful OCR/detail candidate; exact image-limit enforcement and SDK serialization need a boundary test. Keep ≤50 as conservative application limit. |
| [SAM overview](https://dev.meta.ai/docs/sam/overview) | `sam-3.1` returns object boxes/masks and tracks objects in video through Responses | Does not establish temporal scene-cut detection, semantic scene labels or OCR. Use local cut detection; attach SAM geometry only to a real consumer. |
| [Geographic policy](https://dev.meta.ai/legal/geographic-use-policy) | Dated Oct 12, rechecked Oct 28; text restricts Muse Image from India and to end users located there; bypassing access controls is prohibited | Owner reports working playground access. Resolve that discrepancy for API/deployment use; retain frame/layout fallback. Key issuance elsewhere is not proof of permission. |
| [Files guide](https://dev.meta.ai/docs/file-handling) | Upload ≤1 GiB; inline ≤50 MB; stored files do not expire by default. Optional `expires_after` supports 1 hour–30 days; explicit deletion endpoint exists | Set expiry and track all provider IDs for deletion. API deletion is not proof about backups or legal retention. |
| [Voice model description](https://dev.meta.ai/docs/models) | `muse-voice-transcribe-1.0` supports turn timestamps, not word timestamps | Timestamp granularity must travel with transcript. No word-precise claim from turn-level data. |
| [Pricing/limits](https://dev.meta.ai/docs/pricing-rate-limits) | Standard Spark $1.25/$4.25 per million input/output tokens; Wonder $4/$20; SAM $0.20/1,000 video frames, minimum 50 frames/request; Voice $0.18/hour. Spark 1.2/1.3: 3,000 RPM, 4M TPM per team; SAM 3,000 RPM | Published rates, not credit balance or guaranteed throughput. Reserve spend before calls, reconcile measured usage, respect returned limits. Standard mode avoids contributor training permission. |

The supplied SAM 15,000-frame limit was not corroborated in the pages inspected. Record UNKNOWN rather than inherit it as verified. Max native-video duration, effective tokenization, account limits, response latency, refusal behavior and pricing actually charged remain smoke-test questions. The file expiration option is a useful addition to the original brief.

## Alternatives: capabilities, not independently tested quality

| Alternative / first-party source | What it gets right | Mobbs switching hypothesis |
|---|---|---|
| [OpusClip scoring and selection](https://www.opus.pro/blog/viral-moment-detection-api) | Ranks moments and describes standalone scoring | A founder may prefer traceable audience reactions for an already-edited product demo. We cannot claim competitors lack suggestions or that Mobbs is more accurate. |
| [PickFu screen-recording surveys](https://www.pickfu.com/products/screen-recording) | Real respondents explain their experience; supports video/file inputs | Simulations may provide an earlier inexpensive iteration, but cannot replace human validity. No cost/quality superiority has been measured. |
| [Frame.io comments](https://help.frame.io/en/articles/9105278-comments-panel-overview) | Time-linked, completable feedback with sorting/export | Automating first-pass feedback may help before a human review. We retain the timestamp-to-evidence interaction principle. |
| [Descript transcript editor](https://www.descript.com/tools/video-transcript-generator) | Transcript-linked video editing | Mobbs can prescribe an edit for an existing editor; building another editor would dilute the wedge. |

No interviews, trial use or competitive benchmark occurred. Product demand, relative cost, uniqueness and willingness to pay are HYPOTHESES.

## Architecture and design reference evidence

- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html): temporal scene-change signals are available. Whether thresholds yield useful segments on product footage is an experiment.
- [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/): distinguishes small in-process tasks from heavier separate processing. Our recommendation is a durable out-of-process worker.
- [PostgreSQL SELECT](https://www.postgresql.org/docs/current/sql-select.html): SKIP LOCKED supports queue-like consumers. Lease/retry correctness remains our responsibility.
- [GitHub comparisons](https://docs.github.com/en/pull-requests/how-tos/commit-changes/comparing-commits): explicit base/compare references motivate labeled A/B settings. This is an interaction analogy, not copied branding.

These references were inspected as documentation, not as a screenshot-level visual audit. Proposed art direction is original. No source assets were downloaded or licensed.

## Event and rights gaps

The supplied participant guide reports public-repo/new-work rules, a three-minute demo, credit-card requirement, $150 credits, detailed rubric/prizes and selection status. Preserve those as conservative working constraints, but confirm against the actual accepted rules before submission. The public page's linked waiver/rules were not reviewed; participant enrollment, credit terms, prize eligibility, IP terms, license choice and public rights to the demo assets remain UNKNOWN. Do not present this planning pass as legal clearance.

## Existing integration classification

Every proposed runtime provider (Spark, SAM, Voice, Wonder and alternate image generation), database, storage service, job worker, analytics sink and deployment is **MISSING**. None is REAL-WIRED, CONFIGURED-BUT-UNTESTED, IMPORTED-ONLY or TEST-MOCKED because there is no application. Contract examples are **SYNTHETIC DESIGN FIXTURES**, not DEMO-SIMULATED product runs. Connected creative tools are not app integrations or proof of a paid entitlement.
