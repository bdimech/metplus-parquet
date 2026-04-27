import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from convert_to_parquet import convert

ZIP_PATH = Path(__file__).parent.parent / "AGlobal4_Analysis_T_AllLevels_00Z.zip"

# ---------------------------------------------------------------------------
# Minimal file content strings — space-separated, NA for missing values
# ---------------------------------------------------------------------------

CNT_CONTENT = (
    "VERSION MODEL DESC FCST_LEAD FCST_VALID_BEG FCST_VALID_END OBS_LEAD "
    "OBS_VALID_BEG OBS_VALID_END FCST_VAR FCST_UNITS FCST_LEV OBS_VAR OBS_UNITS "
    "OBS_LEV OBTYPE VX_MASK INTERP_MTHD INTERP_PNTS FCST_THRESH OBS_THRESH "
    "COV_THRESH ALPHA LINE_TYPE TOTAL FBAR OBAR ME RMSE MAE\n"
    "V12.0.2 AGlobal4 desc 120000 20260410_120000 20260410_120000 000000 "
    "20260410_120000 20260410_120000 t K P850 t K P850 ANALYSIS Australia "
    "NEAREST 1 NA NA NA 0.05 CNT 306 288.5 289.0 -0.5 1.87 1.43\n"
)

SL1L2_CONTENT = (
    "VERSION MODEL DESC FCST_LEAD FCST_VALID_BEG FCST_VALID_END OBS_LEAD "
    "OBS_VALID_BEG OBS_VALID_END FCST_VAR FCST_UNITS FCST_LEV OBS_VAR OBS_UNITS "
    "OBS_LEV OBTYPE VX_MASK INTERP_MTHD INTERP_PNTS FCST_THRESH OBS_THRESH "
    "COV_THRESH ALPHA LINE_TYPE TOTAL FBAR OBAR FOBAR FFBAR OOBAR MAE\n"
    "V12.0.2 AGlobal4 desc 120000 20260410_120000 20260410_120000 000000 "
    "20260410_120000 20260410_120000 t K P850 t K P850 ANALYSIS Australia "
    "NEAREST 1 NA NA NA NA SL1L2 306 288.5 289.0 83430.0 83200.0 83600.0 1.43\n"
)

SAL1L2_CONTENT = (
    "VERSION MODEL DESC FCST_LEAD FCST_VALID_BEG FCST_VALID_END OBS_LEAD "
    "OBS_VALID_BEG OBS_VALID_END FCST_VAR FCST_UNITS FCST_LEV OBS_VAR OBS_UNITS "
    "OBS_LEV OBTYPE VX_MASK INTERP_MTHD INTERP_PNTS FCST_THRESH OBS_THRESH "
    "COV_THRESH ALPHA LINE_TYPE TOTAL FABAR OABAR FOABAR FFABAR OOABAR MAE\n"
    "V12.0.2 AGlobal4 desc 120000 20260410_120000 20260410_120000 000000 "
    "20260410_120000 20260410_120000 t K P850 t K P850 ANALYSIS Australia "
    "NEAREST 1 NA NA NA NA SAL1L2 306 1.29 2.14 5.0 3.0 4.0 1.43\n"
)

# ---------------------------------------------------------------------------
# Fixtures: minimal sample folder
# ---------------------------------------------------------------------------

@pytest.fixture
def cnt_content():
    return CNT_CONTENT


@pytest.fixture
def sl1l2_content():
    return SL1L2_CONTENT


@pytest.fixture
def sal1l2_content():
    return SAL1L2_CONTENT


@pytest.fixture
def sample_folder(tmp_path):
    """Minimal folder structure matching METplus GridStat output layout."""
    init_dir = tmp_path / "2026041000"
    init_dir.mkdir()
    (init_dir / "grid_stat_test_120000L_20260410_120000V_cnt.txt").write_text(CNT_CONTENT)
    (init_dir / "grid_stat_test_120000L_20260410_120000V_sl1l2.txt").write_text(SL1L2_CONTENT)
    (init_dir / "grid_stat_test_120000L_20260410_120000V_sal1l2.txt").write_text(SAL1L2_CONTENT)
    return tmp_path


# ---------------------------------------------------------------------------
# Fixtures: real data integration (extracted from zip once per session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def real_data_folder(tmp_path_factory):
    """Extract the test zip to a folder — mirrors real production layout."""
    extract_dir = tmp_path_factory.mktemp("real_data")
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(extract_dir)
    return extract_dir


@pytest.fixture(scope="session")
def parquet_path(real_data_folder, tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("output")
    convert(real_data_folder, out_dir)
    return out_dir / f"{real_data_folder.name}.parquet"


@pytest.fixture(scope="session")
def converted_df(parquet_path):
    return pq.read_table(parquet_path).to_pandas()


@pytest.fixture(scope="session")
def parquet_meta(parquet_path):
    table = pq.read_table(parquet_path)
    return {k.decode(): v.decode() for k, v in table.schema.metadata.items()}
