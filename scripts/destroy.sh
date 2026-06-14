#!/usr/bin/env bash
# Tear down all deployed AWS resources.
set -euo pipefail
REGION="${1:-us-east-1}"
INFRA="$(cd "$(dirname "$0")/.." && pwd)/infra"
TF="$(command -v tofu || command -v terraform)"
cd "$INFRA"
$TF destroy -input=false -auto-approve -var "region=$REGION"
