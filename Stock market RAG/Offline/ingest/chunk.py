"""Paragraph/heading-aware chunking with overlap. See SPEC.md section 5.4."""
from __future__ import annotations

import re

from app.schemas import Chunk, Document

HEADING_MAX_LEN = 80
_SENTENCE_END = (".", "?", "!")


def _is_heading_line(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > HEADING_MAX_LEN:
        return False
    return not line.endswith(_SENTENCE_END)


def _split_paragraphs(text: str) -> list[str]:
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if p.strip()]


def _word_tail(text: str, n: int) -> str:
    """Last <= n characters of text, trimmed to a word boundary."""
    if len(text) <= n:
        return text
    tail = text[-n:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail


def _split_long_block(block: str, size: int, overlap: int) -> list[str]:
    """Split a single oversized paragraph on word boundaries, never mid-word."""
    words = block.split(" ")
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) > size and current:
            pieces.append(current)
            current = f"{_word_tail(current, overlap)} {word}".strip()
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _emit(chunks: list[Chunk], doc: Document, page_no: int, page_index: int, section: str, buffer: str) -> int:
    """Append `buffer` as a chunk if non-empty; return the next page_index."""
    text = buffer.strip()
    if not text:
        return page_index
    chunks.append(
        Chunk(
            chunk_id=f"{doc.doc_id}:{page_no}:{page_index}",
            doc_id=doc.doc_id,
            title=doc.title,
            publisher=doc.publisher,
            url=doc.url,
            page=page_no,
            section=section,
            text=text,
        )
    )
    return page_index + 1


def chunk_document(doc: Document, size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []

    for page_no, page_text in doc.pages:
        blocks = _split_paragraphs(page_text)
        buffer = ""
        section = ""
        page_index = 0

        for block in blocks:
            lines = block.splitlines()
            first_line = lines[0].strip() if lines else ""

            # A heading line starts a new chunk even when PDF text extraction
            # does not preserve the blank line between it and the body that
            # follows (common for insert_textbox-rendered PDFs), so headings
            # are detected by their first line rather than requiring the
            # whole paragraph to be just that line.
            if _is_heading_line(first_line):
                page_index = _emit(chunks, doc, page_no, page_index, section, buffer)
                buffer = ""
                section = first_line
                remainder = "\n".join(lines[1:]).strip()
                if not remainder:
                    continue
                block = remainder

            pieces = _split_long_block(block, size, overlap) if len(block) > size else [block]
            for piece in pieces:
                candidate = f"{buffer}\n\n{piece}".strip() if buffer else piece
                if len(candidate) > size and buffer:
                    tail = _word_tail(buffer, overlap)
                    page_index = _emit(chunks, doc, page_no, page_index, section, buffer)
                    # Trim the carried-over overlap so the new chunk never
                    # exceeds `size`, even if that shortens the overlap.
                    max_tail = max(0, size - len(piece))
                    if len(tail) > max_tail:
                        tail = _word_tail(tail, max_tail)
                    buffer = f"{tail}\n\n{piece}".strip() if tail else piece
                else:
                    buffer = candidate
        _emit(chunks, doc, page_no, page_index, section, buffer)

    return chunks
