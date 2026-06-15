#!/usr/bin/env bash
# Invoke the locally-running Lambda container (started via the RIE) with a
# document + schema, mimicking an API Gateway HTTP API (v2) request to
# POST /extract-json.
#
# Usage: scripts/invoke_local.sh <document> <schema.json> [strategy]
#   defaults: strategy=rule, RIE at localhost:9000
set -euo pipefail

DOC="${1:?usage: invoke_local.sh <document> <schema.json> [strategy]}"
SCHEMA="${2:?usage: invoke_local.sh <document> <schema.json> [strategy]}"
STRATEGY="${3:-rule}"
PORT="${PORT:-9000}"

# Prefer the venv python (has nothing special required, but stay consistent).
PY="$(cd "$(dirname "$0")/.." && pwd)/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

DOC="$DOC" SCHEMA="$SCHEMA" STRATEGY="$STRATEGY" PORT="$PORT" "$PY" - <<'PY'
import base64, json, os, urllib.request

doc, schema_path = os.environ["DOC"], os.environ["SCHEMA"]
body = {
    "filename": os.path.basename(doc),
    "content_base64": base64.b64encode(open(doc, "rb").read()).decode(),
    "schema": json.load(open(schema_path)),
    "options": {"strategy": os.environ["STRATEGY"]},
}
event = {
    "version": "2.0",
    "routeKey": "POST /extract-json",
    "rawPath": "/extract-json",
    "headers": {"content-type": "application/json"},
    "requestContext": {"http": {"method": "POST", "path": "/extract-json", "sourceIp": "127.0.0.1"}},
    "body": json.dumps(body),
    "isBase64Encoded": False,
}
url = f"http://localhost:{os.environ['PORT']}/2015-03-31/functions/function/invocations"
req = urllib.request.Request(url, data=json.dumps(event).encode(),
                             headers={"content-type": "application/json"})
resp = json.load(urllib.request.urlopen(req, timeout=60))
print("Lambda HTTP status:", resp.get("statusCode"))
print(json.dumps(json.loads(resp["body"]), indent=2))
PY
