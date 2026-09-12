"""
anomaly_detector.py
--------------------
Proactively scans uploaded numeric data for statistically unusual days --
BEFORE the user even asks a question. This is pure statistics (rolling
mean + standard deviation / z-score), not an LLM call, so it's instant,
free, and 100% deterministic -- a good complement to the LLM-driven
reasoning elsewhere in the app.

The idea: as soon as evidence is loaded, tell the user "hey, here's what
already looks off" so they know where to point their question.
"""

import pandas as pd


def find_numeric_columns(df: pd.DataFrame, date_col: str = None) -> list:
    if date_col is None:
        for col in df.columns:
            if "date" in col.lower():
                date_col = col
                break
    return [c for c in df.columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]


def detect_anomalies(df: pd.DataFrame, metric_col: str, date_col: str = None,
                      z_threshold: float = 1.5, window: int = 4) -> list:
    """
    Flags rows where `metric_col` deviates more than `z_threshold` standard
    deviations from a TRAILING baseline (the `window` days immediately
    before it -- the current/anomalous day is never included in its own
    baseline).

    This matters for sustained shifts (e.g. a metric that drops and stays
    low for a week): a centered rolling window would average the anomalous
    days into their own baseline and hide the shift. A trailing baseline
    instead asks "is this different from what came right before it?",
    which correctly flags the onset of a sustained change, not just brief
    one-day spikes.

    Returns a list of dicts: [{"date": ..., "value": ..., "expected": ...,
    "z_score": ..., "direction": "spike"|"drop"}], sorted by date.
    """
    if date_col is None:
        for col in df.columns:
            if "date" in col.lower():
                date_col = col
                break
    if date_col is None or metric_col not in df.columns:
        return []

    work_df = df.copy()
    work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
    work_df = work_df.dropna(subset=[date_col, metric_col]).sort_values(date_col).reset_index(drop=True)

    if len(work_df) < window + 1:
        return []  # not enough history to establish a trailing baseline

    trailing_mean = work_df[metric_col].shift(1).rolling(window=window, min_periods=window).mean()
    trailing_std = work_df[metric_col].shift(1).rolling(window=window, min_periods=window).std()

    anomalies = []
    for i, row in work_df.iterrows():
        expected = trailing_mean.iloc[i]
        std = trailing_std.iloc[i]

        if pd.isna(expected) or pd.isna(std) or std == 0:
            continue

        actual = row[metric_col]
        z_score = (actual - expected) / std

        if abs(z_score) >= z_threshold:
            anomalies.append({
                "date": row[date_col].strftime("%Y-%m-%d"),
                "metric": metric_col,
                "value": round(float(actual), 2),
                "expected": round(float(expected), 2),
                "z_score": round(float(z_score), 2),
                "direction": "spike" if z_score > 0 else "drop",
            })

    return anomalies


def scan_dataframe_for_anomalies(df: pd.DataFrame, filename: str,
                                  z_threshold: float = 1.5) -> list:
    """
    Convenience wrapper: scans every numeric column in a dataframe and
    returns a flat list of anomalies across all of them, tagged with the
    source filename so results can be merged across multiple uploaded files.
    """
    date_col = None
    for col in df.columns:
        if "date" in col.lower():
            date_col = col
            break

    numeric_cols = find_numeric_columns(df, date_col)
    all_anomalies = []
    for col in numeric_cols:
        col_anomalies = detect_anomalies(df, col, date_col, z_threshold=z_threshold)
        for a in col_anomalies:
            a["source_file"] = filename
        all_anomalies.extend(col_anomalies)

    all_anomalies.sort(key=lambda a: a["date"])
    return all_anomalies


def format_anomaly_summary(anomaly: dict) -> str:
    direction_word = "spiked to" if anomaly["direction"] == "spike" else "dropped to"
    return (
        f"{anomaly['source_file']}: {anomaly['metric']} {direction_word} "
        f"{anomaly['value']:,} on {anomaly['date']} (expected ~{anomaly['expected']:,}, "
        f"z-score {anomaly['z_score']})"
    )
