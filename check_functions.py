"""
Health check functions: audit input folders against Parquet output files.

Three categories of status:
  OK           - date is accounted for (loaded into Parquet, or archived from disk)
  Pending      - today's daily run has not yet executed
  Missing      - absent from both input and Parquet
                   missed_run   : within retention window (run probably failed)
                   historical   : beyond retention window (never loaded before cleanup)
  Needs load   - date is in the input folder but not yet written to Parquet
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from convert_functions import convert_all, get_existing_dates, parse_config_name, INIT_DATE_RE

# -- Status codes -------------------------------------------------------------
OK_LOADED   = "ok_loaded"       # in Parquet and input still on disk
OK_ARCHIVED = "ok_archived"     # in Parquet, input cleaned up (age > retention)
PENDING     = "pending"         # today; daily run not yet complete
MISSED_RUN  = "missed_run"      # absent from input + Parquet, within retention window
HIST_GAP    = "historical_gap"  # absent from input + Parquet, beyond retention window
NEEDS_LOAD  = "needs_loading"   # in input but not yet in Parquet


def get_input_dates(folder: Path) -> set:
    """Return the set of init datetimes available in a config folder.

    Args:
        folder: path to a config folder containing YYYYMMDDHH subdirectories.

    Returns:
        Set of datetime objects, one per available init date directory.
    """
    return {
        datetime.strptime(d.name, "%Y%m%d%H")
        for d in folder.iterdir()
        if d.is_dir() and INIT_DATE_RE.match(d.name)
    }


def expected_dates(known: set, hour: int, today: date) -> list:
    """Generate all expected init datetimes from the earliest known date to today.

    Args:
        known: set of datetimes already seen (from input or Parquet).
        hour: UTC init hour to check (0 or 12).
        today: reference date (typically date.today()).

    Returns:
        List of datetimes at the given hour, from earliest known date to today.
    """
    if not known:
        return []
    start = min(known)
    start = datetime(start.year, start.month, start.day, hour)
    end   = datetime(today.year, today.month, today.day, hour)
    dates, dt = [], start
    while dt <= end:
        dates.append(dt)
        dt += timedelta(days=1)
    return dates


def classify(dt: datetime, in_input: bool, in_parquet: bool,
             today: date, retention: int) -> str:
    """Classify a single init datetime into one of six status codes.

    Args:
        dt: the init datetime being classified.
        in_input: True if the date directory exists in the input folder.
        in_parquet: True if the date is already loaded in the Parquet file.
        today: reference date for the retention window calculation.
        retention: number of days input data is kept on disk.

    Returns:
        One of the six module-level status code constants.
    """
    if in_parquet:
        return OK_LOADED if in_input else OK_ARCHIVED
    if in_input:
        return NEEDS_LOAD
    if dt.date() == today:
        return PENDING
    if (today - dt.date()).days <= retention:
        return MISSED_RUN
    return HIST_GAP


def check_group(folders: list, parquet_path: Path, today: date, retention: int) -> dict:
    """Check all config folders belonging to one Parquet file.

    Checks GridStat for every folder, and EnsembleStat where an EnsembleStat
    subfolder exists or rows are already present in the Parquet.

    Args:
        folders: list of config folder Paths for this model/obs group.
        parquet_path: path to the corresponding Parquet output file.
        today: reference date.
        retention: number of days input data is kept on disk.

    Returns:
        Dict mapping each status code to a list of (label, datetime) tuples.
    """
    results = {k: [] for k in (OK_LOADED, OK_ARCHIVED, PENDING, MISSED_RUN, HIST_GAP, NEEDS_LOAD)}

    for folder in sorted(folders):
        _, _, parameter, timestep = parse_config_name(folder.name)
        hour  = 0 if timestep.upper().startswith("00") else 12
        label = f"{parameter} {timestep}"

        # GridStat
        data_dir   = folder / "GridStat" if (folder / "GridStat").is_dir() else folder
        gs_input   = get_input_dates(data_dir)
        gs_parquet = get_existing_dates(parquet_path, parameter, "GridStat")
        for dt in expected_dates(gs_input | gs_parquet, hour, today):
            status = classify(dt, dt in gs_input, dt in gs_parquet, today, retention)
            results[status].append((label, dt))

        # EnsembleStat (only if subfolder exists or rows already in Parquet)
        ens_dir     = folder / "EnsembleStat"
        ens_parquet = get_existing_dates(parquet_path, parameter, "EnsembleStat")
        if ens_dir.is_dir() or ens_parquet:
            ens_input = get_input_dates(ens_dir) if ens_dir.is_dir() else set()
            for dt in expected_dates(ens_input | ens_parquet, hour, today):
                status = classify(dt, dt in ens_input, dt in ens_parquet, today, retention)
                results[status].append((f"{label} (ECNT)", dt))

    return results


def discover_groups(input_dir: Path) -> dict:
    """Group config folders in input_dir by their model_obs key.

    Args:
        input_dir: directory containing config folders named
            <model>_<obs>_<parameter>_<timestep>.

    Returns:
        Dict mapping '<model>_<obs>' key to a list of config folder Paths.
    """
    groups: dict[str, list] = {}
    for folder in sorted(input_dir.iterdir()):
        if not folder.is_dir():
            continue
        try:
            model, obs, _, _ = parse_config_name(folder.name)
        except (ValueError, IndexError):
            continue
        groups.setdefault(f"{model}_{obs}", []).append(folder)
    return groups


def print_report(parquet_name: str, results: dict) -> None:
    """Print a formatted health check report for one Parquet file.

    Args:
        parquet_name: display name for the Parquet file (e.g. 'AGlobal4_Analysis.parquet').
        results: dict returned by check_group().
    """
    STATUS_LABELS = {
        OK_LOADED:   ("OK (loaded)            ", False),
        OK_ARCHIVED: ("OK (archived)          ", False),
        PENDING:     ("Pending                ", False),
        MISSED_RUN:  ("MISSING  missed run    ", True),
        HIST_GAP:    ("MISSING  historical gap", True),
        NEEDS_LOAD:  ("Needs loading          ", True),
    }

    print(f"\n{'=' * 62}")
    print(f"  {parquet_name}")
    print(f"{'=' * 62}")

    has_issues = False
    for status, (label, is_issue) in STATUS_LABELS.items():
        entries = results[status]
        if not entries:
            continue
        n      = len(entries)
        marker = "  <--" if is_issue else ""
        print(f"  {label}  {n:>4} date{'s' if n != 1 else ''}{marker}")
        if is_issue:
            has_issues = True

    # Detail lines for anything requiring attention
    detail_statuses = [s for s in (MISSED_RUN, HIST_GAP, NEEDS_LOAD) if results[s]]
    if detail_statuses:
        print()
        for status in detail_statuses:
            label = STATUS_LABELS[status][0].strip()
            print(f"  {label}:")
            for param_label, dt in sorted(results[status], key=lambda x: (x[0], x[1])):
                print(f"    {param_label:<36}  {dt.strftime('%Y-%m-%d %HZ')}")

    if not has_issues:
        print("\n  All dates accounted for.")


def run_check(input_dir: Path, output_dir: Path, retention: int, fix: bool) -> bool:
    """Run the full health check across all groups and print reports.

    Args:
        input_dir: directory containing config folders.
        output_dir: directory containing Parquet output files.
        retention: number of days input data is kept on disk.
        fix: if True, run convert_all to load any dates flagged as needs_loading.

    Returns:
        True if any issues were found (missed runs, gaps, or dates needing load).
    """
    today  = date.today()
    groups = discover_groups(input_dir)

    # Include any Parquet files that have no corresponding input folders
    parquet_only = {
        p.stem for p in output_dir.glob("*.parquet")
        if p.stem not in groups
    }

    all_results: dict[str, dict] = {}
    for key in sorted(set(groups) | parquet_only):
        parquet_path = output_dir / f"{key}.parquet"
        results = check_group(groups.get(key, []), parquet_path, today, retention)
        all_results[key] = results
        print_report(f"{key}.parquet", results)

    has_issues = any(
        r[MISSED_RUN] or r[HIST_GAP] or r[NEEDS_LOAD]
        for r in all_results.values()
    )

    if fix:
        needs_load = sum(len(r[NEEDS_LOAD]) for r in all_results.values())
        if needs_load:
            print(f"\n  --fix: loading {needs_load} date{'s' if needs_load != 1 else ''}...")
            convert_all(input_dir, output_dir)
            print("  Done.")
        else:
            print("\n  --fix: nothing to load.")

    return has_issues
