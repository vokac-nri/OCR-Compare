"""MarkItDown (Microsoft): lightweight anything->Markdown. md only, pdf only
(image input would require wiring an LLM client). Page limiting via a
pymupdf-built temp PDF subset.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from importlib.metadata import version

    return version("markitdown")


def run(ctx: WorkerContext) -> AdapterResult:
    from markitdown import MarkItDown

    from app.core.raster import pdf_page_count, pdf_subset

    source = ctx.input_path
    tmp: Path | None = None
    try:
        if ctx.page_indices != list(range(pdf_page_count(ctx.input_path))):
            tmp = Path(tempfile.mkdtemp()) / f"subset_{ctx.input_path.name}"
            pdf_subset(ctx.input_path, ctx.page_indices, tmp)
            source = tmp

        ctx.emit({"event": "page", "page": 1, "total": len(ctx.page_indices)})
        text = MarkItDown().convert(str(source)).text_content
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)

    return AdapterResult(output_text=text or "",
                         pages_processed=list(ctx.page_indices), device="cpu")
