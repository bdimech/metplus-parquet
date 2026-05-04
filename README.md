# METplus to Parquet

Converting METplus GridStat verification outputs into Parquet format for efficient storage and analysis.

## Project Issues

| # | Issue | Status |
|---|-------|--------|
| [#1](https://github.com/bdimech/metplus-parquet/issues/1) | Design and mock parquet schema from .stat file | Done |
| [#2](https://github.com/bdimech/metplus-parquet/issues/2) | Convert .stat files to parquet via Jupyter notebook | Done |
| [#3](https://github.com/bdimech/metplus-parquet/issues/3) | Incremental data loading from daily outputs | Done |
| [#4](https://github.com/bdimech/metplus-parquet/issues/4) | Generalise pipeline as a template for other variables/models | Open |
| [#5](https://github.com/bdimech/metplus-parquet/issues/5) | Add metadata to parquet files | Open |
| [#6](https://github.com/bdimech/metplus-parquet/issues/6) | Enable other users to query the data | Open |
| [#7](https://github.com/bdimech/metplus-parquet/issues/7) | Basic visualisation | Open |

## Project Structure

```
.
├── convert_to_parquet.py   # CLI entry point
├── convert_functions.py    # Core conversion logic
├── workspace.ipynb         # Jupyter notebook for exploration
└── tests/
    ├── conftest.py         # Shared fixtures
    └── test_convert_functions.py
```

## Requirements

```
pandas
pyarrow
```

## Usage

```bash
python convert_to_parquet.py --input <folder> [--output <dir>]
```

- `--input`: folder containing daily GridStat output subdirectories (named `YYYYMMDDHH`)
- `--output`: directory for the output parquet file (defaults to alongside the input folder)

The output file is named after the input folder, e.g. `AGlobal4_Analysis_T_AllLevels_00Z.parquet`.

**Re-running** is safe — already-loaded init dates are detected and skipped, so only new days are appended.

## Parquet Schema

The pipeline reads three METplus line types and merges them into one row per unique combination of init date, forecast lead, forecast level, and verification domain.

| Column | Source | Description |
|--------|--------|-------------|
| `INIT_DATE` | derived | Model initialisation date (`YYYYMMDDHH` directory name) |
| `FCST_LEAD_H` | CNT/SL1L2/SAL1L2 | Forecast lead time in hours (converted from HHMMSS) |
| `FCST_VALID_BEG` | CNT/SL1L2/SAL1L2 | Forecast valid time (datetime) |
| `FCST_LEV` | CNT/SL1L2/SAL1L2 | Forecast level (e.g. `P850`) |
| `VX_MASK` | CNT/SL1L2/SAL1L2 | Verification domain (e.g. `Australia`) |
| `TOTAL` | CNT | Number of matched pairs |
| `FBAR` | CNT | Mean forecast value |
| `OBAR` | CNT | Mean observation value |
| `ME` | CNT | Mean error (bias) |
| `RMSE` | CNT | Root mean square error |
| `MAE` | CNT | Mean absolute error |
| `FOBAR`, `FFBAR`, `OOBAR` | SL1L2 | Scalar partial sums |
| `FABAR`, `OABAR`, `FOABAR`, `FFABAR`, `OOABAR` | SAL1L2 | Anomaly partial sums |

Constant columns (model name, variable, units, observation type, interpolation method) are stripped from the table and embedded as file-level Parquet metadata instead.

## Running Tests

```bash
pytest tests/
```

Tests use a mix of synthetic fixtures and a real GridStat data sample (`AGlobal4_Analysis_T_AllLevels_00Z.zip`) to cover parsing, cleaning, merging, incremental loading, and end-to-end conversion.
