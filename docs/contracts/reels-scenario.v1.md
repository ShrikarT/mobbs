# Reels hypothetical scenario v1

Integrator's executable definition of the existing V03 propagation proposal, for subsequent reporting work. **Not implemented or accepted yet.** No fresh personas, paid requests, platform API or claim about real Instagram distribution. Preserve the first [Flash report boundary](flash.v1.md); do not ask its current worker to expand scope. This contract must receive independent review with its implementation before integration.

## Meaning and fixed assumptions

The architecture fixes seed audience50, at most3 cohorts, expansion2x, gate0.6, weights completion/share/save/like/comment =45/25/15/10/5 percent, 48-hour exponential decay and168 hourly steps. This defines the previously unspecified timing precisely:

- Three cohorts **include the seed**, giving assumed capacities50,100,200; maximum potential350. These are hypothetical exposure capacities, not extra LLM viewers or actual people.
- All gates reuse the same effective panel's whole terminal traces. Each rate is the fraction of terminal personas completing or taking the action at least once. No resampling scenes independently, synthetic extra responses or learned platform coefficients.
- A next cohort unlocks if the preceding cohort's reused-panel score is >=0.6. With this fixed shared panel each gate has the same score; disclose that limitation. Compare exact weighted integer counts: `45*completed + 25*shared + 15*saved + 10*liked + 5*commented >= 60*N`. Do not round percentages before the gate. At equality expansion is allowed.
- The source PRD calls decay a half-life; ARCHITECTURE names48 hours without defining its convention. Preserve the source meaning: **48-hour half-life**, `2**(-hour/48)`, not an unexplained change to a48-hour e-folding time. Apply decay after cohort expansion, as the original flow specifies. It models the rate of additional hypothetical exposures tapering over time, so cumulative reach never decreases.
- All seed capacity is present at hour0. For total unlocked capacity `C`, cumulative expected exposures at hour `h` are `50 + (C-50)*(1 - 2**(-h/48))`. Hourly rows are h=1..168; initial hour0=50 is stored separately. This simple timing is an uncalibrated assumption, not a fitted recommendation algorithm. No hidden competition dampener or extra parameters.
- Potential and expected exposures are distinct. Keep fractional expected values in calculations; UI may round them with an approximation label. Do not label expected exposure counts as observed simulated persona counts.

Available only for a complete Flash50 run with observed completion and the four weighted action signals. Test/incomplete/zero-valid or missing-signal runs return explicit unavailability. Missing follow intent is irrelevant to this formula and remains unavailable in engagement. An unavailable scenario cannot prevent inspection/deletion of the rest of the report.

## Additive report field

`scenario` has `schema_version:'reels-hypothesis-1'`, `status:'available'|'unavailable'`, and `label:'Hypothetical Reels scenario'`. Unavailable includes a safe `unavailable_reason` and no fabricated numeric curve.

Available includes:

- `assumptions`: `{seed_audience:50,max_cohorts:3,expansion_factor:2,gate_threshold:0.6,weights:{completion:0.45,share:0.25,save:0.15,like:0.10,comment:0.05},decay_half_life_hours:48,horizon_hours:168,step_hours:1}` plus an explicit assumption-version/hash in manifest/report provenance.
- `panel`: `{requested:50,effective:50,additional_llm_viewers:0}`; `gate_score` is the derived fraction with range/method, effective denominator and evidence IDs.
- `cohorts`: three ordered rows `{index,capacity,unlocked,gate_required,gate_score}`. Index0 seed has no gate, index1/2 use the same declared panel score; index2 is locked if index1 is locked. Fixed capacity is a parameter, not a metric with invented uncertainty.
- `potential_exposures`, `reach_7d` and `initial_exposures` use the metric shape `{kind:'hypothetical_scenario',unit:'expected_exposures',observed,denominator,range,evidence_ids}`. The existing `observed` JSON key means scenario central estimate in this explicitly marked field, never observed views. Prefer plain scenario estimate wording in the UI.
- `curve`:168 rows `{hour,cumulative_exposures:<same metric shape>}`. `initial_exposures` is separate hour0. `totals` completion/like/share/save/comment expected exposures equal the corresponding panel rate times central cumulative reach. Their ranges recompute the full function per resample; do not multiply independent interval endpoints.
- `methodology`:200 whole-persona resamples, replacement, stored seed and nearest-rank p10-p90; same sampled trace indices as other report metrics. Apply the entire gate/expansion/decay function to each sample, then take bounds at each hour/total. A threshold can produce a bimodal range; never smooth it into a calibrated confidence interval. Fixed assumptions can have zero-width resampling ranges.
- `caveats`: not calibrated against real viewers/platform; no causal or reach-uplift claim; thin archetype library warning from manifest; future cohorts reuse the panel and add no independent evidence; half-life and gate are assumptions.

UI keeps this secondary to the actual50-instance report, with a text table and assumptions. Live event nodes always correspond to actual persisted persona decisions; hypothetical cohorts never animate as fresh model activity or increment the actual cast.

## Canonical arithmetic fixtures

These are deliberately synthetic hand-checkable traces for production-function tests, not evidence of real audience outcomes. N=50 complete terminal traces and one scene suffice for each; action intent has unobserved timing, preserving existing normalized shapes.

| Fixture | Terminal outcomes/actions | Gate / potential | Expected cumulative exposures |
|---|---|---|---|
| no expansion | All50 stop, no actions |0; seed only50 |50 at every hour |
| all pass | All50 complete and each likes/shares/saves/comments |1; all3 cohorts,350 | h0=50, h48=200, h96=275, h168=323.4834957055045 |
| exact threshold | All50 complete and save; no other action |0.60; all3 cohorts,350 |same reach curve as all pass; share/like/comment totals0, completion/save totals equal reach |
| below threshold | All50 complete;49 save; no other action |0.597; seed only50 |central curve50; resampled ranges must be computed, not assumed zero-width because some samples can pass |

Required mutations: gate equality vs one missing save; fewer than50 valid traces; null/missing weighted action; duplicate action per persona; resample a whole multi-scene trace vs individual scene mixing; same seed reproducibility; end hour168; monotonic bounded curve; empty inputs finite/unavailable. Tests must call the production scenario/report component, not a duplicate formula installed solely in tests.

Source authority: [ARCHITECTURE](../ARCHITECTURE.md#simulation-methodology-proposal), [brief reconciliation](../PROJECT_BRIEF.md#reconcile-before-implementation), owner-approved V03 directive. Original private source PRD section8.4/propagation lines206-208 is reference intent; no private text/media is copied into fixtures. This mathematical completion preserves the declared constants and labels rather than claiming an empirical platform model.
