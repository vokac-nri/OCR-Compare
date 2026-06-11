"""MainWindow: config column on the left, Progress/Results tabs on the right.
Wires panels to the RunController and owns the import feature.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path

from PySide6.QtCore import QRunnable, QThreadPool, Signal, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFileDialog, QMainWindow, QMessageBox,
                               QSplitter, QTabWidget, QToolBar, QVBoxLayout,
                               QWidget)

from app.core.pages import parse_pages_spec
from app.core.plan import RunPlan, discover_files
from app.core.precheck import build_precheck_report
from app.core.rundata import HostInfo, load_rundata
from app.core.runner import RunController
from app.core.settings import AppSettings
from app.gui.config_panel import ConfigPanel
from app.gui.engine_panel import EnginePanel
from app.gui.precheck_dialog import PrecheckDialog
from app.gui.progress_panel import ProgressPanel
from app.gui.results_panel import ResultsPanel
from app.gui.settings_dialog import SettingsDialog


class _GpuProbeBridge(QObject):
    done = Signal(dict)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR Compare — text-extraction engine benchmarking")
        self.resize(1280, 800)
        self.settings = AppSettings()
        self._gpu_status: dict | None = None

        # ---- toolbar
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.run_action = QAction("▶ Run", self)
        self.run_action.triggered.connect(self._on_run)
        self.cancel_action = QAction("■ Cancel", self)
        self.cancel_action.setEnabled(False)
        self.cancel_action.triggered.connect(self._on_cancel)
        import_action = QAction("Import run…", self)
        import_action.triggered.connect(self._on_import)
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._on_settings)
        outputs_action = QAction("Open outputs folder", self)
        outputs_action.triggered.connect(self._open_outputs)
        for a in (self.run_action, self.cancel_action, import_action,
                  settings_action, outputs_action):
            tb.addAction(a)

        # ---- layout
        splitter = QSplitter()
        left = QWidget()
        ll = QVBoxLayout(left)
        self.engine_panel = EnginePanel()
        self.config_panel = ConfigPanel()
        ll.addWidget(self.engine_panel, 1)
        ll.addWidget(self.config_panel)
        splitter.addWidget(left)

        self.tabs = QTabWidget()
        self.progress_panel = ProgressPanel()
        self.results_panel = ResultsPanel(self.settings)
        self.tabs.addTab(self.progress_panel, "Progress")
        self.tabs.addTab(self.results_panel, "Results")
        splitter.addWidget(self.tabs)
        splitter.setSizes([380, 900])
        self.setCentralWidget(splitter)

        # ---- runner
        self.runner = RunController(self.settings, self)
        self.runner.logLine.connect(self.progress_panel.append_log)
        self.runner.jobStarted.connect(self.progress_panel.on_job_started)
        self.runner.rasterProgress.connect(self.progress_panel.on_raster_progress)
        self.runner.pageProgress.connect(self.progress_panel.on_page_progress)
        self.runner.jobWarning.connect(self.progress_panel.on_warning)
        self.runner.runProgress.connect(self.progress_panel.on_run_progress)
        self.runner.jobFinished.connect(self.results_panel.add_result)
        self.runner.scoresUpdated.connect(self._on_scores_updated)
        self.runner.runFinished.connect(self._on_run_finished)
        self.runner.runFailed.connect(self._on_run_failed)

        # ---- restore last state
        self.settings.restore_geometry(self)
        if self.settings.last_engines:
            self.engine_panel.set_selected(self.settings.last_engines)
        self.config_panel.format_combo.setCurrentText(self.settings.last_format)
        if self.settings.last_source_dir and Path(self.settings.last_source_dir).is_dir():
            self.config_panel.set_source_dir(Path(self.settings.last_source_dir))
        self.engine_panel.selectionChanged.connect(self._refresh_hints)
        self.config_panel.configChanged.connect(self._refresh_hints)
        self._refresh_hints()
        self._probe_gpu_async()
        self.statusBar().showMessage("Probing GPU availability…")

    # ------------------------------------------------------------- gpu probe
    def _probe_gpu_async(self):
        bridge = self._gpu_bridge = _GpuProbeBridge(self)
        bridge.done.connect(self._on_gpu_probed)

        class _Probe(QRunnable):
            def run(_self):
                from app.core.device import probe_gpu

                bridge.done.emit(probe_gpu())

        QThreadPool.globalInstance().start(_Probe())

    def _on_gpu_probed(self, status: dict):
        self._gpu_status = status
        gpu = status.get("gpu_name") or "no CUDA GPU detected"
        self.statusBar().showMessage(
            f"GPU: {gpu} | torch CUDA: {status.get('torch')} | "
            f"paddle CUDA: {status.get('paddle')}")

    # ------------------------------------------------------------- run
    def _refresh_hints(self):
        self.config_panel.update_fallback_hint(self.engine_panel.selected_engines())

    def _build_plan(self) -> RunPlan | None:
        engines = self.engine_panel.selected_engines()
        if not engines:
            QMessageBox.information(self, "Run", "Select at least one engine.")
            return None
        cp = self.config_panel
        if cp.source_dir is None or not cp.source_dir.is_dir():
            QMessageBox.information(self, "Run", "Choose a source folder first.")
            return None
        if not cp.pages_valid():
            QMessageBox.warning(self, "Run", "Fix the page spec first.")
            return None
        files = discover_files(cp.source_dir)
        if not files:
            QMessageBox.information(self, "Run",
                                    "No PDFs or images found in the source folder.")
            return None
        # Page counts (fast header reads; needed for progress + rundata).
        import fitz

        for sf in files:
            if sf.kind == "pdf":
                try:
                    with fitz.open(sf.path) as doc:
                        sf.total_pages = doc.page_count
                except Exception:
                    sf.total_pages = 0

        explicit_mode = cp.explicit_radio.isChecked()
        return RunPlan(
            source_dir=cp.source_dir,
            files=files,
            engines=engines,
            output_format=cp.format_combo.currentText(),
            charts=cp.charts_check.isChecked(),
            regions_only=cp.regions_check.isChecked(),
            page_mode="explicit" if explicit_mode else "max_pages",
            max_pages=cp.max_pages_spin.value(),
            pages_spec=cp.pages_edit.text().strip() if explicit_mode else "",
            explicit_pages=(parse_pages_spec(cp.pages_edit.text())
                            if explicit_mode else []),
            scoring_enabled=cp.scoring_check.isChecked(),
            dpi=self.settings.dpi,
            timeout_s=self.settings.timeout_s,
            device_pref=self.settings.device_pref,
            output_root=self.settings.output_root,
        )

    def _on_run(self):
        plan = self._build_plan()
        if plan is None:
            return
        gpu = self._gpu_status or {"torch": False, "paddle": False}
        report = build_precheck_report(plan, gpu)
        dialog = PrecheckDialog(report, self)
        if dialog.exec() != PrecheckDialog.DialogCode.Accepted:
            return
        plan.regions_only_action = dialog.regions_only_action()

        # Persist last-used selections
        self.settings.last_engines = plan.engines
        self.settings.last_format = plan.output_format
        self.settings.last_source_dir = str(plan.source_dir)

        host = HostInfo(
            os=platform.platform(), python=platform.python_version(),
            gpu_name=gpu.get("gpu_name", ""),
            torch_cuda=gpu.get("torch"), paddle_cuda=gpu.get("paddle"))

        self.run_action.setEnabled(False)
        self.cancel_action.setEnabled(True)
        self.tabs.setCurrentWidget(self.progress_panel)
        self.runner.start(plan, host)
        if self.runner.rundata is not None:
            self.progress_panel.on_run_started(self.runner.rundata.run_id)
            self.results_panel.begin_run(self.runner.rundata, self.runner.run_dir)

    def _on_cancel(self):
        self.runner.cancel()

    def _on_scores_updated(self, file_index: int):
        rd = self.runner.rundata
        if rd:
            self.results_panel.update_scores(file_index, rd.files[file_index].results)

    def _on_run_finished(self, rundata):
        self.run_action.setEnabled(True)
        self.cancel_action.setEnabled(False)
        self.progress_panel.on_run_finished(f"Run {rundata.run_id}: {rundata.status}")
        self.progress_panel.append_log(f"Run finished: {rundata.status}. "
                                       f"Outputs: {self.runner.run_dir}")
        self.tabs.setCurrentWidget(self.results_panel)

    def _on_run_failed(self, message: str):
        self.run_action.setEnabled(True)
        self.cancel_action.setEnabled(False)
        QMessageBox.critical(self, "Run failed", message)

    # ------------------------------------------------------------- import
    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import run", str(self.settings.output_root),
            "Run data (rundata.json)")
        if not path:
            return
        try:
            rundata = load_rundata(Path(path))
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.critical(self, "Import", f"Could not load rundata.json:\n{e}")
            return

        run_dir = Path(path).parent
        s = rundata.settings
        self.engine_panel.set_selected(s.engines_selected)
        cp = self.config_panel
        cp.format_combo.setCurrentText(s.output_format)
        cp.charts_check.setChecked(s.charts)
        cp.regions_check.setChecked(s.regions_only)
        cp.scoring_check.setChecked(s.scoring_enabled)
        if s.page_mode == "explicit" and s.pages_spec:
            cp.explicit_radio.setChecked(True)
            cp.pages_edit.setText(s.pages_spec)
        else:
            cp.first_n_radio.setChecked(True)
            cp.max_pages_spin.setValue(s.max_pages)
        if s.source_dir and Path(s.source_dir).is_dir():
            cp.set_source_dir(Path(s.source_dir))

        self.results_panel.populate(rundata, run_dir)
        self.tabs.setCurrentWidget(self.results_panel)
        self.statusBar().showMessage(
            f"Imported run {rundata.run_id} (app {rundata.app_version}, "
            f"status: {rundata.status})")

    # ------------------------------------------------------------- misc
    def _on_settings(self):
        SettingsDialog(self.settings, self).exec()

    def _open_outputs(self):
        root = self.settings.output_root
        root.mkdir(parents=True, exist_ok=True)
        os.startfile(str(root))

    def closeEvent(self, event):
        self.settings.save_geometry(self)
        super().closeEvent(event)
