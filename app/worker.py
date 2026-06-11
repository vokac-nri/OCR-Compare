"""Worker entry point: runs ONE engine on ONE file, writes the output document,
and streams sentinel-prefixed JSON events to stdout for the orchestrator.

    python -m app.worker --engine paddleocr --input "C:\\docs\\a.pdf" --kind pdf
        --max-pages 8 --format md --dpi 200 --device auto
        --images-dir "<run>\\_cache\\a_pdf" --output "<run>\\a_pdf\\paddleocr_a_pdf.md"
        --job-id f3a1

Runs under any interpreter that has the engine's dependencies (PYTHONPATH is
set by the orchestrator), which is how per-engine conda-env overrides work.
Never imports PySide6. Exit code 0 whenever a result event was emitted.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import traceback
from pathlib import Path

from app.core.pages import parse_pages_spec, target_indices
from app.core.protocol import emit_event
from app.core.raster import pdf_page_count, render_indices
from app.engines import get_spec
from app.engines.adapters import load_adapter
from app.engines.base import WorkerContext


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--engine", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--kind", choices=["pdf", "image"], required=True)
    p.add_argument("--pages", default="", help="explicit 1-based spec, e.g. '2-5,8'")
    p.add_argument("--max-pages", type=int, default=8, help="0 = all")
    p.add_argument("--format", dest="fmt", required=True, help="requested output format")
    p.add_argument("--charts", action="store_true")
    p.add_argument("--regions-only", action="store_true")
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--device", choices=["auto", "cpu"], default="auto")
    p.add_argument("--images-dir", default="", help="raster cache dir (pdf x raster engine)")
    p.add_argument("--output", required=True)
    p.add_argument("--job-id", required=True)
    return p.parse_args(argv)


def main(argv=None) -> int:
    from app.core.envpath import ensure_conda_bin_on_path

    ensure_conda_bin_on_path()
    args = parse_args(argv)

    # Engine libraries print freely; protocol events go to the REAL stdout and
    # everything else is captured (its tail is attached to the result event).
    real_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    def emit(payload: dict) -> None:
        emit_event(real_stdout, {**payload, "job_id": args.job_id})

    spec = get_spec(args.engine)
    fmt_used, fmt_fallback = spec.effective_format(args.fmt)
    input_path = Path(args.input)

    result = {
        "event": "result", "status": "ok", "output_path": args.output,
        "format_used": fmt_used, "format_fallback": fmt_fallback,
        "pages_processed": [], "wall_time_s": None, "raster_time_s": None,
        "engine_version": "", "device": "", "device_detail": "",
        "chars": 0, "warnings": [], "error": None, "traceback": None,
        "library_log_tail": "",
    }

    try:
        # ---- input compatibility (defense in depth; orchestrator pre-filters)
        if args.kind not in spec.inputs:
            result["status"] = "skipped_input"
            result["error"] = f"{args.engine} does not accept {args.kind} input"
            emit(result)
            return 0

        # ---- resolve pages
        if args.kind == "pdf":
            total = pdf_page_count(input_path)
            explicit = parse_pages_spec(args.pages) if args.pages else None
            indices = target_indices(explicit, args.max_pages,
                                     spec.default_max_pages, total)
        else:
            total, indices = 1, [0]
        emit({"event": "start", "engine": args.engine,
              "file": input_path.name, "total_pages": len(indices)})
        if not indices:
            raise ValueError("No pages to process (all requested pages out of range)")

        # ---- rasterize for engines that read page images
        images: list[Path] = []
        raster_s = None
        if args.kind == "image":
            images = [input_path]
        elif not spec.reads_pdf_directly():
            t = time.perf_counter()
            images = render_indices(input_path, Path(args.images_dir),
                                    args.dpi, indices, emit=emit)
            raster_s = round(time.perf_counter() - t, 2)
        result["raster_time_s"] = raster_s

        # ---- run the adapter (import + model load count toward wall time)
        ctx = WorkerContext(
            input_path=input_path, input_kind=args.kind, page_indices=indices,
            images=images, fmt=fmt_used, charts=args.charts,
            regions_only=args.regions_only and spec.supports_regions_only,
            device_pref=args.device, emit=emit,
        )
        t0 = time.perf_counter()
        adapter = load_adapter(args.engine)
        result["engine_version"] = adapter.get_version()
        out = adapter.run(ctx)
        result["wall_time_s"] = round(time.perf_counter() - t0, 2)

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out.output_text, encoding="utf-8")

        result.update({
            "pages_processed": [i + 1 for i in out.pages_processed],
            "device": out.device, "device_detail": out.device_detail,
            "warnings": out.warnings, "chars": len(out.output_text),
        })
    except Exception as e:
        result.update({
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        })

    log = captured.getvalue()
    result["library_log_tail"] = log[-2000:] if log else ""
    emit(result)
    if result["status"] == "error":
        sys.stderr.write((result["traceback"] or "") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
