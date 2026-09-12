from unittest import mock
from utils import groq_client


def test_extract_json_block_handles_clean_json():
    raw = '{"events": [{"date": "2025-08-12"}]}'
    assert groq_client._extract_json_block(raw) == {"events": [{"date": "2025-08-12"}]}


def test_extract_json_block_handles_markdown_fences():
    raw = '```json\n{"a": 1}\n```'
    assert groq_client._extract_json_block(raw) == {"a": 1}


def test_extract_json_block_handles_stray_text():
    raw = 'Here you go:\n{"a": 1}\nHope that helps!'
    assert groq_client._extract_json_block(raw) == {"a": 1}


def test_extract_json_block_returns_none_for_garbage():
    assert groq_client._extract_json_block("no json here") is None


def test_events_from_dataframe_produces_facts(sample_sales_df):
    events = groq_client.events_from_dataframe(sample_sales_df, "sales.csv")
    assert len(events) == len(sample_sales_df)
    assert all(e["type"] == "FACT" for e in events)
    assert all(e["source_file"] == "sales.csv" for e in events)


def test_critic_review_cannot_raise_confidence_above_original(sample_root_cause):
    """Regression test for a real safety requirement: a red-team critique
    must never be able to RAISE confidence above what the original
    analysis reported, even if the model tries to."""
    misbehaving_response = {
        "critique_summary": "test", "weaknesses": [], "most_critical_evidence": "test",
        "unconsidered_alternatives": [], "adjusted_confidence": 99, "verdict": "Holds up well",
    }
    with mock.patch("utils.groq_client._call_groq") as mock_call:
        mock_call.return_value = (misbehaving_response, "raw", None)
        result, error = groq_client.run_critic_review(sample_root_cause, [], [])
        assert error is None
        assert result["adjusted_confidence"] == sample_root_cause["confidence"]  # capped, not 99


def test_scenario_simulator_confidence_capped_at_70():
    misbehaving_response = {
        "scenario": "test", "estimated_outcome": "test", "estimated_confidence": 95,
        "supporting_patterns": [], "assumptions": [], "caveat": "test",
    }
    with mock.patch("utils.groq_client._call_groq") as mock_call:
        mock_call.return_value = (misbehaving_response, "raw", None)
        result, error = groq_client.simulate_scenario([], {}, "what if?")
        assert error is None
        assert result["estimated_confidence"] == 70


def test_translate_investigation_falls_back_on_dropped_key():
    with mock.patch("utils.groq_client._call_groq") as mock_call:
        mock_call.return_value = ({"field_a": "translated"}, "raw", None)  # field_b missing
        content = {"field_a": "Original A", "field_b": "Original B"}
        result, error = groq_client.translate_investigation(content, "Urdu")
        assert error is None
        assert result["field_a"] == "translated"
        assert result["field_b"] == "Original B"  # fell back to English, not lost


def test_error_propagation_on_api_failure():
    with mock.patch("utils.groq_client._call_groq") as mock_call:
        mock_call.return_value = (None, None, "API timeout")
        result, error = groq_client.generate_recommendations({}, [], [])
        assert result is None
        assert error == "API timeout"