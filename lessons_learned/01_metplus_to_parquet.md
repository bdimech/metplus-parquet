# Lessons Learned — METplus to Parquet Conversion

## Code Structure
- **Three-file layout**: runner (`convert_to_parquet.py`), functions (`convert_functions.py`), tests (`tests/test_convert_functions.py`). Runner has no logic — argparse only.
- **Private functions** (`_name`): small wrappers around standard library calls go at the top, one-line docstring only, no tests needed.
- **Public functions**: Google-style docstrings with Args + Returns. One test per function, named `test_<function_name>`.
- **Test focus**: test things likely to break — data transformations, merges, type conversions, guards. Not simple wrappers.

## Schema Design
- **Merge, don't concat**: CNT as base, join only the unique columns from SL1L2 and SAL1L2. Shared columns (FBAR, OBAR, MAE) appear once — no duplication.
- **Constant columns as metadata**: 14 columns are the same across every row (MODEL, FCST_VAR, OBTYPE, etc.). Store them once in the parquet file-level schema metadata, not in every row. Smaller file, cleaner data.
- **MERGE_KEYS**: `INIT_DATE`, `FCST_LEAD_H`, `FCST_VALID_BEG`, `FCST_LEV`, `VX_MASK` — the minimum set that uniquely identifies a row across all three line types.

## Incremental Loading
- **Skip already-loaded dates**: read `INIT_DATE` values from the existing parquet before walking the folder. Skip any subdirectory whose date is already present. Append new rows to the existing file rather than rewriting it.
- **Date guard in tests**: `skip_dates={INIT_DATE}` returning an empty DataFrame is a key test — this is the logic most likely to break if someone changes the folder-walk code.

## Gotchas
- `FCST_LEAD` is stored as an HHMMSS integer (`120000` = 12h). Always convert with `// 10000`, never divide by 100.
- `git add -A` staged the extracted data folder — always add files explicitly and keep large data directories in `.gitignore`.
- `datetime.utcnow()` is deprecated in Python 3.12+. Use `datetime.now(tz=timezone.utc)`.
