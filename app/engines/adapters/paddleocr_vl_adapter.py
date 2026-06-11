"""PaddleOCR-VL: vision-language model -> structured markdown. md | json.

The decode bounds (max_new_tokens=1024, repetition_penalty=1.3) are essential:
without them dense pages can peg the GPU for many minutes in runaway
autoregressive loops (found the hard way in prior testing).
"""
from __future__ import annotations

from app.core.device import detect_paddle_device
from app.engines.adapters._paddle_structure import (filter_viz_blocks,
                                                    pages_to_output,
                                                    result_json_obj,
                                                    result_markdown)
from app.engines.base import AdapterResult, WorkerContext

VL_MAX_NEW_TOKENS = 1024
VL_REPETITION_PENALTY = 1.3


def get_version() -> str:
    from app.core.device import preload_for_paddle

    preload_for_paddle()  # torch -> paddle DLL order; see device.py
    import paddle  # noqa: F401
    import paddleocr

    return paddleocr.__version__


def run(ctx: WorkerContext) -> AdapterResult:
    device, detail = detect_paddle_device(ctx.device_pref)  # imports paddle first
    from paddleocr import PaddleOCRVL

    ctx.emit({"event": "device", "device": device, "detail": detail})
    warnings = [] if device == "gpu" or ctx.device_pref == "cpu" else ["cpu_fallback"]

    pipe = PaddleOCRVL(
        device=device,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_chart_recognition=ctx.charts,
        use_seal_recognition=False,
    )
    predict_kw = dict(
        max_new_tokens=VL_MAX_NEW_TOKENS,
        repetition_penalty=VL_REPETITION_PENALTY,
        use_chart_recognition=ctx.charts,
    )
    md_pages, json_pages = [], []
    filter_failed = False
    for n, img in enumerate(ctx.images, 1):
        ctx.emit({"event": "page", "page": n, "total": len(ctx.images)})
        page_no = ctx.page_indices[n - 1] + 1 if n - 1 < len(ctx.page_indices) else n
        for r in pipe.predict(input=str(img), **predict_kw):
            if ctx.regions_only:
                md, ok = filter_viz_blocks(r, page_no)
                if not ok:
                    filter_failed = True
                    md = result_markdown(r)
                md_pages.append(md)
            else:
                md_pages.append(result_markdown(r))
            json_pages.append({"page": page_no, "result": result_json_obj(r)})

    if filter_failed:
        warnings.append("regions_filter_unavailable")

    if ctx.fmt == "json" or ctx.regions_only:
        text = pages_to_output(ctx.fmt, md_pages, json_pages)
    else:
        # Stitch per-page markdown with the pipeline's own concatenation when
        # available (it merges cross-page constructs like split tables).
        try:
            full = pipe.concatenate_markdown_pages(
                [{"markdown_texts": m} for m in md_pages])
            text = full.get("markdown_texts", "") if isinstance(full, dict) else str(full)
        except Exception:
            text = "\n\n".join(md_pages)

    return AdapterResult(output_text=text,
                         pages_processed=list(ctx.page_indices),
                         device=device, device_detail=detail, warnings=warnings)
