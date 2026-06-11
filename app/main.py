"""Application entry point: python -m app.main"""
from __future__ import annotations

import sys


def main() -> int:
    from app.core.envpath import ensure_conda_bin_on_path

    ensure_conda_bin_on_path()

    from PySide6.QtWidgets import QApplication

    from app.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("OCR Compare")
    app.setOrganizationName("CoreBTS")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
