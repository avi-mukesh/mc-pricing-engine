import os
import boto3
import numpy as np
import io

profile = os.environ.get("aws_profile")
session = boto3.Session(profile_name=profile) if profile else boto3.Session()
s3 = session.client("s3")

bucket = os.environ.get('s3_bucket', 'avi-mc-pricer-results')
run_id = os.environ['run_id']

key = f"runs/{run_id}/"
response = s3.list_objects_v2(Bucket=bucket, Prefix=key)

arrays = []
for obj in response['Contents']:
    stream = s3.get_object(Bucket=bucket, Key=obj['Key'])['Body']
    buffer = io.BytesIO(stream.read())
    data = np.load(buffer)
    arrays.append(data)
    
# add assertion here to check that indeed we get num_worker number of arrays
    
pnl = np.concatenate(arrays)

var99 = np.percentile(pnl, 1)
es99 = pnl[pnl<=var99].mean()

print(f"scenarios: {len(pnl)}")
print(f"99% VaR: {-var99:.4f}")
print(f"99% ES:  {-es99:.4f}")

np.save('pnl.npy', pnl)