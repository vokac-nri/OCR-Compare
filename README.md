# OCR Compare

Desktop GUI tool for comparing text-extraction / OCR / vision-language engines,
built to answer one question: **which engine should go in your RAG ETL pipeline?**

Select engines, point at a folder of PDFs/images, run, and compare the outputs
side by side (timing, optional CER/WER accuracy, external diff tools).

## Engines (12)

| Class | Engines |
|---|---|
| Digital text layer (instant) | PyMuPDF, pypdfium2, pdftotext (Poppler), LiteParse, MarkItDown |
| Classic raster OCR | Tesseract, EasyOCR, PaddleOCR, RapidOCR |
| Layout/structure pipelines | PP-StructureV3, Docling |
| Vision-language model | PaddleOCR-VL |

Click the ⓘ next to any engine in the app for how it works, what makes it
different, and its known caveats.

## Quick start (one click)

Double-click **`OCR-Compare.exe`** (or **`Start-OCR-Compare.cmd`** if your
machine blocks unsigned executables — they do exactly the same thing).

Every launch verifies the installation and fixes only what is missing or at
the wrong version, then starts the app:

- **First run on a fresh machine:** fully automatic, but slow — it downloads
  and silently installs [Miniforge](https://github.com/conda-forge/miniforge)
  if no conda exists, creates both conda environments, and installs several GB
  of packages (30–60 min depending on network/GPU). Tesseract and Poppler
  binaries are included — no separate installers.
- **Subsequent launches:** a cached stamp confirms nothing changed and the app
  starts in a couple of seconds.
- **GPU is auto-detected:** machines with an NVIDIA GPU get CUDA wheels;
  others get CPU-only torch/paddle (everything works, but PaddleOCR-VL is
  impractically slow on CPU).

> **SmartScreen note:** `OCR-Compare.exe` is unsigned, so Windows may warn on
> first run ("More info" → "Run anyway"). Use `Start-OCR-Compare.cmd` where
> the exe is blocked outright.

Launcher options (run `bootstrap.ps1` directly for these):

```powershell
.\bootstrap.ps1 -Recheck       # ignore the cached stamp, re-verify every pin now
.\bootstrap.ps1 -Reinstall     # force a full setup_env.ps1 pass
.\bootstrap.ps1 -Variant cpu   # force CPU wheels regardless of detected GPU
.\bootstrap.ps1 -NoLaunch      # verify/repair only, don't start the GUI
```

How it works: version pins live in `requirements\<env>\*.txt` (one file per
install stage; the `NN-` prefix encodes the torch → paddle → PyPI install
order that keeps CUDA wheels from being downgraded). `bootstrap.ps1` hashes
those manifests into a stamp at `%LOCALAPPDATA%\OCR-Compare\launcher_state.json`;
editing any pin (or deleting the stamp) makes the next launch re-check and
repair via `tools\check_deps.py` + `setup_env.ps1 -Repair`. Launcher and setup
logs land in `%LOCALAPPDATA%\OCR-Compare\logs\`.

## Manual / development setup

Requires Windows + Miniconda or Miniforge (conda-forge; the setup script never
touches the ToS-gated Anaconda channels — conda is located via `CONDA_EXE`,
`%LOCALAPPDATA%`, `%USERPROFILE%`, or PATH).

```powershell
.\setup_env.ps1          # full install of BOTH conda envs
.\setup_env.ps1 -Repair  # reinstall from the pinned manifests only (faster)
.\setup_env.ps1 -Variant cpu   # CPU-only wheels
.\run_app.ps1            # launch the GUI without the dependency check
```

Setup creates **two** environments, because torch-GPU and paddle-GPU cannot
coexist in one process on Windows (each bundles its own cudnn DLLs; whichever
loads first shadows the other, and `import paddleocr` pulls in both — torch
arrives via modelscope):

| env | contents | used by |
|---|---|---|
| `ocr-compare` | GUI + torch CUDA + everything except paddle | 9 engines incl. easyocr/docling |
| `ocr-compare-paddle` | paddle CUDA + **CPU** torch (import-satisfier only) | paddleocr, ppstructurev3, paddleocr-vl |

The app auto-routes the paddle engines to the second env (override per engine
in *Settings → Interpreters* if needed).

GPU notes:
- If paddle's GPU check fails at setup, it falls back to CPU paddle and the
  app shows a CPU-fallback warning before each run.
- **PaddleOCR-VL is 30–190 s/page even on GPU** and defaults to a 3-page cap.
- A `sitecustomize.py` is installed into both envs to work around an OpenSSL
  3.6 regression that breaks Windows certificate-store loading (and with it
  `import paddleocr`); see `tools/sitecustomize_ssl.py`.

## Output layout

Each run creates `Outputs\<DDMONYYYYHHMM>\`:

```
Outputs\10JUN20261413\
├── rundata.json              # everything about the run (timings, versions,
│                             # settings, statuses) — import this to reload
├── _cache\...                # rasterized page images (optional keep)
└── mycooldoc1_pdf\
    ├── mycooldoc1.pdf        # copy of the original
    ├── manifest.json         # this file's results + settings snapshot
    ├── pymupdf_mycooldoc1_pdf.md
    └── paddleocr_mycooldoc1_pdf.md
```

`Import run…` in the toolbar restores any previous run (settings + results)
from its `rundata.json` — run folders stay importable after being moved.

## Notes

- Jobs run **sequentially** (one engine at a time) so wall-clock timings are
  fair. `wall_time_s` includes engine import + model load (cold-start cost is
  part of the comparison); page rasterization is reported separately.
- CER/WER scoring (opt-in) compares against the PDF's own text layer via
  rapidfuzz — only meaningful for born-digital PDFs, and markdown outputs are
  flattened before scoring.
- ⚠ **Chart parsing:** prior testing showed PP-StructureV3's chart→table
  conversion fabricated values. The app warns whenever the flag is enabled;
  treat chart output as unverified.
- This folder lives under OneDrive; the Outputs root can be moved elsewhere in
  *Settings → General* if sync churn becomes annoying. Model downloads go to
  user-profile caches (`~\.paddlex`, `~\.EasyOCR`, HuggingFace cache) and are
  not synced.

## Development

```powershell
conda run -n ocr-compare python -m pytest          # core logic tests
conda run -n ocr-compare python tools\check_env.py # engine/GPU smoke check
# run a single engine worker without the GUI:
conda run -n ocr-compare python -m app.worker --engine pymupdf `
  --input sample.pdf --kind pdf --max-pages 2 --format txt `
  --output out.txt --job-id test
# rebuild OCR-Compare.exe after changing tools\launcher_stub.ps1
# (bootstrap.ps1 changes do NOT need a rebuild - the exe is a thin shim):
.\tools\build_launcher.ps1
```

Layering rules: `app/worker.py` + `app/engines/adapters/` never import Qt;
`app/gui/` never imports an engine framework (narrow exception: pymupdf for
page counts / scoring reference, which has no CUDA/DLL hazards).
