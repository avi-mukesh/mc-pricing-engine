aws --profile personal-admin ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 091095727984.dkr.ecr.us-east-1.amazonaws.com
docker build --platform linux/amd64 -t mc-pricer .
docker tag mc-pricer:latest 091095727984.dkr.ecr.us-east-1.amazonaws.com/mc-pricer:latest
docker push 091095727984.dkr.ecr.us-east-1.amazonaws.com/mc-pricer:latest