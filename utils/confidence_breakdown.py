"""
confidence_breakdown.py
------------------------
The root-cause engine reports a single confidence percentage, which can
feel like a black box. This module breaks that number down into the
underlying signals a human would actually look for when judging how
trustworthy a conclusion is:

1. Evidence Source Diversity -- how many independent files support this cause
2. Corroboration Strength    -- how many distinct supporting evidence points were cited
3. Lead Over Alternatives    -- how far ahead this cause is versus the next-best explanation

This is a deterministic heuristic over data we already have (not another
LLM call) -- it's meant to explain the SHAPE of the evidence behind the
number, not to recompute the LLM's exact internal reasoning.
"""


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def calculate_confidence_breakdown(root_cause: dict, alternative_causes: list = None) -> dict:
    """
    root_cause: {"description", "confidence", "supporting_evidence": [...], "evidence_sources": [...]}
    alternative_causes: [{"description", "confidence", ...}, ...]

    Returns {"overall_confidence": int, "factors": [{"label", "score", "explanation"}, ...]}
    """
    alternative_causes = alternative_causes or []

    evidence_sources = root_cause.get("evidence_sources", []) or []
    supporting_evidence = root_cause.get("supporting_evidence", []) or []
    overall_confidence = root_cause.get("confidence", 0)

    # --- Factor 1: Evidence Source Diversity ---
    n_sources = len(set(evidence_sources))
    diversity_score = _clamp(n_sources * 25)  # 4+ distinct files = fully strong
    if n_sources == 0:
        diversity_explanation = "No source files were explicitly cited for this cause."
    elif n_sources == 1:
        diversity_explanation = "Only 1 source file supports this -- a single point of failure in the evidence."
    else:
        diversity_explanation = f"{n_sources} independent files corroborate this cause."

    # --- Factor 2: Corroboration Strength ---
    n_evidence = len(supporting_evidence)
    corroboration_score = _clamp(n_evidence * 30)  # 3+ bullets = fully strong
    if n_evidence == 0:
        corroboration_explanation = "No specific supporting evidence points were listed."
    elif n_evidence == 1:
        corroboration_explanation = "Only 1 specific evidence point was cited."
    else:
        corroboration_explanation = f"{n_evidence} specific evidence points were cited in support."

    # --- Factor 3: Lead Over Alternatives ---
    if not alternative_causes:
        lead_score = None
        lead_explanation = "No alternative explanations were considered for comparison."
    else:
        top_alt_confidence = max(a.get("confidence", 0) for a in alternative_causes)
        lead_margin = overall_confidence - top_alt_confidence
        lead_score = round(_clamp(lead_margin * 1.5), 1)
        lead_explanation = (
            f"Leads the next-best explanation by {lead_margin} percentage points "
            f"({overall_confidence}% vs {top_alt_confidence}%)."
        )

    factors = [
        {"label": "Evidence Source Diversity", "score": round(diversity_score, 1), "explanation": diversity_explanation},
        {"label": "Corroboration Strength", "score": round(corroboration_score, 1), "explanation": corroboration_explanation},
        {"label": "Lead Over Alternatives", "score": lead_score, "explanation": lead_explanation},
    ]

    return {
        "overall_confidence": overall_confidence,
        "factors": factors,
    }


def build_breakdown_chart(breakdown: dict):
    """Optional horizontal bar chart of the factors, for visual display alongside the text."""
    import plotly.graph_objects as go

    factors = breakdown.get("factors", [])
    if not factors:
        fig = go.Figure()
        fig.update_layout(title="No confidence breakdown available")
        return fig

    labels = [f["label"] for f in factors]
    scores = [f["score"] if f["score"] is not None else 0 for f in factors]
    colors = [
        "#6b7280" if f["score"] is None else
        "#22c55e" if f["score"] >= 70 else
        "#f59e0b" if f["score"] >= 40 else "#dc2626"
        for f in factors
    ]
    labels_text = [f"{f['score']}%" if f["score"] is not None else "N/A" for f in factors]

    fig = go.Figure(go.Bar(
        x=scores, y=labels, orientation="h",
        marker_color=colors,
        text=labels_text,
        textposition="auto",
    ))
    fig.update_layout(
        title="What's Behind the Confidence Score",
        xaxis=dict(range=[0, 100], title="Strength"),
        height=220,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    fig.update_yaxes(autorange="reversed")
    return fig
