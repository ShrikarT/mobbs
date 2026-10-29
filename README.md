# Viralist

Local V02 development (Windows, Python 3.10.2 / Node 26.7.0):

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
npm ci
npm run build
.venv/Scripts/python -m apps.api.app.db
.venv/Scripts/python -m scripts.check_services
.venv/Scripts/python -m apps.api.app.worker
.venv/Scripts/python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 58000 --no-access-log
```

Private configuration defaults to `~/.codex/private-runs/viralist-v02-local/runtime.json`
(override with `VIRALIST_RUNTIME`). Required keys: `database_url`, `s3_endpoint`,
`s3_access_key`, `s3_secret_key`, `s3_bucket`, `provider_evidence_root`.
Never commit this file. Existing coordinator-owned PostgreSQL 17 and RustFS services
are required; `scripts.check_services` creates the configured private app bucket
if absent and checks a disposable object. Open `http://127.0.0.1:58000`.
This is a local restricted application, with paid inference disabled.

Test a short product demo with a simulated audience, inspect timestamped editing notes, and compare your next cut.

**Status: local V02 slice complete, updated 29 October 2026.** Real local upload, durable PostgreSQL worker, hash-bound recorded 3-person Meta adapter simulation, supported Director's Note with concrete fix and suppressed note disclosure, persistent reloadable workbench UI, and complete deletion lifecycle.

Start with [the planning handoff](docs/START_HERE.md), [the product brief](docs/PROJECT_BRIEF.md), and [the delivery plan](PLAN.md). Current evidence and next actions are in [STATE](docs/STATE.md). Operating rules are in [AGENTS](AGENTS.md).

The hackathon slice is Flash Scan → Director's Notes → edited-cut comparison → Thumbnail Lab, for Instagram Reels. Outputs describe a simulation; they do not predict real-world reach or reproduce Instagram's algorithm. The full product roadmap remains sequenced after this slice.

Verified local regression and end-to-end checks:

```powershell
# Python unit, domain integration, security isolation, and full journey tests (23 passing)
.venv/Scripts/python -m unittest tests.test_normalized tests.test_domain_integration tests.test_api_security_isolation tests.test_full_journey tests.reconcile_saved

# Playwright browser journeys (Desktop Chrome and 320px Mobile, 6 passing)
npx playwright test

# Historical experiment test suite
python -m unittest discover -s experiments -p 'test_*.py' -v
```

The current paid runner is `experiments/meta_pipeline.py`; it requires explicit stage, private output paths and a cumulative prior-spend ledger. Its scale stage requires a passing inspected small-stage gate at the same revision. Credentials use private stdin or `MODEL_API_KEY`; media, raw responses and keys stay outside Git. Do not run a paid stage simply to inspect evidence.
