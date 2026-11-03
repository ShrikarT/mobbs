# MOBBS-RENAME Evidence Record

## 1. Executive Summary

On 2026-11-03, the owner requested renaming the application brand from **Viralist** to **Mobbs** across the repository, documentation, and website. On the same date, the owner explicitly authorized updating the canonical GitHub repository identity and remote origin to `https://github.com/ShrikarT/mobbs.git` (`ShrikarT/mobbs`).

This implementation completes the brand rename across all production frontend, backend, package, and current documentation surfaces while preserving backwards compatibility, security invariants, session cookies, and truthful provenance of physical resources and historical records.

### Summary of Changes
- **Display Brand**: `Mobbs`
- **Slug**: `mobbs`
- **Uppercase Env**: `MOBBS`
- **Web Title & Header**:
  - `apps/web/index.html`: `<title>Mobbs · Evidence desk</title>`
  - `apps/web/src/App.tsx`: `<span className="brand-title">Mobbs / Evidence desk</span>`
- **Package Slug**:
  - `package.json`: `"name": "mobbs-local"`
  - `package-lock.json`: `"name": "mobbs-local"`
- **Backend API & Worker**:
  - `apps/api/app/main.py`: `FastAPI(title='Mobbs local evidence desk')`
  - Ingestion temporary prefix: `mobbs-ingest-`
  - Worker temporary prefix: `mobbs-worker-`
  - Standard provider User-Agent: `Mobbs-StandardProvider/1.0`
- **Configuration Contract**:
  - Primary configuration environment variables: `MOBBS_RUNTIME` and `MOBBS_PROVIDER_MODE`
  - Legacy configuration fallback: `VIRALIST_RUNTIME` and `VIRALIST_PROVIDER_MODE`
  - Explicit precedence: `MOBBS_*` takes priority over `VIRALIST_*`, with whitespace trimmed
  - Default private runtime path: `~/.codex/private-runs/mobbs-v02-local/runtime.json` with fallback to `~/.codex/private-runs/viralist-v02-local/runtime.json`
  - Worker operational pause marker: resolves to identical effective runtime directory (`Path(effective_runtime).parent / 'operational_pause.marker'`)
  - Recorded mode credential isolation: strictly no provider credentials read in recorded mode
- **Browser Cookies**:
  - `vir_session` and `vir_csrf` in `apps/api/app/main.py` preserved strictly unchanged (no cookie key rename, preserving active owner sessions and report accessibility without migration risk).
- **Repository Remote**:
  - Canonical origin updated to `https://github.com/ShrikarT/mobbs.git` (`ShrikarT/mobbs`).

---

## 2. Task & Dispatch Context

- **Logical Task**: `MOBBS-RENAME`
- **Orca Task ID**: `task_607bf4406c34`
- **Orca Dispatch ID**: `ctx_11ade2923bb7`
- **Orca Run ID**: `run_d3354faa0659`
- **Agent**: Antigravity (ordinary implementation)
- **Worktree**: `C:/Users/Shrikar/orca/workspaces/viralist/codex-mobbs-rename`
- **Branch**: `codex/mobbs-rename`
- **Assigned Base HEAD**: `673e2631357f3869724e0edd2662351bee19cdab`
- **Startup Receipt**: Sent via blocking ask and approved by coordinator (`msg_211bd080dc1d`).
- **Milestone State**: **WORKER-REPORTED** (acceptance pending independent verification).

---

## 3. Verification Commands & Observed Results

### A. Configuration Precedence & Security Unit Tests
New dedicated suite `tests/test_mobbs_config.py` exercising:
1. `MOBBS_RUNTIME` precedence over `VIRALIST_RUNTIME`.
2. Whitespace trimming on runtime path env variables.
3. Fallback to `mobbs-v02-local/runtime.json` and legacy `viralist-v02-local/runtime.json`.
4. `MOBBS_PROVIDER_MODE` precedence over `VIRALIST_PROVIDER_MODE`.
5. Whitespace trimming on provider mode env variables.
6. Absolute credential protection in recorded mode (credentials never loaded).
7. Operational pause marker path parity with effective runtime path.

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe -m unittest tests.test_mobbs_config
```
**Result**: 6 tests passed in 0.113s, exit code 0.

### B. Focused Regression & Component Suite
```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
C:/Users/Shrikar/.codex/viralist-v02-review/venv/Scripts/python.exe -m unittest tests.test_mobbs_config tests.test_v03_standard_app.TestStandardProviderUnit tests.test_v03_incomplete_fix tests.test_normalized tests.test_v03_notes_strict_schema tests.test_v03_standard_app.TestNotesContextAndOmission
```
**Result**: 37 tests passed in 42.651s, exit code 0.

### C. Production Frontend Build
```powershell
npm run build
```
**Output**:
```
> mobbs-local@0.2.0 build
> tsc -p apps/web/tsconfig.json && vite build --config apps/web/vite.config.ts

vite v8.3.2 building client environment for production...
transforming...
✓ 17 modules transformed.
rendering chunks...
computing gzip size...
apps/web/dist/index.html                   0.40 kB │ gzip:  0.29 kB
apps/web/dist/assets/index-DlpWRBPX.css   20.12 kB │ gzip:  4.27 kB
apps/web/dist/assets/index-DtznVuKI.js   270.56 kB │ gzip: 81.48 kB
✓ built in 5.71s
```
**Result**: Clean compilation, exit code 0. Generated `apps/web/dist/index.html` confirmed containing `<title>Mobbs · Evidence desk</title>`.

---

## 4. Classified Old-Name Exception Inventory

In accordance with project policy and task criteria, old-name occurrences (`viralist`) are intentionally preserved where modifying them would break compatibility, falsify historical evidence, or corrupt physical filesystem paths. Every remaining occurrence in the repository is inventoried below under its justified category:

| Category | File Pattern / Locations | Justification |
|---|---|---|
| **A. Compatibility Fallbacks** | `apps/api/app/config.py`<br>`README.md`<br>`scripts/v03_ui_runner.py`<br>`scripts/v03_ui_setup.py`<br>`tests/test_v03_bounded_pool.py`<br>`tests/test_v03_standard_app.py`<br>`tests/test_v03_provisional_verdict.py`<br>`tests/v03_pool_worker.py`<br>`tests/v03_standard_r2_worker.py` | Required backwards compatibility. Existing launch scripts, developer environments, and automated test runners setting `VIRALIST_RUNTIME` or `VIRALIST_PROVIDER_MODE` must continue functioning without disruption. |
| **B. Physical Filesystem Paths** | `AGENTS.md` (coordinator checkout `C:/Users/Shrikar/viralist`)<br>`PLAN.md`<br>`docs/STATE.md`<br>`docs/RESEARCH.md`<br>`tests/e2e/journey.spec.ts`<br>`tests/reconcile_saved.py`<br>`scripts/v03_ui_capture_checkpoints.js`<br>`scripts/v03_ui_test_journey.js`<br>`scripts/v03_ui_runner.py`<br>`scripts/v03_ui_setup.py`<br>`tests/test_*.py` | Real absolute and worktree directories on disk (`C:/Users/Shrikar/viralist`, `C:/Users/Shrikar/orca/workspaces/viralist/...`, `C:/Users/Shrikar/.codex/private-runs/viralist-...`, `C:/Users/Shrikar/.codex/viralist-...`). Renaming these in code or docs would cause `FileNotFoundError` or point to nonexistent paths. |
| **C. Database, S3 & Container Identifiers** | `docs/STATE.md`<br>`docs/evidence/*`<br>`scripts/v03_ui_setup.py`<br>`scripts/v03_ui_runner.py` | Names of existing, retained PostgreSQL databases (`viralist_v02_postgres`, `viralist_v03_ui`, `viralist_v03_pool`, `viralist_v03_live_journey_20261102`), S3 storage buckets (`viralist-v02-objectstore`, `viralist-v03-ui`, `viralist-v03-pool`), and Docker container/volume labels. Data and database migrations were explicitly excluded from this task. |
| **D. Historical Evidence & Provenance** | `docs/evidence/*` (historical assignments, reviews, journey records)<br>`docs/LAUNCH_STORY.md`<br>`docs/RESEARCH.md` | Immutable historical evidence from settled milestones (V00, V02, V03), concept attribution to the original creator reel (`@shubhamgl2003`), and local input source hashes (`viralist-prd-spec-complete (2).md`). Modifying historical records would falsify audit trails. |
| **E. Browser Ownership Cookies** | `apps/api/app/main.py` (`vir_session`, `vir_csrf`) | Explicit contract requirement to preserve existing browser ownership cookies without key rename, ensuring existing sessions and reports remain accessible without migration. |

---

## 5. Scope & Settlement Boundaries

- **No paid API calls or live mutations**: All checks used synthetic/offline fixtures and doubles.
- **No data migration**: Existing Postgres databases and RustFS S3 buckets preserved unchanged.
- **No git history rewrites**: All changes are forward commits on branch `codex/mobbs-rename`.
- **Status**: **WORKER-REPORTED** submitted for independent review.
