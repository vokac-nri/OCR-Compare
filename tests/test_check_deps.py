import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_deps  # noqa: E402


def _touch(d: Path, *names: str) -> None:
    for n in names:
        (d / n).write_text("# stub\n", encoding="utf-8")


def test_manifest_files_picks_matching_variant(tmp_path):
    _touch(tmp_path, "01-torch.gpu.txt", "01-torch.cpu.txt",
           "02-paddle.gpu.txt", "02-paddle.cpu.txt", "03-pypi.txt", "conda.txt")
    names = [p.name for p in check_deps._manifest_files(tmp_path, "gpu", "cpu")]
    assert names == ["01-torch.gpu.txt", "02-paddle.cpu.txt",
                     "03-pypi.txt", "conda.txt"]


def test_manifest_files_includes_suffixless_single_variant(tmp_path):
    # mac-style manifests have no .gpu/.cpu split at all
    _touch(tmp_path, "01-torch.txt", "02-paddle.txt", "03-pypi.txt", "conda.txt")
    names = [p.name for p in check_deps._manifest_files(tmp_path, "cpu", "cpu")]
    assert names == ["01-torch.txt", "02-paddle.txt", "03-pypi.txt", "conda.txt"]


def test_pins_parses_extras_comments_and_index_urls(tmp_path):
    (tmp_path / "03-pypi.txt").write_text(
        "# comment\n"
        "--extra-index-url https://example.invalid/simple\n"
        "\n"
        "markitdown[pdf]==0.1.6\n"
        "torch==2.12.0+cu126\n",
        encoding="utf-8")
    pins = check_deps._pins([tmp_path / "03-pypi.txt"])
    assert pins == {"markitdown": "0.1.6", "torch": "2.12.0+cu126"}


# patch the module-global `os`, not the real os module — flipping the real
# os.name makes pathlib refuse to instantiate Path on the "wrong" platform.
def test_cli_path_windows(monkeypatch):
    monkeypatch.setattr(check_deps, "os", types.SimpleNamespace(name="nt"))
    p = check_deps._cli_path(Path("C:/envs/ocr"), "tesseract")
    assert p == Path("C:/envs/ocr") / "Library" / "bin" / "tesseract.exe"


def test_cli_path_posix(monkeypatch):
    monkeypatch.setattr(check_deps, "os", types.SimpleNamespace(name="posix"))
    p = check_deps._cli_path(Path("/opt/envs/ocr"), "tesseract")
    assert p == Path("/opt/envs/ocr") / "bin" / "tesseract"
