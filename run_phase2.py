"""CLI for manually testing Phase 2 reconciliation on one CV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from contracts.phase2_input import Phase2Input
from phase2.adapters.phase1_to_phase2 import build_phase2_input
from phase2.reconciliation.finalize import (
    reconcile_phase2_milestone1,
    reconcile_phase2_milestone2,
)
from extractor.service import extract_raw_pdf


def main() -> None:
    """Run Phase 1 extraction and Phase 2 reconciliation for one PDF."""

    parser = argparse.ArgumentParser(description="Run Phase 2 reconciliation for one CV PDF.")
    parser.add_argument("pdf_path", help="Path to the PDF file to process")
    parser.add_argument(
        "--parser-payload",
        help="Optional parser payload file (.json or .jsonl). If .jsonl, use --parser-index.",
    )
    parser.add_argument(
        "--optimizer-payload",
        help="Optional optimizer payload file (.json or .jsonl). If .jsonl, use --optimizer-index.",
    )
    parser.add_argument(
        "--parser-index",
        type=int,
        default=1,
        help="1-based row index when --parser-payload points to a .jsonl file",
    )
    parser.add_argument(
        "--optimizer-index",
        type=int,
        default=1,
        help="1-based row index when --optimizer-payload points to a .jsonl file",
    )
    parser.add_argument(
        "--milestone",
        choices=("1", "2"),
        default="2",
        help="Phase 2 reconciliation milestone to run",
    )
    parser.add_argument(
        "--output",
        help="Optional path to append the Phase 2 result as one JSON line",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    phase1_output = extract_raw_pdf(str(pdf_path))
    phase2_input = build_phase2_input(phase1_output)
    parser_payload = _load_payload(args.parser_payload, args.parser_index)
    optimizer_payload = _load_payload(args.optimizer_payload, args.optimizer_index)

    validated = (
        reconcile_phase2_milestone1(phase2_input, parser_payload, optimizer_payload)
        if args.milestone == "1"
        else reconcile_phase2_milestone2(phase2_input, parser_payload, optimizer_payload)
    )

    payload = {
        "file_path": str(pdf_path),
        "milestone": args.milestone,
        "phase2_input": phase2_input.model_dump(),
        "validated_cv": validated.model_dump(),
        "parser_payload": parser_payload,
        "optimizer_payload": optimizer_payload,
    }

    if args.output:
        _append_json_line(Path(args.output), payload)
        print("Appended Phase 2 output to {0}".format(args.output))
        return

    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _load_payload(path_str: Optional[str], index: int) -> Dict[str, Any]:
    """Load a parser or optimizer payload from JSON or JSONL."""

    if not path_str:
        return {}

    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError("Payload file does not exist: {0}".format(path))
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl_payload(path, index)
    if path.suffix.lower() == ".json":
        return _load_json_payload(path)
    raise ValueError("Unsupported payload file format: {0}".format(path))


def _load_json_payload(path: Path) -> Dict[str, Any]:
    """Load a JSON payload file."""

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    loaded = json.loads(text)
    return _extract_payload_object(loaded)


def _load_jsonl_payload(path: Path, index: int) -> Dict[str, Any]:
    """Load one row from a JSONL payload file."""

    if index < 1:
        raise ValueError("JSONL index must be >= 1")

    with path.open("r", encoding="utf-8") as handle:
        rows: List[Dict[str, Any]] = [
            json.loads(line) for line in handle if line.strip()
        ]

    if index > len(rows):
        raise IndexError(
            "Requested JSONL row {0}, but file only has {1} rows".format(index, len(rows))
        )

    return _extract_payload_object(rows[index - 1])


def _extract_payload_object(loaded: Any) -> Dict[str, Any]:
    """Extract the schema-like payload dict from loaded JSON content."""

    if isinstance(loaded, dict):
        if "json_output" in loaded:
            json_output = loaded["json_output"]
            if isinstance(json_output, dict):
                return json_output
            if isinstance(json_output, str):
                parsed = json.loads(json_output)
                if isinstance(parsed, dict):
                    return parsed
            raise ValueError("Unsupported json_output payload shape")
        return loaded

    if isinstance(loaded, list):
        if not loaded:
            return {}
        first = loaded[0]
        if isinstance(first, dict):
            return _extract_payload_object(first)

    raise ValueError("Unsupported payload structure")


def _append_json_line(output_path: Path, payload: Dict[str, Any]) -> None:
    """Append one JSON object to a JSONL-style file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


if __name__ == "__main__":
    main()
