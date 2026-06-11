"""Live run progress: overall bar, current job line, per-page bar, log."""
from __future__ import annotations

from PySide6.QtWidgets import (QLabel, QPlainTextEdit, QProgressBar,
                               QVBoxLayout, QWidget)


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        self.run_label = QLabel("No run in progress")
        self.run_label.setStyleSheet("font-weight: bold;")
        lay.addWidget(self.run_label)

        self.overall = QProgressBar()
        self.overall.setFormat("%v / %m jobs")
        lay.addWidget(self.overall)

        self.current_label = QLabel("")
        lay.addWidget(self.current_label)

        self.page_bar = QProgressBar()
        self.page_bar.setFormat("page %v / %m")
        self.page_bar.setVisible(False)
        lay.addWidget(self.page_bar)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        lay.addWidget(self.log, 1)

    # ---- slots wired to RunController signals
    def on_run_started(self, run_id: str):
        self.run_label.setText(f"Run {run_id}")
        self.log.clear()
        self.current_label.setText("")
        self.page_bar.setVisible(False)
        self.overall.reset()

    def on_run_progress(self, done: int, total: int):
        self.overall.setMaximum(max(total, 1))
        self.overall.setValue(done)

    def on_job_started(self, engine: str, file_name: str):
        self.current_label.setText(f"▶ {engine} — {file_name}")
        self.page_bar.setVisible(False)

    def on_raster_progress(self, engine: str, file_name: str, page: int, total: int):
        self.current_label.setText(f"▶ {engine} — {file_name} — rendering page {page}/{total}")

    def on_page_progress(self, engine: str, file_name: str, page: int, total: int):
        self.current_label.setText(f"▶ {engine} — {file_name} — page {page}/{total}")
        self.page_bar.setVisible(True)
        self.page_bar.setMaximum(max(total, 1))
        self.page_bar.setValue(page)

    def on_warning(self, engine: str, file_name: str, message: str):
        self.append_log(f"⚠ {engine} on {file_name}: {message}")

    def on_run_finished(self, status_text: str):
        self.current_label.setText(status_text)
        self.page_bar.setVisible(False)

    def append_log(self, line: str):
        self.log.appendPlainText(line)
