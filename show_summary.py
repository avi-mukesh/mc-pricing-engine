# prints a run's summary.json, e.g. python3 show_summary.py run-20261108-144418
import json
import sys
from pathlib import Path

import boto3

if len(sys.argv) != 2:
    sys.exit("usage: python3 show_summary.py RUN_ID")
run_id = sys.argv[1]

# same source as the shell scripts - written by cdk deploy (see outputsFile in mc_pricer/cdk.json)
outputs_file = Path(__file__).parent / "stack-outputs.json"
if not outputs_file.exists():
    sys.exit(f"{outputs_file} not found - run cdk deploy in mc_pricer/ first")
bucket = json.loads(outputs_file.read_text())["McPricerStack"]["BucketName"]

s3 = boto3.Session(profile_name="personal").client("s3")
try:
    body = s3.get_object(Bucket=bucket, Key=f"runs/{run_id}/results/summary.json")["Body"].read()
except s3.exceptions.NoSuchKey:
    sys.exit(f"no summary for {run_id} - check the run id, or the aggregator may not have finished")

print(json.dumps(json.loads(body), indent=2))
