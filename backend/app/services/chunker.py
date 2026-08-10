"""Document chunking — Markdown header-aware + recursive separator splitting."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from ..config import CHUNK_OVERLAP, CHUNK_SIZE

# Separators in priority order
_SEPARATORS = [
    r"\n\n",          # paragraphs
    r"\n",            # lines
    r"。",            # Chinese period
    r"！",
    r"？",
    r"；",
    r"\\. ",          # English period
    r"! ",
    r"\\? ",
    r"; ",
    r" ",
    r"",
]

_PAGE_RE = re.compile(r"\[PAGE_(\d+)\]")

@dataclass
class Chunk:
    id: str
    text: str
    doc_name: str
    kb_id: str
    doc_id: str
    header_path: str = ""
    page: int = 0
    chunk_index: int = 0
    total_chunks: int = 0
    parent_id: str = ""


def chunk_document(
    markdown_text: str,
    doc_name: str,
    kb_id: str,
    doc_id: str,
) -> list[Chunk]:
    """Main entry: chunk a Markdown document.

    Strategy:
    1. Split by Markdown headers first
    2. For any section longer than CHUNK_SIZE, recursively split with separators
    3. Assign parent-child relationship for Small-to-Big
    """
    # Extract page markers
    pages: dict[int, str] = {}
    clean_text = markdown_text
    for m in _PAGE_RE.finditer(markdown_text):
        pages[m.start()] = m.group(1)
    clean_text = _PAGE_RE.sub("", markdown_text)

    # Step 1: Split by H2/H3 headers
    sections = _split_by_headers(clean_text)

    # Step 2: For each section, split oversized ones
    all_chunks_data: list[dict] = []
    parent_counter = 0

    for section in sections:
        header = section["header"]
        body = section["body"]
        if len(body) <= CHUNK_SIZE:
            all_chunks_data.append({"header_path": header, "text": body.strip()})
        else:
            sub_texts = _recursive_split(body, CHUNK_SIZE)
            for sub in sub_texts:
                all_chunks_data.append({"header_path": header, "text": sub.strip()})

    # Step 3: Build Chunk objects with parent-child relationship
    chunks = []
    total = len(all_chunks_data)
    for i, data in enumerate(all_chunks_data):
        parent_id = f"{doc_id}_parent_{i}"
        chunk_id = f"{doc_id}_chunk_{i}"
        chunks.append(Chunk(
            id=chunk_id,
            text=data["text"],
            doc_name=doc_name,
            kb_id=kb_id,
            doc_id=doc_id,
            header_path=data["header_path"],
            chunk_index=i,
            total_chunks=total,
            parent_id=parent_id,
        ))

    return chunks


def _split_by_headers(text: str) -> list[dict]:
    """Split text into sections at H2/H3 boundaries."""
    # Match markdown headers
    header_re = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
    matches = list(header_re.finditer(text))

    if not matches:
        return [{"header": "", "body": text}]

    sections = []
    headers_stack: list[tuple[int, str]] = []  # [(level, title), ...]

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.end() + 1
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        # Update header stack
        headers_stack = [(l, t) for l, t in headers_stack if l < level]
        headers_stack.append((level, title))
        header_path = " > ".join(t for _, t in headers_stack)

        sections.append({"header": header_path, "body": text[start:end].strip()})

    # Prepend content before the first header
    if matches and matches[0].start() > 0:
        leading = text[:matches[0].start()].strip()
        if leading:
            sections.insert(0, {"header": "", "body": leading})

    return sections


def _recursive_split(text: str, max_size: int) -> list[str]:
    """Recursively split text using separators in priority order."""
    if len(text) <= max_size:
        return [text] if text.strip() else []

    for sep in _SEPARATORS:
        parts = re.split(f"({sep})", text) if sep else list(text)
        if sep:
            # Re-join delimiter with preceding part
            merged = []
            for j in range(0, len(parts) - 1, 2):
                merged.append(parts[j] + (parts[j + 1] if j + 1 < len(parts) else ""))
            if len(parts) % 2 == 1:
                merged.append(parts[-1])
            parts = merged

        # Merge short parts with neighbors
        result = _merge_splits(parts, max_size, CHUNK_OVERLAP)
        if len(result) > 1:  # actually split — good
            return result

    # Fallback: hard character split
    chunks = []
    for start in range(0, len(text), max_size - CHUNK_OVERLAP):
        chunks.append(text[start:start + max_size])
    return chunks


def _merge_splits(parts: list[str], max_size: int, overlap: int) -> list[str]:
    """Merge short parts together to reach target size."""
    if not parts:
        return []
    result = []
    current = parts[0]
    for part in parts[1:]:
        if len(current) + len(part) <= max_size:
            current += part
        else:
            if current.strip():
                result.append(current)
            current = part
    if current.strip():
        result.append(current)
    # If we got only one chunk, it means we need a different separator
    return result
