#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/stack-outputs.sh"

PROFILE=personal
IMAGE=$(stack_output McPricerImage)  # e.g. 0910...dkr.ecr.us-east-1.amazonaws.com/mc-pricer
REGISTRY=${IMAGE%%/*}                # strip the repo name to get the registry host
REGION=$(cut -d. -f4 <<< "$REGISTRY")

aws --profile $PROFILE ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker build --platform linux/amd64 -t mc-pricer .
docker tag mc-pricer:latest "$IMAGE:latest"
docker push "$IMAGE:latest"
