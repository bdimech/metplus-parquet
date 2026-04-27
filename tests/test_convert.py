"""
Tests for convert_to_parquet.py.

Focused on structure and correctness rather than dataset-specific counts,
so these pass regardless of which METplus dataset is being converted.
"""

import re
from datetime import datetime

import pandas as pd
import numpy as np
import pytest
import pyarrow.parquet as pq

from convert_to_parquet import (
    clean,
    convert,
    lead_to_hours,
    merge_line_types,
    MERGE_KEYS,
    METADATA_COLS,
    SL1L2_UNIQUE,
    SAL1L2_UNIQUE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_raw_cnt(**overrides):
    """Minimal raw CNT row as it comes out of _parse_file (before clean)."""
    row = {
        "INIT_DATE": datetime(2026, 4, 10),
        "VERSION": "V12.0.2", "MODEL": "AGlobal4", "DESC": "desc",
        "OBS_LEAD": 0, "FCST_VAR": "t", "FCST_UNITS": "K",
        "OBS_VAR": "t", "OBS_UNITS": "K", "OBTYPE": "ANALYSIS",
        "INTERP_MTHD": "NEAREST", "INTERP_PNTS": 1,
        "FCST_THRESH": None, "OBS_THRESH": None, "COV_THRESH": None,
        "LINE_TYPE": "CNT", "ALPHA": 0.05,
        "FCST_LEAD": 120000,
        "FCST_VALID_BEG": "20260417_000000",
        "FCST_VALID_END": "20260417_000000",
        "OBS_VALID_BEG": "20260417_000000",
        "OBS_VALID_END": "20260417_000000",
        "FCST_LEV": "P850", "OBS_LEV": "P850",
        "VX_MASK": "Australia",
        "TOTAL": 306, "RMSE": 1.87, "ME": -0.37, "FBAR": 288.6, "OBAR": 289.0,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def make_clean_keys(**overrides):
    """Shared merge key values for post-clean DataFrames."""
    keys = {
        "INIT_DATE": datetime(2026, 4, 10),
        "FCST_LEAD_H": 12,
        "FCST_VALID_BEG": datetime(2026, 4, 17, 0, 0),
        "FCST_LEV": "P850",
        "VX_MASK": "Australia",
    }
    keys.update(overrides)
    return keys


# ---------------------------------------------------------------------------
# Unit: lead_to_hours
# ---------------------------------------------------------------------------

class TestLeadToHours:
    def test_12h(self):
        assert lead_to_hours(120000) == 12

    def test_24h(self):
        assert lead_to_hours(240000) == 24

    def test_240h(self):
        assert lead_to_hours(2400000) == 240

    def test_string_input(self):
        assert lead_to_hours("360000") == 36


# ---------------------------------------------------------------------------
# Unit: clean
# ---------------------------------------------------------------------------

class TestClean:
    def test_metadata_cols_removed(self):
        df = clean(make_raw_cnt())
        for col in METADATA_COLS:
            assert col not in df.columns, f"{col} should be removed by clean()"

    def test_line_type_removed(self):
        assert "LINE_TYPE" not in clean(make_raw_cnt()).columns

    def test_alpha_removed(self):
        assert "ALPHA" not in clean(make_raw_cnt()).columns

    def test_fcst_lead_converted(self):
        df = clean(make_raw_cnt())
        assert "FCST_LEAD" not in df.columns
        assert "FCST_LEAD_H" in df.columns
        assert df["FCST_LEAD_H"].iloc[0] == 12

    def test_valid_times_are_datetime(self):
        df = clean(make_raw_cnt())
        for col in ["FCST_VALID_BEG", "FCST_VALID_END", "OBS_VALID_BEG", "OBS_VALID_END"]:
            assert pd.api.types.is_datetime64_any_dtype(df[col]), f"{col} should be datetime"


# ---------------------------------------------------------------------------
# Unit: merge_line_types
# ---------------------------------------------------------------------------

class TestMergeLineTypes:
    def setup_method(self):
        keys = make_clean_keys()
        self.cnt = pd.DataFrame([{
            **keys, "TOTAL": 306, "FBAR": 288.6, "OBAR": 289.0, "MAE": 1.43,
            "RMSE": 1.87, "ME": -0.37,
        }])
        self.sl1l2 = pd.DataFrame([{
            **keys, "TOTAL": 306, "FBAR": 288.6, "OBAR": 289.0, "MAE": 1.43,
            "FOBAR": 83430.0, "FFBAR": 83200.0, "OOBAR": 83600.0,
        }])
        self.sal1l2 = pd.DataFrame([{
            **keys, "TOTAL": 306, "MAE": 1.43,
            "FABAR": 1.29, "OABAR": 2.14, "FOABAR": 5.0, "FFABAR": 3.0, "OOABAR": 4.0,
        }])

    def test_sl1l2_unique_cols_present(self):
        df = merge_line_types(self.cnt, self.sl1l2, self.sal1l2)
        for col in SL1L2_UNIQUE:
            assert col in df.columns

    def test_sal1l2_unique_cols_present(self):
        df = merge_line_types(self.cnt, self.sl1l2, self.sal1l2)
        for col in SAL1L2_UNIQUE:
            assert col in df.columns

    def test_no_duplicate_fbar(self):
        df = merge_line_types(self.cnt, self.sl1l2, self.sal1l2)
        assert "FBAR" in df.columns
        assert df.columns.tolist().count("FBAR") == 1

    def test_one_row_per_combination(self):
        df = merge_line_types(self.cnt, self.sl1l2, self.sal1l2)
        assert len(df) == 1

    def test_empty_sl1l2_handled(self):
        df = merge_line_types(self.cnt, pd.DataFrame(), self.sal1l2)
        assert df is not None
        assert len(df) == 1


# ---------------------------------------------------------------------------
# Integration: schema
# ---------------------------------------------------------------------------

class TestOutputSchema:
    def test_sl1l2_unique_cols_in_output(self, converted_df):
        for col in SL1L2_UNIQUE:
            assert col in converted_df.columns, f"Missing SL1L2 column: {col}"

    def test_sal1l2_unique_cols_in_output(self, converted_df):
        for col in SAL1L2_UNIQUE:
            assert col in converted_df.columns, f"Missing SAL1L2 column: {col}"

    def test_metadata_cols_not_in_output(self, converted_df):
        for col in METADATA_COLS:
            assert col not in converted_df.columns, f"{col} should be metadata, not a column"

    def test_fcst_lead_h_present(self, converted_df):
        assert "FCST_LEAD_H" in converted_df.columns

    def test_fcst_lead_raw_absent(self, converted_df):
        assert "FCST_LEAD" not in converted_df.columns

    def test_init_date_present(self, converted_df):
        assert "INIT_DATE" in converted_df.columns


# ---------------------------------------------------------------------------
# Integration: data types
# ---------------------------------------------------------------------------

class TestDataTypes:
    def test_init_date_is_datetime(self, converted_df):
        assert pd.api.types.is_datetime64_any_dtype(converted_df["INIT_DATE"])

    def test_valid_times_are_datetime(self, converted_df):
        for col in ["FCST_VALID_BEG", "FCST_VALID_END", "OBS_VALID_BEG", "OBS_VALID_END"]:
            assert pd.api.types.is_datetime64_any_dtype(converted_df[col]), f"{col} should be datetime"

    def test_fcst_lead_h_is_integer(self, converted_df):
        assert pd.api.types.is_integer_dtype(converted_df["FCST_LEAD_H"])

    def test_stat_cols_are_numeric(self, converted_df):
        for col in ["RMSE", "ME", "MAE", "PR_CORR", "ANOM_CORR"]:
            assert pd.api.types.is_float_dtype(converted_df[col]), f"{col} should be float"


# ---------------------------------------------------------------------------
# Integration: value validity
# ---------------------------------------------------------------------------

class TestValueValidity:
    def test_fcst_lead_h_positive(self, converted_df):
        assert (converted_df["FCST_LEAD_H"] > 0).all()

    def test_fcst_lev_matches_pressure_pattern(self, converted_df):
        pattern = re.compile(r"^P\d+$")
        invalid = converted_df["FCST_LEV"].dropna()[
            ~converted_df["FCST_LEV"].dropna().str.match(pattern)
        ]
        assert len(invalid) == 0, f"Unexpected FCST_LEV values: {invalid.unique()}"

    def test_vx_mask_not_null(self, converted_df):
        assert converted_df["VX_MASK"].notna().all()

    def test_init_date_not_null(self, converted_df):
        assert converted_df["INIT_DATE"].notna().all()

    def test_rows_are_unique(self, converted_df):
        key_cols = [k for k in MERGE_KEYS if k in converted_df.columns]
        duplicates = converted_df.duplicated(subset=key_cols)
        assert not duplicates.any(), f"{duplicates.sum()} duplicate rows found"

    def test_sl1l2_unique_cols_not_all_null(self, converted_df):
        for col in SL1L2_UNIQUE:
            assert converted_df[col].notna().any(), f"{col} is entirely null"

    def test_sal1l2_unique_cols_not_all_null(self, converted_df):
        for col in SAL1L2_UNIQUE:
            assert converted_df[col].notna().any(), f"{col} is entirely null"


# ---------------------------------------------------------------------------
# Integration: metadata
# ---------------------------------------------------------------------------

class TestParquetMetadata:
    EXPECTED_KEYS = ["MODEL", "VERSION", "FCST_VAR", "FCST_UNITS", "OBTYPE", "source", "created_at"]

    def test_expected_metadata_keys_present(self, parquet_meta):
        for key in self.EXPECTED_KEYS:
            assert key in parquet_meta, f"Missing metadata key: {key}"

    def test_metadata_model_not_empty(self, parquet_meta):
        assert parquet_meta.get("MODEL", "").strip() != ""

    def test_metadata_fcst_var_not_empty(self, parquet_meta):
        assert parquet_meta.get("FCST_VAR", "").strip() != ""


# ---------------------------------------------------------------------------
# Integration: incremental loading
# ---------------------------------------------------------------------------

class TestIncremental:
    def test_second_run_adds_no_rows(self, zip_path, parquet_path, converted_df):
        initial_count = len(converted_df)
        convert(zip_path, parquet_path.parent)
        df_after = pq.read_table(parquet_path).to_pandas()
        assert len(df_after) == initial_count, (
            f"Expected {initial_count} rows after second run, got {len(df_after)}"
        )
