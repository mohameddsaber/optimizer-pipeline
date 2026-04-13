"""Small CLI for manually testing raw CV PDF extraction.

When ``--output`` is provided, results are appended as JSON Lines so multiple
PDF extractions can be collected in one file deterministically.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from extractor.service import audit_extraction_quality, extract_raw_pdf, is_extraction_weak


def main() -> None:
    """Run raw PDF extraction for one file and print JSON output."""

    parser = argparse.ArgumentParser(description="Extract raw text from a CV PDF.")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        help="Path to the PDF file to extract, or a directory when using --batch",
    )
    parser.add_argument(
        "--output",
        help="Optional path to append the extracted JSON payload as one JSON line",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all PDFs inside the provided directory recursively",
    )
    parser.add_argument(
        "--report",
        help="Optional path to write a JSON summary report for batch runs",
    )
    args = parser.parse_args()

    if not args.pdf_path:
        parser.error("pdf_path is required")

    input_path = Path(args.pdf_path)
    if args.batch:
        _run_batch(input_path, args.output, args.report)
        return

    result = extract_raw_pdf(str(input_path))
    payload = _build_output_payload(result.model_dump(), input_path, audit_extraction_quality(result))

    if args.output:
        _append_json_line(Path(args.output), payload)
        print(f"Appended extraction JSON to {args.output}")
        return

    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _run_batch(input_dir: Path, output: Optional[str], report: Optional[str]) -> None:
    """Process all PDFs in a directory and optionally write outputs and a report."""

    if not input_dir.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise ValueError(f"--batch expects a directory path, got: {input_dir}")

    pdf_files = sorted(path for path in input_dir.rglob("*.pdf") if path.is_file())
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found under: {input_dir}")

    results: List[Dict[str, object]] = []
    failures: List[Dict[str, str]] = []
    weak_files: List[Dict[str, object]] = []
    output_path = Path(output) if output else None

    for pdf_file in pdf_files:
        try:
            extraction = extract_raw_pdf(str(pdf_file))
            weak = is_extraction_weak(extraction.pages)
            audit = audit_extraction_quality(extraction)
            payload = _build_output_payload(extraction.model_dump(), pdf_file, audit)

            record: Dict[str, object] = {
                "file_path": str(pdf_file),
                "weak_extraction": weak,
                "audit_weak": audit["weak"],
                "audit_score": audit["score"],
                "audit_reasons": audit["reasons"],
                "page_count": len(extraction.pages),
                "full_text_length": len(extraction.full_text),
                "block_count": sum(len(page.blocks) for page in extraction.pages),
                "section_count": len(extraction.sections),
                "fallback_triggered": bool(extraction.metadata.get("fallback_triggered")),
            }
            results.append(record)

            if audit["weak"]:
                weak_files.append(record)

            if output_path is not None:
                _append_json_line(output_path, payload)

            print(
                f"[OK] {pdf_file.name} | pages={record['page_count']} "
                f"text={record['full_text_length']} weak={audit['weak']} score={audit['score']}"
            )
        except Exception as exc:
            failure = {"file_path": str(pdf_file), "error": str(exc)}
            failures.append(failure)
            print(f"[ERROR] {pdf_file.name} | {exc}")

    summary = {
        "input_dir": str(input_dir),
        "total_files": len(pdf_files),
        "processed_files": len(results),
        "failed_files": len(failures),
        "weak_files": len(weak_files),
        "strict_weak_files": len(weak_files),
        "failures": failures,
        "weak_file_details": weak_files,
    }

    if report:
        report_path = Path(report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote batch report to {report_path}")

    print(
        f"Completed batch extraction: total={summary['total_files']} "
        f"processed={summary['processed_files']} weak={summary['weak_files']} "
        f"failed={summary['failed_files']}"
    )


def _append_json_line(output_path: Path, payload: Dict[str, object]) -> None:
    """Append one JSON object to a JSONL-style file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _build_output_payload(
    payload: Dict[str, object], input_path: Path, audit: Dict[str, object]
) -> Dict[str, object]:
    """Attach consistent metadata for appended JSONL records."""

    output_payload = dict(payload)
    output_payload["file_path"] = str(input_path)
    output_payload["audit"] = audit
    return output_payload


if __name__ == "__main__":
    main()
