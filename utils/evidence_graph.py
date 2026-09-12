"""
evidence_graph.py
------------------
Builds a bipartite network graph connecting evidence SOURCE FILES (bottom row)
to CAUSES -- root cause + alternatives (top row) -- so a judge/user can see at
a glance which files actually back which explanation, and how much evidence
the leading cause has versus the alternatives.

Deliberately implemented with plain Plotly (no networkx) to keep the
dependency list small and cloud-deploy friendly -- the graph is always small
(a handful of causes, a handful of files) so a manual two-row layout is both
simpler and clearer than a force-directed layout would be here.
"""

import plotly.graph_objects as go


ROOT_CAUSE_COLOR = "#dc2626"       # red
ALT_CAUSE_COLOR = "#94a3b8"        # gray
EVIDENCE_COLOR = "#3b82f6"         # blue
EDGE_COLOR_ROOT = "rgba(220, 38, 38, 0.55)"
EDGE_COLOR_ALT = "rgba(148, 163, 184, 0.4)"


def _shorten(text: str, max_chars: int = 40) -> str:
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "..."


def build_evidence_graph(root_cause: dict, alternative_causes: list = None) -> go.Figure:
    """
    root_cause: {"description": ..., "confidence": 87, "evidence_sources": [...]}
    alternative_causes: [{"description": ..., "confidence": 21, "evidence_sources": [...]}, ...]

    Returns a Plotly figure: cause nodes on top, evidence-file nodes on bottom,
    lines connecting each cause to the files that support it.
    """
    alternative_causes = alternative_causes or []

    causes = []
    if root_cause and root_cause.get("description"):
        causes.append({
            "label": _shorten(root_cause.get("description", "Root cause")),
            "full_label": root_cause.get("description", "Root cause"),
            "confidence": root_cause.get("confidence", 0),
            "sources": root_cause.get("evidence_sources", []) or [],
            "is_root": True,
        })
    for alt in alternative_causes:
        causes.append({
            "label": _shorten(alt.get("description", "Alternative")),
            "full_label": alt.get("description", "Alternative"),
            "confidence": alt.get("confidence", 0),
            "sources": alt.get("evidence_sources", []) or [],
            "is_root": False,
        })

    if not causes:
        fig = go.Figure()
        fig.update_layout(title="No causes to graph yet — run an investigation first.")
        return fig

    # Collect unique evidence files across all causes, preserving first-seen order
    all_files = []
    for c in causes:
        for f in c["sources"]:
            if f not in all_files:
                all_files.append(f)

    if not all_files:
        fig = go.Figure()
        fig.update_layout(title="No evidence sources are attached to the causes yet.")
        return fig

    # --- Layout: causes on y=1, files on y=0, evenly spaced along x ---
    cause_x = _even_positions(len(causes))
    file_x = _even_positions(len(all_files))
    file_x_lookup = dict(zip(all_files, file_x))

    fig = go.Figure()

    # Edges first, so nodes render on top of the lines
    for cause, cx in zip(causes, cause_x):
        edge_color = EDGE_COLOR_ROOT if cause["is_root"] else EDGE_COLOR_ALT
        edge_width = 3 if cause["is_root"] else 1.5
        for source_file in cause["sources"]:
            fx = file_x_lookup.get(source_file)
            if fx is None:
                continue
            fig.add_trace(go.Scatter(
                x=[cx, fx], y=[1, 0],
                mode="lines",
                line=dict(color=edge_color, width=edge_width),
                hoverinfo="skip",
                showlegend=False,
            ))

    # Cause nodes (top row)
    fig.add_trace(go.Scatter(
        x=cause_x,
        y=[1] * len(causes),
        mode="markers+text",
        name="Causes",
        marker=dict(
            size=[46 if c["is_root"] else 32 for c in causes],
            color=[ROOT_CAUSE_COLOR if c["is_root"] else ALT_CAUSE_COLOR for c in causes],
            line=dict(width=2, color="white"),
        ),
        text=[c["label"] for c in causes],
        textposition="top center",
        hovertext=[f"{c['full_label']}<br>Confidence: {c['confidence']}%" for c in causes],
        hovertemplate="%{hovertext}<extra></extra>",
    ))

    # Evidence file nodes (bottom row)
    fig.add_trace(go.Scatter(
        x=file_x,
        y=[0] * len(all_files),
        mode="markers+text",
        name="Evidence files",
        marker=dict(size=24, color=EVIDENCE_COLOR, symbol="square", line=dict(width=2, color="white")),
        text=all_files,
        textposition="bottom center",
        hovertext=[f"Evidence file: {f}" for f in all_files],
        hovertemplate="%{hovertext}<extra></extra>",
    ))

    fig.update_layout(
        title="Evidence → Cause Network",
        showlegend=True,
        xaxis=dict(visible=False, range=[-0.15, 1.15]),
        yaxis=dict(visible=False, range=[-0.3, 1.3]),
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _even_positions(n: int) -> list:
    """Evenly spaces n points between 0.05 and 0.95 (single point centers at 0.5)."""
    if n == 1:
        return [0.5]
    step = 0.9 / (n - 1)
    return [round(0.05 + i * step, 4) for i in range(n)]
