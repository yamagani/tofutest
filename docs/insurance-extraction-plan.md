# Proof-of-Insurance Document Extraction — Plan & Requirements

**Goal:** Given (1) a scanned proof-of-insurance document (PDF or PNG) and (2) a
JSON Schema describing the attributes to capture, produce a validated JSON
payload populated with values extracted from the document.

**Constraints (decided):**
- Engine: **Hybrid** — classical OCR for text + a **local** small LLM for
  schema-driven mapping. No cloud LLM APIs; everything runs offline.
- Documents: **mostly standardized forms** (e.g. ACORD certificates / insurance
  ID cards) with some variation.
- Hardware: **CPU only** → favor a small *text* LLM (quantized, via Ollama),
  not a heavy vision-language model.
- Deliverable: **local REST API service** (FastAPI), with the core logic as an
  importable Python library.

---

## 1. Functional requirements

| ID | Requirement |
|----|-------------|
| F1 | Accept a document upload: PDF (single/multi-page) or PNG/JPG image. |
| F2 | Accept a JSON Schema (Draft 2020-12) describing target fields, types, and which are required. |
| F3 | Extract text + word/line bounding boxes from the document via OCR. |
| F4 | Map extracted text onto the schema fields, producing a JSON object. |
| F5 | Validate the output against the supplied schema; report which fields failed/were missing. |
| F6 | Return per-field **confidence** and **provenance** (source text + page) alongside values. |
| F7 | Expose all of the above via a REST endpoint; also runnable as a CLI/library call. |
| F8 | Run fully offline on CPU. |

## 2. Non-functional requirements

- **Privacy/offline:** no document or field data leaves the host.
- **Latency:** target < 10s/page on CPU for the OCR path; LLM mapping step is
  the slow part — keep prompts small (only OCR text + schema, not images).
- **Determinism:** LLM called with `temperature=0`; same input → same output.
- **Auditability:** persist the raw OCR text and the model's raw response per
  request for debugging (configurable, off by default for PII).
- **Extensibility:** adding a new form template or schema requires no code change.

---

## 3. Architecture

```
            ┌─────────────────────────────────────────────────────────┐
            │                  FastAPI service                         │
            │  POST /extract  (multipart: file + schema)               │
            └───────────────┬─────────────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ 1. Ingest & normalize       │  PDF→images / image load,
              │    (PyMuPDF, Pillow)        │  deskew, denoise, upscale
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ 2. OCR                      │  PaddleOCR or Tesseract
              │    text + bounding boxes    │  → lines with (text, bbox, conf)
              └─────────────┬──────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                        │
┌───────▼─────────┐                    ┌─────────▼──────────┐
│ 3a. Template     │  (fast path —     │ 3b. LLM mapper      │  (fallback /
│     anchor match │   known forms)    │  local Ollama model │   varied forms)
│  regex + label   │                   │  OCR text + schema  │
│  proximity rules │                   │  → JSON             │
└───────┬─────────┘                    └─────────┬──────────┘
        └───────────────────┬───────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ 4. Coerce + validate        │  type coercion (dates, money),
              │    (Pydantic + jsonschema)  │  schema validation
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ 5. Response                 │  {data, confidence, provenance,
              │                             │   validation_errors}
              └─────────────────────────────┘
```

### Why this shape
- **OCR does the reading** (cheap, reliable on standardized forms). The LLM only
  *maps already-extracted text* to schema fields — a small text model handles
  this well on CPU, and we never pay vision-model cost.
- **Template fast-path (3a)** handles your common forms deterministically and
  near-instantly; the **LLM path (3b)** is the safety net for layouts without a
  template. Start with 3b working end-to-end, add 3a templates as you see real
  documents.

---

## 4. Technology choices (all local / open source)

| Concern | Primary pick | Notes / alternatives |
|---------|--------------|----------------------|
| PDF → image / text layer | **PyMuPDF (fitz)** | Detects if a PDF already has a text layer (skip OCR). `pdfplumber` alt. |
| Image preprocessing | **OpenCV + Pillow** | deskew, grayscale, adaptive threshold, upscale low-DPI scans. |
| OCR | **PaddleOCR** (PP-OCRv4) | Best accuracy + bounding boxes on CPU; `pytesseract` (Tesseract) is the lighter, simpler fallback. |
| Local LLM runtime | **Ollama** | Easiest local serving; OpenAI-compatible `/api/chat` with JSON mode. |
| LLM model (CPU) | **Qwen2.5-3B-Instruct** (or 7B if RAM allows), quantized Q4 | Strong structured-output behavior at small size. Llama 3.1 8B alt. |
| Structured output | Ollama **`format: json`** + schema in prompt | Forces valid JSON; pair with Pydantic validation. |
| Validation | **jsonschema** + **Pydantic v2** | jsonschema validates against the *user's* schema; Pydantic for internal coercion. |
| Date/money normalization | **dateparser**, **price-parser**/`babel` | Insurance docs have messy date & limit formats. |
| API | **FastAPI + Uvicorn** | multipart upload, async. |
| Tests | **pytest** + sample fixtures | golden-file tests per template. |

> If you'd rather avoid even a local LLM at first, the template/rules path (3a)
> alone can ship for the standardized forms; the LLM is the generalization layer.

---

## 5. API contract

```
POST /extract
Content-Type: multipart/form-data
  file:   <pdf|png|jpg>
  schema: <json schema string>           # the target field definitions
  options (optional json): { "template": "acord_25", "save_debug": false }

200 OK
{
  "data": { ... },                        # values, conforming to schema
  "confidence": { "policy_number": 0.97, "insured_name": 0.88, ... },
  "provenance": {
     "policy_number": { "page": 1, "text": "Policy No. ABC-123", "bbox": [...] }
  },
  "validation": { "valid": true, "errors": [] },
  "engine": "template:acord_25" | "llm:qwen2.5-3b"
}
```

**Example input schema** (proof of insurance):
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "insured_name":      { "type": "string", "description": "Name of the insured party" },
    "carrier_name":      { "type": "string", "description": "Insurance company" },
    "policy_number":     { "type": "string" },
    "effective_date":    { "type": "string", "format": "date" },
    "expiration_date":   { "type": "string", "format": "date" },
    "coverage_type":     { "type": "string" },
    "liability_limit":   { "type": "number" },
    "vin":               { "type": "string", "description": "Vehicle identification number" }
  },
  "required": ["insured_name", "policy_number", "effective_date", "expiration_date"]
}
```
The `description` fields are passed to the LLM as hints — good descriptions
materially improve mapping accuracy.

---

## 6. The LLM mapping step (detail)

Prompt = system instruction + the JSON Schema + the OCR text (with line
positions). Ask for **only** the JSON object, `format: json`, `temperature: 0`.

Key tactics:
- Pass OCR lines in reading order with light positional cues; keep under the
  model's context window.
- Instruct: "Only use values present in the text. If a field is absent, set it
  to null. Do not invent values." (reduces hallucination — critical for compliance data).
- Return values as strings first, then **coerce** (dates via `dateparser`,
  money by stripping `$`/`,`), then validate. Don't trust the model to format
  dates correctly.
- Attach provenance by fuzzy-matching each returned value back to an OCR line.

---

## 7. Repository layout

```
insurance_extractor/
  __init__.py
  ingest.py          # PDF/image → normalized page images, text-layer detection
  preprocess.py      # OpenCV deskew/denoise/threshold
  ocr.py             # PaddleOCR/Tesseract wrapper → lines[(text,bbox,conf)]
  templates/         # per-form anchor definitions (yaml/json)
    acord_25.yaml
  template_match.py  # 3a fast-path
  llm_mapper.py      # 3b Ollama client + prompt builder
  coerce.py          # date/money/string normalization
  validate.py        # jsonschema validation + error report
  pipeline.py        # orchestrates 1→5, picks template vs llm
  api.py             # FastAPI app
  cli.py             # `extract <file> <schema.json>`
tests/
  fixtures/          # sample docs + expected JSON (golden files)
docker/              # optional: Dockerfile bundling Ollama + service
pyproject.toml
```

---

## 8. Milestones

1. **M1 — Skeleton + OCR:** ingest PDF/PNG, preprocess, OCR to text. CLI prints text. *(validates the hard part on CPU)*
2. **M2 — LLM mapping path:** wire Ollama, prompt with schema, return + validate JSON. End-to-end on one sample.
3. **M3 — API:** FastAPI `/extract`, multipart upload, structured response.
4. **M4 — Coercion + confidence + provenance:** dates/money normalization, per-field confidence, source provenance.
5. **M5 — Template fast-path:** add ACORD-25 (and your top forms) anchor templates; route to them when matched.
6. **M6 — Hardening:** golden-file tests, multi-page PDFs, bad-scan handling, Docker bundle (service + Ollama), basic auth on the API.

---

## 9. Open questions / risks

- **Model size vs CPU speed:** confirm available RAM. 3B Q4 ≈ ~3GB RAM and is
  the safe default; 7B is better but slower. Benchmark on M1.
- **Scan quality:** low-DPI/skewed scans are the #1 accuracy killer — invest in
  preprocessing (M1) and consider rejecting < ~150 DPI inputs.
- **PII handling:** decide retention policy for uploaded docs and debug logs.
- **Which exact forms** dominate your volume? That list drives M5 template work.
- **Multi-page:** does one document map to one payload, or one-per-page?
```
