# V00-R1 correction submission 1

State: **WORKER-REPORTED**, independent exact-commit review pending. This is the first correction submission against findings 1–4 of the unchanged [original review](v00-readiness-review.md), not a new general readiness review. Candidate revision is the single commit containing this report; the Orca worker completion supplies its full SHA and post-commit check results. Coordinator records any accepted prerequisite/integration SHA afterward.

Author: dispatched Codex default, no helpers. Run `run_eb62638ed3eb`, task `task_b413039b3ddf`, dispatch `ctx_5ac751b884ef`. Assigned checkout `C:/Users/Shrikar/orca/workspaces/viralist/codex-v00-correction`, branch `codex/v00-correction`, exact starting HEAD `14cbdb036ea2ef9b8ef62f3e881c0de3d9d93e43`. Root/branch/HEAD/clean tree and separate worktree verified before edits; coordinator accepted startup receipt via Orca ask. Main/coordinator checkout was never edited.

Read shared/project AGENTS, STATE, PLAN V00/V01/V02 and correction batch, PROJECT_BRIEF, CONTRACTS and original fixture, ARCHITECTURE, ACCEPTANCE, original review, both ADRs, original task criteria, latest owner attachment, README/GLOSSARY, ORCA-HANDOFF, installed orchestration/runtime, writing-for-agents and domain-modeling. Additional discovery stayed within owned code and explicitly authorized saved evidence. No helper, provider credential read, provider call, app startup, browser, tracker write, push, merge, deployment or publication. Initial broad Orca environment discovery included runtime hook/launch metadata in local tool output; none was committed, coordinator was notified, and later environment checks were scoped.

## Criterion-by-criterion correction

1. **Saved envelope mapping:** [provider-saved.v1.json](../contracts/provider-saved.v1.json) projects actual success, incomplete and HTTP500 ledger entries. `normalize_envelope` joins the exact body and ledger receipt, preserves token usage even when generation is incomplete, keeps immutable backend version null and cancellation unknown, and emits safe errors. Generation incomplete is distinct from HTTP/ledger success. Success uses final bounded source `04b852728ae22967f408f71e34f274911ab07578`; incomplete/HTTP500 use the actual pre-repair source `e8abd1bee0b5706d9166aba4f38985ed6fa6bcff`. No saved error body exists: the error example is explicitly ledger-only. No refusal was found; synthetic refusal handling is not observed provider evidence. Model paths now describe Spark 1.3 current-frame/scene-observation persona input, with native clips at shared extraction.
2. **Executable shared producer/consumer contract:** [contracts/normalized.py](../../contracts/normalized.py) owns envelope, strict JSON, reaction, evidence, note, detector and validation logic; future application and tests import this same module. Exact persona IDs, duplicate verdicts/actions, action whitelist, finite times and impression bounds are checked locally. Seconds convert decimal half-up to integer ms. Legacy string actions carry null time/unobserved timing. Signals stay null; continued reasons remain separate evidence, not drop_reason. A deterministic >=15% stop-fraction trigger plus exact quote/range/reference validation constrains the supported V02 note. All 19 actual saved small-cast response envelopes map to their persisted reactions; both note envelopes match saved notes. One note converts and one is suppressed for lack of the supported trigger. Historical experiment source/results are unchanged.
3. **Report/deletion/profile fixtures:** [vertical-slice.v1.json](../contracts/vertical-slice.v1.json) now carries cast status/effective denominator, complete synthetic provenance and methodology, coverage/caveats, five content/config hashes, observation-time kind, explicit unavailable source/backend/usage and report evidence. Hand-checkable completion is 1/2, samples [0,50,100], range [0,100]. Stopped is a valid terminal trace; two successful requested test traces produce complete_test_profile. Partial/all-failed/processing/Flash examples are explicit; no Flash 40–49 full-cast claim. Deletion inventories originals/derivatives/provider files/runs/events/reports/jobs with access revocation, per-target and operation completion, failed-provider retry, same operation on repeat, stale lease/tombstone and late-output cleanup rules. Event discrimination/cursor/idempotency/atomic lease-fence rules are documented. Pure validation/fence examples do not prove PostgreSQL transactions or real deletion.
4. **Owner authority/prerequisites:** AGENTS/PLAN/STATE/brief/architecture and ADR status record the actual approved local V02 stack, MP4 limits and implementation instruction. Independent reviewer owns exact correction acceptance; coordinator owns recording immutable accepted/integration/dispatch SHAs. Independently observed offline scope stays pinned to `a2c90b5e99109d79a8ebbf2249aab0960838666a`; no correction self-acceptance SHA is fabricated. Historical paid runs remain WORKER-REPORTED. Full-Flash cost/latency, 60s worst-case and p95 belong V03, while corrected adapter/schema feasibility gates the small V02 slice. New paid smoke remains separately unauthorized; recorded responses are labeled replay and must match original media hash.

## Observed author verification

Environment: Windows `Windows-10-10.0.26300-SP0`, PowerShell, Python 3.10.2; standard library for all added code. Existing experiment dependencies were reused without installation. These checks run actual production converter/detector/fixture code; the unchanged experimental offline suite replaces external provider/HTTP outcomes only. No application HTTP/session/DB/storage/report-renderer/deletion journey exists in this submission. Coordinator-reported PostgreSQL/S3 preparation was not independently exercised here.

| Command | Exit / observed result | Boundary |
|---|---|---|
| `git rev-parse --show-toplevel`; `git branch --show-current`; `git rev-parse HEAD`; `git status --short`; `git worktree list` | 0; assigned baseline/branch/root, initially clean and unique tree | Identity only |
| `Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue` then `python -m unittest discover -s experiments -p 'test_*.py' -v` | 0; original **25 passed**, 1.462s observed | Actual experiment code; external doubles, not live inference |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | 0; **14 passed**, 0.024s on final converter contents | Positive/negative mutations, saved projections, detector, quote/range validation, profile and deletion/fence contracts |
| `python -m tests.reconcile_saved` | 0; saved projection equals deterministic extraction, original hashes/IDs/usage match ledger; 19 reaction / 2 note envelopes reconciled; 1 supported, 1 suppressed | Private originals read-only; no transcript/model text printed; no network |
| Python JSON parse + `validate_fixture` + SHA-256 enumeration (below) | 0; both JSON fixtures parse, synthetic arithmetic/identities/hashes valid | Synthetic shape only |
| `git diff --check` | 0; no output | Formatting only |

Reconciliation `--write` was run to create/refresh only the public sanitized projection. Normal reconciliation performs equality checks without writes. Source modules at both recorded revisions are hashed using `git show <revision>:experiments/{meta_pipeline,meta_smoke}.py`; those hashes and original ledger/revision-record hashes are committed in the projection. This links evidence to author-supplied saved revision metadata, not cryptographic proof of historical runtime identity. No whole paid-stage, performance, cleanup or billing acceptance is inferred.

Fixture byte SHA-256:

- `docs/contracts/provider-saved.v1.json`: `39b2ac1f4488e992e624e9d54322f28639fb3a390ec44c44d1afe6021b69c2fd`
- `docs/contracts/vertical-slice.v1.json`: `17a3fc8168584edae5a1a04c78f64016042a95ae6e61b3264088aa7b49e335b0`

Fixture consistency reproduction from root:

```powershell
@'
import hashlib
from pathlib import Path
from contracts.normalized import parse_json, validate_fixture
for p in sorted(Path('docs/contracts').glob('*.json')):
    value = parse_json(p.read_text(encoding='utf-8-sig'))
    if p.name == 'vertical-slice.v1.json': validate_fixture(value)
    print(p.as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
'@ | python -
```

Private source root is the authorized `C:/Users/Shrikar/.codex/private-runs/viralist-spark13-20261028/`; no originals changed. Allowlisted examples retain sanitized request IDs, usage and relative source filenames/digests. Private output text is substituted with synthetic `{}`; encrypted reasoning, headers, private transcript/media and error prose are excluded. Raw success output shapes preserve only schema field names/types. The full public projection cannot establish semantic fidelity from substituted text alone; the private reconciliation executes the converter against original content and reports only counts/digests.

## Acceptance and remaining work

No routine correction remains known within findings 1–4. This submission is **WORKER-REPORTED**, awaiting independent exact-SHA review; product INTEGRATED and JOURNEY-VERIFIED are pending, RELEASED is inapplicable. No app journey, new paid inference, provider refusal/cancellation, upstream backup erasure, full-Flash latency/cost/p95, or fifty-distinct-human-behavior claim. Existing cumulative estimate $13.38427320 plus $1.31327 uncertain reserve remains $14.69754320 / $15; no cost ledger was edited.

Coordinator next action: verify this exact candidate against original findings, record accepted correction/prerequisite SHA and integration baseline, then dispatch the single V02 writer with local runtime ownership and explicit recorded-evidence/fresh-inference boundary. Stop editing this candidate during review; two unsuccessful submitted correction rounds require reassessment.
