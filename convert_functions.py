"""
Functions for converting METplus GridStat .stat output files to Parquet format.
"""

import io
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

METADATA_COLS = [
    "VERSION", "MODEL", "DESC", "OBS_LEAD",
    "FCST_VAR", "FCST_UNITS", "OBS_VAR", "OBS_UNITS",
    "OBTYPE", "INTERP_MTHD", "INTERP_PNTS",
    "FCST_THRESH", "OBS_THRESH", "COV_THRESH",
]

MERGE_KEYS = ["INIT_DATE", "FCST_LEAD_H", "FCST_VALID_BEG", "FCST_LEV", "VX_MASK"]

SL1L2_UNIQUE = ["FOBAR", "FFBAR", "OOBAR"]
SAL1L2_UNIQUE = ["FABAR", "OABAR", "FOABAR", "FFABAR", "OOABAR"]

INIT_DATE_RE = re.compile(r"^\d{10}$")


def lead_to_hours(fcst_lead: int | str) -> int:
    """Convert a MET FCST_LEAD value from HHMMSS integer to hours.

    Args:
        fcst_lead (int | str): lead time in HHMMSS format (e.g. 120000 for 12h).

    Returns:
        int: lead time in hours.
    """
    return int(fcst_lead) // 10000


def parse_file(content: str, init_date: datetime) -> pd.DataFrame:
    """Parse a single METplus .stat or line-type text file into a DataFrame.

    Args:
        content (str): raw text content of the file.
        init_date (datetime): initialisation date parsed from the parent folder name.

    Returns:
        pd.DataFrame: parsed data with INIT_DATE as the first column.
    """
    df = pd.read_csv(io.StringIO(content), sep=r"\s+", na_values="NA")
    df.insert(0, "INIT_DATE", init_date)
    return df


def read_folder(folder_path: str | Path, suffix: str, skip_dates: set) -> pd.DataFrame:
    """Read all files matching a suffix from a folder of YYYYMMDDHH subdirectories.

    Args:
        folder_path (str | Path): path to the folder containing daily subdirectories.
        suffix (str): file suffix to match (e.g. '_cnt.txt').
        skip_dates (set): init dates already loaded — matching subdirectories are skipped.

    Returns:
        pd.DataFrame: concatenated data from all matched files, empty DataFrame if none found.
    """
    frames = []
    for subdir in sorted(Path(folder_path).iterdir()):
        if not subdir.is_dir() or not INIT_DATE_RE.match(subdir.name):
            continue
        init_date = datetime.strptime(subdir.name, "%Y%m%d%H")
        if init_date in skip_dates:
            continue
        for f in subdir.glob(f"*{suffix}"):
            frames.append(parse_file(f.read_text(encoding="utf-8"), init_date))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def read_line_type(folder_path: str | Path, suffix: str, skip_dates: set) -> pd.DataFrame:
    """Read all files of a given METplus line type from a GridStat output folder.

    Args:
        folder_path (str | Path): path to the folder containing daily subdirectories.
        suffix (str): line-type file suffix (e.g. '_cnt.txt', '_sl1l2.txt').
        skip_dates (set): init dates to skip (already present in the parquet).

    Returns:
        pd.DataFrame: concatenated data for the requested line type.
    """
    return read_folder(folder_path, suffix, skip_dates)


def extract_metadata(df: pd.DataFrame, folder_path: str | Path) -> dict:
    """Extract constant column values into a metadata dictionary.

    Args:
        df (pd.DataFrame): raw DataFrame containing METADATA_COLS columns.
        folder_path (str | Path): source folder path recorded as provenance.

    Returns:
        dict: metadata key/value pairs for embedding in the parquet file.
    """
    meta = {
        "source": str(folder_path),
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    for col in METADATA_COLS:
        if col not in df.columns:
            continue
        vals = df[col].dropna().unique()
        meta[col] = ",".join(str(v) for v in vals)
    return meta


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Remove metadata columns and convert lead time and valid times to usable types.

    Args:
        df (pd.DataFrame): raw parsed DataFrame including metadata and LINE_TYPE columns.

    Returns:
        pd.DataFrame: cleaned DataFrame with FCST_LEAD_H (hours) and datetime columns.
    """
    drop = [c for c in METADATA_COLS + ["LINE_TYPE", "ALPHA"] if c in df.columns]
    df = df.drop(columns=drop)
    if "FCST_LEAD" in df.columns:
        df.insert(1, "FCST_LEAD_H", df["FCST_LEAD"].apply(lead_to_hours))
        df = df.drop(columns=["FCST_LEAD"])
    for col in ["FCST_VALID_BEG", "FCST_VALID_END", "OBS_VALID_BEG", "OBS_VALID_END"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%Y%m%d_%H%M%S")
    return df


def merge_line_types(cnt: pd.DataFrame, sl1l2: pd.DataFrame, sal1l2: pd.DataFrame) -> pd.DataFrame:
    """Merge CNT, SL1L2, and SAL1L2 into one row per init date / lead / level / domain.

    CNT is used as the base. Only the columns unique to SL1L2 and SAL1L2 are joined,
    so shared columns such as FBAR, OBAR, and MAE are not duplicated.

    Args:
        cnt (pd.DataFrame): cleaned CNT line-type DataFrame.
        sl1l2 (pd.DataFrame): cleaned SL1L2 line-type DataFrame (may be empty).
        sal1l2 (pd.DataFrame): cleaned SAL1L2 line-type DataFrame (may be empty).

    Returns:
        pd.DataFrame: merged DataFrame with one row per unique combination.
    """
    merged = cnt
    if not sl1l2.empty:
        cols = MERGE_KEYS + [c for c in SL1L2_UNIQUE if c in sl1l2.columns]
        merged = merged.merge(sl1l2[cols], on=MERGE_KEYS, how="left")
    if not sal1l2.empty:
        cols = MERGE_KEYS + [c for c in SAL1L2_UNIQUE if c in sal1l2.columns]
        merged = merged.merge(sal1l2[cols], on=MERGE_KEYS, how="left")
    return merged


def get_existing_dates(parquet_path: str | Path) -> set:
    """Return the set of INIT_DATE values already present in a parquet file.

    Args:
        parquet_path (str | Path): path to the existing parquet file.

    Returns:
        set: existing init dates, or an empty set if the file does not exist.
    """
    if not Path(parquet_path).exists():
        return set()
    table = pq.read_table(parquet_path, columns=["INIT_DATE"])
    return set(table.to_pandas()["INIT_DATE"].unique())


def write_parquet(df: pd.DataFrame, metadata: dict, parquet_path: str | Path) -> None:
    """Write a DataFrame to a parquet file with embedded file-level metadata.

    Args:
        df (pd.DataFrame): data to write.
        metadata (dict): key/value pairs to embed in the parquet schema metadata.
        parquet_path (str | Path): destination file path.

    Returns:
        None
    """
    table = pa.Table.from_pandas(df)
    encoded = {k.encode(): v.encode() for k, v in metadata.items()}
    table = table.replace_schema_metadata({**table.schema.metadata, **encoded})
    pq.write_table(table, parquet_path)


def convert(folder_path: str | Path, output_dir: str | Path = None) -> None:
    """Convert a folder of METplus GridStat outputs to a single parquet file.

    Walks YYYYMMDDHH subdirectories, merges CNT, SL1L2, and SAL1L2 line types,
    and appends only new init dates if a parquet file already exists.

    Args:
        folder_path (str | Path): folder containing daily GridStat output subdirectories.
        output_dir (str | Path): directory for the output parquet file. Defaults to
            the parent of folder_path.

    Returns:
        None
    """
    folder_path = Path(folder_path)
    out_dir = Path(output_dir) if output_dir else folder_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / f"{folder_path.name}.parquet"

    existing_dates = get_existing_dates(parquet_path)
    if existing_dates:
        print(f"Skipping {len(existing_dates)} already-loaded init date(s).")

    print("Reading CNT...")
    cnt_raw = read_line_type(folder_path, "_cnt.txt", existing_dates)
    if cnt_raw.empty:
        print("No new data found.")
        return

    metadata = extract_metadata(cnt_raw, folder_path)

    print("Reading SL1L2...")
    sl1l2_raw = read_line_type(folder_path, "_sl1l2.txt", existing_dates)
    print("Reading SAL1L2...")
    sal1l2_raw = read_line_type(folder_path, "_sal1l2.txt", existing_dates)

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
