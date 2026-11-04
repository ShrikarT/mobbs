# Queued scan recovery — 2026-11-04

Task MOBBS-WORKER-RECONNECT. Direct Codex implementation per the owner’s explicit no-Orca/no-agents instruction. Functional revision **6b978ddc32ab453f1954d55190d635052b279e20**, isolated `codex/mobbs-app-redesign` checkout. No UI, provider adapter, request retry, API, dependency or upload-limit changes.

## Diagnosis and recovery

The Standard worker had exited on an uncaught psycopg ConnectionTimeout in retention_cleanup. API uploads remained available, so the new scan was queued with no worker to claim it. Confirmed run0e990458980a415996326655eb4bf4f4 had a queued generation0 job, no lease and **zero provider calls** before starting the replacement worker. No completed decision or ambiguous request was replayed.

The production worker loop now catches database OperationalError/InterfaceError, logs only the exception class, and reconnects with1,2,4,8,16,30s capped delays, resetting after recovery. `--once` still fails visibly; unexpected programming errors still propagate. Durable leases, generation fences and existing unresolved-dispatched-call checks remain authoritative. This reconnects database access; it does not authorize a provider-request retry or promise recovery of every mid-request failure.

Replacement Standard worker started at exact6b978dd, parent PID15740. Observed current run advance from queued to simulating, accumulate198 accepted live calls, then persist a complete report: effective50/requested50, failed0, pending0, stopped14, one supported note. Report estimate **0.47175825USD**, not an invoice. Completed2026-11-04T12:41:09.591930Z. Created-to-complete includes the stalled queue period and is not a scan-speed benchmark. Upload/report preserved. An older failed run with one unresolved dispatched request was left unchanged; no blind replay was attempted.

## Author verification at6b978dd

- Before the fix, the production-loop regression command failed2/4 cases on injected cleanup/claim database failures. After the fix all4 pass, covering capped/reset backoff, subsequent queued-work processing, once-mode failure and propagation of unrelated code errors.
- **24 tests passed:** `python -m unittest tests.test_worker_reconnect tests.test_normalized tests.test_mobbs_config -v`, private isolated unit runtime. Connection-error tests control only their database/loop boundaries; they do not establish a live provider result.
- Actual reconnect exercised with a separate QA worker, same production module/revision and no monkeypatch. Only its private runtime pointed initially at unavailable DB port58033. Real psycopg ConnectionTimeouts logged; parent18100 stayed alive. Restored that private runtime to the existing recorded QA database without restarting the worker. The same worker then processed a real browser-upload journey through report, evidence seek, refresh, explicit old-report reopen and complete deletion: **1 passed,50.9s**. Recorded inference is the provider boundary; scheduler, persistence, renderer, deletion and database connection behavior are production components. QA runs/jobs/objects all0 afterward.
- Main database observed17 total connections against max100; C:1.16GB free at the check. No persistent connection saturation or current disk exhaustion observed. The triggering intermittent timeout’s underlying host cause is not established; the worker no longer exits on this connection-error path.
- Both owned workers remain alive. Main API startup6837a58 is unchanged, frontend9dc2e26 unchanged, current local website http://127.0.0.1:58020/. Private recovery summary `reconnect-scan-result.json`; private outage setup/logs under `worker-reconnect-check/`. No customer cookies/media/raw responses were exported.

WORKER-REPORTED / author-verified. Independent REVIEW-ACCEPTED, formal INTEGRATED/JOURNEY-VERIFIED pending because the owner excluded other agents. RELEASED not performed. No merge, push, deployment or submission.
