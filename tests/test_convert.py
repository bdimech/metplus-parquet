"""
Tests for convert_to_parquet.py.
One test group per function, named test_<function_name>_<behaviour>.
"""

from datetime import datetime

import pandas as pd
import pyarrow.parquet as pq
import pytest

from convert_to_parquet import (
    _parse_file,
    _read_folder,
    clean,
    convert,
    extract_metadata,
    get_existing_dates,
    lead_to_hours,
    merge_line_types,
    read_line_type,
    write_parquet,
    MERGE_KEYS,
    METADATA_COLS,
    SAL1L2_UNIQUE,
    SL1L2_UNIQUE,
)

INIT_DATE = datetime(2026, 4, 10)


# ---------------------------------------------------------------------------
# test_lead_to_hours
# ---------------------------------------------------------------------------

def test_lead_to_hours_12h():
    assert lead_to_hours(120000) == 12

def test_lead_to_hours_24h():
    assert lead_to_hours(240000) == 24

def test_lead_to_hours_240h():
    assert lead_to_hours(2400000) == 240

def test_lead_to_hours_accepts_string():
    assert lead_to_hours("360000") == 36


# ---------------------------------------------------------------------------
# test__parse_file
# ---------------------------------------------------------------------------

def test__parse_file_returns_dataframe(cnt_content):
    df = _parse_file(cnt_content, INIT_DATE)
    assert isinstance(df, pd.DataFrame)

def test__parse_file_adds_init_date(cnt_content):
    df = _parse_file(cnt_content, INIT_DATE)
    assert "INIT_DATE" in df.columns
    assert df["INIT_DATE"].iloc[0] == INIT_DATE

def test__parse_file_init_date_is_first_column(cnt_content):
    df = _parse_file(cnt_content, INIT_DATE)
    assert df.columns[0] == "INIT_DATE"

def test__parse_file_parses_na_as_nan(cnt_content):
    df = _parse_file(cnt_content, INIT_DATE)
    assert df["FCST_THRESH"].isna().all()

def test__parse_file_parses_numeric_values(cnt_content):
    df = _parse_file(cnt_content, INIT_DATE)
    assert df["RMSE"].iloc[0] == pytest.approx(1.87)


# ---------------------------------------------------------------------------
# test__read_folder
# ---------------------------------------------------------------------------

def test__read_folder_returns_dataframe(sample_folder):
    df = _read_folder(sample_folder, "_cnt.txt", skip_dates=set())
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0

def test__read_folder_skips_existing_dates(sample_folder):
    df = _read_folder(sample_folder, "_cnt.txt", skip_dates={INIT_DATE})
    assert len(df) == 0

def test__read_folder_adds_init_date(sample_folder):
    df = _read_folder(sample_folder, "_cnt.txt", skip_dates=set())
    assert "INIT_DATE" in df.columns
    assert df["INIT_DATE"].iloc[0] == INIT_DATE

def test__read_folder_ignores_non_date_dirs(sample_folder):
    (sample_folder / "not_a_date").mkdir()
    df = _read_folder(sample_folder, "_cnt.txt", skip_dates=set())
    assert len(df) == 1

def test__read_folder_returns_empty_for_unknown_suffix(sample_folder):
    df = _read_folder(sample_folder, "_unknown.txt", skip_dates=set())
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


# ---------------------------------------------------------------------------
# test_read_line_type
# ---------------------------------------------------------------------------

def test_read_line_type_reads_cnt(sample_folder):
    df = read_line_type(sample_folder, "_cnt.txt", skip_dates=set())
    assert len(df) > 0

def test_read_line_type_reads_sl1l2(sample_folder):
    df = read_line_type(sample_folder, "_sl1l2.txt", skip_dates=set())
    assert len(df) > 0

def test_read_line_type_skips_existing_dates(sample_folder):
    df = read_line_type(sample_folder, "_cnt.txt", skip_dates={INIT_DATE})
    assert len(df) == 0


# ---------------------------------------------------------------------------
# test_extract_metadata
# ---------------------------------------------------------------------------

def test_extract_metadata_captures_model(cnt_content, tmp_path):
    df = _parse_file(cnt_content, INIT_DATE)
    meta = extract_metadata(df, tmp_path)
    assert meta.get("MODEL") == "AGlobal4"

def test_extract_metadata_captures_fcst_var(cnt_content, tmp_path):
    df = _parse_file(cnt_content, INIT_DATE)
    meta = extract_metadata(df, tmp_path)
    assert meta.get("FCST_VAR") == "t"

def test_extract_metadata_includes_source(cnt_content, tmp_path):
    df = _parse_file(cnt_content, INIT_DATE)
    meta = extract_metadata(df, tmp_path)
    assert "source" in meta

def test_extract_metadata_includes_created_at(cnt_content, tmp_path):
    df = _parse_file(cnt_content, INIT_DATE)
    meta = extract_metadata(df, tmp_path)
    assert "created_at" in meta

def test_extract_metadata_captures_all_metadata_cols(cnt_content, tmp_path):
    df = _parse_file(cnt_content, INIT_DATE)
    meta = extract_metadata(df, tmp_path)
    for col in METADATA_COLS:
        if col in df.columns:
            assert col in meta, f"Missing metadata key: {col}"


# ---------------------------------------------------------------------------
# test_clean
# ---------------------------------------------------------------------------

def test_clean_removes_metadata_cols(cnt_content):
    df = clean(_parse_file(cnt_content, INIT_DATE))
    for col in METADATA_COLS:
        assert col not in df.columns

def test_clean_removes_line_type(cnt_content):
    df = clean(_parse_file(cnt_content, INIT_DATE))
    assert "LINE_TYPE" not in df.columns

def test_clean_removes_alpha(cnt_content):
    df = clean(_parse_file(cnt_content, INIT_DATE))
    assert "ALPHA" not in df.columns

def test_clean_replaces_fcst_lead_with_hours(cnt_content):
    df = clean(_parse_file(cnt_content, INIT_DATE))
    assert "FCST_LEAD" not in df.columns
    assert "FCST_LEAD_H" in df.columns

def test_clean_fcst_lead_h_correct_value(cnt_content):
    df = clean(_parse_file(cnt_content, INIT_DATE))
    assert df["FCST_LEAD_H"].iloc[0] == 12

def test_clean_converts_valid_times_to_datetime(cnt_content):
    df = clean(_parse_file(cnt_content, INIT_DATE))
    for col in ["FCST_VALID_BEG", "FCST_VALID_END", "OBS_VALID_BEG", "OBS_VALID_END"]:
        assert pd.api.types.is_datetime64_any_dtype(df[col]), f"{col} should be datetime"


# ---------------------------------------------------------------------------
# test_merge_line_types
# ---------------------------------------------------------------------------

def _make_clean(content, init_date=INIT_DATE):
    return clean(_parse_file(content, init_date))


def test_merge_line_types_sl1l2_unique_cols_present(cnt_content, sl1l2_content, sal1l2_content):
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    for col in SL1L2_UNIQUE:
        assert col in merged.columns

def test_merge_line_types_sal1l2_unique_cols_present(cnt_content, sl1l2_content, sal1l2_content):
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    for col in SAL1L2_UNIQUE:
        assert col in merged.columns

def test_merge_line_types_no_duplicate_shared_cols(cnt_content, sl1l2_content, sal1l2_content):
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    for col in ["FBAR", "OBAR", "MAE", "TOTAL"]:
        assert merged.columns.tolist().count(col) == 1

def test_merge_line_types_one_row_per_combination(cnt_content, sl1l2_content, sal1l2_content):
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    assert len(merged) == 1

def test_merge_line_types_handles_empty_sl1l2(cnt_content, sal1l2_content):
    merged = merge_line_types(
        _make_clean(cnt_content),
        pd.DataFrame(),
        _make_clean(sal1l2_content),
    )
    assert merged is not None
    assert len(merged) == 1

def test_merge_line_types_handles_empty_sal1l2(cnt_content, sl1l2_content):
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        pd.DataFrame(),
    )
    assert merged is not None
    assert len(merged) == 1


# ---------------------------------------------------------------------------
# test_get_existing_dates
# ---------------------------------------------------------------------------

def test_get_existing_dates_returns_empty_set_when_no_file(tmp_path):
    result = get_existing_dates(tmp_path / "nonexistent.parquet")
    assert result == set()

def test_get_existing_dates_returns_dates_from_parquet(tmp_path, cnt_content, sl1l2_content, sal1l2_content):
    parquet_path = tmp_path / "test.parquet"
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    write_parquet(merged, {}, parquet_path)
    assert INIT_DATE in get_existing_dates(parquet_path)

def test_get_existing_dates_returns_a_set(tmp_path, cnt_content, sl1l2_content, sal1l2_content):
    parquet_path = tmp_path / "test.parquet"
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    write_parquet(merged, {}, parquet_path)
    assert isinstance(get_existing_dates(parquet_path), set)


# ---------------------------------------------------------------------------
# test_write_parquet
# ---------------------------------------------------------------------------

def test_write_parquet_creates_file(tmp_path, cnt_content, sl1l2_content, sal1l2_content):
    parquet_path = tmp_path / "out.parquet"
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    write_parquet(merged, {"MODEL": "AGlobal4"}, parquet_path)
    assert parquet_path.exists()

def test_write_parquet_embeds_metadata(tmp_path, cnt_content, sl1l2_content, sal1l2_content):
    parquet_path = tmp_path / "out.parquet"
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    write_parquet(merged, {"MODEL": "AGlobal4", "FCST_VAR": "t"}, parquet_path)
    table = pq.read_table(parquet_path)
    meta = {k.decode(): v.decode() for k, v in table.schema.metadata.items()}
    assert meta.get("MODEL") == "AGlobal4"
    assert meta.get("FCST_VAR") == "t"

def test_write_parquet_preserves_columns(tmp_path, cnt_content, sl1l2_content, sal1l2_content):
    parquet_path = tmp_path / "out.parquet"
    merged = merge_line_types(
        _make_clean(cnt_content),
        _make_clean(sl1l2_content),
        _make_clean(sal1l2_content),
    )
    write_parquet(merged, {}, parquet_path)
    df = pq.read_table(parquet_path).to_pandas()
    assert list(df.columns) == list(merged.columns)


# ---------------------------------------------------------------------------
# test_convert (integration — uses real extracted data folder)
# ---------------------------------------------------------------------------

def test_convert_creates_parquet_file(parquet_path):
    assert parquet_path.exists()

def test_convert_metadata_cols_not_in_columns(converted_df):
    for col in METADATA_COLS:
        assert col not in converted_df.columns

def test_convert_sl1l2_unique_cols_present(converted_df):
    for col in SL1L2_UNIQUE:
        assert col in converted_df.columns

def test_convert_sal1l2_unique_cols_present(converted_df):
    for col in SAL1L2_UNIQUE:
        assert col in converted_df.columns

def test_convert_fcst_lead_h_is_integer(converted_df):
    assert pd.api.types.is_integer_dtype(converted_df["FCST_LEAD_H"])

def test_convert_valid_times_are_datetime(converted_df):
    for col in ["FCST_VALID_BEG", "FCST_VALID_END", "OBS_VALID_BEG", "OBS_VALID_END"]:
        assert pd.api.types.is_datetime64_any_dtype(converted_df[col])

def test_convert_rows_are_unique(converted_df):
    key_cols = [k for k in MERGE_KEYS if k in converted_df.columns]
    assert not converted_df.duplicated(subset=key_cols).any()

def test_convert_fcst_lev_matches_pressure_pattern(converted_df):
    invalid = converted_df["FCST_LEV"].dropna()[
        ~converted_df["FCST_LEV"].dropna().str.match(r"^P\d+$")
    ]
    assert len(invalid) == 0

def test_convert_metadata_keys_present(parquet_meta):
    for key in ["MODEL", "VERSION", "FCST_VAR", "source", "created_at"]:
        assert key in parquet_meta

def test_convert_incremental_no_duplicate_rows(real_data_folder, parquet_path, converted_df):
    initial_count = len(converted_df)
    convert(real_data_folder, parquet_path.parent)
    df_after = pq.read_table(parquet_path).to_pandas()
    assert len(df_after) == initial_count
