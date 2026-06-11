"""The engine catalog: capabilities, speed classes, and user-facing info text.
This drives the engine panel, format fallbacks, the pre-run check dialog, and
version reporting. No engine library is imported here.
"""
from __future__ import annotations

from app.engines.base import EngineSpec

_PDF_ONLY = frozenset({"pdf"})
_PDF_IMG = frozenset({"pdf", "image"})


def _spec(**kw) -> EngineSpec:
    return EngineSpec(**kw)


ENGINE_CATALOG: dict[str, EngineSpec] = {s.id: s for s in [
    _spec(
        id="pymupdf", display_name="PyMuPDF", formats=("txt", "md", "json"),
        inputs=_PDF_ONLY, supports_charts=False, supports_regions_only=False,
        uses_gpu=False, speed_class="fast", default_max_pages=None,
        version_packages=("pymupdf",),
        info=(
            "**Direct text-layer extraction** (no OCR). Reads the text a digital PDF "
            "already contains via the MuPDF engine — essentially instant and "
            "character-perfect on born-digital documents.\n\n"
            "- **How it works:** parses the PDF content streams; never touches pixels.\n"
            "- **Differentiator:** the de-facto reference for digital PDF text; also "
            "emits structured Markdown via *pymupdf4llm* (headings, lists, tables) and "
            "positional JSON.\n"
            "- **Limits:** blind to scanned pages and to text inside images/charts/logos "
            "— output looks complete even when raster content carried the real payload."
        ),
        caveats="Silently blind to raster-only content (scans, charts, logos).",
    ),
    _spec(
        id="pypdfium2", display_name="pypdfium2", formats=("txt",),
        inputs=_PDF_ONLY, supports_charts=False, supports_regions_only=False,
        uses_gpu=False, speed_class="fast", default_max_pages=None,
        version_packages=("pypdfium2",),
        info=(
            "**Direct text-layer extraction** using Google's PDFium (the Chromium PDF "
            "engine). Same class as PyMuPDF: instant, near-perfect on digital PDFs.\n\n"
            "- **Differentiator:** permissive license (PDFium is BSD; PyMuPDF is AGPL), "
            "which often decides production use.\n"
            "- **Limits:** plain text only; blind to scanned/raster content. Known to "
            "emit U+FFFE on soft hyphens — normalize before indexing."
        ),
        caveats="Emits U+FFFE on soft hyphens; normalize before indexing.",
    ),
    _spec(
        id="pdftotext", display_name="pdftotext (Poppler)", formats=("txt",),
        inputs=_PDF_ONLY, supports_charts=False, supports_regions_only=False,
        uses_gpu=False, speed_class="fast", default_max_pages=None,
        version_packages=(),
        info=(
            "**Direct text-layer extraction** via the classic Poppler CLI with "
            "`-layout`, which preserves the visual column/row arrangement of the page "
            "in plain text.\n\n"
            "- **Differentiator:** layout-preserving mode is excellent for tables in "
            "born-digital PDFs; battle-tested for decades.\n"
            "- **Limits:** reading order on multi-column pages diverges from logical "
            "order (it mirrors visual order); blind to raster content."
        ),
    ),
    _spec(
        id="liteparse", display_name="LiteParse", formats=("md", "txt"),
        inputs=_PDF_ONLY, supports_charts=False, supports_regions_only=False,
        uses_gpu=False, speed_class="fast", default_max_pages=None,
        version_packages=("liteparse",),
        info=(
            "**Digital text extraction → Markdown.** Parses the PDF text layer and "
            "reconstructs document structure (headings, lists) as Markdown, with OCR "
            "disabled in this tool.\n\n"
            "- **Differentiator:** lightweight structure recovery without any model "
            "downloads — a fast middle ground between raw text dumps and heavy "
            "layout pipelines.\n"
            "- **Limits:** structure inference is heuristic; multi-column reading "
            "order can diverge from the text layer."
        ),
    ),
    _spec(
        id="tesseract", display_name="Tesseract", formats=("txt",),
        inputs=_PDF_IMG, supports_charts=False, supports_regions_only=False,
        uses_gpu=False, speed_class="medium", default_max_pages=None,
        version_packages=("pytesseract",),
        info=(
            "**Classic raster OCR** (CPU). Pages are rendered to images, then "
            "recognized with the venerable LSTM-based Tesseract engine.\n\n"
            "- **How it works:** line finding + LSTM sequence recognition on pixels; "
            "needs OCR even for digital PDFs since it never reads the text layer.\n"
            "- **Differentiator:** zero GPU requirement, tiny footprint, very good on "
            "clean single-column scans.\n"
            "- **Limits:** weak on complex layouts and stylized text; prior testing "
            "caught a silent numeric misread (70% → \"10%\")."
        ),
        caveats="Can silently corrupt numbers on stylized text (misread 70% as 10% in prior testing).",
    ),
    _spec(
        id="easyocr", display_name="EasyOCR", formats=("txt",),
        inputs=_PDF_IMG, supports_charts=False, supports_regions_only=False,
        uses_gpu=True, speed_class="medium", default_max_pages=None,
        version_packages=("easyocr",),
        info=(
            "**Deep-learning raster OCR** on PyTorch (CRAFT text detection + CRNN "
            "recognition), GPU-accelerated when CUDA is available.\n\n"
            "- **Differentiator:** very easy multi-language support (80+ languages), "
            "paragraph grouping built in.\n"
            "- **Limits:** mid-pack accuracy and speed in prior testing; no layout/"
            "structure output."
        ),
    ),
    _spec(
        id="paddleocr", display_name="PaddleOCR (PP-OCRv5)", formats=("txt", "json"),
        inputs=_PDF_IMG, supports_charts=False, supports_regions_only=False,
        uses_gpu=True, speed_class="medium", default_max_pages=None,
        version_packages=("paddleocr",),
        info=(
            "**Deep-learning raster OCR** — Baidu's PP-OCRv5 pipeline (detection + "
            "recognition) on PaddlePaddle.\n\n"
            "- **Differentiator:** the fastest GPU OCR in prior testing (~1.8 s/page) "
            "and the best classic OCR at recovering raster content (matrices, logos, "
            "vendor names) that text-layer engines miss entirely.\n"
            "- **Limits:** returns recognized lines in detection order — multi-column "
            "pages come out interleaved line-by-line; no structure output (use "
            "PP-StructureV3 for that)."
        ),
    ),
    _spec(
        id="ppstructurev3", display_name="PP-StructureV3", formats=("md", "json"),
        inputs=_PDF_IMG, supports_charts=True, supports_regions_only=True,
        uses_gpu=True, speed_class="slow", default_max_pages=None,
        version_packages=("paddleocr",),
        info=(
            "**Document-structure pipeline** on PaddlePaddle: layout detection → "
            "region-typed OCR → table structure recognition → Markdown, with optional "
            "chart→table conversion.\n\n"
            "- **Differentiator:** real table structure recovery and region types "
            "(table/chart/figure), which enables this tool's regions-only mode.\n"
            "- **Limits:** slow; **prior testing showed its chart→table conversion "
            "FABRICATED 6 of 12 values on a slope chart** — treat chart output as "
            "unverified."
        ),
        caveats="Chart→table conversion fabricated values in prior testing — do not trust unverified.",
    ),
    _spec(
        id="paddleocr-vl", display_name="PaddleOCR-VL", formats=("md", "json"),
        inputs=_PDF_IMG, supports_charts=True, supports_regions_only=True,
        uses_gpu=True, speed_class="very_slow", default_max_pages=3,
        version_packages=("paddleocr",),
        info=(
            "**Vision-language model.** A multimodal LLM reads the page image and "
            "*generates* structured Markdown (headings, lists, tables) token by "
            "token — the most RAG-friendly output structure of any engine here.\n\n"
            "- **Differentiator:** best word accuracy and structure in prior testing "
            "(mean WER ~0.20, far ahead of classic OCR).\n"
            "- **Limits:** extremely slow (30–190 s/page ON GPU; impractical on CPU — "
            "default page cap is 3 here). Makes silent fluency rewrites of body text, "
            "strips footers/page numbers (breaks page citation), and leaves "
            "charts/logos as image stubs unless chart parsing is enabled."
        ),
        caveats="30–190 s/page on GPU; silent fluency rewrites; strips footers/page numbers.",
    ),
    _spec(
        id="rapidocr", display_name="RapidOCR", formats=("txt",),
        inputs=_PDF_IMG, supports_charts=False, supports_regions_only=False,
        uses_gpu=False, speed_class="medium", default_max_pages=None,
        version_packages=("rapidocr",),
        info=(
            "**Raster OCR via ONNX Runtime** — the PP-OCR models exported to ONNX, so "
            "they run anywhere (CPU by default) without the PaddlePaddle framework.\n\n"
            "- **Differentiator:** the deployment-friendly flavor of PaddleOCR: no "
            "paddle dependency, easy CPU inference.\n"
            "- **Limits:** trailed the other OCR engines on accuracy in prior testing."
        ),
    ),
    _spec(
        id="docling", display_name="Docling (IBM)", formats=("md", "json", "txt"),
        inputs=_PDF_IMG, supports_charts=False, supports_regions_only=False,
        uses_gpu=True, speed_class="slow", default_max_pages=None,
        version_packages=("docling",),
        info=(
            "**Layout-aware document conversion** (IBM Research). Combines a layout "
            "model and the TableFormer table-structure model with the PDF text layer "
            "(plus OCR for scans) to produce clean Markdown/JSON.\n\n"
            "- **Differentiator:** the current go-to open-source converter for RAG "
            "ingestion; real table structure recovery with a permissive license; "
            "reading-order aware.\n"
            "- **Limits:** model downloads on first run; document-level progress only "
            "in this tool; slower than plain text extractors."
        ),
    ),
    _spec(
        id="markitdown", display_name="MarkItDown (Microsoft)", formats=("md",),
        inputs=_PDF_ONLY, supports_charts=False, supports_regions_only=False,
        uses_gpu=False, speed_class="fast", default_max_pages=None,
        version_packages=("markitdown",),
        info=(
            "**Lightweight anything→Markdown converter** (Microsoft). For PDFs it "
            "extracts the text layer and emits minimally-structured Markdown.\n\n"
            "- **Differentiator:** one tool for many formats (Office, HTML, ...), "
            "near-zero overhead — a useful baseline for what \"cheap and cheerful\" "
            "buys you.\n"
            "- **Limits:** little real structure recovery for PDFs; no OCR (scans come "
            "out empty); image input would require wiring an LLM, so it is PDF-only "
            "in this tool."
        ),
    ),
]}

# Sanity: catalog must stay in sync with the adapter registry.
from app.engines.adapters import ADAPTERS as _ADAPTERS  # noqa: E402

assert set(ENGINE_CATALOG) == set(_ADAPTERS), "catalog/adapters registry mismatch"
