"""Server-only local configuration. Never load provider credentials in recorded mode."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

winget_links = str(Path.home() / 'AppData/Local/Microsoft/WinGet/Links')
if os.path.isdir(winget_links) and winget_links not in os.environ.get('PATH', ''):
    os.environ['PATH'] = winget_links + os.pathsep + os.environ.get('PATH', '')


@dataclass(frozen=True)
class Settings:
    database_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    provider_evidence_root: str
    origin: str = 'http://127.0.0.1:58000'
    session_hours: int = 24
    lease_seconds: int = 120


def settings():
    path = Path(os.environ.get('VIRALIST_RUNTIME', str(Path.home()/'.codex/private-runs/viralist-v02-local/runtime.json')))
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    fields = ('database_url', 's3_endpoint', 's3_access_key', 's3_secret_key', 's3_bucket', 'provider_evidence_root')
    kwargs = {k: raw[k] for k in fields}
    if 'origin' in raw:
        kwargs['origin'] = raw['origin']
    return Settings(**kwargs)
