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
from .inspect import inspect_jsonl
from .report import generate_dashboard
from .research import research_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crash-feed-inspector")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("capture", help="Capture a bounded authorized WebSocket sample")

    inspect = subparsers.add_parser(
        "inspect-jsonl",
        help="Summarize local sanitized WebSocket samples without assuming a schema",
    )
    inspect.add_argument("jsonl_path", nargs="?", type=Path, default=Path("data/messages.jsonl"))
    inspect.add_argument("--max-messages", type=int, default=100)

    validate = subparsers.add_parser("validate-csv", help="Validate a historical CSV dataset")
    validate.add_argument("csv_path", type=Path)

    analyze = subparsers.add_parser("analyze-csv", help="Analyze explicitly verified CSV rows only")
    analyze.add_argument("csv_path", type=Path)
    analyze.add_argument("--threshold", type=float, default=2.0)
    analyze.add_argument("--min-train", type=int, default=30)

    research = subparsers.add_parser(
        "research-csv",
        help="Run transparent historical-frequency, uncertainty, and stability filters",
    )
    research.add_argument("csv_path", type=Path)
    research.add_argument("--thresholds", type=float, nargs="+", default=[1.5, 2.0, 3.0, 5.0])
    research.add_argument("--windows", type=int, nargs="+", default=[30, 100, 300])
    research.add_argument("--min-history", type=int, default=100)
    research.add_argument("--max-window-rate-gap", type=float, default=0.15)

    dashboard = subparsers.add_parser("dashboard-csv", help="Generate a local HTML report from verified CSV rows")
    dashboard.add_argument("csv_path", type=Path)
    dashboard.add_argument("--output", type=Path, default=Path("data/dashboard.html"))
    dashboard.add_argument("--threshold", type=float, default=2.0)

    args = parser.parse_args(argv)
    if args.command in (None, "capture"):
        capture()
        return 0

    if args.command == "inspect-jsonl":
        if not 1 <= args.max_messages <= 1000:
            parser.error("--max-messages must be between 1 and 1000.")
        try:
            report = inspect_jsonl(args.jsonl_path, max_messages=args.max_messages)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    try:
        rows = load_rounds_csv(args.csv_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    report = {"quality": quality_report(rows)}

    if args.command == "research-csv":
        verified_rows = [row for row in rows if row.get("verified") is True]
        if not verified_rows:
            parser.error("No rows are explicitly verified=true; refusing to analyze unverified candidates.")

        # Multiplier-only research cannot establish chronology. Require every verified
        # row to have a timestamp and confirm that those timestamps are oldest-to-newest.
        verified_quality = quality_report(verified_rows)
        if verified_quality["missing_timestamps"]:
            report["research"] = {
                "status": "no_signal_missing_timestamps",
                "verified_rows": len(verified_rows),
                "missing_timestamps": verified_quality["missing_timestamps"],
                "interpretation": (
                    "Research was not run because verified rows need timestamps to confirm "
                    "oldest-to-newest ordering."
                ),
            }
        elif verified_quality["chronology_violations"]:
            report["research"] = {
                "status": "no_signal_chronology_invalid",
                "verified_rows": len(verified_rows),
                "chronology_violations": verified_quality["chronology_violations"],
                "interpretation": (
                    "Research was not run because verified CSV rows are not ordered oldest-to-newest."
                ),
            }
        else:
            data = verified_multipliers(verified_rows)
            try:
                report["research"] = research_report(
                    data,
                    thresholds=tuple(args.thresholds),
                    windows=tuple(args.windows),
                    min_history=args.min_history,
                    max_window_rate_gap=args.max_window_rate_gap,
                )
            except ValueError as exc:
                parser.error(str(exc))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

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
        verified_rows = [row for row in rows if row.get("verified") is True]
        data = verified_multipliers(verified_rows)
        if not data:
            parser.error("No rows are explicitly verified=true; refusing to analyze unverified candidates.")
        report["verified_analysis"] = describe(data, thresholds=(1.5, 2.0, 3.0, 5.0))
        verified_quality = quality_report(verified_rows)
        if verified_quality["missing_timestamps"]:
            report["walk_forward_baseline"] = {
                "status": "no_signal_missing_timestamps",
                "verified_rows": len(data),
                "missing_timestamps": verified_quality["missing_timestamps"],
                "interpretation": "Walk-forward evaluation was skipped because verified rows need timestamps to establish chronology.",
            }
        elif verified_quality["chronology_violations"]:
            report["walk_forward_baseline"] = {
                "status": "no_signal_chronology_invalid",
                "verified_rows": len(data),
                "chronology_violations": verified_quality["chronology_violations"],
                "interpretation": "Walk-forward evaluation was skipped because verified rows are not ordered oldest-to-newest.",
            }
        elif len(data) > args.min_train:
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
