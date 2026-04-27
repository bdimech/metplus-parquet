#!/usr/bin/env python3
"""
Convert METplus GridStat .stat output files to a single Parquet file.

Supports a folder of daily output directories or a zip archive.
Merges CNT, SL1L2, and SAL1L2 line types into one row per
init date / lead / level / domain — no duplicated columns.
Incremental: skips init dates already present in the parquet.

Usage:
    python convert_to_parquet.py --input <folder_or_zip> [--output <dir>]

Output parquet is named from the input folder/zip (e.g. AGlobal4_Analysis_T_AllLevels_00Z.parquet).
If --output is omitted it is written alongside the input.
"""

import argparse
import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Confirmed constant across the dataset — stored as file metadata, not columns
METADATA_COLS = [
    "VERSION", "MODEL", "DESC", "OBS_LEAD",
    "FCST_VAR", "FCST_UNITS", "OBS_VAR", "OBS_UNITS",
    "OBTYPE", "INTERP_MTHD", "INTERP_PNTS",
    "FCST_THRESH", "OBS_THRESH", "COV_THRESH",
]

LINE_TYPE_SUFFIXES = {
    "CNT":    "_cnt.txt",
    "SL1L2":  "_sl1l2.txt",
    "SAL1L2": "_sal1l2.txt",
}

# Keys that uniquely identify one row in the merged output
MERGE_KEYS = ["INIT_DATE", "FCST_LEAD_H", "FCST_VALID_BEG", "FCST_LEV", "VX_MASK"]

# Columns unique to SL1L2 — everything else is already in CNT
SL1L2_UNIQUE = ["FOBAR", "FFBAR", "OOBAR"]

# Columns unique to SAL1L2 — everything else is already in CNT
SAL1L2_UNIQUE = ["FABAR", "OABAR", "FOABAR", "FFABAR", "OOABAR"]

INIT_DATE_RE = re.compile(r"^\d{10}$")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _parse_file(content, init_date):
    df = pd.read_csv(io.StringIO(content), sep=r"\s+", na_values="NA")
    df.insert(0, "INIT_DATE", init_date)
    return df


def _read_zip(zip_path, suffix, skip_dates):
    frames = []
    with zipfile.ZipFile(zip_path) as z:
        for fname in z.namelist():
            if not fname.endswith(suffix):
                continue
            folder = fname.split("/")[0]
            if not INIT_DATE_RE.match(folder):
                continue
            init_date = datetime.strptime(folder, "%Y%m%d%H")
            if init_date in skip_dates:
                continue
            with z.open(fname) as f:
                frames.append(_parse_file(f.read().decode("utf-8"), init_date))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _read_folder(folder_path, suffix, skip_dates):
    frames = []
    for subdir in sorted(Path(folder_path).iterdir()):
        if not subdir.is_dir() or not INIT_DATE_RE.match(subdir.name):
            continue
        init_date = datetime.strptime(subdir.name, "%Y%m%d%H")
        if init_date in skip_dates:
            continue
        for f in subdir.glob(f"*{suffix}"):
            frames.append(_parse_file(f.read_text(encoding="utf-8"), init_date))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def read_line_type(input_path, suffix, skip_dates):
    is_zip = Path(input_path).suffix == ".zip"
    return _read_zip(input_path, suffix, skip_dates) if is_zip else _read_folder(input_path, suffix, skip_dates)


# ---------------------------------------------------------------------------
# Transforming
# ---------------------------------------------------------------------------

def lead_to_hours(fcst_lead):
    """Convert MET FCST_LEAD from HHMMSS integer to hours (e.g. 120000 -> 12)."""
    return int(fcst_lead) // 10000


def extract_metadata(df, input_path):
    """Pull constant column values into a metadata dict before they are dropped."""
    meta = {
        "source": str(input_path),
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    for col in METADATA_COLS:
        if col not in df.columns:
            continue
        vals = df[col].dropna().unique()
        meta[col] = ",".join(str(v) for v in vals)
    return meta


def clean(df):
    """Drop metadata + LINE_TYPE columns, convert lead time and datetimes."""
    drop = [c for c in METADATA_COLS + ["LINE_TYPE", "ALPHA"] if c in df.columns]
    df = df.drop(columns=drop)
    if "FCST_LEAD" in df.columns:
        df.insert(1, "FCST_LEAD_H", df["FCST_LEAD"].apply(lead_to_hours))
        df = df.drop(columns=["FCST_LEAD"])
    for col in ["FCST_VALID_BEG", "FCST_VALID_END", "OBS_VALID_BEG", "OBS_VALID_END"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%Y%m%d_%H%M%S")
    return df


def merge_line_types(cnt, sl1l2, sal1l2):
    """CNT is the base. Join only the unique columns from SL1L2 and SAL1L2."""
    merged = cnt
    if not sl1l2.empty:
        cols = MERGE_KEYS + [c for c in SL1L2_UNIQUE if c in sl1l2.columns]
        merged = merged.merge(sl1l2[cols], on=MERGE_KEYS, how="left")
    if not sal1l2.empty:
        cols = MERGE_KEYS + [c for c in SAL1L2_UNIQUE if c in sal1l2.columns]
        merged = merged.merge(sal1l2[cols], on=MERGE_KEYS, how="left")
    return merged


# ---------------------------------------------------------------------------
# Parquet I/O
# ---------------------------------------------------------------------------

def get_existing_dates(parquet_path):
    if not Path(parquet_path).exists():
        return set()
    table = pq.read_table(parquet_path, columns=["INIT_DATE"])
    return set(table.to_pandas()["INIT_DATE"].unique())


def write_parquet(df, metadata, parquet_path):
    table = pa.Table.from_pandas(df)
    encoded = {k.encode(): v.encode() for k, v in metadata.items()}
    table = table.replace_schema_metadata({**table.schema.metadata, **encoded})
    pq.write_table(table, parquet_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def convert(input_path, output_dir=None):
    input_path = Path(input_path)
    stem = input_path.stem  # folder or zip name without extension
    out_dir = Path(output_dir) if output_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / f"{stem}.parquet"

    existing_dates = get_existing_dates(parquet_path)
    if existing_dates:
        print(f"Skipping {len(existing_dates)} already-loaded init date(s).")

    print("Reading CNT...")
    cnt_raw = read_line_type(input_path, "_cnt.txt", existing_dates)
    if cnt_raw.empty:
        print("No new data found.")
        return

    metadata = extract_metadata(cnt_raw, input_path)

    print("Reading SL1L2...")
    sl1l2_raw = read_line_type(input_path, "_sl1l2.txt", existing_dates)
    print("Reading SAL1L2...")
    sal1l2_raw = read_line_type(input_path, "_sal1l2.txt", existing_dates)

    cnt    = clean(cnt_raw)
    sl1l2  = clean(sl1l2_raw)  if not sl1l2_raw.empty  else pd.DataFrame()
    sal1l2 = clean(sal1l2_raw) if not sal1l2_raw.empty else pd.DataFrame()

    print("Merging line types...")
    new_data = merge_line_types(cnt, sl1l2, sal1l2)

    if parquet_path.exists():
        print("Appending to existing parquet...")
        existing = pq.read_table(parquet_path).to_pandas()
        new_data = pd.concat([existing, new_data], ignore_index=True)

    write_parquet(new_data, metadata, parquet_path)
    print(f"Written: {parquet_path}  ({len(new_data):,} rows total)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert METplus GridStat .stat files to Parquet."
    )
    parser.add_argument("--input",  required=True, help="Folder or zip of GridStat outputs")
    parser.add_argument("--output", default=None,  help="Output directory (default: alongside input)")
    args = parser.parse_args()
    convert(args.input, args.output)


if __name__ == "__main__":
    main()
