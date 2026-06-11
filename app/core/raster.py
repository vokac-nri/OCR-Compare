"""PDF page rasterization for OCR engines, cached per run in _cache/<folder>/.
Jobs run sequentially, so simple file-existence caching is race-free.
"""
from __future__ import annotations

from pathlib import Path


def render_indices(pdf_path: Path, images_dir: Path, dpi: int,
                   indices: list[int], emit=None) -> list[Path]:
    """Render the given 0-based page indices to PNGs (cached). Returns paths."""
    import fitz

    images_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        todo = [i for i in indices if 0 <= i < doc.page_count]
        for n, i in enumerate(todo, 1):
            out = images_dir / f"page_{i + 1:03d}.png"
            if not out.exists():
                if emit:
                    emit({"event": "raster", "page": n, "total": len(todo)})
                doc[i].get_pixmap(dpi=dpi).save(str(out))
            paths.append(out)
    return paths


def pdf_page_count(pdf_path: Path) -> int:
    import fitz

    with fitz.open(pdf_path) as doc:
        return doc.page_count


def pdf_subset(pdf_path: Path, indices: list[int], out_path: Path) -> Path:
    """Write a temp PDF containing only the given 0-based pages (for engines
    with no page-selection API: docling, markitdown)."""
    import fitz

    with fitz.open(pdf_path) as doc:
        valid = [i for i in indices if 0 <= i < doc.page_count]
        doc.select(valid)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out_path))
    return out_path
