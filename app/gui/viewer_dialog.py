"""Built-in output viewer: txt/json plain (json pretty-printed), md with a
Raw/Rendered toggle."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QStackedWidget, QTextBrowser,
                               QVBoxLayout)

from app.core.openpath import open_path


class ViewerDialog(QDialog):
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.setWindowTitle(self.path.name)
        self.resize(820, 640)
        lay = QVBoxLayout(self)

        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            text = f"<could not read file: {e}>"

        suffix = self.path.suffix.lower()
        if suffix == ".json":
            try:
                text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

        self.stack = QStackedWidget()
        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(10)
        self.raw.setFont(mono)
        self.raw.setPlainText(text)
        self.stack.addWidget(self.raw)

        self.toggle_btn = None
        if suffix == ".md":
            self.rendered = QTextBrowser()
            self.rendered.setOpenExternalLinks(True)
            self.rendered.setMarkdown(text)
            self.stack.addWidget(self.rendered)
            self.stack.setCurrentWidget(self.rendered)
        lay.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        path_label = QLabel(str(self.path))
        path_label.setStyleSheet("color:#666; font-size:11px;")
        footer.addWidget(path_label, 1)
        if suffix == ".md":
            self.toggle_btn = QPushButton("Show raw")
            self.toggle_btn.clicked.connect(self._toggle)
            footer.addWidget(self.toggle_btn)
        ext_btn = QPushButton("Open externally")
        ext_btn.clicked.connect(lambda: open_path(self.path))
        footer.addWidget(ext_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        lay.addLayout(footer)

    def _toggle(self):
        if self.stack.currentWidget() is self.raw:
            self.stack.setCurrentWidget(self.rendered)
            self.toggle_btn.setText("Show raw")
        else:
            self.stack.setCurrentWidget(self.raw)
            self.toggle_btn.setText("Show rendered")
