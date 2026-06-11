"""Pre-run capability analysis: everything the precheck dialog shows the user
before a run starts. Pure logic — fully unit-testable without Qt.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.plan import RunPlan
from app.engines import get_spec

@dataclass
class PrecheckReport:
    # engines selected but lacking regions-only support (dialog offers skip/run-full)
    regions_unsupported: list[str] = field(default_factory=list)
    # engines that will honor chart parsing (others silently ignore the flag)
    chart_capable: list[str] = field(default_factory=list)
    # (engine, message) slowness warnings
    slow_warnings: list[tuple[str, str]] = field(default_factory=list)
    # (engine, requested, used) for engines falling back to their native format
    format_fallbacks: list[tuple[str, str, str]] = field(default_factory=list)
    # (engine, n_image_files) for pdf-only engines that will skip image inputs
    input_skips: list[tuple[str, int]] = field(default_factory=list)

    def has_content(self) -> bool:
        return bool(self.regions_unsupported or self.chart_capable
                    or self.slow_warnings or self.format_fallbacks
                    or self.input_skips)


def build_precheck_report(plan: RunPlan, gpu_available: dict[str, bool]) -> PrecheckReport:
    """gpu_available: {"torch": bool, "paddle": bool} from device probing."""
    rep = PrecheckReport()
    n_images = sum(1 for f in plan.files if f.kind == "image")

    for eid in plan.engines:
        spec = get_spec(eid)

        if plan.regions_only and not spec.supports_regions_only:
            rep.regions_unsupported.append(eid)

        if plan.charts and spec.supports_charts:
            rep.chart_capable.append(eid)

        used, fb = spec.effective_format(plan.output_format)
        if fb:
            rep.format_fallbacks.append((eid, plan.output_format, used))

        if n_images and "image" not in spec.inputs:
            rep.input_skips.append((eid, n_images))

        if spec.speed_class == "very_slow":
            cap = spec.default_max_pages
            cap_note = (f" (page cap: {cap} per PDF)"
                        if cap and plan.page_mode == "max_pages" else "")
            rep.slow_warnings.append((eid, f"30–190 s/page even on GPU{cap_note}."))
        if spec.uses_gpu:
            framework = "paddle" if eid.startswith(("paddle", "ppstructure")) else "torch"
            if not gpu_available.get(framework, False):
                rep.slow_warnings.append(
                    (eid, f"No GPU acceleration available for {framework} — will run on CPU, "
                          "likely 10–50× slower."))

    return rep
