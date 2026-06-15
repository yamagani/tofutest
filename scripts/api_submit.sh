#!/usr/bin/env bash
# Submit a document to the async ingest API (POST /jobs).
# Prints the job_id to stdout; full response goes to stderr.
#
# Usage:   scripts/api_submit.sh [document] [schema.json] [strategy]
# Defaults: examples/sample_certificate.png  examples/proof_of_insurance.schema.json  rule
# Env:     BASE_URL (default http://localhost:8000)
#
# Example: JOB=$(scripts/api_submit.sh) ; scripts/api_get.sh "$JOB"
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOC="${1:-$ROOT/examples/sample_certificate.png}"
SCHEMA="${2:-$ROOT/examples/proof_of_insurance.schema.json}"
STRATEGY="${3:-rule}"

# Auto-generate the demo document if the default is missing.
if [ ! -f "$DOC" ] && [ "$DOC" = "$ROOT/examples/sample_certificate.png" ]; then
    echo ">> generating demo document..." >&2
    (cd "$ROOT" && python -m tests.sample_doc >&2)
fi
[ -f "$DOC" ] || { echo "document not found: $DOC" >&2; exit 1; }
[ -f "$SCHEMA" ] || { echo "schema not found: $SCHEMA" >&2; exit 1; }

resp="$(curl -sS -X POST "$BASE_URL/jobs" \
    -F "file=@$DOC" \
    -F "schema=$(cat "$SCHEMA")" \
    -F "options={\"strategy\":\"$STRATEGY\"}")"

echo ">> POST $BASE_URL/jobs" >&2
echo "$resp" | python3 -m json.tool >&2

# Emit just the job_id on stdout so it can be captured by other scripts.
echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])"
