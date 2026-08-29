"""Hand-crafted features for classical detectors. Per-file vector from the layer summary."""
from __future__ import annotations

import numpy as np

from amsec.gcode import layer_summary, parse

FEATURES = ["n_layers", "layer_dz_med", "layer_dz_std", "e_per_mm_med", "e_per_mm_cv", "e_per_mm_min_ratio",
            "fill_ratio_med", "fill_ratio_std", "fill_ratio_min_ratio", "path_len_cv", "n_temp_cmds",
            "temp_first", "temp_min", "bbox_x", "bbox_y", "jitter_score", "frac_travel_in_fill"]

def featurize(text: str) -> dict:
    df = parse(text); s = layer_summary(df)
    dz = np.diff(s.z.values) if len(s) > 1 else np.array([0.0])
    temps = [float(l.split("S")[1]) for l in text.splitlines() if l.startswith(("M104", "M109"))]
    temps = [t for t in temps if t > 0]  # ignore end-of-print cool-down
    fill = df[(df.kind == "FILL") & df.is_extrude]
    # jitter: deviation of consecutive infill segment headings from the dominant 45/135 angles
    ang = np.degrees(np.arctan2(fill.y1 - fill.y0, fill.x1 - fill.x0)) % 180
    jitter = float(np.mean(np.minimum(np.abs(ang - 45), np.abs(ang - 135)))) if len(ang) else 0.0
    travel_in_fill = df[(df.kind == "FILL") & ~df.is_extrude]
    epm = s.e_per_mm.replace(0, np.nan).dropna()
    fr = s.fill_ratio.replace(0, np.nan).dropna()
    return {
        "n_layers": len(s), "layer_dz_med": float(np.median(dz)), "layer_dz_std": float(np.std(dz)),
        "e_per_mm_med": float(epm.median()) if len(epm) else 0.0,
        "e_per_mm_cv": float(epm.std() / epm.median()) if len(epm) > 1 else 0.0,
        "e_per_mm_min_ratio": float(epm.min() / epm.median()) if len(epm) else 0.0,
        "fill_ratio_med": float(fr.median()) if len(fr) else 0.0, "fill_ratio_std": float(fr.std()) if len(fr) > 1 else 0.0,
        "fill_ratio_min_ratio": float(fr.min() / fr.median()) if len(fr) else 0.0,
        "path_len_cv": float(s.path_len.std() / s.path_len.mean()) if len(s) > 1 else 0.0,
        "n_temp_cmds": len(temps), "temp_first": temps[0] if temps else 0.0, "temp_min": min(temps) if temps else 0.0,
        "bbox_x": float(s.xmax.max() - s.xmin.min()), "bbox_y": float(s.ymax.max() - s.ymin.min()),
        "jitter_score": jitter, "frac_travel_in_fill": float(len(travel_in_fill) / max(1, len(fill))),
    }
