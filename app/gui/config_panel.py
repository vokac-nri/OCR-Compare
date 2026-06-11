"""Run configuration panel: source dir, output format, feature flags, pages."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QRadioButton, QSpinBox, QVBoxLayout)

from app.core.pages import parse_pages_spec
from app.core.plan import discover_files
from app.engines import get_spec

FORMATS = ["md", "txt", "json"]


class ConfigPanel(QGroupBox):
    configChanged = Signal()

    def __init__(self, parent=None):
        super().__init__("Run configuration", parent)
        self.source_dir: Path | None = None
        lay = QVBoxLayout(self)

        # --- source directory
        row = QHBoxLayout()
        self.dir_btn = QPushButton("Choose source folder…")
        self.dir_btn.clicked.connect(self._pick_dir)
        row.addWidget(self.dir_btn)
        lay.addLayout(row)
        self.dir_label = QLabel("No folder selected")
        self.dir_label.setWordWrap(True)
        self.dir_label.setStyleSheet("color: #666;")
        lay.addWidget(self.dir_label)

        # --- output format
        row = QHBoxLayout()
        row.addWidget(QLabel("Output format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(FORMATS)
        self.format_combo.currentTextChanged.connect(lambda *_: self.configChanged.emit())
        row.addWidget(self.format_combo)
        row.addStretch(1)
        lay.addLayout(row)
        self.fallback_hint = QLabel("")
        self.fallback_hint.setWordWrap(True)
        self.fallback_hint.setStyleSheet("color: #ef6c00; font-size: 11px;")
        lay.addWidget(self.fallback_hint)

        # --- feature flags
        self.charts_check = QCheckBox("Chart parsing (chart → table) ⚠")
        self.charts_check.setToolTip(
            "Only PP-StructureV3 and PaddleOCR-VL honor this.\n"
            "⚠ Chart→table output is experimental — verify extracted values.")
        lay.addWidget(self.charts_check)

        self.regions_check = QCheckBox("Charts/tables regions only")
        self.regions_check.setToolTip(
            "Output only detected table/chart regions, skipping body text.\n"
            "Supported by PP-StructureV3 and PaddleOCR-VL; you will be asked\n"
            "what to do with other selected engines before the run.")
        lay.addWidget(self.regions_check)

        self.scoring_check = QCheckBox("CER/WER scoring (vs PyMuPDF text layer)")
        self.scoring_check.setToolTip(
            "Optional accuracy scoring for digital PDFs: character/word error\n"
            "rate against the PDF's own text layer. Meaningless for scans.")
        lay.addWidget(self.scoring_check)

        # --- page limits
        pages_box = QGroupBox("PDF pages")
        pl = QVBoxLayout(pages_box)
        row = QHBoxLayout()
        self.first_n_radio = QRadioButton("First")
        self.first_n_radio.setChecked(True)
        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(0, 9999)
        self.max_pages_spin.setValue(8)
        self.max_pages_spin.setSpecialValueText("all")
        row.addWidget(self.first_n_radio)
        row.addWidget(self.max_pages_spin)
        row.addWidget(QLabel("pages (0 = all)"))
        row.addStretch(1)
        pl.addLayout(row)
        row = QHBoxLayout()
        self.explicit_radio = QRadioButton("Pages:")
        self.pages_edit = QLineEdit()
        self.pages_edit.setPlaceholderText("e.g. 2-5,8")
        self.pages_edit.textChanged.connect(self._validate_pages)
        self.pages_edit.editingFinished.connect(self._validate_pages)
        row.addWidget(self.explicit_radio)
        row.addWidget(self.pages_edit)
        pl.addLayout(row)
        self.pages_error = QLabel("")
        self.pages_error.setStyleSheet("color:#c62828; font-size:11px;")
        pl.addWidget(self.pages_error)
        lay.addWidget(pages_box)

    # ------------------------------------------------------------- source dir
    def _pick_dir(self):
        start = str(self.source_dir or "")
        path = QFileDialog.getExistingDirectory(self, "Source folder", start)
        if path:
            self.set_source_dir(Path(path))

    def set_source_dir(self, path: Path):
        self.source_dir = path
        files = discover_files(path)
        pdfs = sum(1 for f in files if f.kind == "pdf")
        imgs = len(files) - pdfs
        self.dir_label.setText(f"{path}\n{pdfs} PDF(s), {imgs} image(s)")
        self.configChanged.emit()

    # ------------------------------------------------------------- validation
    def _validate_pages(self):
        if not self.pages_edit.text().strip():
            self.pages_error.setText("")
            self.pages_edit.setStyleSheet("")
            return
        self.explicit_radio.setChecked(True)
        try:
            parse_pages_spec(self.pages_edit.text())
            self.pages_error.setText("")
            self.pages_edit.setStyleSheet("")
        except ValueError as e:
            self.pages_error.setText(str(e))
            self.pages_edit.setStyleSheet("border: 1px solid #c62828;")

    def pages_valid(self) -> bool:
        if not self.explicit_radio.isChecked():
            return True
        try:
            parse_pages_spec(self.pages_edit.text())
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------- fallbacks
    def update_fallback_hint(self, selected_engines: list[str]):
        fmt = self.format_combo.currentText()
        falls = []
        for eid in selected_engines:
            used, fb = get_spec(eid).effective_format(fmt)
            if fb:
                falls.append(f"{eid}→{used}")
        self.fallback_hint.setText(
            ("Format fallback: " + ", ".join(falls)) if falls else "")
