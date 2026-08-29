"""Minimal FDM slicer: STL -> G-code with perimeters + rectilinear infill.

Deliberately simple and fully inspectable so every attack in `attacks.py` has a
known ground-truth effect. Not a production slicer.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import trimesh
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union


@dataclass
class PrintParams:
    layer_height: float = 0.2
    nozzle: float = 0.4
    perimeters: int = 2
    infill_density: float = 0.3      # 0-1
    infill_angle_deg: float = 45.0
    nozzle_temp: int = 210
    bed_temp: int = 60
    print_speed: float = 40.0        # mm/s
    filament_diameter: float = 1.75
    extrusion_multiplier: float = 1.0
    notes: dict = field(default_factory=dict)

def _e_per_mm(p: PrintParams) -> float:
    """Extrusion (mm of filament) per mm of travel for a rectangular bead."""
    bead_area = p.nozzle * p.layer_height
    fil_area = np.pi * (p.filament_diameter / 2) ** 2
    return bead_area / fil_area * p.extrusion_multiplier

def slice_layers(mesh: trimesh.Trimesh, layer_height: float) -> list[tuple[float, MultiPolygon]]:
    zmin, zmax = mesh.bounds[0][2], mesh.bounds[1][2]
    zs = np.arange(zmin + layer_height / 2, zmax, layer_height)
    layers = []
    for z in zs:
        sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sec is None:
            continue
        planar, _ = sec.to_2D()
        polys = [pp for pp in planar.polygons_full if pp is not None and pp.is_valid and pp.area > 0.5]
        if not polys:
            continue
        geom = unary_union(polys)
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        layers.append((float(z), geom))
    return layers

def _perimeter_paths(poly: Polygon, p: PrintParams) -> list[np.ndarray]:
    paths = []
    for i in range(p.perimeters):
        inset = poly.buffer(-(i + 0.5) * p.nozzle, join_style=2)
        if inset.is_empty:
            break
        geoms = inset.geoms if hasattr(inset, "geoms") else [inset]
        for g in geoms:
            for ring in [g.exterior, *g.interiors]:
                paths.append(np.asarray(ring.coords))
    return paths

def _infill_paths(poly: Polygon, p: PrintParams, z: float) -> list[np.ndarray]:
    if p.infill_density <= 0:
        return []
    inner = poly.buffer(-(p.perimeters + 0.5) * p.nozzle, join_style=2)
    if inner.is_empty:
        return []
    spacing = p.nozzle / p.infill_density
    ang = np.deg2rad(p.infill_angle_deg + (90 if round(z / p.layer_height) % 2 else 0))
    d = np.array([np.cos(ang), np.sin(ang)]); n = np.array([-d[1], d[0]])
    minx, miny, maxx, maxy = poly.bounds
    diag = np.hypot(maxx - minx, maxy - miny); c = np.array([(minx + maxx) / 2, (miny + maxy) / 2])
    paths = []
    for k in np.arange(-diag, diag, spacing):
        a = c + n * k - d * diag; b = c + n * k + d * diag
        seg = LineString([a, b]).intersection(inner)
        if seg.is_empty:
            continue
        for g in (seg.geoms if hasattr(seg, "geoms") else [seg]):
            if g.length > p.nozzle:
                paths.append(np.asarray(g.coords))
    return paths

def slice_to_gcode(mesh: trimesh.Trimesh, p: PrintParams, part_name: str = "part") -> str:
    epm = _e_per_mm(p); feed = int(p.print_speed * 60)
    out = [f"; AMSecBench mini-slicer | part={part_name}", (f"; layer_height={p.layer_height} nozzle={p.nozzle} "
           f"perimeters={p.perimeters} infill={p.infill_density} temp={p.nozzle_temp} bed={p.bed_temp}"),
           f"M104 S{p.nozzle_temp}", f"M140 S{p.bed_temp}", f"M109 S{p.nozzle_temp}", f"M190 S{p.bed_temp}",
           "G21", "G90", "M82", "G28", "G92 E0"]
    e = 0.0
    for li, (z, geom) in enumerate(slice_layers(mesh, p.layer_height)):
        out.append(f";LAYER:{li}"); out.append(f"G1 Z{z + p.layer_height/2:.3f} F1200")
        for poly in geom.geoms:
            for kind, paths in (("PERIMETER", _perimeter_paths(poly, p)), ("FILL", _infill_paths(poly, p, z))):
                for path in paths:
                    out.append(f";TYPE:{kind}")
                    out.append(f"G0 X{path[0][0]:.3f} Y{path[0][1]:.3f} F6000")
                    for (x0, y0), (x1, y1) in itertools.pairwise(path):
                        e += np.hypot(x1 - x0, y1 - y0) * epm
                        out.append(f"G1 X{x1:.3f} Y{y1:.3f} E{e:.5f} F{feed}")
    out += ["M104 S0", "M140 S0", "G28 X0", "M84", "; END"]
    return "\n".join(out) + "\n"

def slice_file(stl_path, p: PrintParams | None = None) -> str:
    p = p or PrintParams()
    mesh = trimesh.load(stl_path, force="mesh")
    return slice_to_gcode(mesh, p, part_name=str(stl_path).rsplit("/", 1)[-1])
