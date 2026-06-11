"""Application entry point: python -m app.main"""
from __future__ import annotations

import os
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

    # The one-click launchers run a console-mode python so first-run install
    # progress is visible; they set this var so we hide that console once the
    # GUI is up, and re-show it on exit for the launcher's pause-on-failure.
    hidden_hwnd = 0
    if sys.platform == "win32" and os.environ.get("OCR_COMPARE_HIDE_CONSOLE") == "1":
        import ctypes

        hidden_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hidden_hwnd:
            ctypes.windll.user32.ShowWindow(hidden_hwnd, 0)  # SW_HIDE

    code = app.exec()
    if hidden_hwnd:
        ctypes.windll.user32.ShowWindow(hidden_hwnd, 5)  # SW_SHOW
    return code


if __name__ == "__main__":
    sys.exit(main())
