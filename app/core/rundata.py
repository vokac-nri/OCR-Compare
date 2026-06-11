"""rundata.json schema (v1): the single source of truth for a run, written
preliminarily at run start and atomically rewritten after every job, so even a
crashed run is importable. Per-file manifest.json files are derived slices.

from_json tolerates unknown keys (forward compatibility with future schema
additions) and missing keys (defaults), so older app versions can still import
newer runs at best effort.
"""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1


def _from_dict(cls, d: dict):
    """Build a dataclass from a dict, ignoring unknown keys."""
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


@dataclass
class HostInfo:
    os: str = ""
    python: str = ""
    gpu_name: str = ""
    gpu_driver: str = ""
    torch_cuda: bool | None = None
    paddle_cuda: bool | None = None


@dataclass
class RunSettings:
    source_dir: str = ""
    engines_selected: list[str] = field(default_factory=list)
    output_format: str = "md"
    charts: bool = False
    regions_only: bool = False
    regions_only_action: str = "skip"      # skip | run_full
    page_mode: str = "max_pages"           # max_pages | explicit
    max_pages: int = 8                     # 0 = all
    pages_spec: str = ""
    scoring_enabled: bool = False
    dpi: int = 200
    timeout_s: int = 600
    device_pref: str = "auto"              # auto | cpu


@dataclass
class JobResult:
    engine: str = ""
    status: str = ""                       # ok|error|timeout|skipped_input|skipped_regions|cancelled
    output_file: str = ""                  # relative to the file's folder
    format_requested: str = ""
    format_used: str = ""
    format_fallback: bool = False
    wall_time_s: float | None = None
    raster_time_s: float | None = None
    sec_per_page: float | None = None
    pages_processed: list[int] = field(default_factory=list)   # 1-based
    device: str = ""
    device_detail: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    chars: int = 0
    cer: float | None = None
    wer: float | None = None
    score_note: str = ""                   # why scoring was skipped, if it was


@dataclass
class FileEntry:
    source_path: str = ""
    file_name: str = ""
    folder: str = ""                       # relative to run dir -> runs are relocatable
    kind: str = "pdf"                      # pdf | image
    total_pages: int = 0
    has_text_layer: bool | None = None
    results: list[JobResult] = field(default_factory=list)


@dataclass
class RunData:
    schema_version: int = SCHEMA_VERSION
    app_version: str = ""
    run_id: str = ""
    status: str = "running"                # running | complete | cancelled
    started_at: str = ""
    finished_at: str = ""
    host: HostInfo = field(default_factory=HostInfo)
    settings: RunSettings = field(default_factory=RunSettings)
    engine_versions: dict[str, str] = field(default_factory=dict)
    engine_interpreters: dict[str, str] = field(default_factory=dict)
    files: list[FileEntry] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "RunData":
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError("rundata.json: top level is not an object")
        if d.get("schema_version", 0) > SCHEMA_VERSION:
            # Newer schema: still load best-effort, unknown keys are dropped.
            pass
        rd = _from_dict(cls, d)
        rd.host = _from_dict(HostInfo, d.get("host", {}) or {})
        rd.settings = _from_dict(RunSettings, d.get("settings", {}) or {})
        rd.files = [
            dataclasses.replace(
                _from_dict(FileEntry, f),
                results=[_from_dict(JobResult, r) for r in f.get("results", [])],
            )
            for f in d.get("files", [])
        ]
        return rd


def write_rundata(rundata: RunData, run_dir: Path) -> None:
    """Atomic write: a crash mid-write never leaves a corrupt rundata.json."""
    target = run_dir / "rundata.json"
    tmp = run_dir / "rundata.json.tmp"
    tmp.write_text(rundata.to_json(), encoding="utf-8")
    os.replace(tmp, target)


def load_rundata(path: Path) -> RunData:
    return RunData.from_json(Path(path).read_text(encoding="utf-8"))


def write_manifests(rundata: RunData, run_dir: Path) -> None:
    """Per-file manifest.json: that file's results + versions + settings snapshot."""
    for entry in rundata.files:
        folder = run_dir / entry.folder
        if not folder.is_dir():
            continue
        ran = {r.engine for r in entry.results}
        manifest = {
            "schema_version": rundata.schema_version,
            "run_id": rundata.run_id,
            "settings": dataclasses.asdict(rundata.settings),
            "engine_versions": {k: v for k, v in rundata.engine_versions.items() if k in ran},
            "file": dataclasses.asdict(entry),
        }
        (folder / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
