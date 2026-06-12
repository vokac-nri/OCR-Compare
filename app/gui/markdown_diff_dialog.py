"""Rendered markdown diff: side-by-side view (default) plus a track-changes
merged view, built on app.core.mddiff block diffing. Unchanged blocks render
as markdown; similar changed blocks show word-level highlights; dissimilar
blocks render whole as removed/added (word-interleaving two unrelated
paragraphs is unreadable). Colors adapt to light/dark palettes and always
pair a background with an explicit text color."""
from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import (QColor, QPalette, QTextBlockFormat, QTextCharFormat,
                           QTextCursor, QTextDocument)
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QSplitter, QStackedWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

from app.core.mddiff import (Block, diff_blocks, similarity, split_blocks,
                             word_diff)

# Replaced blocks at least this word-similar show as one word-level diff;
# anything less similar reads better as separate removed/added blocks.
PAIR_THRESHOLD = 0.4


@dataclass(frozen=True)
class _Colors:
    del_bg: QColor
    ins_bg: QColor
    del_word: QColor   # word-level highlight, stronger than the block tint
    ins_word: QColor
    del_fg: QColor
    ins_fg: QColor


_LIGHT = _Colors(QColor("#ffebe9"), QColor("#dafbe1"), QColor("#ffc0c0"),
                 QColor("#abf2bc"), QColor("#82071e"), QColor("#116329"))
_DARK = _Colors(QColor("#3a1d1f"), QColor("#1b3022"), QColor("#6e2a2e"),
                QColor("#1f5c2e"), QColor("#ffa198"), QColor("#7ee787"))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"<could not read file: {e}>"


def _start_block(cur: QTextCursor):
    """New block with formats reset so md/highlight styling doesn't bleed."""
    if not cur.document().isEmpty():
        cur.insertBlock(QTextBlockFormat(), QTextCharFormat())


def _append_md(cur: QTextCursor, md: str, bg: QColor | None = None,
               fg: QColor | None = None):
    _start_block(cur)
    start = cur.position()
    cur.insertMarkdown(md)
    if bg is None and fg is None:
        return
    sel = QTextCursor(cur.document())
    sel.setPosition(start)
    sel.setPosition(cur.position(), QTextCursor.MoveMode.KeepAnchor)
    if bg is not None:
        bf = QTextBlockFormat()
        bf.setBackground(bg)
        sel.mergeBlockFormat(bf)
    if fg is not None:
        cf = QTextCharFormat()
        cf.setForeground(fg)
        sel.mergeCharFormat(cf)


def _append_words(cur: QTextCursor, pieces: list[tuple[str, str]], c: _Colors):
    _start_block(cur)
    plain = QTextCharFormat()
    for k, (op, txt) in enumerate(pieces):
        fmt = QTextCharFormat()
        if op == "delete":
            fmt.setBackground(c.del_word)
            fmt.setForeground(c.del_fg)
            fmt.setFontStrikeOut(True)
        elif op == "insert":
            fmt.setBackground(c.ins_word)
            fmt.setForeground(c.ins_fg)
        if k:
            cur.insertText(" ", plain)
        cur.insertText(txt, fmt)


class MarkdownDiffDialog(QDialog):
    def __init__(self, left: Path, right: Path, parent=None):
        super().__init__(parent)
        self.left, self.right = Path(left), Path(right)
        self.setWindowTitle(f"Rendered diff — {self.left.name} vs {self.right.name}")
        self.resize(1100, 720)
        self._syncing = False
        dark = self.palette().color(QPalette.ColorRole.Base).lightness() < 128
        self._c = c = _DARK if dark else _LIGHT
        lay = QVBoxLayout(self)

        lb = split_blocks(_read(self.left))
        rb = split_blocks(_read(self.right))
        ops = diff_blocks(lb, rb)
        changed = sum(max(i2 - i1, j2 - j1)
                      for tag, i1, i2, j1, j2 in ops if tag != "equal")
        summary = (f"{changed} changed block(s)" if changed
                   else "no rendered differences (markup-only noise ignored)")
        header = QLabel(
            f'<span style="background-color:{c.del_bg.name()}; '
            f'color:{c.del_fg.name()};">&nbsp;removed: '
            f'{html.escape(self.left.name)}&nbsp;</span>&nbsp;&nbsp;'
            f'<span style="background-color:{c.ins_bg.name()}; '
            f'color:{c.ins_fg.name()};">&nbsp;added: '
            f'{html.escape(self.right.name)}&nbsp;</span>&nbsp;&nbsp;— {summary}')
        lay.addWidget(header)

        self.stack = QStackedWidget()
        self.merged = QTextBrowser()
        self.merged.setOpenExternalLinks(True)
        self.merged.setDocument(self._build_merged(lb, rb, ops))
        self.stack.addWidget(self.merged)

        split = QSplitter(Qt.Orientation.Horizontal)
        lwrap, self.lpane = _pane(self.left.name)
        rwrap, self.rpane = _pane(self.right.name)
        self.lpane.setDocument(self._build_side(lb, rb, ops, "left"))
        self.rpane.setDocument(self._build_side(lb, rb, ops, "right"))
        split.addWidget(lwrap)
        split.addWidget(rwrap)
        self.lpane.verticalScrollBar().valueChanged.connect(
            lambda _: self._sync(self.lpane, self.rpane))
        self.rpane.verticalScrollBar().valueChanged.connect(
            lambda _: self._sync(self.rpane, self.lpane))
        self.stack.addWidget(split)
        self.stack.setCurrentWidget(split)
        lay.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        paths_label = QLabel(f"{self.left}  ⟷  {self.right}")
        paths_label.setStyleSheet("color:#888; font-size:11px;")
        footer.addWidget(paths_label, 1)
        self.toggle_btn = QPushButton("Show merged")
        self.toggle_btn.clicked.connect(self._toggle)
        footer.addWidget(self.toggle_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        lay.addLayout(footer)

    # --------------------------------------------------------- doc building
    def _build_merged(self, lb: list[Block], rb: list[Block],
                      ops: list[tuple]) -> QTextDocument:
        c = self._c
        doc = QTextDocument(self)
        doc.setDocumentMargin(12)
        cur = QTextCursor(doc)
        for tag, i1, i2, j1, j2 in ops:
            if tag == "equal":
                for b in rb[j1:j2]:
                    _append_md(cur, b.md)
            elif tag == "delete":
                for b in lb[i1:i2]:
                    _append_md(cur, b.md, bg=c.del_bg, fg=c.del_fg)
            elif tag == "insert":
                for b in rb[j1:j2]:
                    _append_md(cur, b.md, bg=c.ins_bg, fg=c.ins_fg)
            else:  # replace: word-diff similar pairs, group the rest as
                   # removed-then-added runs
                pend_del: list[Block] = []
                pend_ins: list[Block] = []

                def flush():
                    for b in pend_del:
                        _append_md(cur, b.md, bg=c.del_bg, fg=c.del_fg)
                    for b in pend_ins:
                        _append_md(cur, b.md, bg=c.ins_bg, fg=c.ins_fg)
                    pend_del.clear()
                    pend_ins.clear()

                for k in range(max(i2 - i1, j2 - j1)):
                    lblk = lb[i1 + k] if i1 + k < i2 else None
                    rblk = rb[j1 + k] if j1 + k < j2 else None
                    if (lblk is not None and rblk is not None
                            and similarity(lblk.norm, rblk.norm) >= PAIR_THRESHOLD):
                        flush()
                        _append_words(cur, word_diff(lblk.norm, rblk.norm), c)
                    else:
                        if lblk is not None:
                            pend_del.append(lblk)
                        if rblk is not None:
                            pend_ins.append(rblk)
                flush()
        return doc

    def _build_side(self, lb: list[Block], rb: list[Block],
                    ops: list[tuple], side: str) -> QTextDocument:
        c = self._c
        doc = QTextDocument(self)
        doc.setDocumentMargin(12)
        cur = QTextCursor(doc)
        bg, fg, drop_op = ((c.del_bg, c.del_fg, "insert") if side == "left"
                           else (c.ins_bg, c.ins_fg, "delete"))
        for tag, i1, i2, j1, j2 in ops:
            if tag == "equal":
                for b in (lb[i1:i2] if side == "left" else rb[j1:j2]):
                    _append_md(cur, b.md)
            elif tag == "delete" and side == "left":
                for b in lb[i1:i2]:
                    _append_md(cur, b.md, bg=bg, fg=fg)
            elif tag == "insert" and side == "right":
                for b in rb[j1:j2]:
                    _append_md(cur, b.md, bg=bg, fg=fg)
            elif tag == "replace":
                n_own = (i2 - i1) if side == "left" else (j2 - j1)
                for k in range(n_own):
                    lblk = lb[i1 + k] if i1 + k < i2 else None
                    rblk = rb[j1 + k] if j1 + k < j2 else None
                    if (lblk is not None and rblk is not None
                            and similarity(lblk.norm, rblk.norm) >= PAIR_THRESHOLD):
                        pieces = [(op, t)
                                  for op, t in word_diff(lblk.norm, rblk.norm)
                                  if op != drop_op]
                        _append_words(cur, pieces, c)
                    else:
                        b = lblk if side == "left" else rblk
                        _append_md(cur, b.md, bg=bg, fg=fg)
        return doc

    # --------------------------------------------------------------- events
    def _toggle(self):
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
            self.toggle_btn.setText("Show merged")
        else:
            self.stack.setCurrentIndex(0)
            self.toggle_btn.setText("Show side by side")

    def _sync(self, src: QTextBrowser, dst: QTextBrowser):
        if self._syncing:
            return
        self._syncing = True
        sbar, dbar = src.verticalScrollBar(), dst.verticalScrollBar()
        if sbar.maximum() > 0:
            dbar.setValue(round(sbar.value() / sbar.maximum() * dbar.maximum()))
        self._syncing = False


def _pane(title: str) -> tuple[QWidget, QTextBrowser]:
    """A labeled side-by-side pane: filename header above the browser."""
    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    label = QLabel(title)
    label.setStyleSheet("font-weight:bold; padding:2px;")
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    v.addWidget(label)
    v.addWidget(browser, 1)
    return wrap, browser
