# V00-R1 independent readiness review

**Decision: REVISE before starting V02.** The frozen experiments provide useful, independently checked offline adapter/scheduler evidence, but the provider mapping and canonical contract example are not ready to freeze. This calls for a bounded contract/gate correction, not an architectural redesign or another persona-diversity experiment.

- Reviewer: Codex, independent of the experiment author, configured default model; no helpers spawned.
- Run: `run_78e9fa786ccc`; Task: `task_f0e1665a723f`; Dispatch: `ctx_c2891d1189a6`; parent/task: V00 / V00-R1, initial review, no correction submission reviewed.
- Reviewed full SHA: `a2c90b5e99109d79a8ebbf2249aab0960838666a`.
- Checkout/root: `C:/Users/Shrikar/orca/workspaces/viralist/codex-v00-readiness-review`; branch: `codex/v00-readiness-review`. Assigned worktree verified using `git worktree list`; main checkout is separate. Identity matched before and after inspection; tracked tree clean.
- Environment: Windows `Windows-10-10.0.26300-SP0`, PowerShell, Python 3.10.2, requests 2.32.5, Pillow 12.2.0. No packages installed. Coordinator reports Docker engine unavailable; this review did not inspect/change services or attempt database integration.
- Owned output: this report only, outside Git. No tracked edits, commits, remote writes, provider requests, credential reads, private media/transcript/raw-response access, browser sessions or deployment.

## Guidance and receipt

Read `C:/Users/Shrikar/AGENTS.md`, assigned checkout `AGENTS.md`, `README.md`, `docs/STATE.md`, `PLAN.md` V00/V01/V02, `docs/PROJECT_BRIEF.md`, `docs/ACCEPTANCE.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/contracts/vertical-slice.v1.json`, both `docs/adr/0001-simulation-evidence-boundary.md` and `0002-durable-worker.md`, and `docs/evidence/spark13-rerun.md`. Read installed code-review/orchestration skills, version-matched `orca skills get orchestration`, and `C:/Users/Shrikar/.agents/policy/ORCA-HANDOFF.md`. Optional `docs/agents/{issue-tracker,triage-labels,domain}.md` and additional ancestor instructions were absent. Relevant Python source, tests, requirements and artifact-verifier source were inspected; unrelated product briefs/private artifacts were not opened.

Coordinator accepted the startup receipt before tests/report drafting, explicitly retaining the frozen SHA and read-only scope. The historical root-checkout instruction was superseded only for this assigned review. The task's no-spawning rule overrides the code-review skill's delegation workflow; standards and specification were reviewed here without delegation. No branch-diff acceptance was invented: this is a frozen-candidate readiness review against the supplied task criteria. A historical source comparison was read-only.

## Observed checks

| Command/component | Observed result | Boundary/limit |
|---|---|---|
| `git rev-parse --show-toplevel`; `git branch --show-current`; `git rev-parse HEAD`; `git worktree list` | Exit 0; exact assigned root/branch/SHA and separate worktree | Local identity only |
| `git status --short`; `git diff --check` before/after review | Exit 0; no output/clean; final explicit `git_diff_check_exit=0` | No tracked changes |
| `python --version` | Exit 0; Python 3.10.2 | Review environment, not selected deployment runtime |
| `Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue` then `python -m unittest discover -s experiments -p 'test_*.py' -v` | Exit 0; **25 tests passed**, unittest reported 1.438s | Key removed from child environment without reading it; tests supply dummy stdin. Actual experiment functions execute; external models/HTTP responses are doubles |
| PowerShell Python-stdin structural/probe audit, reproduced below | Exit 0; fixture arithmetic/structural assertions passed; shape incompatibilities reproduced | Test-local assertions, not a production schema validator |
| `git diff --stat 04b852728ae22967f408f71e34f274911ab07578 a2c90b5e99109d79a8ebbf2249aab0960838666a -- experiments/meta_pipeline.py experiments/meta_smoke.py experiments/test_pipeline.py`; targeted `git diff` for first two modules | Exit 0; current scheduler adds optional cards/schema and definition counting; legacy paid CLI retired | Source comparison does not reconcile historical paid artifacts or rerun them |
| Targeted `rg`/source reads for contracts, fixture, experiments, tests and verifier | Exit 0; findings below | Repository contents only |

Fixture SHA-256: `450ba3e67a368a0c21de97cedbd65a4d50bb51b4773701a76edb51c3ca150f8d`.

Tests observed: 50 IDs/148 verdicts under a provider double; skipped viewer receives no later dispatch; early projection excludes final-only cue and peer state; failure stops that viewer while preserving partial count; malformed/incomplete output and duplicate/wrong IDs rejected; concurrent budget reservations constrain actual Client logic; note quotes/ranges and fake-proof suggestions checked; privacy/layout and behavioral-fixture regressions pass. These are properties of the experimental implementation, not HTTP/DB integration. Even test summaries containing `live_native_scene_clips: true` came from stubs and do not establish live inference.

An initial checkpoint send used unsupported Orca type `message` and was rejected without enqueue; it was corrected to supported type `status` and durably sent. Lifecycle/report delivery is separate from technical checks.

## Numbered findings

1. **HIGH / V02 blocker: the required provider-response mapping/receipt fixture is absent.** `docs/CONTRACTS.md:50-56` still labels the account untested and requires V01 redacted real examples before serialization; `PLAN.md:27,79-80` makes that a prerequisite. The only canonical JSON example, `docs/contracts/vertical-slice.v1.json:24`, is explicitly illustrative, uses Spark 1.2 plus an input file, and has no real normalized response. Current `PipelineClient.text(label,prompt,schema,file_id=None,max_output=1200,audit=None,image_path=None)` at `experiments/meta_pipeline.py:134-169` returns parsed content only; `output_json` at :56-60 strips the envelope, while `Client.call` at `experiments/meta_smoke.py:112-145` records header request ID/usage/latency separately. No implemented normalized `{request_id,model_id,reported_version,output,usage,latency_ms,status}` return exists. The latest reported persona path is Spark 1.3 with a current frame plus scene observations, with native clips used in extraction. **Smallest remedy:** have an authorized evidence custodian produce sanitized success and incomplete/refusal/error examples from saved V01 artifacts, with source revision/hash and an explicit envelope/usage/error mapping; update the illustrative request to the selected path or mark it historical. Keep unavailable backend version null and unsupported cancellation unknown. No new charge is needed to inspect existing evidence, and this review does not certify a provider's present schema.

2. **HIGH / V02 blocker: C3/C5 cannot directly consume the experimental verdict/note shapes.** `docs/CONTRACTS.md:11,24` and fixture :19-21 use `impression_update`, nullable `drop_reason`, typed timestamped actions, signals and `follow`. `experiments/meta_smoke.py:49-52` uses `reason`, `impression`, string actions, four actions excluding follow, and no signal/timing fields. `validate_verdict(raw,pid)` at `experiments/meta_pipeline.py:278-285` accepts at most 30 impression words, whereas C3 permits 60. Feeding fixture p1 into it produces `KeyError 'reason'`; a forged string action `execute_tool` also passes that local validator (data only; no tool executed). Provider structured-output constraints are not a substitute for local validation. `validate_notes(value,records)` at :366-382 expects `evidence_id`, `reason`, `start_sec/end_sec`, `quotes` and `suggested_edit`; the canonical note/evidence produce `KeyError 'evidence_id'`. **Smallest remedy:** freeze an explicit normalization layer and server-side schema, not a claim that the experiment already implements C3/C5. Specify seconds-to-integer-ms rounding, ID and evidence mapping, impression bounds, allowed actions and unknown signals. Do not invent action timestamps or confusion/CTA evidence from a string action/reason; either request and validate the richer fields or mark unsupported optional outputs unavailable under an explicit rule. Preserve continued-viewer reasons in evidence without misusing `drop_reason`. Build the already-proposed deterministic trigger plus quote/range validation for the V02 supported note (`docs/ARCHITECTURE.md:60`); experimental `make_notes` is model prose, not that detector implementation.

3. **HIGH / contract-freeze blocker: the canonical example omits required C5/C8 guarantees and lacks a precise small-profile completion rule.** `docs/CONTRACTS.md:13,64` requires effective/requested cast, methodology, coverage/caveats, hashes, observation time and usage provenance; fixture :26-32 has a denominator and minimal trust block but no complete manifest/coverage/effective-cast representation. C8 at :16 requires access-revocation and completion times; fixture :35 supplies only `access_revoked: true`, no revocation timestamp, no per-target/completion representation or repeated-delete relation. The pending-provider state is honest, but cannot exercise the promised lifecycle. `docs/ARCHITECTURE.md:58` / `docs/ACCEPTANCE.md:16` describe <40 valid personas as incomplete; V02 and fixture :4 intentionally use two. The test-profile label distinguishes scope, but an executable rule must keep an otherwise successful two-person run from inheriting Flash's failure threshold. **Smallest remedy:** complete the synthetic report/deletion shapes with clearly synthetic values/explicit unavailable reasons, add pending/completed/late-job/repeated-delete examples, and encode profile-specific requested/effective/failure semantics (a stopped viewer is not a failed viewer). Define cursor/event discrimination, idempotency scoping and lease fencing while implementing C4/C8; fixture `event_example` alone proves none of them. These are routine integrator/schema choices within approved invariants, not a reason for an owner architecture questionnaire. Executable schemas and negative mutations remain V02 work, after the proposal is reconciled.

4. **HIGH / readiness gate blocker: full V01 acceptance would overstate the evidence, while the V02 dependency currently requires it.** `PLAN.md:54-56,79` requires accepted V00/V01 and includes 60s worst-case, <=$0.50 and <=90s Flash criteria. `docs/evidence/spark13-rerun.md:22,55` instead reports ~$0.9433 and one 33.78s-video sample, not worst-case/p95. Paid evidence remains author-reported and was not independently reconciled here. `PLAN.md:7,34` still has no accepted prerequisite baseline; the direct task authorizes readiness review, not automatic adoption of all proposals. **Smallest remedy:** record exact independently accepted prerequisite scope/SHAs after correction; explicitly separate adapter feasibility needed for the small V02 path from still-pending full-Flash cost/latency tests in V03. If the owner keeps full S2 as a mandatory prerequisite, V02 remains blocked until it is met or amended. Do not mark all V01 or its historical paid runs REVIEW-ACCEPTED on the strength of this offline suite.

## Acceptance by component and evidence boundary

| Component | Decision at reviewed SHA |
|---|---|
| Frozen source / clean tree | ACCEPT, independently observed |
| Experimental scheduling, projection, tested validators and concurrent budget logic | ACCEPT only for the bounded offline properties observed above; validation gaps in finding 2 remain |
| Synthetic fixture syntax, scene continuity/hook, skip membership, references and example arithmetic | ACCEPT as a synthetic arithmetic example: 1/2 completes; samples [0,50,100]; nearest-rank p10/p90 [0,100] |
| C1 ingest/authz, C4 durable events/checkpoints, C8 fenced deletion | UNIMPLEMENTED / unverified; this is expected V02 implementation work, not a failed existing application |
| C2/C3/C5 executable provider/report mapping and complete canonical fixture | REVISE before freeze, findings 1-3 |
| Historical Spark paid stages and cleanup | WORKER-REPORTED only; source read/compared, no raw artifact reconciliation or live calls |
| Overall V00/V01 prerequisites for V02 | NOT ACCEPTED pending findings/decision record |
| Product integration | Pending/inapplicable to this candidate; no app exists |
| JOURNEY-VERIFIED | Pending; no HTTP upload, DB recovery, authorization, report browser or deletion journey exercised |
| RELEASED | Inapplicable; no release/deployment authorized or performed |

The historical 256 reactions, 88.192025s, $0.94328385 and 157 deleted/404 files are explicitly **author-reported**, not new independent observations. Their reported source is `04b852728ae22967f408f71e34f274911ab07578`, not this reviewed SHA. The offline tests at this SHA cannot transfer paid-source acceptance across revisions. No independent p95, real-world audience fidelity, distinct-fifty-personality, paired A/B or thumbnail-vote claim is earned.

## Owner input versus engineering and later release

**Owner decisions genuinely needed for dependent work:** explicit V02 implementation authorization; adopt/amend proposed upload/latency boundaries and any material S2 gate change; set the allowed spend/source of authority for a future real adapter smoke. The recorded $15 cumulative experiment ceiling and $14.69754320 tracked maximum in `docs/STATE.md:6,20` are existing author-reported history, not a fresh smoke budget. Preserve all prior cost and the $1.31327 uncertain reserve; $150 credits are not spending permission. Confirm retention/consent/provider terms before new private media is sent or a training claim made. Supplied test footage/repository/credits and actual prior Muse API access are settled; do not ask for them again.

**Routine engineering choices:** normalized local types, null semantics, selected supported/pinned local runtimes, migration details, transaction/lease/idempotency rules, decoder limits, explicit small-profile status, safe escaping, deterministic evidence-linked note trigger, and replay tests. Follow the proposed modular-monolith/durable-worker design unless an implementation constraint requires a material change. Docker unavailability is a local verification limitation to resolve in the authorized V02 environment, not grounds to install packages/change services here.

**Deferred release decisions:** public license, accepted event rules/submission, public hosting/vendor spend, publication, public demo footage/matched A/B rights, Muse Image policy resolution for app generation and release capacity. License/publication need not block a private small local V02 slice. Matched A/B and Thumbnail Lab are later work; no need to reopen the entire roadmap or solve all fifty persona differentiation before V02.

## Minimal next action

Integrator should make one bounded numbered correction submission addressing findings 1-4: reconcile provider mapping from sanitized saved receipts, complete the proposal/fixture and small-profile rules, and record only the owner decisions affecting V02. Commit it and request independent exact-SHA re-review under **V00-R1**; this is the initial review, so the two-correction limit has not been consumed. Then dispatch one V02 writer with accepted immutable prerequisite SHAs, disjoint owned paths, selected runnable DB/storage environment, and explicit real-smoke authority. Its acceptance must run production upload/session validation, durable state/event transactions, current-only cast dispatch, supported note, refresh recovery, cross-session denial and deletion fencing; external error doubles may not replace those components. No paid request should be made by this reviewer.

This review task is complete and submitted for coordinator handling; product acceptance remains pending. No integration SHA was created.

## Reproduction: executed Python-stdin audit

Executed as a PowerShell single-quoted here-string piped to `python -`, exit 0. It imports no client instance and opens only repository fixture/source modules.

```python
import hashlib, json, math, platform, sys
from pathlib import Path
sys.path.insert(0, 'experiments')
from meta_pipeline import validate_verdict, validate_notes
import PIL, requests
p = Path('docs/contracts/vertical-slice.v1.json')
f = json.loads(p.read_text(encoding='utf-8-sig'))
scenes = f['features']['scenes']
assert scenes[0]['start_ms'] == 0 and scenes[-1]['end_ms'] == f['media']['duration_ms']
assert scenes[0]['end_ms'] == min(3000, f['media']['duration_ms'])
assert all(a['end_ms'] == b['start_ms'] for a,b in zip(scenes, scenes[1:]))
assert all(0 < s['end_ms']-s['start_ms'] <= 5000 for s in scenes)
assert len({(v['persona_id'],v['scene_id']) for v in f['verdicts']}) == len(f['verdicts'])
stops = {v['persona_id']:v['scene_id'] for v in f['verdicts'] if not v['still_watching']}
assert all(b['scene_id'] <= stops.get(pid,999) for b in f['batches'] for pid in b['persona_ids'])
completed = [any(v['persona_id']==pid and v['scene_id']==scenes[-1]['scene_id'] and v['still_watching'] for v in f['verdicts']) for pid in f['batches'][0]['persona_ids']]
samples = [sum(completed[i] for i in indices)/len(indices)*100 for indices in f['expected']['bootstrap_indices']]
assert samples == f['expected']['completion_samples_percent'] == [0,50,100]
assert [sorted(samples)[math.ceil(q*len(samples))-1] for q in (.1,.9)] == [0,100]
assert f['expected']['completion_count'] == sum(completed) == 1
refs = {e['id'] for e in f['expected']['evidence']}
assert set(f['expected']['note']['evidence_refs']) <= refs
assert f['expected']['note']['trigger_id'] in {o['id'] for o in f['expected']['observations']}
assert f['expected']['deletion']['can_claim_complete'] is False
print('fixture structural/arithmetic smoke PASS; synthetic only; sha256='+hashlib.sha256(p.read_bytes()).hexdigest())
try:
    validate_verdict({'verdicts':[f['verdicts'][0]]}, 'p1')
except Exception as e:
    print('canonical verdict into experiment validator:',type(e).__name__,str(e))
v={'persona_id':'p1','still_watching':False,'reason':'specific','impression':'past','actions':['execute_tool']}
print('experiment validator accepts out-of-enum action:',validate_verdict({'verdicts':[v]},'p1')['actions'])
try:
    validate_notes({'notes':[f['expected']['note']]}, f['expected']['evidence'])
except Exception as e:
    print('canonical note into experiment validator:',type(e).__name__,str(e))
print('platform='+platform.platform()+' Python='+platform.python_version()+' requests='+requests.__version__+' Pillow='+PIL.__version__)
```
