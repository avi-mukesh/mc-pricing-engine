#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/stack-outputs.sh"

JOB_QUEUE=$(stack_output JobQueueName)
WORKER_JOB_DEF=$(stack_output WorkerJobDefinitionArn)
AGGREGATOR_JOB_DEF=$(stack_output AggregatorJobDefinitionArn)

# runs with fixed inputs, skipping the market data fetch - for reproducibility checks and
# experiments. Live runs go through the mc-pricer-run state machine instead
CONFIG=${1:-config/repro.json}
if [[ ! -f "$CONFIG" ]]; then
    echo "config not found: $CONFIG" >&2
    exit 1
fi
# base.json leaves S0 and sigma to the fetch, so it can't be submitted directly
if ! jq -e 'has("S0") and has("sigma")' "$CONFIG" > /dev/null; then
    echo "$CONFIG has no S0 or sigma - it relies on live market data, start it with the state machine" >&2
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
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"}
    ]}" \
    --depends-on "jobId=$ARRAY_JOB_ID" \
    --query jobId \
    --output text
)

echo Aggregator job starting... jobId=$AGG_JOB_ID