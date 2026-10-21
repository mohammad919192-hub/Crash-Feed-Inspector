"""Command-line entry point for capture and offline research workflows."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

from .analytics import describe, walk_forward_baseline
from .capture import capture
from .dataset import load_rounds_csv, quality_report, verified_multipliers
from .report import generate_dashboard


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crash-feed-inspector")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("capture", help="Capture a bounded authorized WebSocket sample")

    validate = subparsers.add_parser("validate-csv", help="Validate a historical CSV dataset")
    validate.add_argument("csv_path", type=Path)

    analyze = subparsers.add_parser("analyze-csv", help="Analyze explicitly verified CSV rows only")
    analyze.add_argument("csv_path", type=Path)
    analyze.add_argument("--threshold", type=float, default=2.0)
    analyze.add_argument("--min-train", type=int, default=30)

    dashboard = subparsers.add_parser("dashboard-csv", help="Generate a local HTML report from verified CSV rows")
    dashboard.add_argument("csv_path", type=Path)
    dashboard.add_argument("--output", type=Path, default=Path("data/dashboard.html"))
    dashboard.add_argument("--threshold", type=float, default=2.0)

    args = parser.parse_args(argv)
    if args.command in (None, "capture"):
        capture()
        return 0

    rows = load_rounds_csv(args.csv_path)
    report = {"quality": quality_report(rows)}
    if args.command == "dashboard-csv":
        if args.threshold < 1 or not math.isfinite(args.threshold):
            parser.error("--threshold must be a finite number >= 1.0.")
        try:
            output = generate_dashboard(rows, args.output, threshold=args.threshold)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({
            "dashboard_path": str(output),
            "verified_rows": report["quality"]["verified_rows"],
            "threshold": args.threshold,
            "interpretation": "Static local report; not a live dashboard or a prediction guarantee.",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "analyze-csv":
        if args.min_train < 1:
            parser.error("--min-train must be a positive integer.")
        if args.threshold < 1 or not math.isfinite(args.threshold):
            parser.error("--threshold must be a finite number >= 1.0.")
        data = verified_multipliers(rows)
        if not data:
            parser.error("No rows are explicitly verified=true; refusing to analyze unverified candidates.")
        report["verified_analysis"] = describe(data, thresholds=(1.5, 2.0, 3.0, 5.0))
        if len(data) > args.min_train:
            report["walk_forward_baseline"] = walk_forward_baseline(
                data, threshold=args.threshold, min_train=args.min_train
            )
        else:
            report["walk_forward_baseline"] = {
                "status": "insufficient_data",
                "verified_rows": len(data),
                "required_rows": f"more than {args.min_train}",
            }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
