"""
timeline.py
-----------
Takes evidence events from multiple parsed files (already extracted via
groq_client.py) and:
1. Merges + sorts them into one chronological timeline
2. Builds an interactive Plotly "swimlane" chart (one lane per source file)
3. Builds the confidence bar chart for root cause vs alternative explanations

Kept free of Streamlit imports so it can be unit-tested on its own.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


CLASSIFICATION_COLORS = {
    "FACT": "#6c757d",             # neutral gray
    "EVENT": "#3b82f6",            # blue
    "CORRELATION": "#eab308",      # yellow
    "POSSIBLE CAUSE": "#f97316",   # orange
    "CONFIRMED CAUSE": "#dc2626",  # red
}

DEFAULT_COLOR = "#94a3b8"


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

def merge_events(list_of_event_lists: list) -> list:
    """
    Takes multiple lists of event dicts (one list per source file) and
    returns one flat, chronologically sorted list.
    Drops events with unparseable/missing dates instead of crashing.
    """
    merged = []
    for event_list in list_of_event_lists:
        merged.extend(event_list)

    def _sort_key(event):
        try:
            return pd.to_datetime(event.get("date"))
        except Exception:
            return pd.Timestamp.max  # push unparseable dates to the end

    valid_events = [e for e in merged if e.get("date")]
    valid_events.sort(key=_sort_key)
    return valid_events


def filter_by_date_range(events: list, start_date=None, end_date=None) -> list:
    """Optional helper to narrow the timeline to a window the user asked about."""
    if not start_date and not end_date:
        return events

    start_ts = pd.to_datetime(start_date) if start_date else pd.Timestamp.min
    end_ts = pd.to_datetime(end_date) if end_date else pd.Timestamp.max

    filtered = []
    for e in events:
        try:
            ts = pd.to_datetime(e.get("date"))
            if start_ts <= ts <= end_ts:
                filtered.append(e)
        except Exception:
            continue
    return filtered


def events_to_dataframe(events: list) -> pd.DataFrame:
    """Flattens events into a DataFrame for easy display in st.dataframe()."""
    if not events:
        return pd.DataFrame(columns=["date", "type", "description", "source_file"])

    rows = []
    for e in events:
        rows.append({
            "date": e.get("date"),
            "type": e.get("classification", e.get("type", "FACT")),
            "description": e.get("description", ""),
            "source_file": e.get("source_file", "unknown"),
        })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.sort_values("date")


# ---------------------------------------------------------------------------
# Plotly: timeline swimlane chart
# ---------------------------------------------------------------------------

def build_timeline_figure(events: list, title: str = "Evidence Timeline") -> go.Figure:
    """
    Builds a swimlane-style scatter chart:
    x = date, y = source file (one lane per file), color = classification,
    hover text = full description.

    Works with either raw extracted events (type: FACT/EVENT) or the
    LLM-classified timeline from analyze_root_cause (classification: ...).
    """
    df = events_to_dataframe(events)

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No dated evidence found yet",
            xaxis_title="Date",
            yaxis_title="Source",
        )
        return fig

    fig = go.Figure()

    for classification in df["type"].unique():
        subset = df[df["type"] == classification]
        color = CLASSIFICATION_COLORS.get(classification, DEFAULT_COLOR)

        fig.add_trace(go.Scatter(
            x=subset["date"],
            y=subset["source_file"],
            mode="markers",
            name=classification,
            marker=dict(size=14, color=color, line=dict(width=1, color="white")),
            hovertext=subset["description"],
            hovertemplate="<b>%{y}</b><br>%{x|%Y-%m-%d}<br>%{hovertext}<extra></extra>",
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Evidence Source",
        legend_title="Classification",
        height=max(300, 60 * df["source_file"].nunique() + 150),
        hovermode="closest",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


# ---------------------------------------------------------------------------
# Plotly: confidence bar chart (root cause vs alternatives)
# ---------------------------------------------------------------------------

def build_confidence_chart(root_cause: dict, alternative_causes: list) -> go.Figure:
    """
    root_cause: {"description": ..., "confidence": 87, ...}
    alternative_causes: [{"description": ..., "confidence": 21}, ...]
    """
    labels = []
    values = []
    colors = []

    if root_cause:
        labels.append(_shorten(root_cause.get("description", "Root cause")))
        values.append(root_cause.get("confidence", 0))
        colors.append("#dc2626")  # red = the leading cause

    for alt in alternative_causes or []:
        labels.append(_shorten(alt.get("description", "Alternative")))
        values.append(alt.get("confidence", 0))
        colors.append("#94a3b8")  # gray = alternatives

    if not labels:
        fig = go.Figure()
        fig.update_layout(title="No root-cause analysis yet")
        return fig

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v}%" for v in values],
        textposition="auto",
    ))

    fig.update_layout(
        title="Likely Cause vs Alternative Explanations",
        xaxis_title="Confidence (%)",
        xaxis=dict(range=[0, 100]),
        height=max(250, 60 * len(labels) + 100),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    fig.update_yaxes(autorange="reversed")  # highest confidence on top
    return fig


def _shorten(text: str, max_chars: int = 60) -> str:
    if not text:
        return ""
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "..."
