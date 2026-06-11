from pathlib import Path

from app.core.plan import RunPlan, SourceFile
from app.core.precheck import build_precheck_report

GPU_OK = {"torch": True, "paddle": True}
GPU_NONE = {"torch": False, "paddle": False}


def make_plan(**kw) -> RunPlan:
    defaults = dict(
        source_dir=Path("C:/docs"),
        files=[SourceFile(path=Path("C:/docs/a.pdf"), kind="pdf", total_pages=5)],
        engines=["pymupdf"],
        output_format="txt",
        charts=False,
        regions_only=False,
    )
    defaults.update(kw)
    return RunPlan(**defaults)


def test_clean_plan_has_no_content():
    rep = build_precheck_report(make_plan(), GPU_OK)
    assert not rep.has_content()


def test_regions_only_flags_unsupported():
    plan = make_plan(engines=["pymupdf", "ppstructurev3", "paddleocr-vl"],
                     regions_only=True, output_format="md")
    rep = build_precheck_report(plan, GPU_OK)
    assert rep.regions_unsupported == ["pymupdf"]


def test_chart_capable_only_when_capable_engine_selected():
    plan = make_plan(engines=["ppstructurev3"], charts=True, output_format="md")
    rep = build_precheck_report(plan, GPU_OK)
    assert rep.chart_capable == ["ppstructurev3"]

    plan2 = make_plan(engines=["pymupdf"], charts=True)
    rep2 = build_precheck_report(plan2, GPU_OK)
    assert rep2.chart_capable == []


def test_format_fallback_detected():
    plan = make_plan(engines=["pypdfium2"], output_format="md")
    rep = build_precheck_report(plan, GPU_OK)
    assert rep.format_fallbacks == [("pypdfium2", "md", "txt")]


def test_image_inputs_skipped_for_pdf_only_engines():
    files = [SourceFile(path=Path("a.pdf"), kind="pdf"),
             SourceFile(path=Path("b.png"), kind="image"),
             SourceFile(path=Path("c.jpg"), kind="image")]
    plan = make_plan(files=files, engines=["pdftotext", "tesseract"])
    rep = build_precheck_report(plan, GPU_OK)
    assert rep.input_skips == [("pdftotext", 2)]


def test_vl_slowness_always_warned():
    plan = make_plan(engines=["paddleocr-vl"], output_format="md")
    rep = build_precheck_report(plan, GPU_OK)
    assert any(e == "paddleocr-vl" and "s/page" in msg
               for e, msg in rep.slow_warnings)


def test_cpu_fallback_warned_per_framework():
    plan = make_plan(engines=["easyocr", "paddleocr"])
    rep = build_precheck_report(plan, GPU_NONE)
    warned = {e for e, _ in rep.slow_warnings}
    assert warned == {"easyocr", "paddleocr"}
    rep_ok = build_precheck_report(plan, GPU_OK)
    assert rep_ok.slow_warnings == []
