"""Helpers for generating tiny fixture PDFs at test time."""
from __future__ import annotations

from pathlib import Path

import fitz


def make_pdf(path: Path, pages: list[str]) -> None:
    doc = fitz.open()
    rect = fitz.Rect(72, 72, 540, 720)
    for text in pages:
        page = doc.new_page(width=612, height=792)
        page.insert_textbox(rect, text, fontsize=11)
    doc.save(str(path))
    doc.close()
