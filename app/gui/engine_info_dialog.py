"""Per-engine info dialog: how the engine works, differentiators, caveats."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QTextBrowser,
                               QVBoxLayout)


class EngineInfoDialog(QDialog):
    def __init__(self, spec, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {spec.display_name}")
        self.resize(520, 420)
        lay = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        md = f"# {spec.display_name}\n\n{spec.info}\n"
        md += (f"\n**Output formats:** {', '.join(spec.formats)} "
               f"(native: {spec.formats[0]})\n")
        md += f"\n**Inputs:** {', '.join(sorted(spec.inputs))}"
        md += f"  |  **Speed:** {spec.speed_class.replace('_', ' ')}"
        md += f"  |  **GPU:** {'yes' if spec.uses_gpu else 'no'}\n"
        if spec.supports_charts or spec.supports_regions_only:
            feats = [f for f, on in [("chart parsing", spec.supports_charts),
                                     ("regions-only mode", spec.supports_regions_only)] if on]
            md += f"\n**Optional features:** {', '.join(feats)}\n"
        browser.setMarkdown(md)
        lay.addWidget(browser)

        if spec.caveats:
            warn = QLabel(f"⚠ {spec.caveats}")
            warn.setWordWrap(True)
            warn.setStyleSheet("color:#c62828; font-weight:bold;")
            lay.addWidget(warn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)
