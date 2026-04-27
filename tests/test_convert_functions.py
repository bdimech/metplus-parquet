"""
Tests for convert_functions.py — one test per public function, focused on what is
likely to break: data transformations, merges, type conversions, and guards.
"""

from datetime import datetime

import pandas as pd
import pyarrow.parquet as pq

from convert_functions import (
    _parse_file,
    _write_parquet,
    clean,
    convert,
    extract_metadata,
    get_existing_dates,
    merge_line_types,
    read_folder,
    METADATA_COLS,
    MERGE_KEYS,
    SAL1L2_UNIQUE,
    SL1L2_UNIQUE,
)

INIT_DATE = datetime(2026, 4, 10)


def test_read_folder(sample_folder):
    df = read_folder(sample_folder, "_cnt.txt", skip_dates=set())
    assert len(df) > 0
    assert read_folder(sample_folder, "_cnt.txt", skip_dates={INIT_DATE}).empty
    (sample_folder / "logs").mkdir()
    assert len(read_folder(sample_folder, "_cnt.txt", skip_dates=set())) == 1


def test_extract_metadata(cnt_content, tmp_path):
    df = _parse_file(cnt_content, INIT_DATE)
    meta = extract_metadata(df, tmp_path)
    assert meta["MODEL"] == "AGlobal4"
    assert meta["FCST_VAR"] == "t"
    assert "source" in meta and "created_at" in meta


def test_clean(cnt_content):
    df = clean(_parse_file(cnt_content, INIT_DATE))
    for col in METADATA_COLS + ["LINE_TYPE", "ALPHA", "FCST_LEAD"]:
        assert col not in df.columns
    assert df["FCST_LEAD_H"].iloc[0] == 12
    assert pd.api.types.is_datetime64_any_dtype(df["FCST_VALID_BEG"])


def test_merge_line_types(cnt_content, sl1l2_content, sal1l2_content):
    cnt    = clean(_parse_file(cnt_content,    INIT_DATE))
    sl1l2  = clean(_parse_file(sl1l2_content,  INIT_DATE))
    sal1l2 = clean(_parse_file(sal1l2_content, INIT_DATE))
    merged = merge_line_types(cnt, sl1l2, sal1l2)
    for col in SL1L2_UNIQUE + SAL1L2_UNIQUE:
        assert col in merged.columns
    assert merged.columns.tolist().count("FBAR") == 1
    assert len(merged) == 1
    assert len(merge_line_types(cnt, pd.DataFrame(), sal1l2)) == 1


def test_get_existing_dates(tmp_path, cnt_content, sl1l2_content, sal1l2_content):
    assert get_existing_dates(tmp_path / "missing.parquet") == set()
    parquet_path = tmp_path / "test.parquet"
    merged = merge_line_types(
        clean(_parse_file(cnt_content,    INIT_DATE)),
        clean(_parse_file(sl1l2_content,  INIT_DATE)),
        clean(_parse_file(sal1l2_content, INIT_DATE)),
    )
    _write_parquet(merged, {}, parquet_path)
    assert INIT_DATE in get_existing_dates(parquet_path)


def test_convert(real_data_folder, tmp_path):
    convert(real_data_folder, tmp_path)
    parquet_path = tmp_path / f"{real_data_folder.name}.parquet"
    assert parquet_path.exists()
    df = pq.read_table(parquet_path).to_pandas()
    for col in METADATA_COLS:
        assert col not in df.columns
    key_cols = [k for k in MERGE_KEYS if k in df.columns]
    assert not df.duplicated(subset=key_cols).any()
    initial_count = len(df)
    convert(real_data_folder, tmp_path)
    assert len(pq.read_table(parquet_path).to_pandas()) == initial_count
