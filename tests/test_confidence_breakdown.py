from utils import confidence_breakdown as cb


def test_strong_case_scores_high(sample_root_cause, sample_alternatives):
    breakdown = cb.calculate_confidence_breakdown(sample_root_cause, sample_alternatives)
    assert breakdown["overall_confidence"] == 87
    diversity = breakdown["factors"][0]
    assert diversity["score"] == 100  # 4 sources * 25, capped at 100


def test_no_alternatives_gives_none_not_misleading_number(sample_root_cause):
    """Regression test for a real bug: 'Lead Over Alternatives' used to show
    a numeric score (implying it beat a 0% alternative) even when there
    were no alternatives to compare against at all."""
    breakdown = cb.calculate_confidence_breakdown(sample_root_cause, [])
    lead_factor = breakdown["factors"][2]
    assert lead_factor["score"] is None
    assert "no alternative" in lead_factor["explanation"].lower()


def test_empty_root_cause_does_not_crash():
    breakdown = cb.calculate_confidence_breakdown({}, [])
    assert breakdown["overall_confidence"] == 0
    assert len(breakdown["factors"]) == 3


def test_weak_case_scores_low():
    weak_root_cause = {
        "description": "Maybe seasonal", "confidence": 40,
        "supporting_evidence": [], "evidence_sources": ["sales.csv"],
    }
    breakdown = cb.calculate_confidence_breakdown(weak_root_cause, [])
    diversity = breakdown["factors"][0]
    corroboration = breakdown["factors"][1]
    assert diversity["score"] == 25   # only 1 source
    assert corroboration["score"] == 0  # no supporting evidence listed