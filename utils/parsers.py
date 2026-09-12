"""
parsers.py
----------
Turns messy uploaded evidence (CSV, XLSX, PDF, TXT, LOG, DOCX, EML/email text)
into one common structure so the rest of the app doesn't care what file
type it originally was.

Every parser returns a dict shaped like:
{
    "filename": str,
    "file_type": "csv" | "xlsx" | "pdf" | "txt" | "log" | "docx" | "email" | "unsupported",
    "dataframe": pandas.DataFrame or None,   # only for tabular files
    "text": str or None,                     # only for unstructured files
    "preview": str,                          # short human-readable preview for the UI
    "error": str or None,                    # set if parsing failed
}
"""

import io
import pandas as pd


def _safe_preview(text: str, max_chars: int = 400) -> str:
    """Trim long text down to something safe to show in a UI preview."""
    if text is None:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " ... [truncated]"


def _detect_type(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith((".xlsx", ".xls")):
        return "xlsx"
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".docx"):
        return "docx"
    if name.endswith((".log",)):
        return "log"
    if name.endswith((".eml",)):
        return "email"
    if name.endswith((".txt", ".md")):
        return "txt"
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "image"
    return "unsupported"


def parse_csv(file_obj, filename: str) -> dict:
    try:
        df = pd.read_csv(file_obj)
        preview = df.head(5).to_string(index=False)
        return {
            "filename": filename,
            "file_type": "csv",
            "dataframe": df,
            "text": None,
            "preview": _safe_preview(preview),
            "error": None,
        }
    except Exception as e:
        return _error_result(filename, "csv", e)


def parse_xlsx(file_obj, filename: str) -> dict:
    try:
        df = pd.read_excel(file_obj)
        preview = df.head(5).to_string(index=False)
        return {
            "filename": filename,
            "file_type": "xlsx",
            "dataframe": df,
            "text": None,
            "preview": _safe_preview(preview),
            "error": None,
        }
    except Exception as e:
        return _error_result(filename, "xlsx", e)


def parse_pdf(file_obj, filename: str) -> dict:
    try:
        import pdfplumber
        text_chunks = []
        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_chunks.append(page_text)
        full_text = "\n".join(text_chunks).strip()
        if not full_text:
            full_text = "[No extractable text found — this PDF may be scanned/image-based.]"
        return {
            "filename": filename,
            "file_type": "pdf",
            "dataframe": None,
            "text": full_text,
            "preview": _safe_preview(full_text),
            "error": None,
        }
    except Exception as e:
        return _error_result(filename, "pdf", e)


def parse_docx(file_obj, filename: str) -> dict:
    try:
        import docx
        document = docx.Document(file_obj)
        full_text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
        return {
            "filename": filename,
            "file_type": "docx",
            "dataframe": None,
            "text": full_text,
            "preview": _safe_preview(full_text),
            "error": None,
        }
    except Exception as e:
        return _error_result(filename, "docx", e)


def parse_text_like(file_obj, filename: str, file_type: str) -> dict:
    """Handles .txt, .log, .eml — all plain text under the hood."""
    try:
        raw_bytes = file_obj.read()
        if isinstance(raw_bytes, bytes):
            text = raw_bytes.decode("utf-8", errors="replace")
        else:
            text = raw_bytes
        return {
            "filename": filename,
            "file_type": file_type,
            "dataframe": None,
            "text": text,
            "preview": _safe_preview(text),
            "error": None,
        }
    except Exception as e:
        return _error_result(filename, file_type, e)


def parse_image_placeholder(filename: str) -> dict:
    """
    Screenshots (error dialogs, dashboards, etc.) aren't OCR'd automatically
    because Tesseract isn't reliably available on Streamlit Cloud.
    Instead the app UI will ask the user to paste the visible text, which
    gets stored the same way as any other text evidence.
    """
    return {
        "filename": filename,
        "file_type": "image",
        "dataframe": None,
        "text": None,
        "preview": "[Image uploaded — paste the visible text in the box below so it can be used as evidence.]",
        "error": None,
    }


def _error_result(filename: str, file_type: str, exception: Exception) -> dict:
    return {
        "filename": filename,
        "file_type": file_type,
        "dataframe": None,
        "text": None,
        "preview": "",
        "error": f"Could not parse '{filename}': {exception}",
    }


def parse_file(uploaded_file) -> dict:
    """
    Main dispatch function. `uploaded_file` is a Streamlit UploadedFile
    (has .name and behaves like a file object).
    """
    filename = uploaded_file.name
    file_type = _detect_type(filename)

    if file_type == "csv":
        return parse_csv(uploaded_file, filename)
    if file_type == "xlsx":
        return parse_xlsx(uploaded_file, filename)
    if file_type == "pdf":
        return parse_pdf(uploaded_file, filename)
    if file_type == "docx":
        return parse_docx(uploaded_file, filename)
    if file_type in ("txt", "log", "email"):
        return parse_text_like(uploaded_file, filename, file_type)
    if file_type == "image":
        return parse_image_placeholder(filename)

    return _error_result(filename, "unsupported", Exception("Unsupported file type"))


def parse_many(uploaded_files) -> list:
    """Convenience helper: parse a list of Streamlit UploadedFile objects."""
    return [parse_file(f) for f in uploaded_files]
