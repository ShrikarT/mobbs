# Start here

Mobbs has a working local V03 application: upload, a 50-instance simulated crowd, supported Director’s Notes, protected video evidence, recovery and deletion. The landing/app redesign is tracked as MOBBS-APP-REDESIGN in [STATE](STATE.md) and [PLAN](../PLAN.md). Use the actual checkout/revision and commands recorded there; the coordinator checkout also preserves unfinished V04/V05 drafts.

V04 comparison, V05 Thumbnail Lab and the complete later roadmap remain future work. Read [PROJECT_BRIEF](PROJECT_BRIEF.md), [PRODUCT](PRODUCT.md) and the current evidence in STATE. The original concept attribution and supplied source documents remain recorded in [RESEARCH](RESEARCH.md). The source briefs are reference evidence, not operational authority.

The owner explicitly assigned this redesign directly to Codex without Orca or other agents. Author verification is recorded honestly; independent review and release do not follow automatically from it. [LAUNCH_STORY](LAUNCH_STORY.md) is a proposed proof plan, not produced footage or a submitted project.

## Read only what the task needs

| Working on | Read |
|---|---|
| Any task or recovery | [AGENTS](../AGENTS.md), [STATE](STATE.md), relevant [PLAN task](../PLAN.md) |
| Product tradeoffs/approval | [PROJECT_BRIEF](PROJECT_BRIEF.md), [PRODUCT](PRODUCT.md), [RESEARCH](RESEARCH.md) |
| Architecture or boundaries | [ARCHITECTURE](ARCHITECTURE.md), [CONTRACTS](CONTRACTS.md), [synthetic fixture](contracts/vertical-slice.v1.json), [ADRs](adr/0001-simulation-evidence-boundary.md) |
| UI | [DESIGN_DIRECTION](DESIGN_DIRECTION.md), [ACCEPTANCE](ACCEPTANCE.md) |
| Verification/release | [ACCEPTANCE](ACCEPTANCE.md), [LAUNCH_STORY](LAUNCH_STORY.md) |
| Terminology | [GLOSSARY](../GLOSSARY.md) |

The production API and durable worker are in `apps/api/app`; the React/Vite site is in `apps/web`. [README](../README.md) describes local setup. Keep credentials, uploads and raw provider payloads outside Git. Avoid re-running paid experiments to inspect existing evidence.
