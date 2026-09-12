import io
from utils import parsers


class FakeUploadedFile(io.BytesIO):
    """Mimics Streamlit's UploadedFile: has a .name attribute alongside file-like behavior."""
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name


def test_detects_csv_type():
    f = FakeUploadedFile("sales.csv", b"date,revenue\n2025-08-08,18200\n")
    result = parsers.parse_file(f)
    assert result["file_type"] == "csv"
    assert result["error"] is None
    assert result["dataframe"] is not None
    assert list(result["dataframe"].columns) == ["date", "revenue"]


def test_detects_txt_type():
    f = FakeUploadedFile("notes.txt", b"Some plain text evidence.")
    result = parsers.parse_file(f)
    assert result["file_type"] == "txt"
    assert result["text"] == "Some plain text evidence."


def test_detects_log_type():
    f = FakeUploadedFile("server.log", b"2025-08-12 ERROR something broke")
    result = parsers.parse_file(f)
    assert result["file_type"] == "log"


def test_unsupported_extension_does_not_crash():
    f = FakeUploadedFile("weird.xyz", b"???")
    result = parsers.parse_file(f)
    assert result["file_type"] == "unsupported"
    assert result["error"] is not None


def test_image_type_uses_paste_fallback_not_ocr():
    result = parsers.parse_image_placeholder("screenshot.png")
    assert result["file_type"] == "image"
    assert result["text"] is None
    assert "paste" in result["preview"].lower()


def test_malformed_csv_returns_error_not_exception():
    # A file with a .csv extension but binary garbage inside should fail
    # gracefully via the error field, not raise.
    f = FakeUploadedFile("broken.csv", b"\x00\x01\x02\x03not,valid,csv\x00")
    result = parsers.parse_file(f)
    assert result["file_type"] == "csv"
    # Either it parses something or reports an error -- it must not raise.
    assert result["error"] is None or isinstance(result["error"], str)


def test_parse_many_handles_a_batch():
    files = [
        FakeUploadedFile("a.csv", b"x,y\n1,2\n"),
        FakeUploadedFile("b.txt", b"hello"),
    ]
    results = parsers.parse_many(files)
    assert len(results) == 2
    assert results[0]["filename"] == "a.csv"
    assert results[1]["filename"] == "b.txt"