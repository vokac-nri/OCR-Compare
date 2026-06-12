"""Results tree: per-file groups with per-engine result rows, checkbox
selection for diffing, built-in/external open, live updates during a run."""
from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QHBoxLayout, QMessageBox, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from app.core.openpath import open_path
from app.core.rundata import JobResult, RunData
from app.gui.markdown_diff_dialog import MarkdownDiffDialog
from app.gui.viewer_dialog import ViewerDialog

COLS = ["Output", "Status", "Format", "Wall s", "s/page", "Pages", "Device",
        "CER", "WER", "Warnings"]
PATH_ROLE = Qt.ItemDataRole.UserRole


class ResultsPanel(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.run_dir: Path | None = None
        self._file_items: list[QTreeWidgetItem] = []
        self._folders: list[str] = []
        lay = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(COLS)
        self.tree.setColumnWidth(0, 280)
        self.tree.itemDoubleClicked.connect(self._open_item)
        self.tree.itemChanged.connect(lambda *_: self._update_buttons())
        self.tree.currentItemChanged.connect(lambda *_: self._update_buttons())
        lay.addWidget(self.tree, 1)

        btns = QHBoxLayout()
        self.open_btn = QPushButton("Open")
        self.open_btn.clicked.connect(self._open_current)
        self.open_ext_btn = QPushButton("Open externally")
        self.open_ext_btn.clicked.connect(self._open_current_external)
        self.diff_btn = QPushButton("Diff selected")
        self.diff_btn.setToolTip("Check exactly 2 outputs, then diff them in "
                                 "the configured external tool")
        self.diff_btn.clicked.connect(self._diff_selected)
        self.diff_md_btn = QPushButton("Diff rendered")
        self.diff_md_btn.setToolTip("Check exactly 2 markdown outputs to "
                                    "compare them as rendered documents, "
                                    "ignoring markup noise")
        self.diff_md_btn.clicked.connect(self._diff_rendered)
        self.folder_btn = QPushButton("Open run folder")
        self.folder_btn.clicked.connect(self._open_run_folder)
        for b in (self.open_btn, self.open_ext_btn, self.diff_btn,
                  self.diff_md_btn, self.folder_btn):
            btns.addWidget(b)
        btns.addStretch(1)
        lay.addLayout(btns)
        self._update_buttons()

    # ------------------------------------------------------------- populate
    def clear(self):
        self.tree.clear()
        self._file_items.clear()
        self._folders.clear()
        self.run_dir = None
        self._update_buttons()

    def begin_run(self, rundata: RunData, run_dir: Path):
        """Set up file groups at run start; results stream in via add_result."""
        self.clear()
        self.run_dir = run_dir
        self._folders = [fe.folder for fe in rundata.files]
        for fe in rundata.files:
            item = QTreeWidgetItem(self.tree, [fe.file_name])
            item.setExpanded(True)
            # Select/unselect-all for the document: checking the parent toggles
            # every checkable result row beneath it (auto-tristate).
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable
                          | Qt.ItemFlag.ItemIsAutoTristate)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            self._file_items.append(item)

    def populate(self, rundata: RunData, run_dir: Path):
        """Full (re)population, e.g. after import."""
        self.begin_run(rundata, run_dir)
        for fi, fe in enumerate(rundata.files):
            for res in fe.results:
                self.add_result(fi, res)
            self.update_scores(fi, fe.results)

    def add_result(self, file_index: int, res: JobResult):
        parent = self._file_items[file_index]
        child = QTreeWidgetItem(parent)
        child.setText(0, res.output_file or f"({res.engine})")
        child.setText(1, res.status)
        child.setText(2, res.format_used + (" ⚠" if res.format_fallback else ""))
        child.setText(3, "" if res.wall_time_s is None else f"{res.wall_time_s:.2f}")
        child.setText(4, "" if res.sec_per_page is None else f"{res.sec_per_page:.3f}")
        child.setText(5, _pages_summary(res.pages_processed))
        child.setText(6, res.device)
        child.setText(9, "; ".join(res.warnings) + (f" {res.error}" if res.error else ""))
        if res.status == "ok" and res.output_file and self.run_dir:
            path = self._output_path(file_index, res)
            child.setData(0, PATH_ROLE, str(path))
            child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            child.setCheckState(0, Qt.CheckState.Unchecked)
            if not path.exists():
                child.setDisabled(True)
                child.setToolTip(0, "Output file is missing on disk")
        else:
            child.setForeground(1, Qt.GlobalColor.red
                                if res.status in ("error", "timeout")
                                else Qt.GlobalColor.gray)
        self._update_buttons()

    def _output_path(self, file_index: int, res: JobResult) -> Path:
        return self.run_dir / self._folders[file_index] / res.output_file

    def update_scores(self, file_index: int, results: list[JobResult]):
        parent = self._file_items[file_index]
        by_name = {res.output_file or f"({res.engine})": res for res in results}
        for i in range(parent.childCount()):
            child = parent.child(i)
            res = by_name.get(child.text(0))
            if res is None:
                continue
            child.setText(7, "" if res.cer is None else f"{res.cer:.4f}")
            child.setText(8, "" if res.wer is None else f"{res.wer:.4f}")
            if res.score_note:
                child.setToolTip(7, res.score_note)
                child.setToolTip(8, res.score_note)

    # ------------------------------------------------------------- actions
    def _checked_paths(self) -> list[Path]:
        out = []
        for fi in self._file_items:
            for i in range(fi.childCount()):
                c = fi.child(i)
                if (c.checkState(0) == Qt.CheckState.Checked and not c.isDisabled()
                        and c.data(0, PATH_ROLE)):
                    out.append(Path(c.data(0, PATH_ROLE)))
        return out

    def _update_buttons(self):
        paths = self._checked_paths() if self._file_items else []
        n = len(paths)
        self.diff_btn.setEnabled(n == 2)
        self.diff_btn.setText(f"Diff selected ({n}/2)" if n else "Diff selected")
        self.diff_md_btn.setEnabled(
            n == 2 and all(p.suffix.lower() == ".md" for p in paths))
        has_run = self.run_dir is not None
        self.folder_btn.setEnabled(has_run)
        current = self.tree.currentItem()
        openable = bool(current and current.data(0, PATH_ROLE))
        self.open_btn.setEnabled(openable)
        self.open_ext_btn.setEnabled(openable)

    def _open_item(self, item: QTreeWidgetItem, _col: int):
        path = item.data(0, PATH_ROLE)
        if path:
            ViewerDialog(Path(path), self).exec()

    def _open_current(self):
        item = self.tree.currentItem()
        if item:
            self._open_item(item, 0)

    def _open_current_external(self):
        item = self.tree.currentItem()
        if item and item.data(0, PATH_ROLE):
            open_path(item.data(0, PATH_ROLE))

    def _open_run_folder(self):
        if self.run_dir:
            open_path(self.run_dir)

    def _diff_rendered(self):
        paths = self._checked_paths()
        if len(paths) == 2:
            MarkdownDiffDialog(paths[0], paths[1], self).exec()

    def _diff_selected(self):
        paths = self._checked_paths()
        if len(paths) != 2:
            return
        kind = self._settings.diff_tool_kind
        try:
            if kind == "vscode":
                mac_code = "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
                exe = self._settings.diff_tool_path or shutil.which("code") \
                    or shutil.which("code.cmd") \
                    or (mac_code if sys.platform == "darwin" and Path(mac_code).exists()
                        else None)
                if not exe:
                    raise FileNotFoundError(
                        "VS Code ('code') not found on PATH — set its location "
                        "in Settings.")
                QProcess.startDetached(exe, ["--diff", str(paths[0]), str(paths[1])])
            elif kind == "bcompare":
                default_bc = (r"C:\Program Files\Beyond Compare 5\BCompare.exe"
                              if os.name == "nt" else
                              "/Applications/Beyond Compare.app/Contents/MacOS/bcomp")
                exe = self._settings.diff_tool_path or shutil.which("BCompare") \
                    or shutil.which("bcomp") or default_bc
                if not Path(exe).exists() and not shutil.which(exe):
                    raise FileNotFoundError(
                        "Beyond Compare not found — set its location in Settings.")
                QProcess.startDetached(exe, [str(paths[0]), str(paths[1])])
            else:
                template = self._settings.diff_tool_template
                cmd = template.format(left=str(paths[0]), right=str(paths[1]))
                parts = shlex.split(cmd, posix=False)
                QProcess.startDetached(parts[0], [p.strip('"') for p in parts[1:]])
        except (OSError, FileNotFoundError, IndexError, KeyError) as e:
            QMessageBox.warning(self, "Diff tool", str(e))


def _pages_summary(pages: list[int]) -> str:
    if not pages:
        return ""
    if len(pages) <= 4:
        return ",".join(map(str, pages))
    return f"{pages[0]}–{pages[-1]} ({len(pages)})"
