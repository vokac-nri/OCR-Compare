"""Pre-run check dialog: warnings + the regions-only skip/run-full choice."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGroupBox, QLabel,
                               QRadioButton, QVBoxLayout)

from app.core.precheck import PrecheckReport


class PrecheckDialog(QDialog):
    """exec() returns Accepted to run; regions_only_action() gives the choice."""

    def __init__(self, report: PrecheckReport, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Before this run…")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        self._skip_radio = None

        def section(text: str, color: str = "#333"):
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {color};")
            lay.addWidget(lbl)

        if report.chart_warning:
            section(f"⚠ <b>Chart parsing:</b> {report.chart_warning}<br>"
                    f"Honored by: {', '.join(report.chart_capable)}.", "#c62828")

        if report.regions_unsupported:
            box = QGroupBox("Regions-only mode")
            bl = QVBoxLayout(box)
            lbl = QLabel("These selected engines do <b>not</b> support "
                         "charts/tables-only output: <b>"
                         + ", ".join(report.regions_unsupported) + "</b>")
            lbl.setWordWrap(True)
            bl.addWidget(lbl)
            self._skip_radio = QRadioButton("Skip these engines for this run")
            self._skip_radio.setChecked(True)
            run_full = QRadioButton("Run them normally (full output)")
            bl.addWidget(self._skip_radio)
            bl.addWidget(run_full)
            lay.addWidget(box)

        for engine, msg in report.slow_warnings:
            section(f"🐢 <b>{engine}</b>: {msg}", "#ef6c00")

        if report.format_fallbacks:
            rows = "".join(f"<li><b>{e}</b>: {req} → {used}</li>"
                           for e, req, used in report.format_fallbacks)
            section("Format fallbacks (engine doesn't support the requested "
                    f"format):<ul>{rows}</ul>")

        if report.input_skips:
            rows = "".join(f"<li><b>{e}</b> will skip {n} image file(s) "
                           "(PDF-only engine)</li>" for e, n in report.input_skips)
            section(f"<ul>{rows}</ul>")

        if not report.has_content():
            section("No warnings — ready to run.")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Run")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def regions_only_action(self) -> str:
        if self._skip_radio is None or self._skip_radio.isChecked():
            return "skip"
        return "run_full"
