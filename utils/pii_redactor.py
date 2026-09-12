"""
pii_redactor.py
----------------
Runs BEFORE any raw evidence text (customer complaints, emails, logs) is
sent to the Groq API. Uploaded evidence often contains real customer PII
(emails, phone numbers, card numbers) that has no business being sent to
a third-party LLM provider just to extract a dated event out of it.

This is deliberately regex-based (not LLM-based) so it's:
- Free and instant (no extra API call)
- Deterministic and auditable (a judge/reviewer can read exactly what it does)
- Applied even if the LLM extraction call fails, since redaction always
  happens first regardless of what happens downstream

Note: this is a best-effort layer for a hackathon prototype, not a
compliance-grade PII scrubber -- it's here to demonstrate the *practice*
of not sending raw customer data to a third party unnecessarily.
"""

import re


# Order matters: card numbers before generic digit sequences, etc.
PATTERNS = [
    ("EMAIL", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ \-]?){13,19}\b")),
    ("PHONE", re.compile(r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(\d{2,4}\)[\s\-.]?)?\d{3,4}[\s\-.]?\d{3,4}(?:[\s\-.]?\d{2,4})?\b")),
    ("SSN_LIKE", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]

# Phone regex is intentionally broad -- run it AFTER credit card / SSN so those
# more specific, higher-confidence patterns claim their matches first.
_ORDERED_PATTERNS = [
    ("EMAIL", PATTERNS[0][1]),
    ("SSN_LIKE", PATTERNS[3][1]),
    ("CREDIT_CARD", PATTERNS[1][1]),
    ("PHONE", PATTERNS[2][1]),
]


def redact_text(text: str) -> dict:
    """
    Returns {"redacted_text": str, "redaction_count": int, "redaction_types": {label: count}}.
    Replaces each match with a bracketed placeholder like [REDACTED_EMAIL].
    """
    if not text:
        return {"redacted_text": text, "redaction_count": 0, "redaction_types": {}}

    working_text = text
    counts = {}

    for label, pattern in _ORDERED_PATTERNS:
        matches = pattern.findall(working_text)
        if matches:
            counts[label] = counts.get(label, 0) + len(matches)
            working_text = pattern.sub(f"[REDACTED_{label}]", working_text)

    total = sum(counts.values())
    return {
        "redacted_text": working_text,
        "redaction_count": total,
        "redaction_types": counts,
    }


def redact_file_text(parsed_file: dict) -> dict:
    """
    Convenience wrapper for the parsers.py output shape: redacts `text` in
    place if present, and reports what was redacted. Does not touch
    dataframes (tabular evidence is numeric/dated, not free text, so PII
    risk there is minimal and out of scope for this pass).
    """
    text = parsed_file.get("text")
    if not text:
        return {"redacted_file": parsed_file, "redaction_summary": None}

    result = redact_text(text)
    redacted_file = dict(parsed_file)
    redacted_file["text"] = result["redacted_text"]

    summary = None
    if result["redaction_count"] > 0:
        summary = {
            "filename": parsed_file.get("filename"),
            "count": result["redaction_count"],
            "types": result["redaction_types"],
        }

    return {"redacted_file": redacted_file, "redaction_summary": summary}


def format_redaction_summary(summaries: list) -> str:
    """Human-readable one-liner for a list of per-file redaction summaries (skips None entries)."""
    active = [s for s in summaries if s]
    if not active:
        return "No PII detected in uploaded evidence."

    parts = []
    for s in active:
        type_str = ", ".join(f"{v} {k.lower()}" for k, v in s["types"].items())
        parts.append(f"{s['filename']} ({type_str})")

    return f"Redacted PII before sending to AI: {'; '.join(parts)}."
