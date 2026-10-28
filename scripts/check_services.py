"""Real PostgreSQL and app-owned S3 roundtrip. Prints no credentials."""
from apps.api.app.db import connection, uid
from apps.api.app.storage import Storage

with connection() as conn:
    assert conn.execute('SELECT version FROM schema_migrations').fetchone()['version'] == 1
store = Storage()
try:
    store.check()
except store.client.exceptions.ClientError as exc:
    if exc.response['Error']['Code'] not in ('404', 'NoSuchBucket'):
        raise
    store.client.create_bucket(Bucket=store.bucket)
key = 'v02-health/'+uid()
try:
    store.put(key, b'viralist-roundtrip')
    obj = store.get(key)
    try:
        assert obj['Body'].read() == b'viralist-roundtrip'
    finally:
        obj['Body'].close()
finally:
    store.delete(key)
print('PASS: real PostgreSQL migration and private S3 put/get/delete')
