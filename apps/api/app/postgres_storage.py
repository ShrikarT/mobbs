"""Private, chunked object storage for the small free-hosting deployment.

The existing object inventory still owns every byte and deletion cascades.
The normal deployment continues to use S3.
"""
import re
import io
import tempfile
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from .db import connection
from .storage import StorageCapacityError

CHUNK = 128 * 1024
DATABASE_CEILING = 700_000_000


class PostgresStorage:
    def check(self):
        with connection() as conn:
            conn.execute('SELECT 1 FROM media_objects LIMIT 1')

    def put(self, key, data, content_type='application/octet-stream'):
        owned=not hasattr(data,'read')
        source=io.BytesIO(data) if owned else data
        start=source.tell()
        source.seek(0,2);length=source.tell()-start;source.seek(start)
        # Serialize capacity admission, leaving room for reports and deletion.
        try:
            with connection() as conn:
                conn.execute('SELECT pg_advisory_xact_lock(733030)')
                used=conn.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n']
                if used + length * 1.1 > DATABASE_CEILING:
                    raise StorageCapacityError('private_storage_full')
                conn.execute('DELETE FROM media_objects WHERE key=%s',(key,))
                conn.execute('INSERT INTO media_objects(key,bytes,content_type) VALUES(%s,%s,%s)',(key,length,content_type))
                with conn.cursor() as cursor:
                    for batch in range(0,length,CHUNK*8):
                        rows=[]
                        for offset in range(batch,min(length,batch+CHUNK*8),CHUNK):
                            chunk=source.read(min(CHUNK,length-offset))
                            if len(chunk)!=min(CHUNK,length-offset):raise ValueError('incomplete_object_body')
                            rows.append((key,offset//CHUNK,chunk))
                        cursor.executemany('INSERT INTO media_chunks(key,part,data) VALUES(%s,%s,%s)',rows)
        finally:
            if owned:source.close()

    def get(self, key, **kwargs):
        body=tempfile.SpooledTemporaryFile(max_size=1024*1024,mode='w+b')
        try:
            with connection() as conn:
                row=conn.execute('SELECT bytes,content_type FROM media_objects WHERE key=%s',(key,)).fetchone()
                if not row:
                    raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
                size=row['bytes'];start=0;end=size-1
                requested=kwargs.get('Range')
                if requested:
                    match=re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
                    if not match: raise ValueError('unsupported_range')
                    start=int(match[1]);end=min(int(match[2]) if match[2] else size-1,size-1)
                    if start>end: raise ValueError('invalid_range')
                with conn.cursor(name='media_reader') as cursor:
                    cursor.itersize=8
                    cursor.execute('SELECT part,data FROM media_chunks WHERE key=%s AND part BETWEEN %s AND %s ORDER BY part',(key,start//CHUNK,max(0,end)//CHUNK))
                    for part in cursor:
                        offset=part['part']*CHUNK
                        body.write(part['data'][max(0,start-offset):min(CHUNK,end-offset+1)])
                if body.tell()!=max(0,end-start+1): raise ValueError('stored_media_incomplete')
            body.seek(0)
            length=max(0,end-start+1)
            result={'Body':StreamingBody(body,length),'ContentLength':length,'ContentType':row['content_type']}
            if requested:result['ContentRange']=f'bytes {start}-{end}/{size}'
            return result
        except BaseException:
            body.close()
            raise

    def delete(self, key):
        with connection() as conn:
            conn.execute('DELETE FROM media_objects WHERE key=%s',(key,))
