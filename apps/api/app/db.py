from contextlib import contextmanager
from pathlib import Path
import uuid
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .config import ROOT, settings


def uid():
    return uuid.uuid4().hex


@contextmanager
def connection():
    with psycopg.connect(settings().database_url, row_factory=dict_row, connect_timeout=5) as conn:
        yield conn


def migrate():
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(733029)')
        conn.execute((ROOT/'migrations/001_initial.sql').read_text())


if __name__ == '__main__':
    migrate()
    print('Migration 001 applied')
