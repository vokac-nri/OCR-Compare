"""pypdfium2: digital text layer via PDFium. txt only."""
from __future__ import annotations

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from importlib.metadata import version

    return version("pypdfium2")


def run(ctx: WorkerContext) -> AdapterResult:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(ctx.input_path)
    try:
        chunks = []
        for n, i in enumerate(ctx.page_indices, 1):
            ctx.emit({"event": "page", "page": n, "total": len(ctx.page_indices)})
            chunks.append(pdf[i].get_textpage().get_text_range())
    finally:
        pdf.close()
    return AdapterResult(output_text="\n\n".join(chunks),
                         pages_processed=list(ctx.page_indices), device="cpu")
