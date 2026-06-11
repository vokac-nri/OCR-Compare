"""Tesseract via pytesseract: classic CPU raster OCR, txt only."""
from __future__ import annotations

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    import pytesseract

    return str(pytesseract.get_tesseract_version())


def run(ctx: WorkerContext) -> AdapterResult:
    import pytesseract
    from PIL import Image

    chunks = []
    for n, img in enumerate(ctx.images, 1):
        ctx.emit({"event": "page", "page": n, "total": len(ctx.images)})
        chunks.append(pytesseract.image_to_string(Image.open(img)))
    return AdapterResult(output_text="\n\n".join(chunks),
                         pages_processed=list(ctx.page_indices), device="cpu")
