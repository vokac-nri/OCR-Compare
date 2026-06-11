"""Engine spec + worker-side adapter contracts. No Qt, no engine imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class EngineSpec:
    id: str
    display_name: str
    formats: tuple[str, ...]            # supported output formats; formats[0] is native
    inputs: frozenset[str]              # {"pdf"} or {"pdf", "image"}
    supports_charts: bool               # chart->table recognition flag
    supports_regions_only: bool         # layout detection with region types
    uses_gpu: bool
    speed_class: str                    # fast | medium | slow | very_slow
    default_max_pages: int | None       # engine-specific page cap (None = run-wide)
    version_packages: tuple[str, ...]   # importlib.metadata distribution names
    info: str                           # markdown for the info dialog
    caveats: str = ""                   # short warning line(s)

    @property
    def native_format(self) -> str:
        return self.formats[0]

    def effective_format(self, requested: str) -> tuple[str, bool]:
        """(format_used, format_fallback)."""
        if requested in self.formats:
            return requested, False
        return self.native_format, True

    def reads_pdf_directly(self) -> bool:
        """True if the adapter consumes the PDF itself (no rasterization)."""
        return self.id in ("pymupdf", "pypdfium2", "pdftotext", "liteparse",
                           "docling", "markitdown")


@dataclass
class WorkerContext:
    input_path: Path
    input_kind: str                     # "pdf" | "image"
    page_indices: list[int]             # 0-based, resolved; [0] for images
    images: list[Path]                  # rendered page PNGs (or the image itself)
    fmt: str                            # effective output format
    charts: bool
    regions_only: bool
    device_pref: str                    # "auto" | "cpu"
    emit: Callable[[dict], None]        # progress event sink


@dataclass
class AdapterResult:
    output_text: str
    pages_processed: list[int]          # 0-based
    device: str                         # "cpu" | "gpu"
    device_detail: str = ""
    warnings: list[str] = field(default_factory=list)
