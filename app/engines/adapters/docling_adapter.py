"""Docling (IBM): layout-aware document conversion. md | json | txt.

Page limiting uses a pymupdf-built temp PDF containing only the target pages
(version-proof vs. docling's evolving page_range options). Document-level
progress only.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from importlib.metadata import version

    return version("docling")


def run(ctx: WorkerContext) -> AdapterResult:
    from docling.document_converter import DocumentConverter

    source = ctx.input_path
    tmp: Path | None = None
    try:
        if ctx.input_kind == "pdf":
            from app.core.raster import pdf_page_count, pdf_subset

            if ctx.page_indices != list(range(pdf_page_count(ctx.input_path))):
                tmp = Path(tempfile.mkdtemp()) / f"subset_{ctx.input_path.name}"
                pdf_subset(ctx.input_path, ctx.page_indices, tmp)
                source = tmp

        ctx.emit({"event": "page", "page": 1, "total": len(ctx.page_indices)})
        doc = DocumentConverter().convert(str(source)).document

        if ctx.fmt == "json":
            text = json.dumps(doc.export_to_dict(), indent=2,
                              ensure_ascii=False, default=str)
        elif ctx.fmt == "txt":
            export_txt = getattr(doc, "export_to_text", None)
            if callable(export_txt):
                text = export_txt()
            else:
                from app.core.scoring import strip_markdown

                text = strip_markdown(doc.export_to_markdown())
        else:
            text = doc.export_to_markdown()
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)

    return AdapterResult(output_text=text,
                         pages_processed=list(ctx.page_indices), device="cpu")
