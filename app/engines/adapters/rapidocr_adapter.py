"""RapidOCR: PP-OCR models on ONNX Runtime (CPU), txt only."""
from __future__ import annotations

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from importlib.metadata import version

    return version("rapidocr")


def run(ctx: WorkerContext) -> AdapterResult:
    from rapidocr import RapidOCR

    engine = RapidOCR()
    chunks = []
    for n, img in enumerate(ctx.images, 1):
        ctx.emit({"event": "page", "page": n, "total": len(ctx.images)})
        res = engine(str(img))
        txts = getattr(res, "txts", None)
        chunks.append("\n".join(txts) if txts else "")
    return AdapterResult(output_text="\n\n".join(chunks),
                         pages_processed=list(ctx.page_indices), device="cpu")
