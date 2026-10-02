#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${1:?usage: submit-aggregate.sh RUN_ID}"

aws --profile personal batch submit-job \
    --job-name mc-pricer-aggregate-job \
    --job-queue mc-pricer-job-queue \
    --job-definition mc-pricer-aggregator-job-definition \
    --container-overrides "{\"environment\": [
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"},
        {\"name\":\"num_workers\", \"value\":\"10\"}
    ]}"