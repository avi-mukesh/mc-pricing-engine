import os
import boto3
import numpy as np
import io
import json

profile = os.environ.get("aws_profile")
session = boto3.Session(profile_name=profile) if profile else boto3.Session()
s3 = session.client("s3")

bucket = os.environ['s3_bucket']
run_id = os.environ['run_id']

# worker 0 writes the run's inputs, including how many workers there were
manifest_key = f"runs/{run_id}/inputs/manifest.json"
manifest = json.loads(s3.get_object(Bucket=bucket, Key=manifest_key)['Body'].read())
num_workers = manifest['workload']['num_workers']

# list_objects_v2 returns at most 1000 keys and this isn't paginated - with more
# workers than that the count assertion below fails rather than silently dropping arrays
key = f"runs/{run_id}/pnl/"
response = s3.list_objects_v2(Bucket=bucket, Prefix=key)
objects = response.get('Contents', [])

# sort by worker index (pnl_10 would otherwise come before pnl_2) so the combined
# array has the same order on every run
objects.sort(key=lambda obj: int(obj['Key'].rsplit('_', 1)[1].removesuffix('.npy')))

arrays = []
for obj in objects:
    stream = s3.get_object(Bucket=bucket, Key=obj['Key'])['Body']
    buffer = io.BytesIO(stream.read())
    data = np.load(buffer)
    arrays.append(data)

assert len(arrays) == num_workers, f"expected {num_workers} files, got {len(arrays)}"

pnl = np.concatenate(arrays)

var99 = np.percentile(pnl, 1)
es99 = pnl[pnl<=var99].mean()

print(f"scenarios: {len(pnl)}")
print(f"99% VaR: {-var99:.4f}")
print(f"99% ES:  {-es99:.4f}")

buffer = io.BytesIO()
np.save(buffer, pnl)
s3.put_object(Bucket=bucket, Key=f"runs/{run_id}/results/pnl.npy", Body=buffer.getvalue())

summary = {
    "run_id": run_id,
    "var_99": float(-var99),
    "es_99": float(-es99),
    "scenarios": len(pnl),
    "inputs": manifest
}

s3.put_object(Bucket=bucket, Key=f"runs/{run_id}/results/summary.json", Body=json.dumps(summary))
