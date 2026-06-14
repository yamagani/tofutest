#!/usr/bin/env bash
# Pull a job's status/result from the async API (GET /jobs/{id}).
#
# Usage:   scripts/api_get.sh <job_id>
# Env:     BASE_URL (default http://localhost:8000)
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
JOB_ID="${1:?usage: api_get.sh <job_id>}"

code="$(curl -sS -o /tmp/ie_job.json -w '%{http_code}' "$BASE_URL/jobs/$JOB_ID")"
echo ">> GET $BASE_URL/jobs/$JOB_ID  ->  HTTP $code" >&2
python3 -m json.tool < /tmp/ie_job.json
[ "$code" = "200" ]
