"""Headless end-to-end exercise of RunController (no GUI window): runs real
worker subprocesses over the samples dir and validates the output tree.

    conda run -n ocr-compare python tools/headless_run.py \
        [engine,engine,...] [max_pages] [charts|regions|charts+regions]
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.envpath import ensure_conda_bin_on_path  # noqa: E402

ensure_conda_bin_on_path()

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from app.core.plan import RunPlan, discover_files  # noqa: E402
from app.core.rundata import HostInfo  # noqa: E402
from app.core.runner import RunController  # noqa: E402
from app.core.settings import AppSettings  # noqa: E402


def main() -> int:
    engines = (sys.argv[1].split(",") if len(sys.argv) > 1
               else ["pymupdf", "pdftotext", "tesseract"])
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    flags = sys.argv[3] if len(sys.argv) > 3 else ""
    app = QCoreApplication([])
    settings = AppSettings()

    files = discover_files(PROJECT_ROOT / "samples")
    import fitz

    for sf in files:
        if sf.kind == "pdf":
            with fitz.open(sf.path) as doc:
                sf.total_pages = doc.page_count

    plan = RunPlan(
        source_dir=PROJECT_ROOT / "samples",
        files=files,
        engines=engines,
        output_format="md",
        charts="charts" in flags,
        regions_only="regions" in flags,
        max_pages=max_pages,
        scoring_enabled=True,
        dpi=150,
        timeout_s=900,
        output_root=PROJECT_ROOT / "Outputs",
    )

    runner = RunController(settings)
    exit_code = {"v": 1}

    runner.logLine.connect(lambda s: print(f"  | {s}"))
    runner.pageProgress.connect(
        lambda e, f, p, t: print(f"  | {e} {f} page {p}/{t}"))
    runner.runFailed.connect(lambda msg: (print("RUN FAILED:", msg), app.quit()))

    def on_finished(rd):
        print(f"\nrun {rd.run_id} -> {rd.status}")
        run_dir = runner.run_dir
        problems = []
        if not (run_dir / "rundata.json").is_file():
            problems.append("missing rundata.json")
        for fe in rd.files:
            folder = run_dir / fe.folder
            if not (folder / fe.file_name).is_file():
                problems.append(f"missing original copy in {fe.folder}")
            if not (folder / "manifest.json").is_file():
                problems.append(f"missing manifest.json in {fe.folder}")
            for r in fe.results:
                line = (f"  {fe.file_name:<22} {r.engine:<12} {r.status:<14} "
                        f"{r.format_used:<4} wall={r.wall_time_s} "
                        f"cer={r.cer} wer={r.wer} {r.error or ''}")
                print(line)
                if r.status == "ok" and not (folder / r.output_file).is_file():
                    problems.append(f"missing output {r.output_file}")
        if problems:
            print("PROBLEMS:", *problems, sep="\n  - ")
            exit_code["v"] = 1
        else:
            print("output tree OK")
            exit_code["v"] = 0
        # Give scoring threads a moment, then quit.
        QTimer.singleShot(3000, app.quit)

    runner.runFinished.connect(on_finished)
    runner.start(plan, HostInfo(os="headless-test"))
    app.exec()
    return exit_code["v"]


if __name__ == "__main__":
    sys.exit(main())
