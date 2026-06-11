"""Page-spec parsing and per-engine page index resolution."""
from __future__ import annotations

import re

_SPEC_TOKEN = re.compile(r"^(\d+)(?:-(\d+))?$")


def parse_pages_spec(spec: str) -> list[int]:
    """Parse a 1-based page spec like '2-5,8' into a sorted, deduped list.

    Raises ValueError with a user-presentable message on invalid input.
    """
    pages: set[int] = set()
    if not spec or not spec.strip():
        raise ValueError("Page spec is empty")
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        m = _SPEC_TOKEN.match(token)
        if not m:
            raise ValueError(f"Invalid page token: '{token}' (use e.g. '2-5,8')")
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start < 1:
            raise ValueError(f"Pages are 1-based: '{token}'")
        if end < start:
            raise ValueError(f"Range is backwards: '{token}'")
        pages.update(range(start, end + 1))
    if not pages:
        raise ValueError("Page spec is empty")
    return sorted(pages)


def target_indices(explicit_pages: list[int] | None, max_pages: int,
                   engine_cap: int | None, total: int) -> list[int]:
    """Resolve the 0-based page indices an engine should process.

    explicit_pages (1-based, from parse_pages_spec) wins and applies to every
    engine; out-of-range pages are dropped. Otherwise the first max_pages
    (0 = all), further capped by the engine's own default cap (e.g. the slow
    paddleocr-vl gets 3).
    """
    if explicit_pages:
        return [p - 1 for p in explicit_pages if 0 <= p - 1 < total]
    n = total if max_pages <= 0 else min(max_pages, total)
    if engine_cap and engine_cap > 0:
        n = min(n, engine_cap)
    return list(range(n))
