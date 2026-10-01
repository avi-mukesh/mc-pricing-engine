aws --profile personal-admin batch create-compute-environment \                             
    --compute-environment-name mc-pricer-compute-env \
    --type MANAGED \
    --state ENABLED \
    --compute-resources type=FARGATE,maxvCpus=128,subnets=subnet-03346336bd9eea875,securityGroupIds=sg-07c752064f7840b31

aws --profile personal-admin batch create-job-queue \                                       
    --job-queue-name mc-pricer-job-queue \
    --state ENABLED \
    --priority 900 \
    --compute-environment-order order=1,computeEnvironment=mc-pricer-compute-env

aws --profile personal-admin batch register-job-definition \
    --job-definition-name mc-pricer-job-definition \
    --type container \
    --platform-capabilities FARGATE \
    --container-properties '{
        "image": "091095727984.dkr.ecr.us-east-1.amazonaws.com/mc-pricer",
        "resourceRequirements": [
            {"type": "VCPU", "value": "0.25"},
            {"type": "MEMORY", "value": "512"}
        ],
        "executionRoleArn": "arn:aws:iam::091095727984:role/BatchEcsTaskExecutionRoleTutorial",
        "networkConfiguration": {
            "assignPublicIp": "ENABLED"
        },
        "environment": [
            {"name": "s3_bucket", "value": "avi-mc-pricer-results"},
            {"name": "num_workers", "value": "4"},
            {"name": "num_simulations", "value": "20"}
        ],
        "jobRoleArn": "arn:aws:iam::091095727984:role/BatchEcsJobRole"
    }'
    