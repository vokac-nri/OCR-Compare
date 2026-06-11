"""Generate the sample test corpus in samples/:
- digital_sample.pdf : 3-page born-digital PDF (text + small table)
- scanned_sample.pdf : same content rasterized into an image-only PDF (no text layer)
- chart_sample.pdf   : page with a bar chart drawn as vector graphics + labels
- image_sample.png   : standalone image with text
"""
from __future__ import annotations

from pathlib import Path

import fitz

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def digital() -> fitz.Document:
    doc = fitz.open()
    for n in range(3):
        page = doc.new_page()
        page.insert_text((72, 80), f"Engine Comparison Sample - Page {n + 1}", fontsize=18)
        page.insert_text((72, 120),
                         "The quick brown fox jumps over the lazy dog. "
                         "Revenue grew 70% year over year.", fontsize=11)
        y = 160
        for row in [("Region", "Q1", "Q2"), ("North", "120", "135"), ("South", "98", "143")]:
            x = 72
            for cell in row:
                page.insert_text((x, y), cell, fontsize=10)
                x += 90
            y += 18
        page.insert_text((72, 760), f"Footer - page {n + 1} of 3", fontsize=8)
    return doc


def main() -> None:
    SAMPLES.mkdir(exist_ok=True)

    doc = digital()
    doc.save(SAMPLES / "digital_sample.pdf")

    # Scanned-style: rasterize each page, rebuild as image-only PDF.
    scan = fitz.open()
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        p = scan.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, pixmap=pix)
    scan.save(SAMPLES / "scanned_sample.pdf")
    scan.close()
    doc.close()

    # Chart page: labeled bar chart drawn with vector graphics (no data table
    # in text — chart parsing must recover the values from the bars/labels).
    chart = fitz.open()
    page = chart.new_page()
    page.insert_text((72, 70), "Quarterly Active Users (millions)", fontsize=16)
    values = [("Q1", 12), ("Q2", 19), ("Q3", 27), ("Q4", 23)]
    base_y, max_h, bar_w = 420.0, 280.0, 60.0
    max_v = max(v for _, v in values)
    x = 100.0
    for label, v in values:
        h = max_h * v / max_v
        page.draw_rect(fitz.Rect(x, base_y - h, x + bar_w, base_y),
                       color=(0.1, 0.3, 0.7), fill=(0.3, 0.5, 0.9))
        page.insert_text((x + 18, base_y - h - 8), str(v), fontsize=10)
        page.insert_text((x + 18, base_y + 16), label, fontsize=10)
        x += bar_w + 40
    page.insert_text((72, 470), "Source: internal analytics, FY2026.", fontsize=8)
    chart.save(SAMPLES / "chart_sample.pdf")
    chart.close()

    # Standalone PNG.
    img_doc = fitz.open()
    page = img_doc.new_page()
    page.insert_text((72, 100), "SCANNED-STYLE IMAGE TEXT", fontsize=20)
    page.insert_text((72, 140), "OCR engines must read this from pixels.", fontsize=12)
    page.get_pixmap(dpi=150).save(SAMPLES / "image_sample.png")
    img_doc.close()

    print("samples:", sorted(p.name for p in SAMPLES.iterdir()))


if __name__ == "__main__":
    main()
