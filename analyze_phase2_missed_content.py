"""CLI for benchmarking Phase 2 recovery against missed_from_raw_text CSV data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase2.reporting.missed_content_report import (
    evaluate_phase2_missed_content,
    load_missed_csv,
    load_phase2_results,
)


def main() -> None:
    """Compare a Phase 2 JSONL results file against the missed-content benchmark CSV."""

    parser = argparse.ArgumentParser(
        description="Evaluate whether Phase 2 recovered content listed in missed_from_raw_text."
    )
    parser.add_argument("csv_path", help="Path to parsed_vs_raw_with_missed_column.csv")
    parser.add_argument("results_path", help="Path to a Phase 2 JSONL results file")
    parser.add_argument("--output", help="Optional JSON output path for the full report")
    args = parser.parse_args()

    report = evaluate_phase2_missed_content(
        load_missed_csv(args.csv_path),
        load_phase2_results(args.results_path),
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Wrote missed-content report to {0}".format(output_path))

    print(
        "Missed-content recovery: rows_with_missed={0} rows_with_any_recovered={1} total_chunks={2} recovered_chunks={3} recovery_rate={4}".format(
            report["total_rows_with_missed_content"],
            report["rows_with_any_recovered_content"],
            report["total_missed_chunks"],
            report["recovered_chunks"],
            report["recovery_rate"],
        )
    )


if __name__ == "__main__":
    main()
