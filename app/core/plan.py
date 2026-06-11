"""RunPlan + source-file discovery. Qt-free so precheck/tests can import it."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTS = {".pdf"}


@dataclass
class SourceFile:
    path: Path
    kind: str               # "pdf" | "image"
    total_pages: int = 1    # filled for PDFs at discovery


@dataclass
class RunPlan:
    source_dir: Path
    files: list[SourceFile]
    engines: list[str]
    output_format: str
    charts: bool
    regions_only: bool
    regions_only_action: str = "skip"     # skip | run_full (set by precheck dialog)
    page_mode: str = "max_pages"          # max_pages | explicit
    max_pages: int = 8                    # 0 = all
    pages_spec: str = ""
    explicit_pages: list[int] = field(default_factory=list)  # parsed, 1-based
    scoring_enabled: bool = False
    dpi: int = 200
    timeout_s: int = 600
    device_pref: str = "auto"
    output_root: Path = Path("Outputs")
    max_concurrency: int = 1              # plumbed, fixed at 1 for fair timing


def discover_files(source_dir: Path) -> list[SourceFile]:
    """Find PDFs and images in source_dir (non-recursive), sorted by name.
    PDF page counts are filled lazily by the caller (needs pymupdf)."""
    out: list[SourceFile] = []
    for p in sorted(source_dir.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in PDF_EXTS:
            out.append(SourceFile(path=p, kind="pdf"))
        elif ext in IMAGE_EXTS:
            out.append(SourceFile(path=p, kind="image"))
    return out
