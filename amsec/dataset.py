"""Build the labelled benchmark.

For each part: the reference (default parameters), BENIGN variants (legitimate parameter
choices an operator might make - the detector must not flag these), and one file per
attack x seed. Benign variants are what make reference-free detection hard: a detector must
separate 'different but legitimate' from 'sabotaged'."""
from __future__ import annotations

import json
import random

import pandas as pd
import trimesh
from rich.progress import track

from amsec.attacks import ATTACKS
from amsec.config import GCODE_DIR, MODELS_DIR, RENDER_DIR, RESULTS_DIR
from amsec.features import featurize
from amsec.models import generate_all
from amsec.render import render
from amsec.slicer import PrintParams, slice_to_gcode


def build(seeds: int = 3, renders: bool = True) -> pd.DataFrame:
    if not list(MODELS_DIR.glob("*.stl")):
        generate_all()
    p = PrintParams(); rows = []
    benign = [{"infill_density": d} for d in (0.2, 0.4)] + [{"layer_height": h} for h in (0.15, 0.25)] + \
             [{"nozzle_temp": t} for t in (200, 220)] + [{"print_speed": v} for v in (30.0, 60.0)]
    stls = [s for s in sorted(MODELS_DIR.glob("*.stl")) if not s.stem.endswith(("_dummy", "_gated"))]
    for stl in track(stls, description="Slicing + attacking"):
        mesh = trimesh.load(stl, force="mesh"); clean = slice_to_gcode(mesh, p, stl.stem)
        ref_path = GCODE_DIR / f"{stl.stem}_clean.gcode"; ref_path.write_text(clean)
        if renders: render(clean, RENDER_DIR / f"{stl.stem}_clean.png")
        rows.append({"part": stl.stem, "attack": "none", "seed": 0, "path": str(ref_path),
                     "reference_path": str(ref_path), "meta": "{}", **featurize(clean)})
        for k, kw in enumerate(benign):
            q = PrintParams(**{**p.__dict__, **kw}); g = slice_to_gcode(mesh, q, stl.stem)
            bp = GCODE_DIR / f"{stl.stem}_benign{k}.gcode"; bp.write_text(g)
            rows.append({"part": stl.stem, "attack": "none", "seed": k + 1, "path": str(bp),
                         "reference_path": str(ref_path), "meta": json.dumps(kw), **featurize(g)})
        for seed in range(seeds):
            rng = random.Random(1000 * seed + hash(stl.stem) % 1000)
            for name, fn in ATTACKS.items():
                text, meta = fn(clean, mesh, p, rng)
                if text == clean:  # attack had no effect on this geometry (e.g. no infill) -> skip, not label noise
                    continue
                path = GCODE_DIR / f"{stl.stem}_{name}_s{seed}.gcode"; path.write_text(text)
                if renders and seed == 0: render(text, RENDER_DIR / f"{stl.stem}_{name}_s{seed}.png")
                rows.append({"part": stl.stem, "attack": name, "seed": seed, "path": str(path),
                             "reference_path": str(ref_path), "meta": json.dumps(meta), **featurize(text)})
    df = pd.DataFrame(rows); df.to_csv(RESULTS_DIR / "manifest.csv", index=False)
    return df

def load_manifest() -> pd.DataFrame:
    return pd.read_csv(RESULTS_DIR / "manifest.csv")
