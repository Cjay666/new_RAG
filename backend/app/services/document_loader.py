"""Document loading — MinerU API for rich formats, direct read for plain text."""

from __future__ import annotations

import asyncio
import csv
import io
import zipfile
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
    """Send document to MinerU API v4, return Markdown.

    v4 流程：申请批量上传 URL → PUT 文件字节 → 轮询结果 → 下载 ZIP 解出 full.md。
    """
    headers = {"Authorization": f"Bearer {MINERU_API_KEY}"}

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. 申请预签名上传 URL（文件 PUT 成功后会自动触发解析）
        apply_resp = await client.post(
            f"{MINERU_BASE_URL}/file-urls/batch",
            headers={**headers, "Content-Type": "application/json"},
            json={"files": [{"name": filename}], "model_version": "vlm"},
        )
        apply_resp.raise_for_status()
        apply_data = apply_resp.json()
        if apply_data.get("code") != 0:
            raise RuntimeError(f"MinerU upload apply failed: {apply_data.get('msg', 'unknown')}")

        upload_urls = apply_data.get("data", {}).get("file_urls") or []
        if not upload_urls:
            raise RuntimeError(f"MinerU upload apply returned no file_urls: {apply_data}")
        batch_id = apply_data["data"]["batch_id"]
        upload_url = upload_urls[0]

        # 2. 把文件原始字节 PUT 到签名 URL（不带鉴权头、不带 Content-Type）
        with open(file_path, "rb") as f:
            put_resp = await client.put(upload_url, content=f.read())
        put_resp.raise_for_status()

        # 3. 轮询解析结果
        for _ in range(60):  # 最多约 10 分钟
            result_resp = await client.get(
                f"{MINERU_BASE_URL}/extract-results/batch/{batch_id}",
                headers=headers,
            )
            result_resp.raise_for_status()
            result_data = result_resp.json()
            if result_data.get("code") != 0:
                raise RuntimeError(f"MinerU result query failed: {result_data.get('msg', 'unknown')}")

            items = result_data.get("data", {}).get("extract_result") or []
            if not items:
                await asyncio.sleep(10)
                continue
            item = items[0]
            state = item["state"]
            if state == "done":
                # 4. 下载结果 ZIP，解出 full.md
                zip_resp = await client.get(item["full_zip_url"])
                zip_resp.raise_for_status()
                return _extract_markdown(zip_resp.content)
            if state == "failed":
                raise RuntimeError(f"MinerU parsing failed: {item.get('err_msg', 'unknown')}")

            await asyncio.sleep(10)

        raise TimeoutError("MinerU parsing timed out")


def _extract_markdown(zip_bytes: bytes) -> str:
    """从 MinerU 结果 ZIP 中读取 full.md。"""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        md_name = "full.md" if "full.md" in names else next((n for n in names if n.endswith(".md")), None)
        if md_name is None:
            raise RuntimeError(f"MinerU ZIP has no markdown: {names[:10]}")
        return zf.read(md_name).decode("utf-8")


def _csv_to_text(file_path: Path) -> str:
    """Convert CSV rows to text lines. Each row → one line."""
    content = file_path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(content))
    lines = []
    for row in reader:
        parts = [f"{k}: {v}" for k, v in row.items() if v]
        lines.append("，".join(parts))
    return "\n\n".join(lines)
