"""Render G-code toolpaths to PNG (top view + a mid-height layer) for VLM detectors."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from amsec.gcode import parse


def render(text: str, out: Path, layer: int | None = None) -> Path:
    df = parse(text); ext = df[df.is_extrude]
    if layer is None:
        layer = int(ext.layer.median())
    fig, axes = plt.subplots(1, 2, figsize=(8, 4))
    for ax, sel, title in ((axes[0], ext, "all layers (top view)"), (axes[1], ext[ext.layer == layer], f"layer {layer}")):
        for kind, col in (("PERIMETER", "black"), ("FILL", "tab:blue")):
            k = sel[sel.kind == kind]
            ax.plot([k.x0, k.x1], [k.y0, k.y1], color=col, lw=0.4 if kind == "FILL" else 0.8, alpha=0.6)
        ax.set_aspect("equal"); ax.set_title(title); ax.axis("off")
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out
