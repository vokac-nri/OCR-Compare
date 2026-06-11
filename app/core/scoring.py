"""CER/WER scoring against the PyMuPDF text layer (ported from the proven
WSL harness). Lower = closer to the reference. Markdown outputs are flattened
with strip_markdown before scoring so markup isn't counted as error.
"""
from __future__ import annotations

import re

from rapidfuzz.distance import Levenshtein


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for a fair text comparison."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def strip_markdown(md: str) -> str:
    """Flatten markdown to plain text (for scoring and .txt companion dumps)."""
    t = md or ""
    t = re.sub(r"`{1,3}", "", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)   # headings
    t = re.sub(r"[*_]{1,3}", "", t)                        # emphasis
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)             # blockquote
    t = re.sub(r"\|", " ", t)                              # table pipes
    t = re.sub(r"^\s*[-:]{3,}\s*$", "", t, flags=re.M)     # table rules
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)        # links/images
    t = re.sub(r"<[^>]+>", " ", t)                          # html tags (VL emits some)
    return t


def score(reference: str, hypothesis: str) -> dict:
    """Returns {"cer": float|None, "wer": float|None} (None when no reference)."""
    ref = _normalize(reference)
    hyp = _normalize(hypothesis)
    if not ref:
        return {"cer": None, "wer": None}
    cer = Levenshtein.distance(ref, hyp) / max(1, len(ref))
    ref_w, hyp_w = ref.split(" "), hyp.split(" ")
    wer = Levenshtein.distance(ref_w, hyp_w) / max(1, len(ref_w))
    return {"cer": round(cer, 4), "wer": round(wer, 4)}
