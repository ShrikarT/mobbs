from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .config import ROOT
from .db import connection
from .storage import Storage

app = FastAPI(title='Viralist local evidence desk', docs_url=None, redoc_url=None)


@app.get('/health')
def health():
    with connection() as conn:
        assert conn.execute('SELECT version FROM schema_migrations').fetchone()['version'] == 1
    Storage().check()
    return {'status': 'ok', 'database': 'postgresql', 'storage': 'private_s3', 'inference': 'recorded_only'}


dist = ROOT/'apps/web/dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='web')
