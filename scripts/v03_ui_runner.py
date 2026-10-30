"""Focused UI workbench runner for V03-U1.
Runs FastAPI server on 127.0.0.1:58003 and resilient supervised worker process for viralist_v03_ui.
Patches Storage client read_timeout to 60s in runner process to accommodate Windows Docker loopback IO.
"""
import os
import sys
import time
import threading
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LIVE = Path(r"C:\Users\Shrikar\.codex\viralist-v03-ui\runtime-live.json")

os.environ["VIRALIST_RUNTIME"] = str(RUNTIME_LIVE)
os.environ["PYTHONPATH"] = str(ROOT)
sys.path.insert(0, str(ROOT))

# Patch Storage read_timeout to 60s for Windows loopback IO
import boto3
from botocore.config import Config
import apps.api.app.storage

def _patched_storage_init(self):
    cfg = apps.api.app.storage.settings()
    self.bucket = cfg.s3_bucket
    self.client = boto3.client(
        's3',
        endpoint_url=cfg.s3_endpoint,
        aws_access_key_id=cfg.s3_access_key,
        aws_secret_access_key=cfg.s3_secret_key,
        config=Config(
            signature_version='s3v4',
            retries={'max_attempts': 1},
            connect_timeout=10,
            read_timeout=60,
            s3={'addressing_style': 'path'},
        ),
    )

apps.api.app.storage.Storage.__init__ = _patched_storage_init

if len(sys.argv) > 1 and sys.argv[1] == "--worker-only":
    from apps.api.app.worker import process_once, retention_cleanup
    print("Resilient worker process started for viralist_v03_ui...", flush=True)
    while True:
        try:
            retention_cleanup()
            worked = process_once()
            time.sleep(0.05 if worked else 0.5)
        except Exception as exc:
            print(f"Worker notice: {type(exc).__name__}: {exc}; retrying in 1s...", flush=True)
            time.sleep(1)

import uvicorn
from apps.api.app.main import app

stop_event = threading.Event()

def supervisor_loop(env):
    while not stop_event.is_set():
        try:
            print("Starting separate worker subprocess for viralist_v03_ui...", flush=True)
            p = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--worker-only"],
                cwd=str(ROOT),
                env=env,
            )
            while not stop_event.is_set():
                ret = p.poll()
                if ret is not None:
                    print(f"Worker process exited with code {ret}, restarting...", flush=True)
                    break
                time.sleep(0.5)
            if stop_event.is_set():
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
        except Exception as e:
            print(f"Supervisor notice: {e}; retrying in 1s...", flush=True)
            time.sleep(1)

def main():
    if not RUNTIME_LIVE.exists():
        print("Error: runtime-live.json does not exist. Run scripts/v03_ui_setup.py first.", file=sys.stderr)
        sys.exit(1)

    env = os.environ.copy()
    env["VIRALIST_RUNTIME"] = str(RUNTIME_LIVE)
    env["PYTHONPATH"] = str(ROOT)

    supervisor_thread = threading.Thread(target=supervisor_loop, args=(env,), daemon=True)
    supervisor_thread.start()

    print("Starting FastAPI / Uvicorn on http://127.0.0.1:58003...", flush=True)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=58003,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    finally:
        stop_event.set()
        supervisor_thread.join(timeout=3)
        print("UI runner stopped.", flush=True)

if __name__ == "__main__":
    main()
