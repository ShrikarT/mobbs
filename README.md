# Viralist

Local V02 development (Windows, Python 3.10.2 / Node 26.7.0):

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
npm ci
npm run build
.venv/Scripts/python -m apps.api.app.db
.venv/Scripts/python -m scripts.check_services
.venv/Scripts/python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 58000 --no-access-log
```

Private configuration defaults to `~/.codex/private-runs/viralist-v02-local/runtime.json`
(override with `VIRALIST_RUNTIME`). Required keys: `database_url`, `s3_endpoint`,
`s3_access_key`, `s3_secret_key`, `s3_bucket`, `provider_evidence_root`.
Never commit this file. Existing coordinator-owned PostgreSQL17 and RustFS services
are required; `scripts.check_services` creates the configured private app bucket
if absent and checks a disposable object. Open `http://127.0.0.1:58000`.
This is a local restricted application, with paid inference disabled.

Test a short product demo with a simulated audience, inspect timestamped editing notes, and compare your next cut.

**Status: planning and feasibility experiments complete, updated 28 October 2026.** Real Meta API experiments and offline scheduler/validation tests exist; the application and deployment remain unbuilt. Owner-selected repository: [ShrikarT/viralist](https://github.com/ShrikarT/viralist). The owner is moving to app development; remaining proposals and evidence limits are recorded in the handoff.

Start with [the planning handoff](docs/START_HERE.md), [the product brief](docs/PROJECT_BRIEF.md), and [the delivery plan](PLAN.md). Current evidence and next actions are in [STATE](docs/STATE.md). Operating rules are in [AGENTS](AGENTS.md).

The hackathon slice is Flash Scan → Director's Notes → edited-cut comparison → Thumbnail Lab, for Instagram Reels. Outputs describe a simulation; they do not predict real-world reach or reproduce Instagram's algorithm. The full product roadmap remains sequenced after this slice.

Experiment evidence: [initial provider spike](docs/evidence/provider-spike.md), [Spark 1.3 fixes and rerun](docs/evidence/spark13-rerun.md), and [fifty strengthened persona results](docs/evidence/fifty-persona-results.md). These are author-reported experimental results, not a deployed product or validated audience forecast. Further persona differentiation is lower priority than the first working upload-to-report flow. Dependencies observed in the experiment environment are recorded in `experiments/requirements.txt`; FFmpeg/ffprobe must also be available.

Free local regression checks, from this repository root:

```powershell
python -m unittest discover -s experiments -p 'test_*.py' -v
```

The current paid runner is `experiments/meta_pipeline.py`; it requires explicit stage, private output paths and a cumulative prior-spend ledger. Its scale stage requires a passing inspected small-stage gate at the same revision. Credentials use private stdin or `MODEL_API_KEY`; media, raw responses and keys stay outside Git. Do not run a paid stage simply to inspect evidence. No application development commands exist yet; do not run a parent directory's package scripts.
