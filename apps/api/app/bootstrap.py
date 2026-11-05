"""Initialize the app schema and private bucket; never sends model requests."""
import argparse
from botocore.exceptions import ClientError
from .db import migrate
from .storage import Storage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--create-bucket', action='store_true', help='Create the configured bucket if absent (local storage only)')
    args = parser.parse_args()
    migrate()
    store = Storage()
    try:
        store.check()
    except ClientError as exc:
        if not args.create_bucket or exc.response['Error']['Code'] not in ('404', 'NoSuchBucket'):
            raise
        store.client.create_bucket(Bucket=store.bucket)
        store.check()
    print('Database and private storage ready')


if __name__ == '__main__':
    main()
