import pandas as pd
from utils import correlation_engine as ce


def test_perfect_positive_correlation():
    r = ce.calculate_pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
    assert abs(r - 1.0) < 1e-6


def test_perfect_negative_correlation():
    r = ce.calculate_pearson([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
    assert abs(r - (-1.0)) < 1e-6


def test_constant_series_returns_none():
    assert ce.calculate_pearson([5, 5, 5, 5], [1, 2, 3, 4]) is None


def test_too_few_points_returns_none():
    assert ce.calculate_pearson([1, 2], [3, 4]) is None


def test_correlate_metrics_across_two_dataframes(sample_sales_df):
    ad_df = pd.DataFrame({
        "date": sample_sales_df["date"],
        "ad_conversions": [210, 205, 215, 198, 150, 120, 98, 90, 95, 88, 92, 205, 212],
    })
    result = ce.correlate_metrics(sample_sales_df, "revenue", "sales.csv", ad_df, "ad_conversions", "ad_spend.csv")
    assert result["error"] is None
    assert result["r"] > 0.9  # these were designed to move together
    assert result["strength"] == "Strong"


def test_segment_column_pivots_instead_of_averaging():
    """Regression test: a file with two rows per date (e.g. device=mobile/desktop)
    must be pivoted, not blindly merged, or a real signal gets diluted."""
    ga_df = pd.DataFrame({
        "date": ["2025-08-08", "2025-08-08", "2025-08-09", "2025-08-09"],
        "device": ["mobile", "desktop", "mobile", "desktop"],
        "sessions": [5200, 3100, 5150, 3050],
    })
    expanded = ce.expand_categorical_segments(ga_df, "date")
    assert len(expanded) == 2  # one row per date now
    assert "sessions_mobile" in expanded.columns
    assert "sessions_desktop" in expanded.columns


def test_expand_leaves_normal_files_unchanged(sample_sales_df):
    result = ce.expand_categorical_segments(sample_sales_df, "date")
    assert list(result.columns) == list(sample_sales_df.columns)


def test_no_overlapping_dates_returns_error(sample_sales_df):
    other_df = pd.DataFrame({"date": ["2099-01-01", "2099-01-02"], "value": [1, 2]})
    result = ce.correlate_metrics(sample_sales_df, "revenue", "sales.csv", other_df, "value", "other.csv")
    assert result["error"] is not None