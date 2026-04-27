"""
Tests for convert_functions.py — one test per function, focused on what is
likely to break: data transformations, merges, type conversions, and guards.
"""

from datetime import datetime

import pandas as pd
import pyarrow.parquet as pq
import pytest

from convert_functions import (
    clean,
    convert,
    extract_metadata,
    get_existing_dates,
    lead_to_hours,
    merge_line_types,
    parse_file,
    read_folder,
    read_line_type,
    write_parquet,
    METADATA_COLS,
    MERGE_KEYS,
    SAL1L2_UNIQUE,
    SL1L2_UNIQUE,
)

INIT_DATE = datetime(2026, 4, 10)


def test_lead_to_hours():
    assert lead_to_hours(120000) == 12
    assert lead_to_hours(2400000) == 240
    assert lead_to_hours("360000") == 36


def test_parse_file(cnt_content):
    df = parse_file(cnt_content, INIT_DATE)
    assert df.columns[0] == "INIT_DATE"
    assert df["INIT_DATE"].iloc[0] == INIT_DATE
    assert df["FCST_THRESH"].isna().all()
    assert df["RMSE"].iloc[0] == pytest.approx(1.87)


def test_read_folder(sample_folder):
    df = read_folder(sample_folder, "_cnt.txt", skip_dates=set())
    assert len(df) > 0
    assert read_folder(sample_folder, "_cnt.txt", skip_dates={INIT_DATE}).empty
    (sample_folder / "logs").mkdir()
    assert len(read_folder(sample_folder, "_cnt.txt", skip_dates=set())) == 1


def test_read_line_type(sample_folder):
    assert len(read_line_type(sample_folder, "_cnt.txt", skip_dates=set())) > 0
    assert read_line_type(sample_folder, "_cnt.txt", skip_dates={INIT_DATE}).empty


def test_extract_metadata(cnt_content, tmp_path):
    df = parse_file(cnt_content, INIT_DATE)
    meta = extract_metadata(df, tmp_path)
    assert meta["MODEL"] == "AGlobal4"
    assert meta["FCST_VAR"] == "t"
    assert "source" in meta and "created_at" in meta


def test_clean(cnt_content):
    df = clean(parse_file(cnt_content, INIT_DATE))
    for col in METADATA_COLS + ["LINE_TYPE", "ALPHA", "FCST_LEAD"]:
        assert col not in df.columns
    assert df["FCST_LEAD_H"].iloc[0] == 12
    assert pd.api.types.is_datetime64_any_dtype(df["FCST_VALID_BEG"])


def test_merge_line_types(cnt_content, sl1l2_content, sal1l2_content):
    cnt    = clean(parse_file(cnt_content,    INIT_DATE))
    sl1l2  = clean(parse_file(sl1l2_content,  INIT_DATE))
    sal1l2 = clean(parse_file(sal1l2_content, INIT_DATE))
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
        clean(parse_file(cnt_content,    INIT_DATE)),
        clean(parse_file(sl1l2_content,  INIT_DATE)),
        clean(parse_file(sal1l2_content, INIT_DATE)),
    )
    write_parquet(merged, {}, parquet_path)
    assert INIT_DATE in get_existing_dates(parquet_path)


def test_write_parquet(tmp_path, cnt_content, sl1l2_content, sal1l2_content):
    parquet_path = tmp_path / "out.parquet"
    merged = merge_line_types(
        clean(parse_file(cnt_content,    INIT_DATE)),
        clean(parse_file(sl1l2_content,  INIT_DATE)),
        clean(parse_file(sal1l2_content, INIT_DATE)),
    )
    write_parquet(merged, {"MODEL": "AGlobal4"}, parquet_path)
    assert parquet_path.exists()
    meta = {k.decode(): v.decode() for k, v in pq.read_table(parquet_path).schema.metadata.items()}
    assert meta["MODEL"] == "AGlobal4"


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
