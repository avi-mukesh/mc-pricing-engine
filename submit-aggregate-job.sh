#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/stack-outputs.sh"

JOB_QUEUE=$(stack_output JobQueueName)
AGGREGATOR_JOB_DEF=$(stack_output AggregatorJobDefinitionArn)

RUN_ID="${1:?usage: submit-aggregate.sh RUN_ID}"

aws --profile personal batch submit-job \
    --job-name mc-pricer-aggregate-job \
    --job-queue "$JOB_QUEUE" \
    --job-definition "$AGGREGATOR_JOB_DEF" \
    --container-overrides "{\"environment\": [
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"}
    ]}"