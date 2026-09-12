from utils import timeline as tl


def test_merge_events_sorts_chronologically():
    list_a = [{"date": "2025-08-15", "description": "later", "source_file": "a.csv"}]
    list_b = [{"date": "2025-08-11", "description": "earlier", "source_file": "b.csv"}]
    merged = tl.merge_events([list_a, list_b])
    assert merged[0]["description"] == "earlier"
    assert merged[1]["description"] == "later"


def test_merge_events_drops_missing_dates():
    events = [{"description": "no date", "source_file": "a.csv"}]
    merged = tl.merge_events([events])
    assert merged == []


def test_filter_by_date_range():
    events = [
        {"date": "2025-08-10", "description": "x"},
        {"date": "2025-08-15", "description": "y"},
        {"date": "2025-08-20", "description": "z"},
    ]
    filtered = tl.filter_by_date_range(events, "2025-08-12", "2025-08-18")
    assert len(filtered) == 1
    assert filtered[0]["description"] == "y"


def test_events_to_dataframe_shape():
    events = [{"date": "2025-08-10", "type": "FACT", "description": "x", "source_file": "a.csv"}]
    df = tl.events_to_dataframe(events)
    assert list(df.columns) == ["date", "type", "description", "source_file"]
    assert len(df) == 1


def test_events_to_dataframe_empty_list():
    df = tl.events_to_dataframe([])
    assert len(df) == 0