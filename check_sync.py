#!/usr/bin/env python3
"""
Health check: audit input folders against Parquet output files.

Distinguishes between:
  - OK            data is in the Parquet (loaded or archived)
  - Pending       today's daily run has not yet executed
  - Missed run    date absent from both input and Parquet, within retention window
  - Historical    date absent from both input and Parquet, beyond retention window
  - Needs loading date is in input but not yet written to Parquet (use --fix to load)

Usage:
    python check_sync.py --input <input_dir> --output <output_dir>
    python check_sync.py --input <input_dir> --output <output_dir> --fix
    python check_sync.py --input <input_dir> --output <output_dir> --retention-days 7
"""

import argparse
import sys
from pathlib import Path

from check_functions import run_check


def main():
    parser = argparse.ArgumentParser(
        description="Audit input folders against Parquet outputs and report sync status."
    )
    parser.add_argument(
        "--input", required=True,
        help="Directory containing METplus config folders.",
    )
    parser.add_argument(
        "--output", required=True,
        help="Directory containing Parquet output files.",
    )
    parser.add_argument(
        "--retention-days", type=int, default=5, metavar="N",
        help="Days that input data is kept on disk (default: 5). "
             "Dates older than this missing from input but present in Parquet are OK.",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Load any dates flagged as 'needs loading' into the Parquet files.",
    )
    args = parser.parse_args()

    has_issues = run_check(
        input_dir  = Path(args.input),
        output_dir = Path(args.output),
        retention  = args.retention_days,
        fix        = args.fix,
    )
    sys.exit(1 if has_issues else 0)


if __name__ == "__main__":
    main()
