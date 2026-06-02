"""
File extraction helpers: robust text extraction from TXT/CSV/PDF/DOCX/RTF.
Includes encoding autodetection for plain-text formats.
"""
from __future__ import annotations

from typing import Optional
from charset_normalizer import from_bytes
from PyPDF2 import PdfReader
from docx import Document


def _decode_with_autodetect(file_bytes: bytes) -> str:
    guess = from_bytes(file_bytes).best()
    if guess and guess.encoding:
        try:
            return file_bytes.decode(guess.encoding, errors="strict")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8", "utf-8-sig", "cp1251", "windows-1251", "latin1"):
        try:
            return file_bytes.decode(enc, errors="strict")
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("latin1", errors="replace")


def extract_text_from_file(file) -> str:
    """Extract text from an uploaded file (Django UploadedFile-like object)."""
    try:
        name = (file.name or "").lower()
        if name.endswith((".txt", ".csv")):
            file.seek(0)
            raw = file.read()
            return _decode_with_autodetect(raw)
        elif name.endswith(".pdf"):
            file.seek(0)
            reader = PdfReader(file)
            return "".join((page.extract_text() or "") for page in reader.pages)
        elif name.endswith(".docx"):
            file.seek(0)
            doc = Document(file)
            return "\n".join(p.text for p in doc.paragraphs)
        elif name.endswith(".rtf"):
            file.seek(0)
            raw = file.read()
            return _decode_with_autodetect(raw)
        else:
            return "Формат файлу не підтримується"
    except Exception as e:
        return f"Помилка при розпаковці файлу: {e}"
