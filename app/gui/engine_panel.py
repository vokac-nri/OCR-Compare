"""Engine selection panel: checkbox per engine + speed/GPU badges + info button."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton,
                               QToolButton, QVBoxLayout, QWidget)

from app.engines import all_specs
from app.gui.engine_info_dialog import EngineInfoDialog

SPEED_BADGE = {
    "fast": ("fast", "#2e7d32"),
    "medium": ("medium", "#9e9d24"),
    "slow": ("slow", "#ef6c00"),
    "very_slow": ("very slow", "#c62828"),
}


class _EngineRow(QWidget):
    def __init__(self, spec, parent=None):
        super().__init__(parent)
        self.spec = spec
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)

        self.check = QCheckBox(spec.display_name)
        first_line = spec.info.split("\n")[0].replace("**", "")
        self.check.setToolTip(first_line)
        lay.addWidget(self.check, 1)

        label, color = SPEED_BADGE[spec.speed_class]
        chip = QLabel(label)
        chip.setStyleSheet(f"color: white; background: {color}; border-radius: 7px;"
                           "padding: 1px 7px; font-size: 10px;")
        lay.addWidget(chip)

        if spec.uses_gpu:
            gpu = QLabel("GPU")
            gpu.setStyleSheet("color: white; background: #1565c0; border-radius: 7px;"
                              "padding: 1px 7px; font-size: 10px;")
            lay.addWidget(gpu)

        info = QToolButton()
        info.setText("ⓘ")
        info.setAutoRaise(True)
        info.setToolTip(f"About {spec.display_name}")
        info.clicked.connect(self._show_info)
        lay.addWidget(info)

    def _show_info(self):
        EngineInfoDialog(self.spec, self).exec()


class EnginePanel(QGroupBox):
    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__("Engines", parent)
        self._rows: dict[str, _EngineRow] = {}
        lay = QVBoxLayout(self)

        links = QHBoxLayout()
        for text, fn in [("All", self._select_all), ("None", self._select_none),
                         ("Fast only", self._select_fast)]:
            btn = QPushButton(text)
            btn.setFlat(True)
            btn.setMaximumWidth(70)
            btn.setStyleSheet("text-align:left; color:#1565c0;")
            btn.clicked.connect(fn)
            links.addWidget(btn)
        links.addStretch(1)
        lay.addLayout(links)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for spec in all_specs():
            row = _EngineRow(spec)
            row.check.stateChanged.connect(lambda *_: self.selectionChanged.emit())
            item = QListWidgetItem(self.list)
            item.setSizeHint(row.sizeHint())
            self.list.setItemWidget(item, row)
            self._rows[spec.id] = row
        lay.addWidget(self.list)

    def selected_engines(self) -> list[str]:
        return [eid for eid, row in self._rows.items() if row.check.isChecked()]

    def set_selected(self, engine_ids: list[str]) -> None:
        for eid, row in self._rows.items():
            row.check.setChecked(eid in engine_ids)

    def _select_all(self):
        self.set_selected(list(self._rows))

    def _select_none(self):
        self.set_selected([])

    def _select_fast(self):
        self.set_selected([eid for eid, row in self._rows.items()
                           if row.spec.speed_class == "fast"])
