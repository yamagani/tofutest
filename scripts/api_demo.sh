#!/usr/bin/env bash
# End-to-end async demo: submit a document, then poll until the job finishes.
#
# If the API isn't already running locally, this starts the docker-compose stack
# (API + LocalStack) automatically and leaves it up.
#
# Usage:   scripts/api_demo.sh [document] [schema.json] [strategy]
# Defaults: examples/sample_certificate.png  examples/proof_of_insurance.schema.json  rule
# Env:     BASE_URL (default http://localhost:8000), POLL_TRIES (default 60)
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
POLL_TRIES="${POLL_TRIES:-60}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

ensure_api_up() {
    curl -sf "$BASE_URL/health" >/dev/null 2>&1 && return 0

    # Only auto-start for a local default URL; a custom BASE_URL must already be up.
    if [ "$BASE_URL" != "http://localhost:8000" ]; then
        echo "API not reachable at $BASE_URL (custom BASE_URL) — start it yourself." >&2
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        echo "API down and Docker isn't running. Start Docker Desktop, or run the API directly:" >&2
        echo "  uvicorn insurance_extractor.api:app --port 8000" >&2
        exit 1
    fi

    echo "== 0) API not up — starting docker compose (API + LocalStack) ==" >&2
    ( cd "$ROOT" && docker compose up -d --build )
    echo "   waiting for API health..." >&2
    for _ in $(seq 1 90); do
        curl -sf "$BASE_URL/health" >/dev/null 2>&1 && { echo "   API is up." >&2; return 0; }
        sleep 1
    done
    echo "API did not become healthy in time. Check: docker compose logs" >&2
    exit 1
}

ensure_api_up

echo "== 1) submit (ingest) =="
JOB_ID="$("$HERE/api_submit.sh" "$@")"
echo "   job_id: $JOB_ID"

echo "== 2) poll (pull) until terminal =="
for i in $(seq 1 "$POLL_TRIES"); do
    status="$(curl -sS "$BASE_URL/jobs/$JOB_ID" | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])")"
    echo "   [$i] status=$status"
    case "$status" in
        SUCCEEDED|FAILED) break ;;
    esac
    sleep 1
done

echo "== 3) final result =="
"$HERE/api_get.sh" "$JOB_ID"

echo "" >&2
echo "(stack left running — stop it with: docker compose down -v)" >&2
