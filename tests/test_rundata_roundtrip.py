import json

from app.core.rundata import (FileEntry, HostInfo, JobResult, RunData,
                              RunSettings, load_rundata, write_manifests,
                              write_rundata)


def make_rundata() -> RunData:
    return RunData(
        app_version="0.1.0",
        run_id="10JUN20261413",
        status="complete",
        started_at="2026-06-10T14:13:02-05:00",
        finished_at="2026-06-10T14:41:55-05:00",
        host=HostInfo(os="Windows-11", python="3.11.9", gpu_name="RTX 2000 Ada",
                      gpu_driver="596.59", torch_cuda=True, paddle_cuda=True),
        settings=RunSettings(source_dir="C:\\docs", engines_selected=["pymupdf"],
                             output_format="md", scoring_enabled=True),
        engine_versions={"pymupdf": "1.26.1"},
        files=[FileEntry(
            source_path="C:\\docs\\a.pdf", file_name="a.pdf", folder="a_pdf",
            kind="pdf", total_pages=12, has_text_layer=True,
            results=[JobResult(engine="pymupdf", status="ok",
                               output_file="pymupdf_a_pdf.md",
                               format_requested="md", format_used="md",
                               wall_time_s=0.4, pages_processed=[1, 2],
                               device="cpu", chars=1234, cer=0.01, wer=0.02)],
        )],
    )


def test_round_trip_identity():
    rd = make_rundata()
    assert RunData.from_json(rd.to_json()) == rd


def test_unknown_keys_tolerated():
    rd = make_rundata()
    d = json.loads(rd.to_json())
    d["future_field"] = {"x": 1}
    d["files"][0]["future_flag"] = True
    d["files"][0]["results"][0]["future_metric"] = 0.5
    loaded = RunData.from_json(json.dumps(d))
    assert loaded == rd


def test_missing_keys_get_defaults():
    loaded = RunData.from_json('{"run_id": "X", "files": [{"file_name": "a.pdf"}]}')
    assert loaded.run_id == "X"
    assert loaded.status == "running"
    assert loaded.files[0].results == []


def test_write_is_atomic_and_loadable(tmp_path):
    rd = make_rundata()
    write_rundata(rd, tmp_path)
    assert not (tmp_path / "rundata.json.tmp").exists()
    assert load_rundata(tmp_path / "rundata.json") == rd


def test_manifests(tmp_path):
    rd = make_rundata()
    (tmp_path / "a_pdf").mkdir()
    write_manifests(rd, tmp_path)
    m = json.loads((tmp_path / "a_pdf" / "manifest.json").read_text(encoding="utf-8"))
    assert m["run_id"] == rd.run_id
    assert m["file"]["file_name"] == "a.pdf"
    assert m["engine_versions"] == {"pymupdf": "1.26.1"}
    assert m["settings"]["output_format"] == "md"
