# ADR 0003: Redesign the provider budget guard

- Status: Design accepted by independent review; implementation readiness is blocked on a real PostgreSQL fixture
- Date: 2026-11-01
- Related: V03 budget guard, SQL004 at c58fd52, candidate 48c0a83, review evidence docs/evidence/v03-budget-correction-2-review.md

## Context

Two Antigravity correction submissions under the original V03 budget-guard task failed independent review. The latest exact-commit review found source-visible price/margin override, permissive per-field financial metadata, unbounded arithmetic before durable error handling, incomplete replay identity, and insufficient retry/reconciliation controls. PostgreSQL was unreachable during this review, so the claimed 30-test author suite and all runtime persistence/concurrency findings remain unverified. The full review report separates source findings from blocked runtime criteria.

## Decision

Stop routine patching of the current implementation. Preserve both submitted commits, review batches, correction count and the accepted-but-scoped SQL004 DDL. Use a new versioned guard contract based on a typed single transition path, exact immutable fingerprints, strict field-level financial serialization, bounded arithmetic, explicit retry eligibility and commit-before-error outcomes. Keep provider I/O outside transactions and do not add schema unless the redesigned fixture proves a specific additive field is necessary.

The redesigned contract is [budget-guard.v2.md](../contracts/budget-guard.v2.md). Its design completeness is independently accepted; code, runtime behavior and implementation readiness are not.

Independent design review ACCEPTED contract completeness at `a7d0354424276fb2106c3fd9dadb068053619e5e`; see [review evidence](../evidence/v03-budget-v2-design-review.md). The review identified two implementation choices, now fixed in v2: the `reconciliation_reason` enum and canonical fingerprint fields/serialization. This does not accept code or make implementation READY.

## Consequences

- The existing candidate remains WORKER-REPORTED, not accepted, and must not be integrated into paid transport.
- No third routine correction dispatch is allowed. A future implementation task must be explicitly named as a redesign, linked to the original task/reviews, and must keep the two unsuccessful submissions visible.
- A real PostgreSQL fixture is a READY gate for implementation, not a claim that source tests or an unavailable database prove durability. The current repository runtime evidence says there is no general Docker/service restart authority; obtain owner authorization before starting the existing database container.
- The $30 cumulative provider ceiling and current reserve remain unchanged. This ADR authorizes no paid account, provider call, credential access, push, deployment or release.
- The UI correction remains separately integrated; UI journey and the rest of V03 gates proceed independently when their own runtime is available.
