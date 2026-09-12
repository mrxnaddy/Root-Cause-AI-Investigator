from utils import impact_calculator as ic


def test_find_date_column(sample_sales_df):
    assert ic.find_date_column(sample_sales_df) == "date"


def test_find_numeric_columns_excludes_date(sample_sales_df):
    cols = ic.find_numeric_columns(sample_sales_df)
    assert "date" not in cols
    assert "revenue" in cols
    assert "orders" in cols


def test_calculate_financial_impact_matches_known_numbers(sample_sales_df):
    result = ic.calculate_financial_impact(
        sample_sales_df, "revenue", "2025-08-12", "2025-08-18", baseline_days=4
    )
    assert result["error"] is None
    # Baseline (Aug 8-11): (18200+17950+18400+18100)/4 = 18162.5
    assert result["baseline_avg"] == 18162.5
    assert result["days_affected"] == 7
    assert result["pct_change"] < 0  # a real drop


def test_impact_error_when_no_data_in_range(sample_sales_df):
    result = ic.calculate_financial_impact(sample_sales_df, "revenue", "2030-01-01", "2030-01-05")
    assert result["error"] is not None


def test_impact_error_on_missing_column(sample_sales_df):
    result = ic.calculate_financial_impact(sample_sales_df, "nonexistent", "2025-08-12", "2025-08-18")
    assert result["error"] is not None


def test_impact_error_when_no_baseline_data(sample_sales_df):
    # Incident window starting at the very first row leaves no prior days for a baseline.
    result = ic.calculate_financial_impact(sample_sales_df, "revenue", "2025-08-08", "2025-08-09")
    assert result["error"] is not None


def test_severity_score_ranges():
    low = ic.calculate_severity_score(pct_change=-2, days_affected=1, confidence=50)
    high = ic.calculate_severity_score(pct_change=-80, days_affected=10, confidence=95)
    assert low["label"] in ("Low", "Medium")
    assert high["label"] in ("High", "Critical")
    assert 0 <= low["score"] <= 100
    assert 0 <= high["score"] <= 100


def test_severity_score_never_exceeds_100():
    extreme = ic.calculate_severity_score(pct_change=-500, days_affected=100, confidence=100)
    assert extreme["score"] <= 100