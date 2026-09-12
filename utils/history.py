"""
history.py
----------
Lets the user run multiple investigations in one session and flip back
to any earlier one -- useful for comparing "why did sales fall Aug 12-18"
against a follow-up like "why did signups fall in September" without
losing the first result.

Pure logic, no Streamlit dependency, so it's easy to unit test. app.py
owns the actual session_state list; these are just the functions that
build and manage entries in it.
"""

from datetime import datetime

MAX_HISTORY = 10


def create_history_entry(question: str, analysis_result: dict, evidence_count: int = 0) -> dict:
    """Builds one history record from a completed investigation."""
    root_cause = (analysis_result or {}).get("root_cause", {})
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "question": question,
        "root_cause_description": root_cause.get("description", "N/A"),
        "confidence": root_cause.get("confidence", 0),
        "evidence_count": evidence_count,
        "full_result": analysis_result,
    }


def add_to_history(history_list: list, entry: dict, max_entries: int = MAX_HISTORY) -> list:
    """
    Returns a NEW list with `entry` appended, capped at `max_entries`
    (oldest entries drop off first). Non-mutating so it's safe to call
    directly with st.session_state.history and reassign the result.
    """
    updated = list(history_list) + [entry]
    if len(updated) > max_entries:
        updated = updated[-max_entries:]
    return updated


def format_history_label(entry: dict, max_question_chars: int = 40) -> str:
    """Short one-line label for a selectbox/list item, e.g. sidebar history picker."""
    question = entry.get("question", "")
    if len(question) > max_question_chars:
        question = question[:max_question_chars].rstrip() + "..."
    return f"{entry.get('timestamp', '')} — {question} ({entry.get('confidence', 0)}%)"


def get_entry(history_list: list, index: int) -> dict:
    """Safe lookup by index -- returns None instead of raising if out of range."""
    if 0 <= index < len(history_list):
        return history_list[index]
    return None
