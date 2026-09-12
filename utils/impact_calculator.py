"""
impact_calculator.py
---------------------
Turns a raw metric (revenue, orders, whatever numeric column the user has)
into a concrete dollar/unit impact number, plus a severity score.

This is deliberately NOT an LLM call -- it's pure math on the data the
user actually uploaded, so the number is a FACT-level calculation, not a
guess. That distinction matters: it sits alongside the causal chain as
hard evidence of "how much did this cost us", separate from "why did it
happen".
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Column discovery helpers
# ---------------------------------------------------------------------------

def find_date_column(df: pd.DataFrame) -> str:
    for col in df.columns:
        if "date" in col.lower():
            return col
    return None


def find_numeric_columns(df: pd.DataFrame) -> list:
    """Returns numeric columns that aren't the date column -- candidates for impact metrics."""
    date_col = find_date_column(df)
    numeric_cols = []
    for col in df.columns:
        if col == date_col:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
    return numeric_cols


# ---------------------------------------------------------------------------
# Financial impact
# ---------------------------------------------------------------------------

def calculate_financial_impact(df: pd.DataFrame, metric_col: str,
                                incident_start: str, incident_end: str,
                                date_col: str = None, baseline_days: int = 4) -> dict:
    """
    Compares the average of `metric_col` during the incident window against
    the average of the `baseline_days` immediately before it, and projects
    the total impact over the incident window.

    Returns a dict with baseline_avg, incident_avg, pct_change, daily_impact,
    total_impact, days_affected -- or an "error" key if the data doesn't
    support the calculation (e.g. no rows in range).
    """
    if date_col is None:
        date_col = find_date_column(df)
    if date_col is None:
        return {"error": "No date column found in this file."}
    if metric_col not in df.columns:
        return {"error": f"Column '{metric_col}' not found."}

    work_df = df.copy()
    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    work_df = work_df.dropna(subset=[date_col]).sort_values(date_col)

    incident_start_ts = pd.to_datetime(incident_start)
    incident_end_ts = pd.to_datetime(incident_end)

    incident_mask = (work_df[date_col] >= incident_start_ts) & (work_df[date_col] <= incident_end_ts)
    incident_rows = work_df[incident_mask]

    if incident_rows.empty:
        return {"error": "No data rows fall inside the incident date range."}

    baseline_end_ts = incident_start_ts - pd.Timedelta(days=1)
    baseline_start_ts = baseline_end_ts - pd.Timedelta(days=baseline_days - 1)
    baseline_mask = (work_df[date_col] >= baseline_start_ts) & (work_df[date_col] <= baseline_end_ts)
    baseline_rows = work_df[baseline_mask]

    if baseline_rows.empty:
        return {"error": "No baseline data found in the days immediately before the incident."}

    baseline_avg = float(baseline_rows[metric_col].mean())
    incident_avg = float(incident_rows[metric_col].mean())
    days_affected = int(incident_rows.shape[0])

    daily_impact = baseline_avg - incident_avg
    total_impact = daily_impact * days_affected
    pct_change = ((incident_avg - baseline_avg) / baseline_avg * 100) if baseline_avg else 0.0

    return {
        "metric": metric_col,
        "baseline_avg": round(baseline_avg, 2),
        "incident_avg": round(incident_avg, 2),
        "daily_impact": round(daily_impact, 2),
        "total_impact": round(total_impact, 2),
        "pct_change": round(pct_change, 1),
        "days_affected": days_affected,
        "baseline_window": f"{baseline_start_ts.date()} to {baseline_end_ts.date()}",
        "incident_window": f"{incident_start_ts.date()} to {incident_end_ts.date()}",
        "error": None,
    }


def format_impact_summary(impact: dict) -> str:
    """One or two plain-English sentences summarizing the impact dict, for display or reports."""
    if not impact or impact.get("error"):
        return impact.get("error", "Impact could not be calculated.") if impact else "No impact data."

    direction = "loss" if impact["total_impact"] > 0 else "gain"
    return (
        f"{impact['metric']} averaged {impact['baseline_avg']:,.2f} in the days before the incident "
        f"({impact['baseline_window']}) and dropped to {impact['incident_avg']:,.2f} during the incident "
        f"({impact['incident_window']}), a {abs(impact['pct_change'])}% change. "
        f"Estimated total {direction} over {impact['days_affected']} day(s): {abs(impact['total_impact']):,.2f}."
    )


# ---------------------------------------------------------------------------
# Severity scoring
# ---------------------------------------------------------------------------

def calculate_severity_score(pct_change: float, days_affected: int, confidence: float = 0) -> dict:
    """
    Deterministic heuristic (not LLM-based) combining:
    - magnitude of the metric change (bigger swings = worse)
    - how many days it lasted (longer = worse)
    - confidence in the root cause (more certain = more actionable severity)

    Returns {"score": 0-100, "label": "Low"|"Medium"|"High"|"Critical"}
    """
    magnitude_component = min(abs(pct_change) * 0.6, 60)   # capped contribution
    duration_component = min(days_affected * 5, 30)         # capped contribution
    confidence_component = min(confidence * 0.1, 10)        # capped contribution

    score = round(magnitude_component + duration_component + confidence_component, 1)
    score = max(0, min(100, score))

    if score < 30:
        label = "Low"
    elif score < 60:
        label = "Medium"
    elif score < 85:
        label = "High"
    else:
        label = "Critical"

    return {"score": score, "label": label}
