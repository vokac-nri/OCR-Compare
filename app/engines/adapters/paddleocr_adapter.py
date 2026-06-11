"""PaddleOCR (PP-OCRv5): GPU raster OCR. txt | json (lines + scores + boxes)."""
from __future__ import annotations

import json

from app.core.device import detect_paddle_device
from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from app.core.device import preload_for_paddle

    preload_for_paddle()  # torch -> paddle DLL order; see device.py
    import paddle  # noqa: F401
    import paddleocr

    return paddleocr.__version__


def run(ctx: WorkerContext) -> AdapterResult:
    device, detail = detect_paddle_device(ctx.device_pref)  # imports paddle first
    from paddleocr import PaddleOCR

    ctx.emit({"event": "device", "device": device, "detail": detail})
    warnings = [] if device == "gpu" or ctx.device_pref == "cpu" else ["cpu_fallback"]

    ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False, lang="en", device=device)
    pages_txt, pages_json = [], []
    for n, img in enumerate(ctx.images, 1):
        ctx.emit({"event": "page", "page": n, "total": len(ctx.images)})
        texts, raw = [], []
        for r in ocr.predict(input=str(img)):
            res = r.json.get("res", r.json)
            texts.extend(res.get("rec_texts", []))
            raw.append({"rec_texts": res.get("rec_texts", []),
                        "rec_scores": res.get("rec_scores", []),
                        "rec_boxes": _listify(res.get("rec_boxes", []))})
        pages_txt.append("\n".join(texts))
        pages_json.append({"page": ctx.page_indices[n - 1] + 1
                           if n - 1 < len(ctx.page_indices) else n, "results": raw})

    if ctx.fmt == "json":
        text = json.dumps({"pages": pages_json}, indent=2, ensure_ascii=False)
    else:
        text = "\n\n".join(pages_txt)
    return AdapterResult(output_text=text,
                         pages_processed=list(ctx.page_indices),
                         device=device, device_detail=detail, warnings=warnings)


def _listify(x):
    """numpy arrays -> plain lists for JSON serialization."""
    tolist = getattr(x, "tolist", None)
    return tolist() if callable(tolist) else x


def flatten_json(text: str) -> str | None:
    try:
        data = json.loads(text)
        out = []
        for page in data.get("pages", []):
            for res in page.get("results", []):
                out.extend(res.get("rec_texts", []))
        return "\n".join(out)
    except Exception:
        return None
