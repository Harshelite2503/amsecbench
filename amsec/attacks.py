"""Sabotage attacks applied to G-code, with ground-truth labels.

Each attack is a pure function gcode_text -> (tampered_text, meta). They follow the
taxonomy in the AM-security literature (Gupta & Karri et al., Proc. IEEE 2020; Rossel et
al., USENIX Security 2025): geometric, process-parameter, and toolpath manipulations.
All effects are synthetic; nothing here targets firmware or a physical machine.
"""
from __future__ import annotations

import random
import re

from amsec.slicer import PrintParams, slice_to_gcode

G1 = re.compile(r"^G1 X(?P<x>-?[\d.]+) Y(?P<y>-?[\d.]+) E(?P<e>-?[\d.]+) F(?P<f>\d+)$")

def _layer_blocks(lines: list[str]) -> list[tuple[int, int]]:
    idx = [i for i, l in enumerate(lines) if l.startswith(";LAYER:")]
    return [(a, b) for a, b in zip(idx, idx[1:] + [len(lines)])]

def infill_reduction(text: str, mesh, p: PrintParams, rng: random.Random, factor: float = 0.4):
    """Re-slice with lower infill density in a band of layers (weakens part, invisible outside)."""
    q = PrintParams(**{**p.__dict__, "infill_density": p.infill_density * factor})
    full = slice_to_gcode(mesh, q).splitlines(); orig = text.splitlines()
    ob, tb = _layer_blocks(orig), _layer_blocks(full)
    n = len(ob); a = rng.randint(n // 4, n // 2); b = min(n - 1, a + max(2, n // 4))
    out = orig[:ob[a][0]]
    for i in range(a, b + 1):
        out += full[tb[i][0]:tb[i][1]]
    out += orig[ob[b][1]:]
    return "\n".join(out) + "\n", {"layers": [a, b], "factor": factor}

def _seg_circle(x0, y0, x1, y1, cx, cy, r):
    """Parameters t in [0,1] where segment enters/exits circle, or None."""
    dx, dy = x1 - x0, y1 - y0; fx, fy = x0 - cx, y0 - cy
    a = dx * dx + dy * dy; b = 2 * (fx * dx + fy * dy); c = fx * fx + fy * fy - r * r
    if a == 0: return None
    disc = b * b - 4 * a * c
    if disc < 0: return None
    sq = disc ** 0.5; t1, t2 = (-b - sq) / (2 * a), (-b + sq) / (2 * a)
    t1, t2 = max(0.0, t1), min(1.0, t2)
    return (t1, t2) if t2 > t1 else None

def void_insertion(text: str, mesh, p, rng: random.Random, radius: float = 3.0):
    """Remove extrusion inside a sphere -> internal void (classic 'dr0wned'-style defect).
    Segments crossing the void are split: extrude to entry, travel across, extrude after."""
    lines = text.splitlines(); blocks = _layer_blocks(lines)
    n = len(blocks); li = rng.randint(n // 3, 2 * n // 3)
    # centre the void on the midpoint of a random infill segment so it lies inside material
    segs = []; kind = ""; px = py = None
    for l in lines[blocks[li][0]:blocks[li][1]]:
        if l.startswith(";TYPE:"): kind = l[6:]
        mg = re.match(r"^G0 X(-?[\d.]+) Y(-?[\d.]+)", l)
        if mg: px, py = float(mg[1]), float(mg[2]); continue
        m = G1.match(l)
        if m:
            if kind == "FILL" and px is not None: segs.append((px, py, float(m["x"]), float(m["y"])))
            px, py = float(m["x"]), float(m["y"])
    if not segs:
        return text, {"note": "no infill in chosen layer; attack not applied"}
    x0, y0, x1, y1 = rng.choice(segs); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    span = int(radius / p.layer_height)
    band = set()
    for j in range(max(0, li - span), min(n, li + span + 1)):
        band.update(range(blocks[j][0], blocks[j][1]))
    out = []; x = y = 0.0; e_prev = 0.0; e_removed = 0.0; removed = 0
    for i, l in enumerate(lines):
        m = G1.match(l)
        if not m:
            mg = re.match(r"^G0 X(-?[\d.]+) Y(-?[\d.]+)", l)
            if mg: x, y = float(mg[1]), float(mg[2])
            out.append(l); continue
        x1, y1, e, f = float(m["x"]), float(m["y"]), float(m["e"]), m["f"]
        de = e - e_prev
        hit = _seg_circle(x, y, x1, y1, cx, cy, radius) if i in band else None
        if hit is None:
            out.append(f"G1 X{x1:.3f} Y{y1:.3f} E{e - e_removed:.5f} F{f}")
        else:
            t1, t2 = hit
            ex, ey = x + (x1 - x) * t1, y + (y1 - y) * t1
            qx, qy = x + (x1 - x) * t2, y + (y1 - y) * t2
            if t1 > 0: out.append(f"G1 X{ex:.3f} Y{ey:.3f} E{e_prev + de * t1 - e_removed:.5f} F{f}")
            out.append(f"G0 X{qx:.3f} Y{qy:.3f} F6000")
            e_removed += de * (t2 - t1); removed += 1
            if t2 < 1: out.append(f"G1 X{x1:.3f} Y{y1:.3f} E{e - e_removed:.5f} F{f}")
        x, y, e_prev = x1, y1, e
    return "\n".join(out) + "\n", {"centre": [cx, cy], "layer": li, "radius": radius, "segments_cut": removed}

def layer_height_change(text: str, mesh, p, rng: random.Random, factor: float = 1.5):
    """Re-slice a band with thicker layers (poorer bonding, dimensional error in Z)."""
    q = PrintParams(**{**p.__dict__, "layer_height": p.layer_height * factor})
    return slice_to_gcode(mesh, q), {"layer_height": q.layer_height, "note": "whole part re-sliced"}

def temperature_shift(text: str, mesh, p, rng: random.Random, delta: int = -25):
    """Lower nozzle temperature mid-print -> weak interlayer adhesion."""
    lines = text.splitlines(); blocks = _layer_blocks(lines)
    li = rng.randint(len(blocks) // 4, 3 * len(blocks) // 4)
    lines.insert(blocks[li][0] + 1, f"M104 S{p.nozzle_temp + delta}")
    return "\n".join(lines) + "\n", {"layer": li, "delta": delta}

def scaling(text: str, mesh, p, rng: random.Random, factor: float = 0.97):
    """Uniform XY scaling (dimensional sabotage below visual threshold)."""
    out = []
    for l in text.splitlines():
        m = re.match(r"^(G[01]) X(-?[\d.]+) Y(-?[\d.]+)(.*)$", l)
        if m:
            out.append(f"{m[1]} X{float(m[2]) * factor:.3f} Y{float(m[3]) * factor:.3f}{m[4]}")
        else:
            out.append(l)
    return "\n".join(out) + "\n", {"factor": factor}

def under_extrusion(text: str, mesh, p, rng: random.Random, factor: float = 0.75):
    """Scale E values in a band of layers -> porous, weak layers."""
    lines = text.splitlines(); blocks = _layer_blocks(lines)
    n = len(blocks); a = rng.randint(n // 4, n // 2); b = min(n - 1, a + max(2, n // 5))
    lo, hi = blocks[a][0], blocks[b][1]
    out = []; e_offset = 0.0; last_e = None
    for i, l in enumerate(lines):
        m = G1.match(l)
        if m:
            e = float(m["e"])
            if last_e is not None and lo <= i < hi:
                e_offset += (e - last_e) * (1 - factor)
            last_e = e
            out.append(f"G1 X{m['x']} Y{m['y']} E{e - e_offset:.5f} F{m['f']}")
        else:
            out.append(l)
    return "\n".join(out) + "\n", {"layers": [a, b], "factor": factor}

def toolpath_jitter(text: str, mesh, p, rng: random.Random, sigma: float = 0.15):
    """Random XY noise on infill moves in a band (surface/porosity degradation)."""
    lines = text.splitlines(); blocks = _layer_blocks(lines)
    n = len(blocks); a = rng.randint(n // 4, n // 2); b = min(n - 1, a + max(2, n // 5))
    lo, hi = blocks[a][0], blocks[b][1]
    out = []; kind = ""
    for i, l in enumerate(lines):
        if l.startswith(";TYPE:"): kind = l[6:]
        m = G1.match(l)
        if m and lo <= i < hi and kind == "FILL":
            out.append(f"G1 X{float(m['x']) + rng.gauss(0, sigma):.3f} Y{float(m['y']) + rng.gauss(0, sigma):.3f} "
                       f"E{m['e']} F{m['f']}")
        else:
            out.append(l)
    return "\n".join(out) + "\n", {"layers": [a, b], "sigma": sigma}

ATTACKS = {
    "infill_reduction": infill_reduction, "void_insertion": void_insertion,
    "layer_height_change": layer_height_change, "temperature_shift": temperature_shift,
    "scaling": scaling, "under_extrusion": under_extrusion, "toolpath_jitter": toolpath_jitter,
}
