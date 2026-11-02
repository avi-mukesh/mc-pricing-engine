#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/stack-outputs.sh"

JOB_QUEUE=$(stack_output JobQueueName)
WORKER_JOB_DEF=$(stack_output WorkerJobDefinitionArn)
AGGREGATOR_JOB_DEF=$(stack_output AggregatorJobDefinitionArn)

CONFIG=${1:-config/base.json}
if [[ ! -f "$CONFIG" ]]; then
    echo "config not found: $CONFIG" >&2
    exit 1
fi

RUN_ID="run-$(date +%Y%m%d-%H%M%S)"

NUM_WORKERS=$(jq -r .num_workers "$CONFIG")
# turn every key in the config into a {name, value} env entry, plus run_id
ENV_JSON=$(jq -c --arg run_id "$RUN_ID" \
  '{environment: ([to_entries[] | {name: .key, value: (.value|tostring)}]
                  + [{name: "run_id", value: $run_id}])}' \
  "$CONFIG")

echo "run_id=$RUN_ID config=$CONFIG workers=$NUM_WORKERS"

ARRAY_JOB_ID=$(aws --profile personal batch submit-job \
    --job-name mc-pricer-job \
    --job-queue "$JOB_QUEUE" \
    --job-definition "$WORKER_JOB_DEF" \
    --array-properties size=$NUM_WORKERS \
    --container-overrides "$ENV_JSON" \
    --query jobId \
    --output text
)

echo Worker jobs starting... jobId=$ARRAY_JOB_ID

AGG_JOB_ID=$(aws --profile personal batch submit-job \
    --job-name mc-pricer-aggregate-job \
    --job-queue "$JOB_QUEUE" \
    --job-definition "$AGGREGATOR_JOB_DEF" \
    --container-overrides "{\"environment\": [
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"},
        {\"name\":\"num_workers\", \"value\":\"$NUM_WORKERS\"}
    ]}" \
    --depends-on "jobId=$ARRAY_JOB_ID" \
    --query jobId \
    --output text
)

echo Aggregator job starting... jobId=$AGG_JOB_ID