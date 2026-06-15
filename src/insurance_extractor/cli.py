"""Command-line entry point: extract <document> <schema.json>."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import get_settings
from .pipeline import extract_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract a proof-of-insurance document to JSON.")
    parser.add_argument("document", help="Path to a PDF/PNG/JPG document")
    parser.add_argument("schema", help="Path to a JSON Schema file")
    parser.add_argument(
        "--strategy", choices=["rule", "llm", "auto"], default=None,
        help="Mapping strategy (default: from config, 'rule')",
    )
    parser.add_argument("--model", default=None, help="Ollama model for the LLM path")
    parser.add_argument("--show-ocr", action="store_true", help="Print raw OCR text to stderr")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.model:
        settings = settings.model_copy(update={"ollama_model": args.model})

    schema = json.loads(Path(args.schema).read_text())
    result = extract_path(args.document, schema, strategy=args.strategy, settings=settings)

    if args.show_ocr:
        print(result.ocr_text, file=sys.stderr)

    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.validation["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
