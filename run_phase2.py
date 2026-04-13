"""CLI for manually testing Phase 2 reconciliation on one CV or a JSONL batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from contracts.phase2_input import Phase2Input
from phase2.adapters.phase1_to_phase2 import build_phase2_input
from phase2.reconciliation.finalize import (
    reconcile_phase2_coverage_mode,
    reconcile_phase2_milestone1,
    reconcile_phase2_milestone2,
)
from extractor.service import extract_raw_pdf


def main() -> None:
    """Run Phase 1 extraction and Phase 2 reconciliation for one PDF or many JSONL rows."""

    parser = argparse.ArgumentParser(description="Run Phase 2 reconciliation for one CV PDF.")
    parser.add_argument("pdf_path", nargs="?", help="Path to the PDF file to process")
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
        "--mode",
        choices=("strict", "coverage"),
        default="strict",
        help="Run strict reconciliation or coverage-first recovery mode",
    )
    parser.add_argument(
        "--output",
        help="Optional path to append the Phase 2 result as one JSON line",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run over paired parser/optimizer JSONL rows using each row's pdf_path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of batch rows to process",
    )
    args = parser.parse_args()

    if args.batch:
        _run_batch(args)
        return

    if not args.pdf_path:
        raise ValueError("pdf_path is required unless --batch is used")

    pdf_path = Path(args.pdf_path)
    phase1_output = extract_raw_pdf(str(pdf_path))
    phase2_input = build_phase2_input(phase1_output)
    parser_payload = _load_payload(args.parser_payload, args.parser_index)
    optimizer_payload = _load_payload(args.optimizer_payload, args.optimizer_index)

    validated = _reconcile(args.mode, args.milestone, phase2_input, parser_payload, optimizer_payload)
    payload = _build_result_payload(
        pdf_path=str(pdf_path),
        milestone=args.milestone,
        mode=args.mode,
        phase2_input=phase2_input,
        validated=validated,
        parser_payload=parser_payload,
        optimizer_payload=optimizer_payload,
    )

    if args.output:
        _append_json_line(Path(args.output), payload)
        print("Appended Phase 2 output to {0}".format(args.output))
        return

    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _run_batch(args: argparse.Namespace) -> None:
    """Run Phase 2 over paired parser/optimizer JSONL files keyed by row order and pdf_path."""

    if not args.parser_payload or not args.optimizer_payload:
        raise ValueError("--batch requires both --parser-payload and --optimizer-payload")

    parser_path = Path(args.parser_payload)
    optimizer_path = Path(args.optimizer_payload)
    if parser_path.suffix.lower() != ".jsonl" or optimizer_path.suffix.lower() != ".jsonl":
        raise ValueError("--batch currently requires JSONL parser and optimizer payload files")

    parser_rows = _load_jsonl_rows(parser_path)
    optimizer_rows = _load_jsonl_rows(optimizer_path)
    total_rows = min(len(parser_rows), len(optimizer_rows))
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be >= 1")
        total_rows = min(total_rows, args.limit)

    processed = 0
    failed = 0
    skipped = 0
    output_path = Path(args.output) if args.output else None

    for index in range(total_rows):
        parser_row = parser_rows[index]
        optimizer_row = optimizer_rows[index]
        pdf_path = _resolve_batch_pdf_path(parser_row, optimizer_row)
        if not pdf_path:
            skipped += 1
            print("Skipped row {0}: missing pdf_path".format(index + 1))
            continue

        try:
            phase1_output = extract_raw_pdf(pdf_path)
            phase2_input = build_phase2_input(phase1_output)
            parser_payload = _extract_payload_object(parser_row)
            optimizer_payload = _extract_payload_object(optimizer_row)
            validated = _reconcile(
                args.mode,
                args.milestone,
                phase2_input,
                parser_payload,
                optimizer_payload,
            )
            payload = _build_result_payload(
                pdf_path=pdf_path,
                milestone=args.milestone,
                mode=args.mode,
                phase2_input=phase2_input,
                validated=validated,
                parser_payload=parser_payload,
                optimizer_payload=optimizer_payload,
            )
            payload["cv_id"] = parser_row.get("cv_id") or optimizer_row.get("cv_id")
            if output_path:
                _append_json_line(output_path, payload)
            else:
                print(json.dumps(payload, ensure_ascii=False))
            processed += 1
        except Exception as exc:
            failed += 1
            print("Failed row {0} ({1}): {2}".format(index + 1, pdf_path, exc))

    print(
        "Completed Phase 2 batch: total={0} processed={1} skipped={2} failed={3}".format(
            total_rows,
            processed,
            skipped,
            failed,
        )
    )


def _reconcile(
    mode: str,
    milestone: str,
    phase2_input: Phase2Input,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
):
    """Run the selected Phase 2 reconciliation mode."""

    if mode == "coverage":
        return reconcile_phase2_coverage_mode(phase2_input, parser_payload, optimizer_payload)
    return (
        reconcile_phase2_milestone1(phase2_input, parser_payload, optimizer_payload)
        if milestone == "1"
        else reconcile_phase2_milestone2(phase2_input, parser_payload, optimizer_payload)
    )


def _build_result_payload(
    pdf_path: str,
    milestone: str,
    mode: str,
    phase2_input: Phase2Input,
    validated: Any,
    parser_payload: Dict[str, Any],
    optimizer_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the printed/appended Phase 2 result payload."""

    return {
        "file_path": pdf_path,
        "milestone": milestone,
        "mode": mode,
        "phase2_input": phase2_input.model_dump(),
        "validated_cv": validated.model_dump(),
        "parser_payload": parser_payload,
        "optimizer_payload": optimizer_payload,
    }


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


def _load_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    """Load all non-empty JSONL rows from a file."""

    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _extract_payload_object(loaded: Any) -> Dict[str, Any]:
    """Extract the schema-like payload dict from loaded JSON content."""

    if isinstance(loaded, dict):
        if "parser_payload" in loaded:
            parser_payload = loaded["parser_payload"]
            if isinstance(parser_payload, dict):
                return parser_payload
            raise ValueError("Unsupported parser_payload shape")
        if "optimizer_payload" in loaded:
            optimizer_payload = loaded["optimizer_payload"]
            if isinstance(optimizer_payload, dict):
                return optimizer_payload
            raise ValueError("Unsupported optimizer_payload shape")
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


def _resolve_batch_pdf_path(parser_row: Dict[str, Any], optimizer_row: Dict[str, Any]) -> str:
    """Resolve the PDF path for a batch row from parser or optimizer wrapper rows."""

    for row in (parser_row, optimizer_row):
        pdf_path = row.get("pdf_path")
        if isinstance(pdf_path, str) and pdf_path.strip():
            return pdf_path.strip()
    return ""


def _append_json_line(output_path: Path, payload: Dict[str, Any]) -> None:
    """Append one JSON object to a JSONL-style file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


if __name__ == "__main__":
    main()
