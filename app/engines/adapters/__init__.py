"""Adapter registry: engine id -> module name under app.engines.adapters.

Modules are imported lazily (and only inside the worker process) so the GUI
process never loads an engine library.
"""
ADAPTERS = {
    "pymupdf": "pymupdf_adapter",
    "pypdfium2": "pypdfium2_adapter",
    "pdftotext": "pdftotext_adapter",
    "liteparse": "liteparse_adapter",
    "tesseract": "tesseract_adapter",
    "easyocr": "easyocr_adapter",
    "paddleocr": "paddleocr_adapter",
    "ppstructurev3": "ppstructurev3_adapter",
    "paddleocr-vl": "paddleocr_vl_adapter",
    "rapidocr": "rapidocr_adapter",
    "docling": "docling_adapter",
    "markitdown": "markitdown_adapter",
}


def load_adapter(engine_id: str):
    import importlib

    return importlib.import_module(f"app.engines.adapters.{ADAPTERS[engine_id]}")
