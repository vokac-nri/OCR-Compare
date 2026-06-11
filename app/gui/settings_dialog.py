"""Settings dialog: output root, diff tool, run defaults, per-engine
interpreter overrides, environment verification."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
                               QPlainTextEdit, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from app.engines import all_specs

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")
        self.resize(620, 480)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # ---- General tab
        gen = QWidget()
        form = QFormLayout(gen)
        self.output_root_edit = QLineEdit(str(settings.output_root))
        pick = QPushButton("…")
        pick.setMaximumWidth(30)
        pick.clicked.connect(self._pick_output_root)
        row = QHBoxLayout()
        row.addWidget(self.output_root_edit, 1)
        row.addWidget(pick)
        form.addRow("Outputs folder:", row)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 36000)
        self.timeout_spin.setValue(settings.timeout_s)
        self.timeout_spin.setSuffix(" s")
        form.addRow("Per-job timeout:", self.timeout_spin)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(settings.dpi)
        form.addRow("Raster DPI (OCR engines):", self.dpi_spin)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cpu"])
        self.device_combo.setCurrentText(settings.device_pref)
        form.addRow("Device:", self.device_combo)

        self.keep_cache_check = QCheckBox("Keep rasterized page images after run")
        self.keep_cache_check.setChecked(settings.keep_cache)
        form.addRow("", self.keep_cache_check)
        tabs.addTab(gen, "General")

        # ---- Diff tool tab
        diff = QWidget()
        dform = QFormLayout(diff)
        self.diff_kind_combo = QComboBox()
        self.diff_kind_combo.addItems(["vscode", "bcompare", "custom"])
        self.diff_kind_combo.setCurrentText(settings.diff_tool_kind)
        dform.addRow("Tool:", self.diff_kind_combo)
        self.diff_path_edit = QLineEdit(settings.diff_tool_path)
        self.diff_path_edit.setPlaceholderText("blank = find on PATH")
        dform.addRow("Executable:", self.diff_path_edit)
        self.diff_template_edit = QLineEdit(settings.diff_tool_template)
        self.diff_template_edit.setPlaceholderText('mytool "{left}" "{right}"')
        dform.addRow("Custom command:", self.diff_template_edit)
        tabs.addTab(diff, "Diff tool")

        # ---- Interpreters tab
        interp = QWidget()
        ilay = QVBoxLayout(interp)
        self.interp_table = QTableWidget(0, 2)
        self.interp_table.setHorizontalHeaderLabels(["Engine", "Python interpreter override"])
        self.interp_table.horizontalHeader().setStretchLastSection(True)
        overrides = settings.engine_python_overrides
        specs = all_specs()
        self.interp_table.setRowCount(len(specs))
        for r, spec in enumerate(specs):
            eng_item = QTableWidgetItem(spec.id)
            eng_item.setFlags(eng_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.interp_table.setItem(r, 0, eng_item)
            self.interp_table.setItem(r, 1, QTableWidgetItem(overrides.get(spec.id, "")))
        ilay.addWidget(self.interp_table)
        tabs.addTab(interp, "Interpreters")

        # ---- Environment tab
        env = QWidget()
        elay = QVBoxLayout(env)
        verify_btn = QPushButton("Verify environment (runs tools/check_env.py)")
        verify_btn.clicked.connect(self._verify_env)
        elay.addWidget(verify_btn)
        self.env_output = QPlainTextEdit()
        self.env_output.setReadOnly(True)
        elay.addWidget(self.env_output, 1)
        tabs.addTab(env, "Environment")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._verify_proc: QProcess | None = None

    def _pick_output_root(self):
        path = QFileDialog.getExistingDirectory(self, "Outputs folder",
                                                self.output_root_edit.text())
        if path:
            self.output_root_edit.setText(path)

    def _verify_env(self):
        import sys

        self.env_output.setPlainText("Running checks (each engine imports in its "
                                     "own subprocess — this takes a minute)…")
        self._verify_proc = QProcess(self)
        self._verify_proc.setProgram(sys.executable)
        self._verify_proc.setArguments([str(PROJECT_ROOT / "tools" / "check_env.py")])
        self._verify_proc.readyReadStandardOutput.connect(
            lambda: self.env_output.appendPlainText(
                bytes(self._verify_proc.readAllStandardOutput()).decode(
                    "utf-8", errors="replace").rstrip()))
        self._verify_proc.start()

    def _save(self):
        s = self._settings
        s.output_root = Path(self.output_root_edit.text())
        s.timeout_s = self.timeout_spin.value()
        s.dpi = self.dpi_spin.value()
        s.device_pref = self.device_combo.currentText()
        s.keep_cache = self.keep_cache_check.isChecked()
        s.diff_tool_kind = self.diff_kind_combo.currentText()
        s.diff_tool_path = self.diff_path_edit.text().strip()
        s.diff_tool_template = self.diff_template_edit.text().strip() or "{left} {right}"
        overrides = {}
        for r in range(self.interp_table.rowCount()):
            eng = self.interp_table.item(r, 0).text()
            val = (self.interp_table.item(r, 1).text() or "").strip() \
                if self.interp_table.item(r, 1) else ""
            if val:
                overrides[eng] = val
        s.engine_python_overrides = overrides
        self.accept()
