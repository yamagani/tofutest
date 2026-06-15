#!/usr/bin/env bash
# Build the container image, push it to ECR, and deploy the Lambda + API Gateway.
#
# Prereqs: docker running, aws CLI configured (aws sts get-caller-identity works),
#          and `tofu` (or `terraform`) on PATH.
#
# Usage:   scripts/deploy.sh [aws-region]
set -euo pipefail

REGION="${1:-us-east-1}"
ARCH="arm64"                      # matches infra default; build natively on Apple Silicon
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INFRA="$ROOT/infra"

# Pick the IaC binary.
TF="$(command -v tofu || command -v terraform)"
[ -n "$TF" ] || { echo "Need tofu or terraform on PATH"; exit 1; }

# Unique-ish tag from git, falling back to a timestamp.
TAG="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || date +%s)"

echo ">> Region=$REGION  Arch=$ARCH  Tag=$TAG  IaC=$TF"

cd "$INFRA"
$TF init -input=false

# 1) Create the ECR repo first (the Lambda needs an image to reference).
$TF apply -input=false -auto-approve -var "region=$REGION" -target=aws_ecr_repository.app
ECR_URL="$($TF output -raw ecr_repository_url)"
ACCOUNT="${ECR_URL%%.*}"
echo ">> ECR: $ECR_URL"

# 2) Build and push the image.
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ECR_URL%/*}"

docker build --target lambda --platform "linux/$ARCH" \
  -t "$ECR_URL:$TAG" -t "$ECR_URL:latest" "$ROOT"
docker push "$ECR_URL:$TAG"
docker push "$ECR_URL:latest"

# 3) Deploy everything, pointing the Lambda at the tag we just pushed.
$TF apply -input=false -auto-approve -var "region=$REGION" -var "image_tag=$TAG"

echo
echo ">> Deployed. Endpoints:"
$TF output
