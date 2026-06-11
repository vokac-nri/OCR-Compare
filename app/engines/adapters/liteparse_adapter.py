"""LiteParse: digital text -> markdown/text (OCR disabled)."""
from __future__ import annotations

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from importlib.metadata import version

    return version("liteparse")


def run(ctx: WorkerContext) -> AdapterResult:
    from liteparse import LiteParse

    target_pages = ",".join(str(i + 1) for i in ctx.page_indices)
    output_format = "markdown" if ctx.fmt == "md" else "text"
    ctx.emit({"event": "page", "page": 1, "total": len(ctx.page_indices)})
    text = LiteParse(ocr_enabled=False, quiet=True, output_format=output_format,
                     target_pages=target_pages).parse(str(ctx.input_path)).text
    return AdapterResult(output_text=text,
                         pages_processed=list(ctx.page_indices), device="cpu")
