"""
pattern_matcher.py
-------------------
Compares the CURRENT root cause against past investigations already saved
in the history log (utils/history.py) and flags ones that look similar --
"this looks like the Aug 12 incident" -- using two deterministic signals:

1. Text similarity (Jaccard overlap of meaningful words in the root-cause
   descriptions)
2. Evidence overlap (how many of the same source files were cited)

No LLM call -- this is fast, free, and fully explainable (you can see
exactly which words/files matched), which matters for a "why did you flag
this as similar" trust question.
"""

import re

STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "was",
    "were",
    "to",
    "of",
    "in",
    "on",
    "for",
    "and",
    "or",
    "by",
    "with",
    "this",
    "that",
    "it",
    "its",
    "due",
    "from",
    "after",
    "before",
    "at",
    "as",
    "be", "been",
    "has",
    "have",
    "had",
    "not",
    "but",
    "than",
    "then",
    "into",
    "over",
    "during",
}


def _tokenize(text: str) -> set:
    if not text:
        return set()
    words = re.findall(r"[a-z0-9]+", str(text).lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _evidence_overlap(sources_a: list, sources_b: list):
    set_a, set_b = set(sources_a or []), set(sources_b or [])
    if not set_a or not set_b:
        return 0.0, []
    union = set_a | set_b
    shared = sorted(set_a & set_b)
    return (len(shared) / len(union) if union else 0.0), shared


def find_similar_incidents(
    current_root_cause,
    history_entries: list,
    threshold: float = 0.15,
    top_n: int = 3,
) -> list:
    """
    current_root_cause: string or dictionary containing root cause information
    history_entries: list of entries from utils.history
    """
    # Safe handling: Check if dict or string
    if isinstance(current_root_cause, dict):
        desc = current_root_cause.get("description", "")
        current_sources = current_root_cause.get("evidence_sources", [])
    elif isinstance(current_root_cause, str):
        desc = current_root_cause
        current_sources = []
    else:
        desc = str(current_root_cause or "")
        current_sources = []

    current_tokens = _tokenize(desc)

    matches = []
    for entry in history_entries:
        past_description = entry.get("root_cause_description", "")
        past_tokens = _tokenize(past_description)
        text_sim = jaccard_similarity(current_tokens, past_tokens)

        past_root_cause = (entry.get("full_result") or {}).get(
            "root_cause", {}
        )
        if isinstance(past_root_cause, dict):
            past_sources = past_root_cause.get("evidence_sources", [])
        else:
            past_sources = []

        evidence_score, shared_files = _evidence_overlap(
            current_sources, past_sources
        )

        combined_score = round(0.6 * text_sim + 0.4 * evidence_score, 3)

        if combined_score >= threshold:
            matches.append({
                "entry": entry,
                "combined_score": combined_score,
                "text_similarity": round(text_sim, 3),
                "evidence_overlap_score": round(evidence_score, 3),
                "matched_terms": sorted(current_tokens & past_tokens),
                "shared_evidence_files": shared_files,
            })

    matches.sort(key=lambda m: m["combined_score"], reverse=True)
    return matches[:top_n]


def format_similarity_summary(match: dict) -> str:
    entry = match["entry"]
    pct = round(match["combined_score"] * 100)
    reasons = []
    if match["matched_terms"]:
        reasons.append(f"shared terms: {', '.join(match['matched_terms'][:5])}")
    if match["shared_evidence_files"]:
        reasons.append(
            f"same evidence files: {', '.join(match['shared_evidence_files'][:3])}"
        )
    reason_str = "; ".join(reasons) if reasons else "similar overall pattern"

    return (
        f"{pct}% similar to a past investigation from {entry.get('timestamp', 'an earlier session')} "
        f'("{entry.get("question", "")}") -- {reason_str}.'
    )