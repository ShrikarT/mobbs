import json
import os
import sys
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parents[1]
P = Path(r"C:\Users\Shrikar\.codex\viralist-v03-ui")
P.mkdir(parents=True, exist_ok=True)

raw = json.loads(Path(r"C:\Users\Shrikar\.codex\private-runs\viralist-v02-local\runtime.json").read_text(encoding="utf-8-sig"))
cfg = {k: raw[k] for k in ("database_url", "s3_endpoint", "s3_access_key", "s3_secret_key")}
params = conninfo_to_dict(cfg["database_url"])
params["dbname"] = "viralist_v03_ui"

print("Checking PostgreSQL connection to base...")
with psycopg.connect(cfg["database_url"], autocommit=True, connect_timeout=10) as c:
    exists = c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (params["dbname"],)).fetchone()
    if not exists:
        print("Creating DATABASE viralist_v03_ui...")
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(params["dbname"])))
        print("Database viralist_v03_ui created.")
    else:
        print("Database viralist_v03_ui already exists.")

cfg.update(
    database_url=make_conninfo(**params),
    s3_bucket="viralist-v03-ui",
    provider_evidence_root=raw.get("provider_evidence_root", "C:/Users/Shrikar/.codex/private-runs/viralist-spark13-20261028/stage1-bounded"),
)

for name, port in [("runtime.json", 58000), ("runtime-live.json", 58003)]:
    (P / name).write_text(json.dumps(dict(cfg, origin=f"http://127.0.0.1:{port}"), indent=2), encoding="utf-8")
print("Runtime configs written.")

os.environ["VIRALIST_RUNTIME"] = str(P / "runtime.json")
sys.path.insert(0, str(ROOT))

from apps.api.app.db import migrate
migrate()
print("Migrations applied.")

from apps.api.app.storage import Storage
try:
    Storage().client.create_bucket(Bucket=Storage().bucket)
except Exception:
    pass
Storage().check()
print("S3 bucket ready.")
print("Setup complete.")
