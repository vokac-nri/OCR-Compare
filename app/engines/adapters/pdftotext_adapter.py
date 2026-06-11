"""pdftotext (Poppler CLI) with -layout: digital text layer, txt only."""
from __future__ import annotations

import re
import subprocess

from app.engines.base import AdapterResult, WorkerContext


def get_version() -> str:
    # pdftotext prints its version banner on stderr.
    proc = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
    m = re.search(r"pdftotext version (\S+)", proc.stderr or proc.stdout or "")
    return m.group(1) if m else "unknown"


def run(ctx: WorkerContext) -> AdapterResult:
    chunks = []
    for n, i in enumerate(ctx.page_indices, 1):
        ctx.emit({"event": "page", "page": n, "total": len(ctx.page_indices)})
        pg = str(i + 1)
        proc = subprocess.run(
            ["pdftotext", "-layout", "-f", pg, "-l", pg, str(ctx.input_path), "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"pdftotext failed on page {pg}: "
                               f"{(proc.stderr or '').strip()[-300:]}")
        chunks.append(proc.stdout)
    return AdapterResult(output_text="\n\n".join(chunks),
                         pages_processed=list(ctx.page_indices), device="cpu")
