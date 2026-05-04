#!/usr/bin/env python3
"""
Entry point for converting METplus GridStat .stat files to Parquet.

Usage:
    python convert_to_parquet.py --input <folder> [--output <dir>]
    python convert_to_parquet.py --all --input <dir> --output <dir>
"""

import argparse

from convert_functions import convert, convert_all


def main():
    parser = argparse.ArgumentParser(
        description="Convert METplus GridStat .stat files to Parquet."
    )
    parser.add_argument(
        "--input", required=True,
        help="Single config folder, or directory of config folders when using --all",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output directory (required with --all; defaults to alongside --input otherwise)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Convert all config folders in --input, grouped by model/observation",
    )
    args = parser.parse_args()

    if args.all:
        if args.output is None:
            parser.error("--output is required when using --all")
        convert_all(args.input, args.output)
    else:
        convert(args.input, args.output)


if __name__ == "__main__":
    main()
