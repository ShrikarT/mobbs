import boto3
from botocore.config import Config
from .config import settings


class Storage:
    def __init__(self):
        cfg = settings()
        self.bucket = cfg.s3_bucket
        self.client = boto3.client('s3', endpoint_url=cfg.s3_endpoint,
            aws_access_key_id=cfg.s3_access_key, aws_secret_access_key=cfg.s3_secret_key,
            config=Config(signature_version='s3v4', retries={'max_attempts': 1},
                          connect_timeout=5, read_timeout=20, s3={'addressing_style': 'path'}))

    def put(self, key, data, content_type='application/octet-stream'):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key, **kwargs):
        return self.client.get_object(Bucket=self.bucket, Key=key, **kwargs)

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def check(self):
        self.client.head_bucket(Bucket=self.bucket)
