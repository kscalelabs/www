# Script for testing the docker container.

# Gets the login password for the AWS ECR and logs in to the ECR.
aws ecr get-login-password --profile kscale --region us-east-1 |
    docker login --username AWS --password-stdin 725596835855.dkr.ecr.us-east-1.amazonaws.com

# Pulls the latest docker container.
docker pull 725596835855.dkr.ecr.us-east-1.amazonaws.com/www/staging:latest

# Runs the docker container.
docker run \
    -P \
    --env-file local_docker.env \
    725596835855.dkr.ecr.us-east-1.amazonaws.com/www/staging:latest
