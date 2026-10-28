# Start here

This is a planning-only repository for Viralist. Read [PROJECT_BRIEF](PROJECT_BRIEF.md) for the recommended scope and unresolved owner choices, [PRODUCT](PRODUCT.md) for the product decision, and [STATE](STATE.md) for actual evidence. The supplied original documents remain unchanged outside Git; source hashes and verified corrections are in [RESEARCH](RESEARCH.md).

## The sequence

1. **Discovery/strategy (this pass):** audit the baseline, research claims, define product/design/contracts and acceptance. No product code.
2. **Owner choices:** approve/amend the brief's material proposals; authorize implementation and live-test budget separately. Review the concrete plan, not a generic permission prompt.
3. **Orca implementation coordination:** follow [PLAN](../PLAN.md), beginning V00/V01; load the installed version-matched orchestration guide. A worker receives root AGENTS, task, immutable baseline, interfaces and checks. Orca 1.4.243 was verified running on 2026-10-28. The first independent [readiness review](evidence/v00-readiness-review.md) returned REVISE; resolve PLAN's numbered correction batch before V02 dispatch.
4. **Independent verification:** a different verifier inspects and tests a frozen commit. Keep WORKER-REPORTED if verification cannot run. Two failed correction rounds trigger redesign.
5. **Integration:** one integrator combines accepted commits and checks the new revision. Owner retains merge authority.
6. **Real journey:** independently exercise the production path on the exact integration artifact. Mocked dependencies and recorded replay are identified separately.
7. **Authorized release:** prepare the actual app/demo/submission first, then obtain any outstanding target/spend/publication authorization. [LAUNCH_STORY](LAUNCH_STORY.md) is a shot plan, not produced footage.

## Read only what the task needs

| Working on | Read |
|---|---|
| Any task or recovery | [AGENTS](../AGENTS.md), [STATE](STATE.md), relevant [PLAN task](../PLAN.md) |
| Product tradeoffs/approval | [PROJECT_BRIEF](PROJECT_BRIEF.md), [PRODUCT](PRODUCT.md), [RESEARCH](RESEARCH.md) |
| Architecture or boundaries | [ARCHITECTURE](ARCHITECTURE.md), [CONTRACTS](CONTRACTS.md), [synthetic fixture](contracts/vertical-slice.v1.json), [ADRs](adr/0001-simulation-evidence-boundary.md) |
| UI | [DESIGN_DIRECTION](DESIGN_DIRECTION.md), [ACCEPTANCE](ACCEPTANCE.md) |
| Verification/release | [ACCEPTANCE](ACCEPTANCE.md), [LAUNCH_STORY](LAUNCH_STORY.md) |
| Terminology | [GLOSSARY](../GLOSSARY.md) |

There is no runnable product app, application manifest, CI or deployment. Experiments and a separate HyperFrames experiment manifest do exist; README records the offline Python test command. Do not report those checks as production integration. The next meaningful step is the bounded V00-R1 contract/readiness correction, followed by independent review and the authorized V02 slice. Do not repeat paid experiments to inspect existing evidence.
