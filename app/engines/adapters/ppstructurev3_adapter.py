"""PP-StructureV3: layout + table recognition + optional chart->table. md | json.

CAVEAT (from prior testing): chart->table conversion fabricated values —
the GUI warns whenever chart parsing is enabled.
"""
from __future__ import annotations

from app.core.device import detect_paddle_device
from app.engines.adapters._paddle_structure import (filter_viz_blocks,
                                                    pages_to_output,
                                                    result_json_obj,
                                                    result_markdown)
from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    from app.core.device import preload_for_paddle

    preload_for_paddle()  # torch -> paddle DLL order; see device.py
    import paddle  # noqa: F401
    import paddleocr

    return paddleocr.__version__


def run(ctx: WorkerContext) -> AdapterResult:
    device, detail = detect_paddle_device(ctx.device_pref)  # imports paddle first
    from paddleocr import PPStructureV3

    ctx.emit({"event": "device", "device": device, "detail": detail})
    warnings = [] if device == "gpu" or ctx.device_pref == "cpu" else ["cpu_fallback"]

    pp = PPStructureV3(
        device=device,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_seal_recognition=False,
        use_formula_recognition=False,
        use_chart_recognition=ctx.charts,
    )
    md_pages, json_pages = [], []
    filter_failed = False
    for n, img in enumerate(ctx.images, 1):
        ctx.emit({"event": "page", "page": n, "total": len(ctx.images)})
        page_no = ctx.page_indices[n - 1] + 1 if n - 1 < len(ctx.page_indices) else n
        for r in pp.predict(input=str(img), use_chart_recognition=ctx.charts):
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
    text = pages_to_output(ctx.fmt, md_pages, json_pages)
    return AdapterResult(output_text=text,
                         pages_processed=list(ctx.page_indices),
                         device=device, device_detail=detail, warnings=warnings)
