"""Block-level markdown diffing for the rendered diff view.

Splits markdown into rendered blocks (paragraph, heading, list item, fenced
code, table, quote) and compares them on *normalized* visible text: inline
markup (emphasis, code spans, link targets, HTML tags, escapes) and soft
line wraps are stripped, so two outputs that render the same prose with
different markup noise compare equal. ATX headings and CommonMark setext
underlines are recognized; raw-HTML-heavy output degrades to paragraph
blocks. Pure Python (no Qt) so it is unit-testable headless — rendering
lives in app/gui/markdown_diff_dialog.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST_RE = re.compile(r"^(\s*)(?:[-*+]|\d{1,9}[.)])\s+\S")
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s+")
_HR_RE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
_SETEXT_RE = re.compile(r"^\s{0,3}(={3,}|-{3,})\s*$")
_TABLE_RE = re.compile(r"^\s*\|")
_TABLE_SEP_RE = re.compile(r"^[\s|:\-]+$")
_QUOTE_RE = re.compile(r"^\s{0,3}>")


@dataclass(frozen=True)
class Block:
    md: str    # original fragment, renderable on its own
    kind: str  # para | list | h1..h6 | code | table | quote | hr
    norm: str  # normalized visible text

    @property
    def key(self) -> str:
        """Comparison key: blocks with equal keys render the same."""
        return f"{self.kind}|{self.norm}"


def normalize_inline(text: str) -> str:
    """Visible text of an inline-markdown string: images/links keep their
    text, emphasis/code-span/HTML/escape markup is dropped, whitespace
    collapses. Mid-word underscores (snake_case) survive."""
    # Protect backslash-escaped punctuation so the markup stripping below
    # can't eat it; restored (unescaped) at the end.
    t = re.sub(r"\\([!-/:-@\[-`{-~])",
               lambda m: f"\x00{ord(m.group(1))};", text)
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"</?[A-Za-z][^>\n]*>", "", t)
    t = t.replace("`", "")
    t = re.sub(r"(\*\*|~~|\*)", "", t)
    t = re.sub(r"(?<!\w)_+|_+(?!\w)", "", t)
    t = re.sub(r"\x00(\d+);", lambda m: chr(int(m.group(1))), t)
    return re.sub(r"\s+", " ", t).strip()


def split_blocks(md: str) -> list[Block]:
    lines = md.splitlines()
    blocks: list[Block] = []
    para: list[str] = []

    def flush_para():
        if para:
            text = " ".join(s.strip() for s in para)
            blocks.append(Block("\n".join(para), "para", normalize_inline(text)))
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush_para()
            i += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            flush_para()
            marker = fence.group(1)[:3]
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(marker):
                j += 1
            end = min(j + 1, len(lines))
            code = "\n".join(s.rstrip() for s in lines[i + 1:j])
            blocks.append(Block("\n".join(lines[i:end]), "code", code))
            i = end
            continue

        if _TABLE_RE.match(line):
            flush_para()
            j = i
            while j < len(lines) and _TABLE_RE.match(lines[j]):
                j += 1
            rows = lines[i:j]
            norm_rows = []
            for row in rows:
                if _TABLE_SEP_RE.match(row):
                    continue
                cells = [normalize_inline(c) for c in row.strip().strip("|").split("|")]
                norm_rows.append(" | ".join(cells))
            blocks.append(Block("\n".join(rows), "table", " ¦ ".join(norm_rows)))
            i = j
            continue

        head = _HEADING_RE.match(line)
        if head:
            flush_para()
            blocks.append(Block(line, f"h{len(head.group(1))}",
                                normalize_inline(head.group(2))))
            i += 1
            continue

        # Setext underline closes the open paragraph as a heading; without
        # one, --- / *** / ___ is a horizontal rule (CommonMark order).
        setext = _SETEXT_RE.match(line)
        if setext and para:
            text = " ".join(s.strip() for s in para)
            kind = "h1" if setext.group(1).startswith("=") else "h2"
            blocks.append(Block("\n".join(para) + "\n" + line, kind,
                                normalize_inline(text)))
            para.clear()
            i += 1
            continue
        if _HR_RE.match(line):
            flush_para()
            blocks.append(Block(line.strip(), "hr", ""))
            i += 1
            continue

        if _QUOTE_RE.match(line):
            flush_para()
            j = i
            while j < len(lines) and _QUOTE_RE.match(lines[j]):
                j += 1
            quoted = lines[i:j]
            text = " ".join(re.sub(r"^\s*>+\s?", "", s) for s in quoted)
            blocks.append(Block("\n".join(quoted), "quote", normalize_inline(text)))
            i = j
            continue

        if _LIST_RE.match(line):
            flush_para()
            item = [line]
            j = i + 1
            # Indented follow-on lines are continuations of this item.
            while (j < len(lines) and lines[j].strip()
                   and lines[j][:1] in (" ", "\t")
                   and not _LIST_RE.match(lines[j])):
                item.append(lines[j])
                j += 1
            text = " ".join([_LIST_MARKER_RE.sub("", line)]
                            + [s.strip() for s in item[1:]])
            blocks.append(Block("\n".join(item), "list", normalize_inline(text)))
            i = j
            continue

        para.append(line)
        i += 1

    flush_para()
    return blocks


def diff_blocks(left: list[Block], right: list[Block]) -> list[tuple]:
    """difflib opcodes over the blocks' comparison keys."""
    sm = SequenceMatcher(a=[b.key for b in left], b=[b.key for b in right],
                         autojunk=False)
    return sm.get_opcodes()


def similarity(a: str, b: str) -> float:
    """Word-level similarity ratio (0..1) between two normalized texts."""
    return SequenceMatcher(a=a.split(), b=b.split(), autojunk=False).ratio()


def word_diff(old: str, new: str) -> list[tuple[str, str]]:
    """Word-level track-changes pieces as (op, text), op equal|delete|insert."""
    a, b = old.split(), new.split()
    out: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b,
                                               autojunk=False).get_opcodes():
        if tag in ("equal", "delete", "replace") and i2 > i1:
            out.append(("equal" if tag == "equal" else "delete",
                        " ".join(a[i1:i2])))
        if tag in ("insert", "replace") and j2 > j1:
            out.append(("insert", " ".join(b[j1:j2])))
    return out
