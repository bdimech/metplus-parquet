#!/usr/bin/env python3
"""
Convert METplus GridStat .stat output files from a zip archive to Parquet format.

Usage:
    python convert_to_parquet.py --input <zip_path> --output <output_dir>

One parquet file is written per line type (CNT, SL1L2, SAL1L2).
Constant columns are stripped from rows and stored as file-level metadata.
"""

import argparse
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Columns confirmed constant across this dataset — stored as parquet metadata, not rows
METADATA_COLS = [
    "VERSION", "MODEL", "DESC", "OBS_LEAD",
    "FCST_VAR", "FCST_UNITS", "OBS_VAR", "OBS_UNITS",
    "OBTYPE", "INTERP_MTHD", "INTERP_PNTS",
    "FCST_THRESH", "OBS_THRESH", "COV_THRESH",
]

# Maps line type name to the file suffix used by METplus
LINE_TYPE_SUFFIXES = {
    "CNT":    "_cnt.txt",
    "SL1L2":  "_sl1l2.txt",
    "SAL1L2": "_sal1l2.txt",
}


def lead_to_hours(fcst_lead):
    """Convert MET FCST_LEAD from HHMMSS integer to hours (e.g. 120000 -> 12)."""
    return int(fcst_lead) // 10000


def read_line_type_files(zip_path, suffix):
    """Read all files matching suffix from zip into a single DataFrame."""
    frames = []
    with zipfile.ZipFile(zip_path) as z:
        matched = [n for n in z.namelist() if n.endswith(suffix)]
        if not matched:
            raise FileNotFoundError(f"No files with suffix '{suffix}' found in zip.")
        for fname in matched:
            folder = fname.split("/")[0]
            init_date = datetime.strptime(folder, "%Y%m%d%H")
            with z.open(fname) as f:
                content = f.read().decode("utf-8")
            df = pd.read_csv(io.StringIO(content), sep=r"\s+", na_values="NA")
            df.insert(0, "INIT_DATE", init_date)
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def extract_metadata(df, line_type):
    """Build file-level metadata dict from constant columns."""
    metadata = {"LINE_TYPE": line_type, "created_at": datetime.now(tz=timezone.utc).isoformat()}
    for col in METADATA_COLS:
        if col not in df.columns:
            continue
        unique_vals = df[col].dropna().unique()
        metadata[col] = ",".join(str(v) for v in unique_vals)
    return metadata


def clean_dataframe(df):
    """Drop metadata columns, convert lead time to hours, parse valid times."""
    drop_cols = [c for c in METADATA_COLS + ["LINE_TYPE"] if c in df.columns]
    df = df.drop(columns=drop_cols)

    if "FCST_LEAD" in df.columns:
        df.insert(
            df.columns.get_loc("FCST_VALID_BEG") if "FCST_VALID_BEG" in df.columns else 0,
            "FCST_LEAD_H",
            df["FCST_LEAD"].apply(lead_to_hours),
        )
        df = df.drop(columns=["FCST_LEAD"])

    for col in ["FCST_VALID_BEG", "FCST_VALID_END", "OBS_VALID_BEG", "OBS_VALID_END"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%Y%m%d_%H%M%S")

    return df


def write_parquet(df, metadata, output_path):
    """Write DataFrame to parquet with embedded file-level metadata."""
    table = pa.Table.from_pandas(df)
    encoded_meta = {k.encode(): v.encode() for k, v in metadata.items()}
    table = table.replace_schema_metadata({**table.schema.metadata, **encoded_meta})
    pq.write_table(table, output_path)
    print(f"  Written: {output_path}  ({len(df):,} rows)")


def convert(zip_path, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for line_type, suffix in LINE_TYPE_SUFFIXES.items():
        print(f"Processing {line_type}...")
        df = read_line_type_files(zip_path, suffix)
        metadata = extract_metadata(df, line_type)
        df = clean_dataframe(df)
        write_parquet(df, metadata, output_dir / f"{line_type.lower()}.parquet")

    print("\nDone.")


def main():
    parser = argparse.ArgumentParser(
        description="Convert METplus GridStat .stat files to Parquet."
    )
    parser.add_argument("--input",  required=True, help="Path to the zip file")
    parser.add_argument("--output", required=True, help="Output directory for parquet files")
    args = parser.parse_args()
    convert(args.input, args.output)


if __name__ == "__main__":
    main()
