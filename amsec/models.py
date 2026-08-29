"""Generate a small library of parametric benchmark parts as STL (no downloads needed).

Parts are chosen to cover the sabotage-relevant geometry classes used in the AM-security
literature: solid block, bracket with holes (load-bearing), thin-wall cylinder, tensile
dog-bone (ASTM D638-like), and a lattice-like grid plate.
"""
from __future__ import annotations

import numpy as np
import trimesh

from amsec.config import MODELS_DIR


def _box(x, y, z):
    return trimesh.creation.box(extents=(x, y, z))

def block(): return _box(30, 20, 10)

def bracket():
    base = _box(40, 20, 4)
    wall = _box(40, 4, 20); wall.apply_translation((0, -8, 12))
    part = base.union(wall)
    for dx in (-12, 12):
        hole = trimesh.creation.cylinder(radius=3, height=10); hole.apply_translation((dx, 4, 0))
        part = part.difference(hole)
    return part

def tube():
    outer = trimesh.creation.cylinder(radius=12, height=30)
    inner = trimesh.creation.cylinder(radius=10, height=32)
    return outer.difference(inner)

def dogbone():
    grip1 = _box(20, 12, 4); grip1.apply_translation((-30, 0, 0))
    grip2 = _box(20, 12, 4); grip2.apply_translation((30, 0, 0))
    gauge = _box(40, 6, 4)
    return grip1.union(grip2).union(gauge)

def grid_plate():
    plate = _box(40, 40, 3)
    for x in np.linspace(-15, 15, 4):
        for y in np.linspace(-15, 15, 4):
            hole = _box(5, 5, 6); hole.apply_translation((x, y, 0))
            plate = plate.difference(hole)
    return plate

PARTS = {"block": block, "bracket": bracket, "tube": tube, "dogbone": dogbone, "grid_plate": grid_plate}

def generate_all() -> list[str]:
    out = []
    for name, fn in PARTS.items():
        m = fn()
        m.apply_translation(-m.bounds[0])  # sit on z=0, positive quadrant
        p = MODELS_DIR / f"{name}.stl"; m.export(p); out.append(str(p))
    return out
