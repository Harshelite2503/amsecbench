"""Tiny G-code parser producing a per-layer move table."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Move:
    layer: int; kind: str; x0: float; y0: float; x1: float; y1: float; z: float; e: float; f: float; is_extrude: bool

def parse(text: str) -> pd.DataFrame:
    x = y = z = 0.0; e_prev = 0.0; f = 0.0; layer = -1; kind = "NONE"
    temps = {"M104": None, "M140": None}
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(";LAYER:"):
            layer = int(s.split(":")[1]); continue
        if s.startswith(";TYPE:"):
            kind = s.split(":")[1]; continue
        if not s or s.startswith(";"):
            continue
        parts = s.split()
        cmd = parts[0]
        args = {p[0]: float(p[1:]) for p in parts[1:] if p[0] in "XYZEFS" and len(p) > 1}
        if cmd in ("M104", "M109") and "S" in args:
            temps["M104"] = args["S"]
        if cmd in ("M140", "M190") and "S" in args:
            temps["M140"] = args["S"]
        if cmd == "G92" and "E" in args:
            e_prev = args["E"]; continue
        if cmd in ("G0", "G1"):
            nx, ny, nz = args.get("X", x), args.get("Y", y), args.get("Z", z)
            f = args.get("F", f); ne = args.get("E", e_prev)
            de = ne - e_prev if "E" in args else 0.0
            rows.append(Move(layer, kind, x, y, nx, ny, nz, de, f, de > 0).__dict__)
            x, y, z, e_prev = nx, ny, nz, ne
    df = pd.DataFrame(rows)
    df.attrs["nozzle_temp"] = temps["M104"]; df.attrs["bed_temp"] = temps["M140"]
    return df

def layer_summary(df: pd.DataFrame) -> pd.DataFrame:
    ext = df[df.is_extrude].copy()
    ext["len"] = np.hypot(ext.x1 - ext.x0, ext.y1 - ext.y0)
    g = ext.groupby("layer")
    s = pd.DataFrame({
        "z": g.z.first(), "n_moves": g.size(), "path_len": g.len.sum(), "e_total": g.e.sum(),
        "fill_len": ext[ext.kind == "FILL"].groupby("layer").len.sum(),
        "perim_len": ext[ext.kind == "PERIMETER"].groupby("layer").len.sum(),
        "xmin": g.x1.min(), "xmax": g.x1.max(), "ymin": g.y1.min(), "ymax": g.y1.max(),
    }).fillna(0.0)
    s["e_per_mm"] = s.e_total / s.path_len.replace(0, np.nan)
    s["fill_ratio"] = s.fill_len / (s.fill_len + s.perim_len).replace(0, np.nan)
    return s.fillna(0.0)
