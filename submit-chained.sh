set -euo pipefail

RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
NUM_WORKERS=$1
NUM_SIMULATIONS=$2
NUM_ITERATIONS=$3

echo $NUM_WORKERS
echo $NUM_SIMULATIONS
echo $NUM_ITERATIONS

ARRAY_JOB_ID=$(aws --profile personal batch submit-job \
    --job-name mc-pricer-job \
    --job-queue mc-pricer-job-queue \
    --job-definition mc-pricer-job-definition \
    --array-properties size=$NUM_WORKERS \
    --container-overrides "{\"environment\": [
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"},
        {\"name\":\"num_workers\", \"value\":\"$NUM_WORKERS\"},
        {\"name\":\"num_simulations\", \"value\": \"$NUM_SIMULATIONS\"},
        {\"name\":\"iterations\", \"value\": \"$NUM_ITERATIONS\"}
    ]}" \
    --query jobId \
    --output text
)

echo Worker jobs starting... jobId=$ARRAY_JOB_ID

AGG_JOB_ID=$(aws --profile personal batch submit-job \
    --job-name mc-pricer-aggregate-job \
    --job-queue mc-pricer-job-queue \
    --job-definition mc-pricer-aggregator-job-definition \
    --container-overrides "{\"environment\": [
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"},
        {\"name\":\"num_workers\", \"value\":\"$NUM_WORKERS\"}
    ]}" \
    --depends-on "jobId=$ARRAY_JOB_ID" \
    --query jobId \
    --output text
)

echo Aggregator job starting... jobId=$AGG_JOB_ID