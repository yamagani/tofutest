# Insurance Document Extractor

Offline extraction of scanned **proof-of-insurance** documents (PDF / PNG / JPG)
into a **JSON payload validated against a JSON Schema you supply**.

- **Input:** a document + a JSON Schema describing the fields you want.
- **Output:** a JSON object conforming to that schema, with per-field
  **confidence** and **provenance** (the source OCR line + page + bounding box).
- **No cloud.** OCR runs locally (Tesseract); field mapping uses a deterministic
  rule engine by default and an optional **local** LLM (Ollama) as a fallback.

Two ways to call it:
- **Synchronous** (`POST /extract`) — result in the HTTP response. Best for fast docs.
- **Asynchronous** (`POST /jobs` → `GET /jobs/{id}`) — returns a `job_id` immediately,
  processes in the background, stores the result in **DynamoDB + S3**. Best when
  ingestion may be slow. Runs locally against **LocalStack** (same `docker compose up`).

See [docs/insurance-extraction-plan.md](docs/insurance-extraction-plan.md) for the
full design.

---

## Quick start (60 seconds)

```bash
brew install tesseract                          # one-time: system OCR engine (macOS)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                         # install package + test deps

python -m tests.sample_doc                      # create examples/sample_certificate.png
extract examples/sample_certificate.png examples/proof_of_insurance.schema.json
```

You should see a JSON object with `insured_name`, `policy_number`, dates, etc.,
and `"validation": {"valid": true}` at the bottom. That confirms the whole
pipeline (OCR → mapping → coercion → validation) works.

---

## Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| Python 3.10+ | runtime | (system / pyenv) |
| Tesseract | OCR engine | `brew install tesseract` (macOS) · `apt-get install tesseract-ocr` (Linux) |
| Docker | container / compose / Lambda image | Docker Desktop |
| OpenTofu or Terraform | AWS deploy only | `brew install opentofu` |
| AWS CLI | AWS deploy only | `brew install awscli` |

Docker, Tofu, and the AWS CLI are **only** needed for the Docker/AWS sections.

---

## Testing

Five ways to test, from fastest to most production-like. All use `strategy=rule`
(fully offline, no model). **Run `python -m tests.sample_doc` first** to create
the demo document the examples reference.

### 1. Automated test suite

```bash
pytest -q
```
Expected: **`20 passed, 1 skipped`** (the skip is the LocalStack integration test
— see below). Covers the pipeline end-to-end (synthetic certificate → schema-valid
JSON), the sync + async APIs (via `TestClient`), the job service, config, and the
input guards (oversized file, too many pages, bad base64, unsupported type).

The LocalStack test runs once the stack is up:

```bash
docker compose up -d localstack
IE_AWS_ENDPOINT_URL=http://localhost:4566 AWS_ACCESS_KEY_ID=test \
  AWS_SECRET_ACCESS_KEY=test pytest tests/test_localstack.py -v
```

### 2. CLI

```bash
extract examples/sample_certificate.png examples/proof_of_insurance.schema.json
```
Flags: `--strategy {rule,llm,auto}` (default `rule`), `--model <ollama-model>`,
`--show-ocr` (dump raw OCR text to stderr). Exit code is `0` when the output
validates against the schema, `1` otherwise.

### 3. Local REST API (no Docker)

```bash
# terminal A — start the server
uvicorn insurance_extractor.api:app --port 8000        # or: make run

# terminal B — test it
curl http://localhost:8000/health
# -> {"status":"ok"}

# multipart upload
curl -X POST http://localhost:8000/extract \
  -F "file=@examples/sample_certificate.png" \
  -F "schema=$(cat examples/proof_of_insurance.schema.json)" \
  -F 'options={"strategy":"rule"}'

# OR the base64 JSON endpoint (preferred behind API Gateway)
python - <<'PY'
import base64, json, urllib.request
payload = {
    "filename": "cert.png",
    "content_base64": base64.b64encode(open("examples/sample_certificate.png","rb").read()).decode(),
    "schema": json.load(open("examples/proof_of_insurance.schema.json")),
    "options": {"strategy": "rule"},
}
req = urllib.request.Request("http://localhost:8000/extract-json",
        data=json.dumps(payload).encode(), headers={"content-type":"application/json"})
print(json.dumps(json.load(urllib.request.urlopen(req))["data"], indent=2))
PY
```
Interactive Swagger UI: **http://localhost:8000/docs** (upload a file in the browser).

Endpoints: `GET /health` · `POST /extract` + `POST /extract-json` (sync) ·
`POST /jobs` + `POST /jobs-json` → `GET /jobs/{id}` (async).

### 4. Docker Compose — full stack with async jobs + LocalStack

`docker compose up` starts **the API and LocalStack** (DynamoDB + S3) together,
so the async flow runs entirely offline.

```bash
docker compose up --build              # API :8000 + LocalStack :4566 (or: make compose-up)
curl http://localhost:8000/health

# --- async: submit, get a job_id, poll until SUCCEEDED ---
python - <<'PY'
import base64, json, time, urllib.request
B="http://localhost:8000"
body={"filename":"cert.png",
      "content_base64":base64.b64encode(open("examples/sample_certificate.png","rb").read()).decode(),
      "schema":json.load(open("examples/proof_of_insurance.schema.json")),
      "options":{"strategy":"rule"}}
req=urllib.request.Request(B+"/jobs-json",data=json.dumps(body).encode(),
                           headers={"content-type":"application/json"})
job_id=json.load(urllib.request.urlopen(req))["job_id"]; print("job_id:", job_id)
for _ in range(30):
    j=json.load(urllib.request.urlopen(f"{B}/jobs/{job_id}"))
    if j["status"] in ("SUCCEEDED","FAILED"): break
    time.sleep(0.5)
print("status:", j["status"]); print(json.dumps(j.get("result",{}).get("data"), indent=2))
PY

docker compose logs api                # structured JSON logs (request id + latency)
docker compose down -v                 # stop + clear LocalStack volume
```

The async API also has a multipart variant (`POST /jobs`) and the result is
persisted — inspect it directly in LocalStack:

```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url http://localhost:4566 dynamodb scan --table-name insurance_jobs
```

### 5. Local Lambda container (via the Runtime Interface Emulator)

This runs the **exact arm64 image AWS will run**. A Lambda container is invoked
with an *event* (not plain HTTP), so use the helper script.

```bash
make lambda-run                        # build + run the lambda image on :9000
# or manually:
#   docker build --target lambda --platform linux/arm64 -t insurance-extractor:lambda .
#   docker run -d -p 9000:8080 --name ie-local insurance-extractor:lambda

scripts/invoke_local.sh examples/sample_certificate.png examples/proof_of_insurance.schema.json rule
# -> Lambda HTTP status: 200  + the full JSON result

make lambda-stop                       # stop & remove the container
```

### Test with your own document

Point any of the above at your file. Build a JSON Schema describing the fields
you want (use [examples/proof_of_insurance.schema.json](examples/proof_of_insurance.schema.json)
as a template — `description` fields improve matching):

```bash
extract /path/to/your_scan.pdf examples/proof_of_insurance.schema.json --strategy rule
```

### Expected output shape

```json
{
  "data":        { "policy_number": "NWM-4820-7731", "effective_date": "2026-03-01", ... },
  "confidence":  { "policy_number": 0.93, ... },
  "provenance":  { "policy_number": { "page": 0, "text": "Policy Number: NWM-4820-7731", "bbox": [...] }, ... },
  "validation":  { "valid": true, "errors": [] },
  "engine":      "rule"
}
```

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'PIL'` | You're using system Python — `source .venv/bin/activate` first. |
| `TesseractNotFoundError` / `ocr_failed` | Install Tesseract, or set `IE_TESSERACT_CMD=/full/path/to/tesseract`. |
| Empty / wrong fields | Low-res scan — raise `IE_PDF_DPI`, or install OpenCV (`pip install -e ".[opencv]"`) for deskew/threshold. |
| `docker compose` can't connect | Start Docker Desktop and wait for the daemon. |
| Want to reset config cache in tests | `from insurance_extractor import get_settings; get_settings.cache_clear()`. |

---

## Configuration

All settings are env-driven (`IE_*`), read once at startup — see
[.env.example](.env.example) and `insurance_extractor/config.py`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `IE_DEFAULT_STRATEGY` | `rule` | `rule` / `llm` / `auto` |
| `IE_PDF_DPI` | `200` | PDF render DPI for OCR |
| `IE_OCR_LANG` | `eng` | Tesseract language(s) |
| `IE_TESSERACT_CMD` | _(auto)_ | explicit path to the tesseract binary |
| `IE_OLLAMA_URL` | `http://localhost:11434/api/chat` | local LLM endpoint |
| `IE_OLLAMA_MODEL` | `qwen2.5:3b` | local LLM model |
| `IE_MAX_UPLOAD_MB` | `15` | reject larger uploads (HTTP 413) |
| `IE_MAX_PAGES` | `10` | reject longer PDFs (HTTP 422) |
| `IE_STORE_BACKEND` | `memory` | async job store: `memory` or `dynamo` |
| `IE_AWS_ENDPOINT_URL` | _(unset)_ | LocalStack endpoint; unset = real AWS |
| `IE_DDB_TABLE` / `IE_S3_BUCKET` | `insurance_jobs` / `insurance-documents` | DynamoDB table / S3 bucket |
| `IE_WORKER_CONCURRENCY` | `2` | background worker threads |
| `IE_AUTO_CREATE_RESOURCES` | `true` | create table/bucket on startup (set `false` in prod) |
| `IE_LOG_LEVEL` / `IE_JSON_LOGS` | `INFO` / `true` | structured logging |

---

## Mapping strategies

| Strategy | Behavior |
|----------|----------|
| `rule`   | Deterministic label-proximity matching. Fully offline, no models. Best on standardized forms. |
| `llm`    | Local Ollama model only (e.g. `qwen2.5:3b`). For varied layouts. |
| `auto`   | Rules first; if **required** fields are still missing *and* Ollama is running, the LLM fills the gaps (falls back silently if Ollama is down). |

### Enabling the local LLM path (optional)

```bash
brew install ollama && ollama serve &
ollama pull qwen2.5:3b
extract <doc> <schema.json> --strategy auto

# under docker-compose instead:
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
# then run the api with IE_OLLAMA_URL=http://ollama:11434/api/chat
```

---

## Project layout

```
src/insurance_extractor/
  config.py         env-driven settings (IE_*)
  errors.py         typed exception hierarchy (-> HTTP status codes)
  observability.py  structured logging + request timing
  ingest.py         PDF/image -> page images (size/page guards)
  preprocess.py     image cleanup (OpenCV optional)
  ocr.py            OcrEngine protocol + Tesseract impl
  mappers/          Mapper protocol + rule / llm / auto + factory
  coerce.py         date/money normalization
  validate.py       JSON Schema validation
  pipeline.py       orchestration (single entry point)
  storage/          JobStore protocol + memory / dynamo (DynamoDB+S3) backends
  jobs.py           async JobService (submit -> background worker -> poll)
  api/              FastAPI app factory, routes, schemas, middleware
  cli.py            `extract` command
infra/              OpenTofu/Terraform (ECR, Lambda, API Gateway, DynamoDB, S3, IAM)
```

Pipeline: `ingest (PyMuPDF/Pillow) → preprocess (OpenCV*) → OCR (Tesseract) →
map to schema (rule | local LLM) → coerce (dates/money) → validate (jsonschema)`.
\* OpenCV is optional; without it a Pillow-only preprocessing path is used.

---

## Deploy to AWS Lambda (container image + API Gateway)

The whole pipeline runs as a single **container-image Lambda** behind an **HTTP
API Gateway**. Tesseract is baked into the image; only the deterministic `rule`
strategy is used in the cloud (no Ollama). Cold start ~3–8s, warm ~1s.

```
client → API Gateway (HTTP API) → Lambda (Docker: FastAPI+Mangum, Tesseract) → JSON
```

**Prereqs:** Docker running, a working `aws` CLI (`aws sts get-caller-identity`),
and `tofu` (or `terraform`). IaC lives in [infra/](infra/).

```bash
scripts/deploy.sh us-east-1        # builds + pushes image to ECR, then applies infra
                                   # (or: make deploy REGION=us-east-1)
# outputs:
#   api_base_url      = https://xxxx.execute-api.us-east-1.amazonaws.com
#   extract_json_url  = .../extract-json
```

Test the deployed API by pointing the **section 3** base64 snippet at
`extract_json_url`. Tear down with:

```bash
scripts/destroy.sh us-east-1       # or: make destroy
```

> **Architecture:** images and the Lambda default to **arm64 (Graviton)**. Build
> on the same arch you deploy to, or change `architecture` in
> [infra/variables.tf](infra/variables.tf) and the `--platform` flag.

---

## Make targets

```
make install        install package + dev deps
make test           run the test suite
make run            run the API locally (uvicorn, autoreload)
make compose-up     build & start the HTTP API via docker-compose
make docker-lambda  build the Lambda image
make lambda-run     run the Lambda image locally via the RIE (:9000)
make deploy         build+push image and apply infra
make destroy        tear down all AWS resources
```
