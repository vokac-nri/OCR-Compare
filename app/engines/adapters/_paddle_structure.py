"""Shared helpers for the paddle structure pipelines (PP-StructureV3 and
PaddleOCR-VL): markdown extraction, regions-only filtering, JSON dumping.
"""
from __future__ import annotations

import json

# Layout block labels that count as data visualizations / tables for the
# regions-only mode. PaddleOCR 3.x layout label vocabulary.
VIZ_LABELS = {"table", "chart", "figure_with_table"}


def result_markdown(r) -> str:
    """Markdown text from a paddle pipeline page result."""
    md = getattr(r, "markdown", None)
    if isinstance(md, dict):
        return md.get("markdown_texts", "") or ""
    return str(md) if md is not None else ""


def result_json_obj(r):
    """JSON-safe dict from a paddle pipeline page result."""
    try:
        obj = r.json
        return obj.get("res", obj) if isinstance(obj, dict) else obj
    except Exception:
        return {"error": "result not JSON-serializable"}


def filter_viz_blocks(r, page_no: int) -> tuple[str, bool]:
    """Regions-only: markdown of table/chart blocks only.

    Returns (markdown, filter_worked). filter_worked=False means the result
    had no parsing_res_list to filter (caller should warn and fall back).
    """
    res = result_json_obj(r)
    blocks = res.get("parsing_res_list") if isinstance(res, dict) else None
    if not isinstance(blocks, list):
        return "", False
    out = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        label = str(b.get("block_label", b.get("label", ""))).lower()
        if label in VIZ_LABELS:
            content = b.get("block_content", b.get("content", ""))
            out.append(f"<!-- page {page_no}, region: {label} -->\n{content}")
    return "\n\n".join(out), True


def pages_to_output(fmt: str, md_pages: list[str], json_pages: list[dict]) -> str:
    if fmt == "json":
        return json.dumps({"pages": json_pages}, indent=2,
                          ensure_ascii=False, default=str)
    return "\n\n".join(md_pages)
