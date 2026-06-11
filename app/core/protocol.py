"""Worker -> orchestrator progress protocol.

Workers write one JSON object per line to their REAL stdout, prefixed with a
sentinel. Engine libraries print freely to the captured stdout; any line that
doesn't start with the sentinel is ignored by the orchestrator, so C-level
prints that bypass Python's redirect can't corrupt the stream.

Event vocabulary (all carry "event" and "job_id"):
  start   {engine, file, total_pages}
  device  {device, detail}
  raster  {page, total}            # PDF page pre-rendering progress
  page    {page, total}            # engine inference progress
  warning {code, msg}              # e.g. code="cpu_fallback"
  result  {status, output_path, format_used, format_fallback, pages_processed,
           wall_time_s, raster_time_s, engine_version, device, device_detail,
           chars, warnings, error, traceback, library_log_tail}
"""
from __future__ import annotations

import json

SENTINEL = "@@OCRGUI@@ "


def emit_event(stream, payload: dict) -> None:
    stream.write(SENTINEL + json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()


def parse_event_line(line: str) -> dict | None:
    """Parse one stdout line; None for non-protocol noise."""
    if not line.startswith(SENTINEL):
        return None
    try:
        obj = json.loads(line[len(SENTINEL):])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) and "event" in obj else None
