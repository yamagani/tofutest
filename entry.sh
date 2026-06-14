#!/bin/sh
# Lambda container entrypoint.
# - In real AWS Lambda, AWS_LAMBDA_RUNTIME_API is set: run the runtime client directly.
# - Locally, it is not set: wrap with the Runtime Interface Emulator so the
#   container can be invoked over HTTP for testing.
set -e

if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
    exec /usr/local/bin/aws-lambda-rie /usr/local/bin/python -m awslambdaric "$@"
else
    exec /usr/local/bin/python -m awslambdaric "$@"
fi
