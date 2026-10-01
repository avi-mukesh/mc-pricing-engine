RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
aws --profile personal-admin batch submit-job \
    --job-name mc-pricer-job \
    --job-queue mc-pricer-job-queue \
    --job-definition mc-pricer-job-definition \
    --array-properties size=10 \
    --container-overrides "{\"environment\": [
        {\"name\":\"run_id\", \"value\":\"$RUN_ID\"},
        {\"name\":\"num_workers\", \"value\":\"10\"}
    ]}"