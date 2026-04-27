import sys
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pyarrow.parquet as pq
from convert_to_parquet import convert

ZIP_PATH = Path(__file__).parent.parent / "AGlobal4_Analysis_T_AllLevels_00Z.zip"


@pytest.fixture(scope="session")
def zip_path():
    return ZIP_PATH


@pytest.fixture(scope="session")
def parquet_path(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("output")
    convert(ZIP_PATH, out_dir)
    return out_dir / "AGlobal4_Analysis_T_AllLevels_00Z.parquet"


@pytest.fixture(scope="session")
def converted_df(parquet_path):
    return pq.read_table(parquet_path).to_pandas()


@pytest.fixture(scope="session")
def parquet_meta(parquet_path):
    table = pq.read_table(parquet_path)
    return {k.decode(): v.decode() for k, v in table.schema.metadata.items()}
