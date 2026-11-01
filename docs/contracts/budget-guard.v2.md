# Budget guard redesign contract — v2 (proposed)

Status: proposed for independent design review. This contract is a redesign after two unsuccessful submissions under the original B2G task. It does not accept candidate `48c0a8398086e94320f34fbe575834957d022cab`, authorize another routine patch, create a paid account, connect the guard to transport, or authorize provider calls. Preserve `budget-guard.v1.md` and all prior correction/review history.

## Why a redesign is required

The exact-commit review at `48c0a83` found that the two targeted source changes do not close the financial safety boundary. Public helpers still permit noncanonical price/margin overrides; billing fields are scalar but not typed tightly enough to reject content; unbounded usage can fail before the durable uncertainty branch; retries do not enforce the rejection category; immutable settlement/reconciliation evidence is incomplete; reconciliation can write free text after sanitation. The reviewer could not reach PostgreSQL, so durability, concurrency and persisted JSON remain blocked rather than disproved. See [correction 2 review](../evidence/v03-budget-correction-2-review.md).

## Design decision

Implement a small typed state machine over the existing additive PostgreSQL ledger, with one canonical validator/serializer for all financial writers and explicit transaction results. Keep external provider I/O outside database transactions. Preserve the production architecture and accepted SQL004 DDL unless a separate evidence-backed migration is independently reviewed.

The public guard is a façade over private storage transitions. No caller may pass an open DB connection, price, margin, quote, free-form error, arbitrary evidence map or unrestricted JSON. Each public mutation owns its transaction and returns a grant/result only after commit. A durable expected denial is represented inside the transaction as an outcome; the façade raises its typed exception only after that transaction commits. An ambiguous commit yields an explicit unknown outcome and must never authorize sending or an automatic resend.

## Identity and paid policy

- Validate an immutable `BudgetIdentity` before any financial mutation. It binds exact database name, account ID, ledger instance, environment, canonical source-ledger digest, cap and opening settled/uncertain amounts.
- A test identity is explicitly marked `test` and may use fixture amounts, but can never authorize transport. Test initialization is a test-only helper and cannot create a `paid` row.
- A paid identity fails closed unless its exact digest and amounts match the owner-authorized ledger. Current recorded values are cap USD 30.00, opening settled USD 13.38427320, opening uncertain reserve USD 1.31327, tracked exposure USD 14.69754320, and source digest `8b7929c67cda1d8cf81efea387eef98afaf384989c14fab6ed14ba1aefd293bc`. Recompute and independently verify the ledger before any later paid stage; this document is not a billing balance.
- Verify current database, required schema version 4 and every persisted identity field under the account lock. Equality between two misconfigured values is insufficient for paid authority.

## Canonical input and quote

- Parse the exact canonical request bytes as strict JSON: object only, no duplicate keys, no NaN/Infinity, no trailing data. Its actual `model` and strict integer `max_output_tokens` must equal the pinned profile and `RequestBound`.
- `RequestBound` is immutable and contains request hash, counted-request hash, model, pricing version, strict input/output counts, context limit, count method and verified flag. Hash both the exact bytes and the count basis; bind both to the persisted attempt. Do not persist request bytes or caller dictionaries.
- Only the pinned Spark 1.3 profile and finite pinned price schedule are accepted. Remove public price/margin parameters from every quote/cost helper; helper and guard must share the same validator and constants. Derive the reservation inside the guard with the fixed 10% input margin and upward rounding. Expected fixture: 100,000 input + 20,000 output costs USD 0.2100000000 and reserves USD 0.2225000000.
- All counts are strict integers (booleans rejected), nonnegative, and bounded by the selected model context before any Decimal arithmetic or database write. Input + max output cannot exceed 1,048,576. Actual usage must have input/output within supported maxima, cached <= input, reasoning <= output, and any supplied total exactly equal to input + output. Reject non-finite decimals and overflow. Usage above the reserved bound becomes durable uncertainty with at least the maximum representable known charge; never downgrade known exposure.

## Immutable attempt and replay identity

Persist a canonical, bounded fingerprint covering account/ledger identity, complete video/run/analysis-job/generation/lease tuple, stage, unit, attempt ordinal, exact request and count hashes, model/pricing/context/count basis and server-derived quote. Compare the complete fingerprint for reserve/retry replay. A matching request hash alone is not replay identity.

Settlement has a separate canonical fingerprint over the received receipt hash, normalized usage counts, model/version, status, finite calculated charge and validated billing identifiers. Exact replay of every immutable field is idempotent; any changed usage/evidence conflicts even if the calculated cost happens to be equal. A received receipt hash is immutable. Cancellation/rejection replays use the same exact-input rule.

## Financial evidence schema

Every writer routes through one `encode_financial_evidence` validator immediately before JSONB persistence. It emits a fresh dictionary containing only these field classes:

- Opaque provider/request/response identifiers: ASCII identifier grammar `[A-Za-z0-9_-]{1,128}`; no whitespace, control characters or prose.
- Model and version identifiers: exact pinned model or bounded identifier from the allowlist.
- Status, pause, cancellation, rejection and reconciliation values: enumerated constants only.
- Token counts and HTTP status: strict finite integers within declared ranges; booleans rejected.
- USD values: finite, nonnegative, canonical decimal strings with at most 10 fractional places.
- Hashes: lowercase 64-character SHA-256 hex.

No note, error message, exception text, transcript, prompt, response body, arbitrary nested object, caller-provided reason or unknown key can be persisted. `reconciliation_reason` and `cancelled_reason` become typed enums (not prose). Validate the complete object and all values before writing; stripping a bad field is not sufficient for a transition that depends on it. The encoder is used by reserve, receive, settle, uncertainty, rejection, cancellation, reconciliation and recovery. Raw provider/error text stays out of financial rows and ordinary logs.

## State transitions and transaction rules

Allowed transitions are explicit and checked in one private transition function:

- `reserved -> dispatched`: commit one dispatch marker before any external request; never grant a second send after dispatched/received/settled/uncertain or an unknown commit.
- `reserved -> cancelled`: only when no dispatch marker exists; reason is an enum.
- `dispatched -> received -> settled`: receipt hash and normalized billing metadata are committed before advancing; exact replay only.
- `reserved/dispatched/received -> uncertain`: commit pause and monotonic exposure before returning/raising. An invalid or excessive usage result follows this path.
- `dispatched -> rejected`: only with typed evidence of a known uncharged status/category. Timeout, transport loss, 5xx, unknown outcome and ambiguous send are uncertain, never refundable.
- `uncertain -> settled`: only through reconciliation against the same durable receipt and immutable request identity with shared canonical usage validation. No empty clear-pause method, guessed zero, or manual text shortcut.

All account-affecting operations serialize on the account row. When a transition discovers stale dispatched/received debt, it commits the pause before returning a denial. Dispatch must use the pause state after the stale-debt update. Reserve must not raise from inside a transaction after changing pause state. A valid, unexpired, generation-matched analysis lease is not stale. Expired, missing, deleted, mismatched-generation or otherwise invalid jobs retain debt and pause admission; expiration never proves no charge.

Preserve the existing lock order: video → current job → account/stage → attempt where domain state is involved; financial-only operations use account → attempt. Recovery inspection must not lock another job after locking an account. Never hold a lock over network I/O. A send permit is issued only after durable commit. If commit status is unknown, caller performs no provider call and no automatic retry.

## Retry and reconciliation

- Attempt 1 is reservable only after attempt 0 is a recorded `rate_limit_429` rejection with matching request hash, model, stage and full immutable basis, a strict integer Retry-After in 1–3600 seconds, and the persisted delay has elapsed. The reserve path enforces this rule; `retry_allowed` metadata alone is not authorization. Attempt 2 is always denied.
- Other known uncharged categories (validated 400/403/account denial) do not retry. Ambiguous failures become uncertain. A typed cancellation for a definitely unsent reserved attempt is a separate safe transition.
- Reconciliation requires a nonempty typed set of specific unresolved attempts, exact request and durable receipt hashes, canonical validated usage and bounded allowlisted receipt metadata. It is idempotent only for exact identical inputs. It cannot erase a larger known charge, rewrite a receipt, or clear pause while any uncertain or stale dispatched/received debt remains.
- A manual billing-side resolution with no durable provider receipt requires a separate owner-authorized contract and is out of scope.

## Real fixture and acceptance gate

Do not dispatch redesigned implementation until the fixture below runs against the actual existing PostgreSQL implementation. When the database runtime is authorized and reachable, use only the assigned V03 budget test database, exact committed schema and existing test helpers. Create uniquely namespaced test identity/account/stage/video/run/job rows; capture the IDs created; never truncate tables, drop/recreate a database, or delete pre-existing data. Cleanup may remove only fixture-owned rows after all assertions and only when no unsettled debt remains. Keep crash/recovery debt rows as evidence until separately settled or owner-directed cleanup.

The acceptance fixture must run the actual guard/store and actual PostgreSQL transaction path, then inspect persisted rows through a fresh independent connection. It must cover:

1. Canonical default price/quote; noncanonical price, margin, model, request JSON and bounds rejected before reservation.
2. Paid identity mismatch denied before any row mutation; isolated test identity works without a paid account.
3. Forged video/run/job/kind/generation/lease tuple rejected; valid current analysis lease accepted.
4. Same request with changed lease generation, bounds, stage, model, quote basis, receipt hash, usage or billing IDs is Conflict; exact replay is idempotent.
5. Invalid, missing, excessive, non-finite and arithmetic-overflow usage durably changes state to uncertain, stores bounded evidence, preserves maximum debt, and pauses after caller catches the typed error outside the API.
6. Stale dispatched and received debt discovered first by reserve and by sibling dispatch commits pause; sibling stays reserved and is not granted. A valid current unexpired lease remains usable; test missing, expired, deleted and generation-mismatched debt separately.
7. Repeated uncertainty cannot reduce partial charge or erase receipt. Above-cap exposure remains visible and pauses.
8. Reconciliation rejects mismatched totals, raw reasons, absent receipts and changed replays; it settles only exact durable evidence and does not clear pause while another stale/uncertain attempt remains.
9. Immediate retry after 400/403/account denial and attempt 2 are rejected; known 429 is denied before its bounded delay and allowed only after elapsed time.
10. Every persisted JSON field across all mutation writers conforms to the typed encoder. Use a synthetic private marker; query all rows through a fresh connection after receipt, uncertainty, cancellation, rejection, reconciliation and deletion. The marker must be absent.
11. Two independent processes reserve against one shared cap on distinct job/video tuples; the sum never exceeds cap. Kill a child immediately after committed dispatch and before the external-call marker, then verify no resend; kill after received commit and verify recovery without resend. The only external boundary is a local fsynced marker double; do not call the provider.

Required checks from the assigned API environment:

- `python -m unittest tests.test_v03_budget -v` against the existing PostgreSQL instance; record exact revision, port/database identity, result count and full exit code.
- A bounded fixture driver for criteria 2–11; report each independent connection query/result and every subprocess exit. Compilation/source inspection cannot satisfy transaction, locking, crash or persistence criteria.
- `git diff --check` and clean exact commit.

A database connection timeout blocks the fixture and means the implementation task is not READY; it does not count as a code correction failure. Do not restart Docker/services without owner authorization. No migration, provider call, paid usage, network smoke, deployment, push, public communication or V04/V05 work is in this contract.

## Task lifecycle

Keep the original parent task and both unsuccessful correction submissions visible. The next Orca item must be explicitly titled as a **redesign**, depend on this exact review evidence, and carry a finite scope. The first worker contract should own only the approved redesign implementation paths in one isolated worktree. No second implementation worker until shared interfaces and fixture acceptance are frozen. Independent review uses a different worker/session on the exact committed SHA. A further unsuccessful review triggers another stop/reassessment; never reset correction history by task rename.
