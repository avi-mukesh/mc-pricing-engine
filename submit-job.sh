#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/stack-outputs.sh"

JOB_QUEUE=$(stack_output JobQueueName)
WORKER_JOB_DEF=$(stack_output WorkerJobDefinitionArn)

RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
aws --profile personal batch submit-job \
    --job-name mc-pricer-job \
    --job-queue "$JOB_QUEUE" \
    --job-definition "$WORKER_JOB_DEF" \
    --array-properties size=10 \
    --container-overrides "{\"environment\": [
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"},
        {\"name\":\"num_workers\", \"value\":\"10\"},
        {\"name\":\"num_simulations\", \"value\": \"10000\"},
        {\"name\":\"iterations\", \"value\": \"100000\"}
    ]}"