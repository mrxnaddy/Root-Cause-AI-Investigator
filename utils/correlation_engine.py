"""
correlation_engine.py
-----------------------
Computes actual Pearson correlation coefficients between numeric metrics
across uploaded files (e.g. ad_spend vs revenue, mobile sessions vs
conversion_rate) -- aligned by date. This gives the investigation hard
statistical evidence alongside the LLM's narrative reasoning: "these two
things moved together with r=0.91" is a fact, not a claim.

Deliberately dependency-light: uses numpy for the correlation math (already
a pandas dependency, so no new install) instead of scipy, since we don't
need p-values for a hackathon-grade signal -- a correlation strength label
plus the coefficient and sample size is enough to be genuinely useful and
honest about its limits.
"""

import itertools
import numpy as np
import pandas as pd

from utils.impact_calculator import find_date_column, find_numeric_columns


def calculate_pearson(x, y):
    """Returns the Pearson r for two equal-length numeric sequences, or None if it can't be computed."""
    if x is None or y is None or len(x) < 3 or len(x) != len(y):
        return None
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if np.std(x_arr) == 0 or np.std(y_arr) == 0:
        return None  # a constant series has no meaningful correlation
    return float(np.corrcoef(x_arr, y_arr)[0, 1])


def _strength_label(r: float) -> str:
    abs_r = abs(r)
    if abs_r >= 0.7:
        return "Strong"
    if abs_r >= 0.4:
        return "Moderate"
    if abs_r >= 0.2:
        return "Weak"
    return "Negligible"


def correlate_metrics(df_a: pd.DataFrame, metric_a: str, filename_a: str,
                       df_b: pd.DataFrame, metric_b: str, filename_b: str,
                       date_col_a: str = None, date_col_b: str = None) -> dict:
    """
    Aligns df_a[metric_a] and df_b[metric_b] on their shared dates (inner join)
    and returns the Pearson correlation between them.

    Returns a dict with r, n (overlapping data points), strength, direction,
    and the two metric/file names -- or {"error": ...} if it can't be computed.
    """
    if date_col_a is None:
        date_col_a = find_date_column(df_a)
    if date_col_b is None:
        date_col_b = find_date_column(df_b)

    if date_col_a is None or date_col_b is None:
        return {"error": "One or both files have no date column to align on."}
    if metric_a not in df_a.columns or metric_b not in df_b.columns:
        return {"error": "One or both metric columns were not found."}

    a = df_a[[date_col_a, metric_a]].copy()
    a[date_col_a] = pd.to_datetime(a[date_col_a], errors="coerce")
    a = a.dropna().rename(columns={date_col_a: "_date", metric_a: "_a"})

    b = df_b[[date_col_b, metric_b]].copy()
    b[date_col_b] = pd.to_datetime(b[date_col_b], errors="coerce")
    b = b.dropna().rename(columns={date_col_b: "_date", metric_b: "_b"})

    merged = pd.merge(a, b, on="_date", how="inner")

    if len(merged) < 3:
        return {"error": f"Only {len(merged)} overlapping date(s) between these two files -- not enough to correlate."}

    r = calculate_pearson(merged["_a"].tolist(), merged["_b"].tolist())
    if r is None:
        return {"error": "Could not compute correlation (a series may be constant)."}

    return {
        "metric_a": metric_a, "file_a": filename_a,
        "metric_b": metric_b, "file_b": filename_b,
        "r": round(r, 3),
        "n": len(merged),
        "strength": _strength_label(r),
        "direction": "positive" if r > 0 else "negative",
        "error": None,
    }


def _detect_segment_column(df: pd.DataFrame, date_col: str):
    """
    Finds a categorical column (like "device": mobile/desktop) that causes
    multiple rows per date. If found, that column should be pivoted out
    before correlating -- otherwise a date-based merge would blindly mix
    e.g. mobile and desktop sessions into one misleading average.
    """
    if not df[date_col].duplicated().any():
        return None  # already one row per date, nothing to segment

    candidates = [c for c in df.columns if c != date_col and not pd.api.types.is_numeric_dtype(df[c])]
    for c in candidates:
        if df[c].nunique() > 1 and not df.duplicated(subset=[date_col, c]).any():
            return c
    return None


def expand_categorical_segments(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """
    If the file has a segmenting column (e.g. device = mobile/desktop) that
    puts multiple rows under the same date, pivots it so each segment gets
    its own column per metric (e.g. "sessions_mobile", "sessions_desktop")
    and returns one row per date. If no such column exists, returns df
    unchanged so this is always safe to call.
    """
    segment_col = _detect_segment_column(df, date_col)
    if segment_col is None:
        return df

    numeric_cols = [c for c in df.columns if c not in (date_col, segment_col)
                    and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        return df

    pivoted = df.pivot_table(index=date_col, columns=segment_col, values=numeric_cols)
    pivoted.columns = [f"{metric}_{segment}" for metric, segment in pivoted.columns]
    return pivoted.reset_index()


def scan_correlations(parsed_files: list, min_abs_r: float = 0.3) -> list:
    """
    parsed_files: list of dicts from parsers.py (only entries with a
    "dataframe" are used). Computes correlation for every pair of numeric
    columns across all tabular files (including different columns within
    the same file, e.g. revenue vs orders in sales.csv), and returns the
    ones at or above `min_abs_r`, sorted strongest-first.

    Files with a segmenting column (e.g. "device": mobile/desktop rows
    sharing a date) are automatically pivoted first via
    expand_categorical_segments() so mobile and desktop signals aren't
    blindly averaged together.
    """
    candidates = []
    for parsed in parsed_files:
        df = parsed.get("dataframe")
        if df is None:
            continue
        date_col = find_date_column(df)
        if date_col is None:
            continue

        df = expand_categorical_segments(df, date_col)

        for metric_col in find_numeric_columns(df):
            candidates.append((parsed["filename"], df, date_col, metric_col))

    results = []
    for (fname_a, df_a, date_a, metric_a), (fname_b, df_b, date_b, metric_b) in itertools.combinations(candidates, 2):
        # skip comparing a column to itself if somehow duplicated across identical file+column
        if fname_a == fname_b and metric_a == metric_b:
            continue

        outcome = correlate_metrics(df_a, metric_a, fname_a, df_b, metric_b, fname_b, date_a, date_b)
        if outcome.get("error"):
            continue
        if abs(outcome["r"]) >= min_abs_r:
            results.append(outcome)

    results.sort(key=lambda o: abs(o["r"]), reverse=True)
    return results


def format_correlation_summary(corr: dict) -> str:
    if not corr or corr.get("error"):
        return corr.get("error", "No correlation available.") if corr else "No correlation data."

    return (
        f"{corr['metric_a']} ({corr['file_a']}) and {corr['metric_b']} ({corr['file_b']}) "
        f"show a {corr['strength'].lower()} {corr['direction']} correlation (r={corr['r']}, n={corr['n']} days)."
    )
