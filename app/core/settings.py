"""Typed wrapper over QSettings — all persisted app preferences live here so
no raw QSettings keys are sprinkled around the GUI code.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _find_paddle_env_python() -> Path | None:
    """Locate the ocr-compare-paddle interpreter for any conda root.

    The GUI always runs from the ocr-compare env, so the paddle env is its
    sibling — that first candidate works wherever conda lives (miniconda3,
    miniforge3, custom). The rest cover running outside the env (tests, IDE).
    """
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    candidates = [
        Path(sys.prefix).parent / "ocr-compare-paddle" / "python.exe",
        local / "miniconda3" / "envs" / "ocr-compare-paddle" / "python.exe",
        local / "miniforge3" / "envs" / "ocr-compare-paddle" / "python.exe",
    ]
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        candidates.insert(1, Path(conda_exe).parents[1] / "envs" / "ocr-compare-paddle" / "python.exe")
    return next((c for c in candidates if c.exists()), None)


class AppSettings:
    def __init__(self):
        self._q = QSettings("CoreBTS", "OCRCompare")

    # ---- run configuration defaults
    @property
    def output_root(self) -> Path:
        return Path(self._q.value("output_root", str(PROJECT_ROOT / "Outputs")))

    @output_root.setter
    def output_root(self, v: Path):
        self._q.setValue("output_root", str(v))

    @property
    def timeout_s(self) -> int:
        return int(self._q.value("timeout_s", 600))

    @timeout_s.setter
    def timeout_s(self, v: int):
        self._q.setValue("timeout_s", int(v))

    @property
    def dpi(self) -> int:
        return int(self._q.value("dpi", 200))

    @dpi.setter
    def dpi(self, v: int):
        self._q.setValue("dpi", int(v))

    @property
    def device_pref(self) -> str:
        return str(self._q.value("device_pref", "auto"))

    @device_pref.setter
    def device_pref(self, v: str):
        self._q.setValue("device_pref", v)

    @property
    def keep_cache(self) -> bool:
        return self._q.value("keep_cache", "true") in (True, "true", "True")

    @keep_cache.setter
    def keep_cache(self, v: bool):
        self._q.setValue("keep_cache", "true" if v else "false")

    # ---- diff tool
    @property
    def diff_tool_kind(self) -> str:
        return str(self._q.value("diff_tool/kind", "vscode"))  # vscode|bcompare|custom

    @diff_tool_kind.setter
    def diff_tool_kind(self, v: str):
        self._q.setValue("diff_tool/kind", v)

    @property
    def diff_tool_path(self) -> str:
        return str(self._q.value("diff_tool/path", ""))

    @diff_tool_path.setter
    def diff_tool_path(self, v: str):
        self._q.setValue("diff_tool/path", v)

    @property
    def diff_tool_template(self) -> str:
        return str(self._q.value("diff_tool/template", "{left} {right}"))

    @diff_tool_template.setter
    def diff_tool_template(self, v: str):
        self._q.setValue("diff_tool/template", v)

    # ---- per-engine interpreter overrides (engine id -> python.exe)
    @property
    def engine_python_overrides(self) -> dict[str, str]:
        try:
            return json.loads(str(self._q.value("engine_python_overrides", "{}")))
        except json.JSONDecodeError:
            return {}

    @engine_python_overrides.setter
    def engine_python_overrides(self, v: dict[str, str]):
        self._q.setValue("engine_python_overrides", json.dumps(v))

    # torch-GPU and paddle-GPU cannot share one process (their bundled cudnn
    # DLLs shadow each other -> WinError 127), and paddleocr imports both. The
    # paddle engines therefore run in the `ocr-compare-paddle` env (GPU paddle
    # + CPU torch), created by setup_env.ps1, whenever it exists.
    PADDLE_ENGINES = ("paddleocr", "ppstructurev3", "paddleocr-vl")

    def python_for_engine(self, engine_id: str) -> str:
        override = self.engine_python_overrides.get(engine_id)
        if override:
            return override
        if engine_id in self.PADDLE_ENGINES:
            paddle_python = _find_paddle_env_python()
            if paddle_python is not None:
                return str(paddle_python)
        return sys.executable

    # ---- last-used UI state
    @property
    def last_source_dir(self) -> str:
        return str(self._q.value("last/source_dir", ""))

    @last_source_dir.setter
    def last_source_dir(self, v: str):
        self._q.setValue("last/source_dir", v)

    @property
    def last_engines(self) -> list[str]:
        raw = str(self._q.value("last/engines", ""))
        return [e for e in raw.split(",") if e]

    @last_engines.setter
    def last_engines(self, v: list[str]):
        self._q.setValue("last/engines", ",".join(v))

    @property
    def last_format(self) -> str:
        return str(self._q.value("last/format", "md"))

    @last_format.setter
    def last_format(self, v: str):
        self._q.setValue("last/format", v)

    def save_geometry(self, window) -> None:
        self._q.setValue("geometry", window.saveGeometry())

    def restore_geometry(self, window) -> None:
        geo = self._q.value("geometry")
        if geo is not None:
            window.restoreGeometry(geo)
