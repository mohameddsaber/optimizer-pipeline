"""CLI for Phase 1 regression metrics."""

from __future__ import annotations

import argparse
import json

from extractor.reporting.regression_report import (
    build_phase1_regression_report,
    load_phase1_snapshot,
    write_phase1_regression_report,
)


def main() -> None:
    """Analyze a Phase 1 snapshot and report regression metrics."""

    parser = argparse.ArgumentParser(description="Analyze Phase 1 regression metrics.")
    parser.add_argument("snapshot_path", help="Path to a Phase 1 JSONL snapshot")
    parser.add_argument("--output", help="Optional JSON report output path")
    args = parser.parse_args()

    rows = load_phase1_snapshot(args.snapshot_path)
    report = build_phase1_regression_report(rows)

    if args.output:
        write_phase1_regression_report(args.output, report)
        print(f"Wrote Phase 1 regression report to {args.output}")
        return

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
