"""GPU detection.

Two flavors:
- In-worker probes (import torch/paddle directly — workers are isolated
  subprocesses, so heavy imports are fine there).
- Out-of-process probe for the GUI/orchestrator, which must never import an
  engine framework itself.
"""
from __future__ import annotations

import json
import subprocess
import sys

_PROBE_SNIPPET = r"""
import json
out = {"torch": False, "paddle": False, "gpu_name": "", "torch_err": "", "paddle_err": ""}
try:
    import torch
    if torch.cuda.is_available():
        out["torch"] = True
        out["gpu_name"] = torch.cuda.get_device_name(0)
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        out["torch"] = True
        out["gpu_name"] = "Apple GPU (MPS)"
except Exception as e:
    out["torch_err"] = str(e)
try:
    import paddle
    out["paddle"] = bool(paddle.device.is_compiled_with_cuda())
except Exception as e:
    out["paddle_err"] = str(e)
print(json.dumps(out))
"""


def probe_gpu(python_exe: str | None = None, timeout: int = 120) -> dict:
    """Run the GPU probe in a subprocess. Returns
    {"torch": bool, "paddle": bool, "gpu_name": str, ...}; all-False on failure."""
    exe = python_exe or sys.executable
    try:
        proc = subprocess.run([exe, "-c", _PROBE_SNIPPET],
                              capture_output=True, text=True, timeout=timeout)
        for line in reversed(proc.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
    except Exception:
        pass
    return {"torch": False, "paddle": False, "gpu_name": "",
            "torch_err": "probe failed", "paddle_err": "probe failed"}


def preload_for_paddle() -> None:
    """Windows DLL-order dance for the paddle family.

    torch must load BEFORE paddle: paddleocr imports torch later anyway (via
    modelscope), and whichever framework loads its runtime DLLs first owns
    their names process-wide. In the paddle env torch is CPU-only, so loading
    it first costs paddle nothing — the reverse order kills torch's shm.dll.
    (A CUDA torch in the same process WOULD break paddle's cudnn; that combo
    never happens because the app routes paddle engines to the paddle env.)
    """
    try:
        import torch  # noqa: F401
    except Exception:
        pass  # torch missing entirely is fine; paddleocr will complain if it cares


def detect_paddle_device(device_pref: str = "auto") -> tuple[str, str]:
    """In-worker paddle device pick: ('gpu'|'cpu', detail). Any GPU-init
    problem downgrades to CPU instead of crashing the job."""
    preload_for_paddle()
    if device_pref == "cpu":
        return "cpu", "forced by settings"
    try:
        import paddle
        if paddle.device.is_compiled_with_cuda():
            return "gpu", paddle.device.cuda.get_device_name(0) if hasattr(
                paddle.device.cuda, "get_device_name") else "cuda"
    except Exception as e:
        import sys
        import traceback

        traceback.print_exc(file=sys.stderr)
        return "cpu", f"paddle GPU init failed: {e}"
    return "cpu", "paddle compiled without CUDA"


def detect_torch_device(device_pref: str = "auto") -> tuple[bool, str]:
    """In-worker torch device pick: (use_gpu, detail)."""
    if device_pref == "cpu":
        return False, "forced by settings"
    try:
        import torch
        if torch.cuda.is_available():
            return True, torch.cuda.get_device_name(0)
        if (getattr(torch.backends, "mps", None)
                and torch.backends.mps.is_available()):
            return True, "Apple GPU (MPS)"
    except Exception as e:
        return False, f"torch GPU init failed: {e}"
    return False, "torch GPU not available"
