from utils import pii_redactor


def test_redacts_email():
    result = pii_redactor.redact_text("Contact me at jane.doe@example.com please.")
    assert "[REDACTED_EMAIL]" in result["redacted_text"]
    assert "jane.doe@example.com" not in result["redacted_text"]


def test_redacts_phone_number_fully_not_partially():
    """Regression test for a real bug: the phone number used to be only
    partially redacted (e.g. '+1 415-555-2671' -> '[REDACTED]-2671'),
    leaking the last four digits."""
    result = pii_redactor.redact_text("Call +1 415-555-2671 for support.")
    assert "2671" not in result["redacted_text"]
    assert "555" not in result["redacted_text"]


def test_redacts_dot_separated_phone():
    result = pii_redactor.redact_text("Call 415.555.2671 now.")
    assert "2671" not in result["redacted_text"]


def test_redacts_credit_card_like_number():
    result = pii_redactor.redact_text("Card number 4532 1234 5678 9010 was charged.")
    assert "[REDACTED_CREDIT_CARD]" in result["redacted_text"]


def test_no_false_positives_on_ticket_numbers_and_timestamps():
    text = '[2025-08-13 09:12] Ticket #4471 - Customer: "checkout failed twice."'
    result = pii_redactor.redact_text(text)
    assert result["redaction_count"] == 0


def test_empty_text_does_not_crash():
    result = pii_redactor.redact_text("")
    assert result["redaction_count"] == 0
    result_none = pii_redactor.redact_text(None)
    assert result_none["redaction_count"] == 0


def test_redact_file_text_only_touches_text_field():
    parsed = {"filename": "notes.txt", "text": "Email me: a@b.com", "dataframe": None}
    wrapped = pii_redactor.redact_file_text(parsed)
    assert "[REDACTED_EMAIL]" in wrapped["redacted_file"]["text"]
    assert wrapped["redaction_summary"]["count"] == 1


def test_clean_file_reports_no_pii():
    parsed = {"filename": "clean.txt", "text": "Nothing sensitive here.", "dataframe": None}
    wrapped = pii_redactor.redact_file_text(parsed)
    assert wrapped["redaction_summary"] is None
    summary = pii_redactor.format_redaction_summary([wrapped["redaction_summary"]])
    assert "no pii" in summary.lower()