"""CLI for reporting unrecovered source-backed content from Phase 2 JSONL results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase2.reporting.coverage_report import analyze_phase2_results, load_phase2_results


def main() -> None:
    """Analyze a Phase 2 JSONL file and report unrecovered source-backed content."""

    parser = argparse.ArgumentParser(
        description="Analyze Phase 2 coverage gaps from a JSONL results file."
    )
    parser.add_argument("results_path", help="Path to a Phase 2 JSONL results file")
    parser.add_argument(
        "--output",
        help="Optional path to write the full JSON coverage report",
    )
    args = parser.parse_args()

    rows = load_phase2_results(args.results_path)
    report = analyze_phase2_results(rows)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Wrote coverage report to {0}".format(output_path))

    print(
        "Coverage gaps: total_rows={0} rows_with_missing={1}".format(
            report["total_rows"],
            report["rows_with_missing_source_backed_content"],
        )
    )
    for field_name, stats in report["summary"].items():
        if stats["rows_affected"] == 0:
            continue
        print(
            "{0}: rows={1} phase2_input_missing={2} parser_missing={3}".format(
                field_name,
                stats["rows_affected"],
                stats["phase2_input_missing_count"],
                stats["parser_missing_count"],
            )
        )


if __name__ == "__main__":
    main()
