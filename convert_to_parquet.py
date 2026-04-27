#!/usr/bin/env python3
"""
Entry point for converting METplus GridStat .stat files to Parquet.

Usage:
    python convert_to_parquet.py --input <folder> [--output <dir>]
"""

import argparse

from convert_functions import convert


def main():
    parser = argparse.ArgumentParser(
        description="Convert METplus GridStat .stat files to Parquet."
    )
    parser.add_argument("--input",  required=True, help="Folder of GridStat daily output directories")
    parser.add_argument("--output", default=None,  help="Output directory (default: alongside input folder)")
    args = parser.parse_args()
    convert(args.input, args.output)


if __name__ == "__main__":
    main()
