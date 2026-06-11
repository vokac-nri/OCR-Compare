"""PyMuPDF: digital text layer. txt | md (pymupdf4llm) | json (positional)."""
from __future__ import annotations

import json

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from importlib.metadata import version

    return version("pymupdf")


def run(ctx: WorkerContext) -> AdapterResult:
    import fitz

    with fitz.open(ctx.input_path) as doc:
        if ctx.fmt == "md":
            text = _markdown(doc, ctx)
        elif ctx.fmt == "json":
            pages = []
            for n, i in enumerate(ctx.page_indices, 1):
                ctx.emit({"event": "page", "page": n, "total": len(ctx.page_indices)})
                pages.append({"page": i + 1,
                              "content": json.loads(doc[i].get_text("json"))})
            text = json.dumps({"pages": pages}, indent=2, ensure_ascii=False)
        else:
            chunks = []
            for n, i in enumerate(ctx.page_indices, 1):
                ctx.emit({"event": "page", "page": n, "total": len(ctx.page_indices)})
                chunks.append(doc[i].get_text())
            text = "\n\n".join(chunks)

    return AdapterResult(output_text=text,
                         pages_processed=list(ctx.page_indices), device="cpu")


def _markdown(doc, ctx: WorkerContext) -> str:
    import pymupdf4llm

    ctx.emit({"event": "page", "page": 1, "total": len(ctx.page_indices)})
    try:
        return pymupdf4llm.to_markdown(doc, pages=ctx.page_indices)
    except TypeError:
        # Older pymupdf4llm without a usable pages kwarg: per-page concat.
        return "\n\n".join(
            pymupdf4llm.to_markdown(doc, pages=[i]) for i in ctx.page_indices)


def flatten_json(text: str) -> str | None:
    """Extract plain text from the positional JSON dump (for CER/WER scoring)."""
    try:
        data = json.loads(text)
        out = []
        for page in data.get("pages", []):
            for block in page.get("content", {}).get("blocks", []):
                for line in block.get("lines", []):
                    out.append("".join(s.get("text", "") for s in line.get("spans", [])))
        return "\n".join(out)
    except Exception:
        return None
