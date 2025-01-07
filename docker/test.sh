#!/bin/bash
# Script for testing the docker container.

script_dir=$(dirname "$0")
ecr_path="725596835855.dkr.ecr.us-east-1.amazonaws.com"
image="${ecr_path}/www/staging:latest"

# Gets the login password for the AWS ECR and logs in to the ECR.
aws ecr get-login-password --profile kscale --region us-east-1 |
    docker login --username AWS --password-stdin ${ecr_path}

# Pulls the latest docker container.
docker pull --platform=linux/amd64 ${image}

# Runs the docker container.
docker run \
    -P \
    --env-file "${script_dir}/local_docker.env" \
    ${image}
