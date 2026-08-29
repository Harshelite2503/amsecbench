import random

from amsec.attacks import ATTACKS
from amsec.features import featurize
from amsec.gcode import parse
from amsec.models import block
from amsec.slicer import PrintParams, slice_to_gcode


def _gc():
    m = block(); m.apply_translation(-m.bounds[0]); p = PrintParams()
    return m, p, slice_to_gcode(m, p, "block")

def test_slicer_produces_layers():
    _, _p, g = _gc(); df = parse(g)
    assert df.layer.max() + 1 == 50  # 10 mm / 0.2 mm
    assert df.is_extrude.sum() > 100

def test_attacks_change_features():
    m, p, g = _gc(); base = featurize(g)
    for name, fn in ATTACKS.items():
        t, _meta = fn(g, m, p, random.Random(0))
        assert t != g, name
        f = featurize(t); assert any(abs(f[k] - base[k]) > 1e-6 for k in base), name

def test_rules_flag_attacks_and_pass_clean():
    from amsec.detectors.rules import detect
    m, p, g = _gc()
    assert detect(g, g)[0] is False
    hits = sum(detect(g, fn(g, m, p, random.Random(1))[0])[0] for fn in ATTACKS.values())
    assert hits >= 5
