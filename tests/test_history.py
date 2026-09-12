from utils import history as history_log


def test_create_entry_captures_root_cause(sample_root_cause):
    result = {"root_cause": sample_root_cause}
    entry = history_log.create_history_entry("Why did sales fall?", result, 54)
    assert entry["question"] == "Why did sales fall?"
    assert entry["confidence"] == 87
    assert entry["evidence_count"] == 54


def test_add_to_history_is_non_mutating():
    history = []
    entry = history_log.create_history_entry("Q", {}, 0)
    new_history = history_log.add_to_history(history, entry)
    assert history == []
    assert len(new_history) == 1


def test_history_cap_keeps_most_recent():
    history = []
    for i in range(15):
        entry = history_log.create_history_entry(f"Question {i}", {}, i)
        history = history_log.add_to_history(history, entry)
    assert len(history) == history_log.MAX_HISTORY
    assert history[0]["question"] == "Question 5"
    assert history[-1]["question"] == "Question 14"


def test_get_entry_safe_lookup():
    history = [history_log.create_history_entry("Q", {}, 0)]
    assert history_log.get_entry(history, 0) is not None
    assert history_log.get_entry(history, 99) is None
    assert history_log.get_entry(history, -1) is None