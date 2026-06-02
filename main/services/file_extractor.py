"""
FileExtractor: Unified interface for extracting text from various file formats.

Supports:
- TXT/CSV with automatic encoding detection
- PDF with page concatenation
- DOCX with paragraph joining
- RTF with plain decode fallback
"""
from __future__ import annotations

import io
from typing import Optional


class FileExtractor:
    """Service for extracting text from various file formats."""

    def __init__(self):
        pass

    def extract(self, uploaded_file, filename: str) -> str:
        """
        Extract text from uploaded file based on extension.
        
        Args:
            uploaded_file: Django UploadedFile object
            filename: Original filename with extension
            
        Returns:
            Extracted text content
            
        Raises:
            ValueError: If file format is unsupported
        """
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        
        if ext in ["txt", "csv"]:
            return self._extract_text(uploaded_file)
        elif ext == "pdf":
            return self._extract_pdf(uploaded_file)
        elif ext == "docx":
            return self._extract_docx(uploaded_file)
        elif ext == "rtf":
            return self._extract_rtf(uploaded_file)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _extract_text(self, uploaded_file) -> str:
        """
        Extract text from TXT/CSV with automatic encoding detection.
        
        Tries UTF-8 first, falls back to cp1251.
        """
        try:
            return uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return uploaded_file.read().decode("cp1251", errors="ignore")

    def _extract_pdf(self, uploaded_file) -> str:
        """
        Extract text from PDF file.
        
        Concatenates all pages with newlines.
        """
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract PDF: {e}")

    def _extract_docx(self, uploaded_file) -> str:
        """
        Extract text from DOCX file.
        
        Joins all paragraphs with newlines.
        """
        try:
            from docx import Document
            doc = Document(io.BytesIO(uploaded_file.read()))
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            raise ValueError(f"Failed to extract DOCX: {e}")

    def _extract_rtf(self, uploaded_file) -> str:
        """
        Extract text from RTF file.
        
        Falls back to plain decode if RTF parsing unavailable.
        """
        try:
            from striprtf.striprtf import rtf_to_text
            content = uploaded_file.read().decode("utf-8", errors="ignore")
            return rtf_to_text(content)
        except ImportError:
            # Fallback: plain decode
            uploaded_file.seek(0)
            return uploaded_file.read().decode("utf-8", errors="ignore")
        except Exception as e:
            raise ValueError(f"Failed to extract RTF: {e}")
