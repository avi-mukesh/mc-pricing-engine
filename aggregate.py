import os
import boto3

session = boto3.Session(profile_name="personal")
s3 = session.client("s3")

bucket = os.environ.get('s3_bucket', 'avi-mc-pricer-results')
run_id = os.environ.get('run_id', 'run-20261001-104129')

key = f"runs/{run_id}/"
response = s3.list_objects_v2(Bucket=bucket, Prefix=key)

print(response)