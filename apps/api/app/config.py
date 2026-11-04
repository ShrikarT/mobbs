"""Server-only local configuration. Never load provider credentials in recorded mode."""
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def _build_commit():
    for key in ('APP_COMMIT','RENDER_GIT_COMMIT','VERCEL_GIT_COMMIT_SHA'):
        if os.environ.get(key): return os.environ[key]
    try: return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError): return 'unknown'

BUILD_COMMIT = _build_commit()

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
    provider_mode: str = 'recorded'
    model_api_key: str = ''


def get_effective_runtime_path() -> str:
    mobbs_env = (os.environ.get('MOBBS_RUNTIME') or '').strip()
    if mobbs_env:
        return mobbs_env
    viralist_env = (os.environ.get('VIRALIST_RUNTIME') or '').strip()
    if viralist_env:
        return viralist_env
    new_default = Path.home() / '.codex/private-runs/mobbs-v02-local/runtime.json'
    legacy_default = Path.home() / '.codex/private-runs/viralist-v02-local/runtime.json'
    if new_default.is_file():
        return str(new_default)
    if legacy_default.is_file():
        return str(legacy_default)
    return str(new_default)


def settings():
    runtime_path = get_effective_runtime_path()
    path = Path(runtime_path)
    raw = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    fields = ('database_url', 's3_endpoint', 's3_access_key', 's3_secret_key', 's3_bucket', 'provider_evidence_root')
    kwargs = {k: os.environ.get(k.upper()) or raw.get(k,'') for k in fields}
    if not kwargs['s3_endpoint'] and os.environ.get('S3_HOST'):
        kwargs['s3_endpoint']='http://'+os.environ['S3_HOST']+':9000'
    missing=[k.upper() for k in fields[:-1] if not kwargs[k]]
    if missing: raise ValueError('Missing server settings: '+', '.join(missing))
    if 'origin' in raw:
        kwargs['origin'] = raw['origin']
    origin=os.environ.get('APP_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL')
    if not origin and os.environ.get('VERCEL_URL'):
        origin='https://'+os.environ['VERCEL_URL']
    if origin: kwargs['origin']=origin.rstrip('/')

    # Server config selects recorded or standard mode; default recorded
    mode = (os.environ.get('MOBBS_PROVIDER_MODE') or '').strip()
    if not mode:
        mode = (os.environ.get('VIRALIST_PROVIDER_MODE') or '').strip()
    if not mode:
        mode = raw.get('provider_mode') or ('recorded' if path.is_file() else 'standard')
    if mode not in ('recorded', 'standard'):
        mode = 'recorded'
    kwargs['provider_mode'] = mode

    # In recorded mode, NEVER read provider credentials.
    # In standard mode, server reads MODEL_API_KEY from env or runtime if provided.
    if mode == 'standard':
        kwargs['model_api_key'] = os.environ.get('MODEL_API_KEY') or raw.get('model_api_key') or ''
    else:
        kwargs['model_api_key'] = ''

    return Settings(**kwargs)
