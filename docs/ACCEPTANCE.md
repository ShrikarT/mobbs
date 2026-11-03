# Acceptance and test strategy

Local V02's recorded three-person journey is verified at the exact integration commit in [the current evidence](evidence/v02-integrated-journey.md). The matrix below includes later Flash, comparison and release gates; it is not a list of passes. Freeze the exact source SHA/container digest and fixture hashes before a verifier starts; any implementation correction invalidates affected evidence. Current scope and acceptance states are recorded in STATE.

## Named user journeys

| ID | Scenario and actual component exercised | Required observable result |
|---|---|---|
| A01 First useful Flash | New anonymous session uploads owned 9:16 MP4 ≤60s; actual HTTP/media worker/provider/report renderer | No signup; visible stages; 50-person request/cast manifest; first finding p95<60s from upload completion; verdict ≤90s in each rehearsal; report ≤300s; exact timings and cost recorded. Upload/network time reported separately. |
| A02 Inspect and act | User selects note, seeks player, expands evidence and assumptions | Note range matches underlying observation; at least one concrete edit for every negative finding; quotes resolve to stored simulated reasons; no unsupported “top 10%” or virality/algorithm claim; no forced notes when none supported. |
| A03 Sequential isolation | Production scheduler sees controlled early-skip and final-only secret cue | Skipped persona has zero later dispatches; early prompts exclude final cue/full-video references/summary leakage. Audit dispatch content in private test capture, not merely displayed graph. Fixture mutations reject. |
| A04 Compare cuts | Real owned A/B with same cast/model/prompt/pack/config; one deliberately changed segment | Compare labels base/revised, paired range and evidence; mismatches blocked; unresolved mapping marked uncertain; zero-crossing interval has no winner; unchanged-cut/order-swap controls do not force improvement. |
| A05 Choose thumbnail | Original + three variants from permitted Muse Image API or owned-frame/layout fallback; actual vote adapter and exporter | Thirty requested simulated voters per variant, effective denominators and reasons; ties/failed votes visible; source/provider provenance persists; API use satisfies resolved access/policy conditions; fallback never labeled generated; PNG matches selected variant. |
| A06 Delete and cross-session isolation | Two sessions, files/features/runs/events/provider IDs; delete during processing and after completion | Other session cannot read/stream/compare/delete any resource. Access revoked immediately; controlled artifacts removed ≤60s. Live provider deletion verified separately; provider outage remains pending, never false “complete”; late jobs cannot resurrect content. |
| A07 Honest report/accessibility | Production UI on desktop, 320px mobile, keyboard, 200% zoom and reduced motion | Every derived simulated metric has range/method/evidence and effective denominator; exact counts/time/cost have provenance. Model/trend versions distinct; unknown cutoff explicit; charts/graph have text equivalents, AA contrast, keyboard flow and captions where available. |
| A08 Restart/retry/budget | Kill worker mid-batch; duplicate POST; reconnect SSE with cursor; inject 429, malformed output and ambiguous timeout | Persistent unique events/verdicts, no duplicate counts or uncontrolled spend. Known rejection retry bounded; ambiguous charge paused/reconciled. <40 valid cast visibly incomplete; zero valid cast failed. Budget reservation prevents over-cap dispatch even with two requests. |
| A09 Ingest and abuse | Actual decoder/API: oversized/spoofed/corrupt/61s MP4, silent clip, path-like name, prompt injection in OCR, deceptive content | Bad media rejected before provider dispatch; limits enforce; temp files removed. Silence continues with caveat. Media instructions never execute tools or override schema. Deceptive-content path withholds optimization notes and explains. |
| A10 Reproduce and rehearse | Clean checkout/container at integration SHA; owned input hashes; target staging/deployed environment | Verified commands reproduce build; deployment digest tied to SHA; three full rehearsals recorded; truthful replay fallback; no claims from other revisions. Release additionally needs owner authority and target smoke. |

## Test layers and evidence limits

- Unit: deterministic feature-time projections, no-future visibility, score/range arithmetic, paired resampling, detector thresholds, schema/quote validation. Use fixture and boundary mutations. This cannot prove provider quality or browser behavior.
- Contract: provider parser against redacted V01 receipts; HTTP/event/report schemas against generated client; incompatible version/ID/ref rejection. Synthetic fixtures prove shape only.
- Integration: actual PostgreSQL migrations, job leases/fencing, state/event atomicity, private storage implementation, session authz, budget reservations and deletion inventory. Replace only external model/network outcomes to force failure paths. Do not substitute an in-memory scheduler or fake database for production behavior claims.
- Browser: Playwright journeys once a supported project exists; after UI changes additionally use `browse --local` or `browse --remote` via its skill. Capture console/network failures, tested viewport and keyboard path. A screenshot alone is insufficient.
- Real external smoke: one owned clip through chosen Standard model, usage recorded, real file removal and real 50-person path. Gate on authorization; report if unavailable instead of turning mocks into “integration passed.”
- Mechanism quality: manual review of known-cue footage, matched A/B and swapped order, silent controls; compare statements against pixels/audio and exact prompts. No inference that synthetic audience opinions predict real viewers.
- Usability: five target founders per PRODUCT, record task success and a justified edit. This is product validation, not prediction calibration.

Latency: for p95, collect at least 20 valid full-path attempts in the declared environment and report nearest-rank p95 plus sample size, cache state, upload duration, concurrency and failures. Three rehearsals prove only three rehearsals, not p95. Exclude replay runs from live latency claims. A cache-warm sample report is not fresh inference performance.

## Gates

1. **Ready:** accepted prerequisite SHAs, scope/contract fixed, access/cap authorized, task ownership clear.
2. **Review:** independent verifier inspects exact diff and runs relevant checks; evidence names component, environment, command/output, fixtures and mocked boundaries. No independent verifier → WORKER-REPORTED.
3. **Integration:** one integrator combines accepted commits; re-run relevant combined checks on new SHA.
4. **Journey:** independent A01–A09 on the combined artifact, with A10 reproducibility and live provider evidence where claimed. An outage blocks a live claim, not truthful recorded fallback presentation.
5. **Release:** owner authorizes target/publication/spend; accepted event rules/license/asset rights; secret/dependency scan; access/quota controls; data deletion/retention truthfulness; source/digest mapping; target smoke; rollback plan. Public demo capacity and limitations visible.

For a restricted local demonstration, public-intake/production operations gates may be explicitly inapplicable; they cannot be silently skipped for a public service. No accounts/payments/accuracy-dashboard acceptance is required for the current slice.

## Evidence record format

Task ID; author/verifier identity; full SHA; artifact digest; OS/runtime/browser/provider model; tested component/path; commands and observed outputs; fixture/input hashes and rights; live/mocked/replay boundaries; usage/latency; failures/gaps; achieved acceptance state; next action. Store sanitized evidence under `docs/evidence/`; private media/transcripts remain out of Git. Report each state separately, including pending and inapplicable states.
