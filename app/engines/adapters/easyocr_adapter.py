"""EasyOCR: torch-based raster OCR, txt only. GPU when available."""
from __future__ import annotations

from app.core.device import detect_torch_device
from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from importlib.metadata import version

    return version("easyocr")


def run(ctx: WorkerContext) -> AdapterResult:
    import easyocr

    use_gpu, detail = detect_torch_device(ctx.device_pref)
    device = "gpu" if use_gpu else "cpu"
    ctx.emit({"event": "device", "device": device, "detail": detail})
    warnings = [] if use_gpu or ctx.device_pref == "cpu" else ["cpu_fallback"]

    reader = easyocr.Reader(["en"], gpu=use_gpu, verbose=False)
    chunks = []
    for n, img in enumerate(ctx.images, 1):
        ctx.emit({"event": "page", "page": n, "total": len(ctx.images)})
        lines = reader.readtext(str(img), detail=0, paragraph=True)
        chunks.append("\n".join(lines))
    return AdapterResult(output_text="\n\n".join(chunks),
                         pages_processed=list(ctx.page_indices),
                         device=device, device_detail=detail, warnings=warnings)
