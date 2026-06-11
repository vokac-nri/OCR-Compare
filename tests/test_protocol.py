import io

from app.core.protocol import SENTINEL, emit_event, parse_event_line


def test_round_trip():
    buf = io.StringIO()
    emit_event(buf, {"event": "page", "job_id": "j1", "page": 3, "total": 10})
    line = buf.getvalue().splitlines()[0]
    assert parse_event_line(line) == {"event": "page", "job_id": "j1",
                                      "page": 3, "total": 10}


def test_noise_lines_ignored():
    assert parse_event_line("Loading model weights...") is None
    assert parse_event_line('{"event": "page"}') is None        # no sentinel
    assert parse_event_line(SENTINEL + "not json") is None
    assert parse_event_line(SENTINEL + '["list", "not", "dict"]') is None
    assert parse_event_line(SENTINEL + '{"no_event_key": 1}') is None


def test_unicode_payload():
    buf = io.StringIO()
    emit_event(buf, {"event": "warning", "msg": "naïve — ✓"})
    assert parse_event_line(buf.getvalue().strip())["msg"] == "naïve — ✓"
