"""Document loading — MinerU API for rich formats, direct read for plain text."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx
from docx import Document as DocxDocument

from ..config import MINERU_API_KEY, MINERU_BASE_URL

# File types that should go through MinerU
_MINERU_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"}


async def load_document(file_path: Path, original_filename: str) -> str:
    """Load a document and return clean Markdown text.

    PDF / Word / PPT / images → MinerU API
    TXT / MD → direct read
    CSV → convert to text lines
    """
    ext = file_path.suffix.lower()

    if ext in _MINERU_EXTENSIONS:
        return await _mineru_parse(file_path, original_filename)
    elif ext == ".csv":
        return _csv_to_text(file_path)
    else:
        # .txt, .md, or fallback
        return file_path.read_text(encoding="utf-8")


async def _mineru_parse(file_path: Path, filename: str) -> str:
    """Send document to MinerU API, return Markdown."""
    async with httpx.AsyncClient(timeout=120) as client:
        # Upload file
        with open(file_path, "rb") as f:
            upload_resp = await client.post(
                f"{MINERU_BASE_URL}/file/upload",
                headers={"Authorization": f"Bearer {MINERU_API_KEY}"},
                files={"file": (filename, f)},
            )
            upload_resp.raise_for_status()
            file_id = upload_resp.json()["data"]["file_id"]

        # Poll for parsing result
        for _ in range(30):  # max 5 minutes
            status_resp = await client.get(
                f"{MINERU_BASE_URL}/file/status/{file_id}",
                headers={"Authorization": f"Bearer {MINERU_API_KEY}"},
            )
            status_resp.raise_for_status()
            data = status_resp.json()["data"]
            if data["status"] == "done":
                # Download markdown result
                md_resp = await client.get(
                    f"{MINERU_BASE_URL}/file/download/{file_id}?format=md",
                    headers={"Authorization": f"Bearer {MINERU_API_KEY}"},
                )
                md_resp.raise_for_status()
                return md_resp.text
            if data["status"] == "failed":
                raise RuntimeError(f"MinerU parsing failed: {data.get('error', 'unknown')}")

            import asyncio
            await asyncio.sleep(10)

        raise TimeoutError("MinerU parsing timed out")


def _csv_to_text(file_path: Path) -> str:
    """Convert CSV rows to text lines. Each row → one line."""
    content = file_path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(content))
    lines = []
    for row in reader:
        parts = [f"{k}: {v}" for k, v in row.items() if v]
        lines.append("，".join(parts))
    return "\n\n".join(lines)
