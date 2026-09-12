from utils import pattern_matcher as pm
from utils import history as history_log


def test_jaccard_identical_sets():
    assert pm.jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"}) == 1.0


def test_jaccard_no_overlap():
    assert pm.jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_empty_set_does_not_crash():
    assert pm.jaccard_similarity(set(), {"a"}) == 0.0


def test_recurring_incident_is_detected(sample_root_cause):
    history = []
    past_result = {"root_cause": {
        "description": "Mobile checkout payment failure caused by a broken redirect flow after a deploy",
        "confidence": 84,
        "evidence_sources": ["error_logs.txt", "complaints.txt", "sales.csv"],
    }}
    entry = history_log.create_history_entry("Why did checkout fail in July?", past_result, 40)
    history = history_log.add_to_history(history, entry)

    matches = pm.find_similar_incidents(sample_root_cause, history, threshold=0.1)
    assert len(matches) >= 1
    assert "checkout" in matches[0]["entry"]["question"].lower()


def test_unrelated_incident_is_not_matched(sample_root_cause):
    history = []
    unrelated_result = {"root_cause": {
        "description": "Warehouse inventory shortage delayed order fulfillment",
        "confidence": 70,
        "evidence_sources": ["inventory.csv"],
    }}
    entry = history_log.create_history_entry("Why were orders delayed?", unrelated_result, 25)
    history = history_log.add_to_history(history, entry)

    matches = pm.find_similar_incidents(sample_root_cause, history, threshold=0.3)
    assert len(matches) == 0


def test_empty_history_returns_empty_list(sample_root_cause):
    assert pm.find_similar_incidents(sample_root_cause, [], threshold=0.1) == []


def test_top_n_limits_results(sample_root_cause):
    history = []
    for i in range(5):
        result = {"root_cause": {
            "description": "Mobile checkout payment failure redirect flow deploy",
            "confidence": 80, "evidence_sources": ["error_logs.txt"],
        }}
        entry = history_log.create_history_entry(f"Q{i}", result, 10)
        history = history_log.add_to_history(history, entry)

    limited = pm.find_similar_incidents(sample_root_cause, history, threshold=0.1, top_n=2)
    assert len(limited) == 2