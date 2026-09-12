import pandas as pd
from utils import anomaly_detector as ad


def test_detects_sustained_drop_via_trailing_baseline(sample_sales_df):
    """Regression test for a real bug found during development: a centered
    rolling window hid sustained drops because the anomalous days ended up
    inside their own baseline. The trailing-baseline fix must catch this."""
    anomalies = ad.detect_anomalies(sample_sales_df, "revenue", z_threshold=1.3)
    dates_flagged = {a["date"] for a in anomalies}
    assert "2025-08-12" in dates_flagged  # onset of the drop
    assert any(a["direction"] == "drop" for a in anomalies)


def test_no_anomalies_on_flat_data():
    flat_df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10).strftime("%Y-%m-%d"),
        "value": [100] * 10,
    })
    assert ad.detect_anomalies(flat_df, "value") == []


def test_no_crash_on_too_little_data():
    tiny_df = pd.DataFrame({"date": ["2025-01-01", "2025-01-02"], "value": [10, 12]})
    assert ad.detect_anomalies(tiny_df, "value") == []


def test_no_crash_without_date_column():
    no_date_df = pd.DataFrame({"value": [1, 2, 3, 4, 5]})
    assert ad.detect_anomalies(no_date_df, "value") == []


def test_scan_dataframe_tags_source_file(sample_sales_df):
    results = ad.scan_dataframe_for_anomalies(sample_sales_df, "sales.csv", z_threshold=1.3)
    assert all(r["source_file"] == "sales.csv" for r in results)