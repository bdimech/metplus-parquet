# METplus to Parquet

Converting METplus GridStat and EnsembleStat verification outputs into Parquet format for efficient storage and analysis.

## Project Issues

| # | Issue | Status |
|---|-------|--------|
| [#1](https://github.com/bdimech/metplus-parquet/issues/1) | Design and mock parquet schema from .stat file | Done |
| [#2](https://github.com/bdimech/metplus-parquet/issues/2) | Convert .stat files to parquet via Jupyter notebook | Done |
| [#3](https://github.com/bdimech/metplus-parquet/issues/3) | Incremental data loading from daily outputs | Done |
| [#4](https://github.com/bdimech/metplus-parquet/issues/4) | Generalise pipeline as a template for other variables/models | Done |
| [#5](https://github.com/bdimech/metplus-parquet/issues/5) | Add metadata to parquet files | Open |
| [#6](https://github.com/bdimech/metplus-parquet/issues/6) | Enable other users to query the data | Done |
| [#7](https://github.com/bdimech/metplus-parquet/issues/7) | Basic visualisation | Done |

## Project Structure

```
.
├── convert_to_parquet.py   # CLI entry point
├── convert_functions.py    # Core conversion logic
├── make_pptx.py            # Generates METplus - Parquet Summary.pptx from bureau template
├── metplus-parquet.ipynb   # Jupyter notebook - conversion, exploration, and plotting
├── workspace.ipynb         # scratch notebook
└── tests/
    ├── conftest.py         # Shared fixtures
    └── test_convert_functions.py
```

## Requirements

```
pandas
pyarrow
matplotlib
python-pptx
```

## Usage

### Single config folder

```bash
python convert_to_parquet.py --input <folder> [--output <dir>]
```

- `--input`: a single config folder containing `YYYYMMDDHH` subdirectories
- `--output`: output directory (defaults to alongside the input folder)

### All configs at once (recommended)

```bash
python convert_to_parquet.py --all --input <input_dir> --output <output_dir>
```

- `--input`: directory containing config folders named `<model>_<obs>_<parameter>_<timestep>`
- `--output`: directory for output Parquet files (required)

Discovers all config folders, groups them by `<model>_<observation>`, and writes one Parquet file per group - combining all parameters and timesteps.

**Re-running is safe** - already-loaded init dates are skipped per parameter and stat type, so only new data is appended.

## Output structure

```
output/
├── AGlobal4_Analysis.parquet     # all parameters, 00Z + 12Z, GridStat only
└── AGlobal4E_Analysis.parquet    # all parameters, 00Z + 12Z, GridStat + EnsembleStat
```

> **Note:** Some parameters may differ in units or form between init times (e.g. 00Z vs 12Z).
> When comparing models, filter to a consistent init hour using `pd.to_datetime(df["INIT_DATE"]).dt.hour`.
> The notebook demonstrates this in the cross-model comparison and timeseries sections.

## Parquet Schema

Each row represents one unique combination of init date, forecast lead, forecast level, verification domain, parameter, and stat type.

### Index columns

| Column | Description |
|--------|-------------|
| `PARAMETER` | Parameter derived from config folder name (e.g. `T_AllLevels`, `MSLP`, `T850`) |
| `STAT_TYPE` | Source tool  -  `GridStat` or `EnsembleStat` |
| `INIT_DATE` | Model initialisation date (from `YYYYMMDDHH` directory name) |
| `FCST_LEAD_H` | Forecast lead time in hours (converted from HHMMSS) |
| `FCST_VALID_BEG` | Forecast valid time (datetime) |
| `FCST_LEV` | Forecast level (e.g. `P850`, `L0`) |
| `VX_MASK` | Verification domain (e.g. `Australia`, `NH`) |
| `TOTAL` | Number of matched pairs |

### GridStat statistics (CNT / SL1L2 / SAL1L2)

| Column | Description |
|--------|-------------|
| `ME` | Mean error (bias) |
| `RMSE` | Root mean square error |
| `MAE` | Mean absolute error |
| `FBAR`, `OBAR` | Mean forecast and observed values |
| `FOBAR`, `FFBAR`, `OOBAR` | Scalar partial sums (SL1L2) |
| `FABAR`, `OABAR`, `FOABAR`, `FFABAR`, `OOABAR` | Anomaly partial sums (SAL1L2) |

### EnsembleStat statistics (ECNT)

| Column | Description |
|--------|-------------|
| `CRPS` | Continuous Ranked Probability Score (lower is better) |
| `CRPSS` | CRPS Skill Score |
| `SPREAD` | Ensemble spread - a well-calibrated ensemble has Spread ~ RMSE |
| `N_ENS` | Number of ensemble members |
| `IGN` | Ignorance score |
| `ME_OERR`, `RMSE_OERR`, `SPREAD_OERR` | Observation-error adjusted stats |
| `BIAS_RATIO` | Bias ratio |
| `CRPS_EMP`, `CRPSS_EMP` | Empirical CRPS and skill score |

Constant columns (model name, variable, units, observation type, interpolation method) are stripped from the table and embedded as file-level Parquet metadata.

## Running Tests

```bash
pytest tests/
```

Tests use a mix of synthetic fixtures and a real GridStat data sample (`AGlobal4_Analysis_T_AllLevels_00Z.zip`) to cover parsing, cleaning, merging, incremental loading, and end-to-end conversion.
