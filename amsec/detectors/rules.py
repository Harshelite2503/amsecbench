"""Rule-based detector: compares a suspect G-code against the trusted reference for the same part.
This is the 'design-to-G-code verification' baseline from the literature."""
from __future__ import annotations

import numpy as np

from amsec.features import featurize


def detect(reference: str, suspect: str) -> tuple[bool, list[str]]:
    a, b = featurize(reference), featurize(suspect)
    reasons = []
    if abs(b["n_layers"] - a["n_layers"]) > 1 or abs(b["layer_dz_med"] - a["layer_dz_med"]) > 0.02:
        reasons.append("layer_count_or_height")
    if b["temp_min"] < a["temp_first"] - 5 or b["n_temp_cmds"] != a["n_temp_cmds"]:
        reasons.append("temperature")
    if abs(b["bbox_x"] / a["bbox_x"] - 1) > 0.01 or abs(b["bbox_y"] / a["bbox_y"] - 1) > 0.01:
        reasons.append("dimensions")
    if b["e_per_mm_min_ratio"] < 0.9 * a["e_per_mm_min_ratio"] or b["e_per_mm_cv"] > a["e_per_mm_cv"] + 0.05:
        reasons.append("extrusion_rate")
    if b["fill_ratio_min_ratio"] < 0.85 * a["fill_ratio_min_ratio"]:
        reasons.append("infill")
    if b["jitter_score"] > a["jitter_score"] + 0.2:
        reasons.append("toolpath_noise")
    if b["frac_travel_in_fill"] > a["frac_travel_in_fill"] + 0.02:
        reasons.append("missing_extrusion")
    return bool(reasons), reasons

def score(reference: str, suspect: str) -> float:
    a, b = featurize(reference), featurize(suspect)
    keys = [k for k in a if isinstance(a[k], (int, float))]
    va = np.array([a[k] for k in keys], float); vb = np.array([b[k] for k in keys], float)
    return float(np.linalg.norm((vb - va) / (np.abs(va) + 1e-6)))
