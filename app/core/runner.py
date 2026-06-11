"""Run orchestration: sequential QProcess-per-job execution with live progress.

One worker subprocess per (file x engine) job — crash containment, clean
timing, CUDA DLL isolation, and per-engine interpreter overrides. QProcess is
fully asynchronous on the Qt event loop, so the GUI thread never blocks; the
only off-thread work is file copying and CER/WER scoring (QThreadPool).

Layering note: the GUI process never imports an engine framework. The narrow
exception is pymupdf (fitz), used on pool threads for page counts and the
scoring reference text — it is a self-contained C library with none of the
CUDA/DLL hazards the worker isolation exists for.
"""
from __future__ import annotations

import dataclasses
import platform
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (QObject, QProcess, QProcessEnvironment, QRunnable,
                            QThreadPool, QTimer, Signal)

from app import APP_VERSION
from app.core.naming import file_folder_name, output_file_name, unique_run_dir
from app.core.plan import RunPlan
from app.core.protocol import parse_event_line
from app.core.rundata import (FileEntry, HostInfo, JobResult, RunData,
                              RunSettings, write_manifests, write_rundata)
from app.engines import get_spec

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Job:
    job_id: str
    engine: str
    file_index: int
    output_name: str
    images_dir: Path
    pre_status: str | None = None       # skipped_input | skipped_regions | None


class RunController(QObject):
    jobStarted = Signal(str, str)                 # engine_id, file_name
    rasterProgress = Signal(str, str, int, int)   # engine, file, page, total
    pageProgress = Signal(str, str, int, int)     # engine, file, page, total
    jobWarning = Signal(str, str, str)            # engine, file, message
    jobFinished = Signal(int, object)             # file_index, JobResult
    runProgress = Signal(int, int)                # jobs done, total
    logLine = Signal(str)
    scoresUpdated = Signal(int)                   # file_index
    runFinished = Signal(object)                  # RunData
    runFailed = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._proc: QProcess | None = None
        self._timer: QTimer | None = None
        self._jobs: list[Job] = []
        self._job_no = 0
        self._cancelled = False
        self._stdout_buf = ""
        self._got_result = False
        self.rundata: RunData | None = None
        self.run_dir: Path | None = None
        self.plan: RunPlan | None = None

    # ------------------------------------------------------------- start
    def start(self, plan: RunPlan, host_info: HostInfo) -> None:
        self.plan = plan
        self._cancelled = False
        self._job_no = 0
        try:
            self.run_dir = unique_run_dir(plan.output_root, datetime.now())
            (self.run_dir / "_cache").mkdir(parents=True)
        except OSError as e:
            self.runFailed.emit(f"Cannot create run directory: {e}")
            return

        # File entries + per-file folders
        taken: set[str] = set()
        files: list[FileEntry] = []
        for sf in plan.files:
            folder = file_folder_name(sf.path, taken)
            taken.add(folder)
            (self.run_dir / folder).mkdir()
            files.append(FileEntry(
                source_path=str(sf.path), file_name=sf.path.name, folder=folder,
                kind=sf.kind, total_pages=sf.total_pages))

        self.rundata = RunData(
            app_version=APP_VERSION,
            run_id=self.run_dir.name,
            status="running",
            started_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            host=host_info,
            settings=RunSettings(
                source_dir=str(plan.source_dir),
                engines_selected=list(plan.engines),
                output_format=plan.output_format,
                charts=plan.charts,
                regions_only=plan.regions_only,
                regions_only_action=plan.regions_only_action,
                page_mode=plan.page_mode,
                max_pages=plan.max_pages,
                pages_spec=plan.pages_spec,
                scoring_enabled=plan.scoring_enabled,
                dpi=plan.dpi,
                timeout_s=plan.timeout_s,
                device_pref=plan.device_pref,
            ),
            engine_interpreters={e: self._settings.python_for_engine(e)
                                 for e in plan.engines
                                 if self._settings.python_for_engine(e) != sys.executable},
            files=files,
        )

        # Job queue: file-major so a file's raster cache is reused across engines.
        self._jobs = []
        for fi, (sf, fe) in enumerate(zip(plan.files, files)):
            for eid in plan.engines:
                spec = get_spec(eid)
                fmt_used, _ = spec.effective_format(plan.output_format)
                pre = None
                if sf.kind not in spec.inputs:
                    pre = "skipped_input"
                elif (plan.regions_only and not spec.supports_regions_only
                      and plan.regions_only_action == "skip"):
                    pre = "skipped_regions"
                self._jobs.append(Job(
                    job_id=uuid.uuid4().hex[:8], engine=eid, file_index=fi,
                    output_name=output_file_name(eid, fe.folder, fmt_used),
                    images_dir=self.run_dir / "_cache" / fe.folder,
                    pre_status=pre))

        write_rundata(self.rundata, self.run_dir)
        self.logLine.emit(f"Run {self.rundata.run_id}: {len(plan.files)} file(s) × "
                          f"{len(plan.engines)} engine(s) = {len(self._jobs)} job(s)")
        self._copy_sources_then_start()

    def _copy_sources_then_start(self) -> None:
        rd, run_dir = self.rundata, self.run_dir

        class _Copier(QRunnable):
            def __init__(self, done_cb):
                super().__init__()
                self.done_cb = done_cb

            def run(self):
                err = ""
                try:
                    for fe in rd.files:
                        shutil.copy2(fe.source_path, run_dir / fe.folder / fe.file_name)
                except OSError as e:
                    err = str(e)
                self.done_cb(err)

        # Signal bridge: QRunnable runs off-thread; re-enter the GUI thread.
        bridge = _CopyBridge(self)
        bridge.done.connect(self._on_copies_done)
        QThreadPool.globalInstance().start(_Copier(bridge.done.emit))

    def _on_copies_done(self, err: str) -> None:
        if err:
            self.runFailed.emit(f"Copying source files failed: {err}")
            return
        self.logLine.emit("Source files copied into run folder.")
        self._start_next_job()

    # ------------------------------------------------------------- queue
    def _current_job(self) -> Job | None:
        return self._jobs[self._job_no] if self._job_no < len(self._jobs) else None

    def _start_next_job(self) -> None:
        self.runProgress.emit(self._job_no, len(self._jobs))
        job = self._current_job()
        if job is None or self._cancelled:
            self._finalize()
            return

        fe = self.rundata.files[job.file_index]
        spec = get_spec(job.engine)
        fmt_used, fb = spec.effective_format(self.plan.output_format)

        if job.pre_status:
            res = JobResult(engine=job.engine, status=job.pre_status,
                            format_requested=self.plan.output_format,
                            format_used=fmt_used, format_fallback=fb)
            self._record_result(job, res)
            return

        args = ["-m", "app.worker",
                "--engine", job.engine,
                "--input", fe.source_path,
                "--kind", fe.kind,
                "--format", self.plan.output_format,
                "--dpi", str(self.plan.dpi),
                "--device", self.plan.device_pref,
                "--images-dir", str(job.images_dir),
                "--output", str(self.run_dir / fe.folder / job.output_name),
                "--job-id", job.job_id]
        if self.plan.page_mode == "explicit" and self.plan.pages_spec:
            args += ["--pages", self.plan.pages_spec]
        else:
            args += ["--max-pages", str(self.plan.max_pages)]
        if self.plan.charts:
            args.append("--charts")
        if self.plan.regions_only and spec.supports_regions_only:
            args.append("--regions-only")

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(PROJECT_ROOT))
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")

        self._stdout_buf = ""
        self._got_result = False
        self._proc = QProcess(self)
        self._proc.setProcessEnvironment(env)
        self._proc.setProgram(self._settings.python_for_engine(job.engine))
        self._proc.setArguments(args)
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_proc_error)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.plan.timeout_s * 1000)
        self._timer.timeout.connect(self._on_timeout)

        self.jobStarted.emit(job.engine, fe.file_name)
        self.logLine.emit(f"▶ {job.engine} on {fe.file_name}")
        self._proc.start()
        self._timer.start()

    # ------------------------------------------------------------- events
    def _on_stdout(self) -> None:
        # A killed/finished process's queued signals may arrive after the next
        # job started; only the current process may drive state.
        if self._proc is None or (self.sender() is not None
                                  and self.sender() is not self._proc):
            return
        self._drain_stdout()

    def _drain_stdout(self) -> None:
        if self._proc is None:
            return
        self._stdout_buf += bytes(self._proc.readAllStandardOutput()).decode(
            "utf-8", errors="replace")
        while "\n" in self._stdout_buf:
            line, self._stdout_buf = self._stdout_buf.split("\n", 1)
            event = parse_event_line(line.rstrip("\r"))
            if event:
                self._handle_event(event)

    def _handle_event(self, ev: dict) -> None:
        job = self._current_job()
        if job is None or ev.get("job_id") != job.job_id:
            return
        fe = self.rundata.files[job.file_index]
        kind = ev.get("event")
        if kind == "raster":
            self.rasterProgress.emit(job.engine, fe.file_name,
                                     ev.get("page", 0), ev.get("total", 0))
        elif kind == "page":
            self.pageProgress.emit(job.engine, fe.file_name,
                                   ev.get("page", 0), ev.get("total", 0))
        elif kind == "device":
            self.logLine.emit(f"  {job.engine}: device={ev.get('device')} "
                              f"{ev.get('detail', '')}")
        elif kind == "warning":
            self.jobWarning.emit(job.engine, fe.file_name,
                                 f"{ev.get('code')}: {ev.get('msg', '')}")
        elif kind == "result":
            self._got_result = True
            if ev.get("engine_version"):
                self.rundata.engine_versions[job.engine] = ev["engine_version"]
            self._record_result(job, self._result_from_event(job, ev),
                                advance=False)

    def _result_from_event(self, job: Job, ev: dict) -> JobResult:
        pages = ev.get("pages_processed", []) or []
        wall = ev.get("wall_time_s")
        return JobResult(
            engine=job.engine,
            status=ev.get("status", "error"),
            output_file=job.output_name if ev.get("status") == "ok" else "",
            format_requested=self.plan.output_format,
            format_used=ev.get("format_used", ""),
            format_fallback=bool(ev.get("format_fallback")),
            wall_time_s=wall,
            raster_time_s=ev.get("raster_time_s"),
            sec_per_page=round(wall / len(pages), 3) if wall and pages else None,
            pages_processed=pages,
            device=ev.get("device", ""),
            device_detail=ev.get("device_detail", ""),
            warnings=ev.get("warnings", []) or [],
            error=ev.get("error"),
            chars=ev.get("chars", 0),
        )

    def _on_proc_error(self, _err) -> None:
        # FailedToStart and friends; finished() does not fire for FailedToStart.
        if self._proc and self._proc.error() == QProcess.ProcessError.FailedToStart:
            self._fail_current_job("worker process failed to start "
                                   f"({self._proc.program()})")

    def _on_timeout(self) -> None:
        job = self._current_job()
        if job and self._proc:
            self.logLine.emit(f"⏱ {job.engine} timed out after {self.plan.timeout_s}s — killing")
            self._proc.kill()
            self._fail_current_job(f"timeout: exceeded {self.plan.timeout_s}s",
                                   status="timeout")

    def _on_finished(self, exit_code: int, _status) -> None:
        if self.sender() is not None and self.sender() is not self._proc:
            return  # stale signal from a killed/replaced process
        if self._timer:
            self._timer.stop()
        job = self._current_job()
        if job is None:
            return
        self._drain_stdout()  # remaining buffered events
        if not self._got_result:
            stderr = ""
            if self._proc:
                stderr = bytes(self._proc.readAllStandardError()).decode(
                    "utf-8", errors="replace")
            self._fail_current_job(
                f"worker died without a result (exit {exit_code}); "
                f"stderr tail: {stderr[-400:].strip()}")
            return
        self._advance()

    def _fail_current_job(self, message: str, status: str = "error") -> None:
        job = self._current_job()
        if job is None:
            return
        already = self.rundata.files[job.file_index].results
        if any(r.engine == job.engine for r in already):
            self._advance()
            return
        spec = get_spec(job.engine)
        fmt_used, fb = spec.effective_format(self.plan.output_format)
        res = JobResult(engine=job.engine, status=status,
                        format_requested=self.plan.output_format,
                        format_used=fmt_used, format_fallback=fb, error=message)
        self._record_result(job, res)

    def _record_result(self, job: Job, res: JobResult, advance: bool = True) -> None:
        fe = self.rundata.files[job.file_index]
        fe.results.append(res)
        write_rundata(self.rundata, self.run_dir)
        marker = {"ok": "✓", "error": "✗", "timeout": "⏱"}.get(res.status, "•")
        self.logLine.emit(
            f"{marker} {res.engine} on {fe.file_name}: {res.status}"
            + (f" ({res.wall_time_s}s)" if res.wall_time_s else "")
            + (f" — {res.error}" if res.error else ""))
        self.jobFinished.emit(job.file_index, res)
        self._maybe_score_file(job.file_index)
        if advance:
            self._advance()

    def _advance(self) -> None:
        # Cleanly detach from the finished process before moving on.
        if self._proc is not None:
            self._proc.readyReadStandardOutput.disconnect(self._on_stdout)
            self._proc.finished.disconnect(self._on_finished)
            self._proc.errorOccurred.disconnect(self._on_proc_error)
            self._proc.deleteLater()
            self._proc = None
        self._job_no += 1
        self._start_next_job()

    # ------------------------------------------------------------- cancel/finish
    def cancel(self) -> None:
        self._cancelled = True
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
        self.logLine.emit("Run cancelled by user.")

    def _finalize(self) -> None:
        rd = self.rundata
        rd.status = "cancelled" if self._cancelled else "complete"
        rd.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
        # Engine versions: take from any ok result events recorded via worker.
        write_rundata(rd, self.run_dir)
        write_manifests(rd, self.run_dir)
        if not self._settings.keep_cache:
            shutil.rmtree(self.run_dir / "_cache", ignore_errors=True)
        self.runProgress.emit(len(self._jobs), len(self._jobs))
        self.runFinished.emit(rd)

    # ------------------------------------------------------------- scoring
    def _maybe_score_file(self, file_index: int) -> None:
        if not self.plan.scoring_enabled:
            return
        fe = self.rundata.files[file_index]
        if fe.kind != "pdf":
            return
        expected = {j.engine for j in self._jobs if j.file_index == file_index}
        done = {r.engine for r in fe.results}
        if expected != done:
            return
        bridge = _ScoreBridge(self)
        bridge.done.connect(lambda fi=file_index: self._on_scored(fi))
        task = _ScoringTask(self.rundata, self.run_dir, file_index, bridge.done.emit)
        QThreadPool.globalInstance().start(task)

    def _on_scored(self, file_index: int) -> None:
        write_rundata(self.rundata, self.run_dir)
        self.scoresUpdated.emit(file_index)


class _CopyBridge(QObject):
    done = Signal(str)


class _ScoreBridge(QObject):
    done = Signal()


class _ScoringTask(QRunnable):
    """CER/WER for one file's results, off the GUI thread. Reference = pymupdf
    text over the same pages each engine actually processed."""

    def __init__(self, rundata: RunData, run_dir: Path, file_index: int, done_cb):
        super().__init__()
        self.rundata, self.run_dir, self.file_index = rundata, run_dir, file_index
        self.done_cb = done_cb

    def run(self):
        try:
            self._score()
        except Exception:
            pass
        self.done_cb()

    def _score(self):
        import fitz

        from app.core.scoring import _normalize, score, strip_markdown

        fe = self.rundata.files[self.file_index]
        ref_cache: dict[tuple, str] = {}
        with fitz.open(fe.source_path) as doc:
            def ref_for(pages_1b: list[int]) -> str:
                key = tuple(pages_1b)
                if key not in ref_cache:
                    ref_cache[key] = "\n\n".join(
                        doc[p - 1].get_text() for p in pages_1b
                        if 0 < p <= doc.page_count)
                return ref_cache[key]

            for res in fe.results:
                if res.status != "ok" or not res.output_file:
                    continue
                reference = ref_for(res.pages_processed)
                if len(_normalize(reference)) < 50:
                    fe.has_text_layer = False
                    res.score_note = "no usable text layer (scanned?)"
                    continue
                fe.has_text_layer = True
                out_path = self.run_dir / fe.folder / res.output_file
                try:
                    hyp = out_path.read_text(encoding="utf-8")
                except OSError:
                    res.score_note = "output file unreadable"
                    continue
                if res.output_file.endswith(".md"):
                    hyp = strip_markdown(hyp)
                elif res.output_file.endswith(".json"):
                    hyp = self._flatten_json(res.engine, hyp)
                    if hyp is None:
                        res.score_note = "json output not scored"
                        continue
                s = score(reference, hyp)
                res.cer, res.wer = s["cer"], s["wer"]

    @staticmethod
    def _flatten_json(engine_id: str, text: str) -> str | None:
        # Adapter modules only import engine libs inside run(); importing the
        # module here is safe and cheap.
        try:
            from app.engines.adapters import load_adapter

            fn = getattr(load_adapter(engine_id), "flatten_json", None)
            return fn(text) if callable(fn) else None
        except Exception:
            return None
