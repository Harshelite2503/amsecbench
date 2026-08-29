# AMSecBench

**Can AI detect sabotage in 3D-printing toolpaths — and can it defeat the design-obfuscation defenses the field relies on?**

A synthetic, fully labelled benchmark for additive-manufacturing (AM) security, built to evaluate large language
models (LLMs) and vision-language models (VLMs) as both **defender** (G-code tamper detection) and **red team**
(recovering intended designs from obfuscated CAD). Everything runs offline on generated parts; nothing touches
firmware or a physical printer.

```
parts ──▶ mini-slicer ──▶ clean G-code ──▶ 7 attack classes ──▶ features / renders ──▶ detectors: rules · ML · LLM · VLM
                                                                                          (Track A)
parts ──▶ obfuscation (dummy features, parameter-gated keys) ──▶ LLM/VLM de-obfuscation ──▶ IoU vs. true design
                                                                                          (Track B)
```

## Quickstart
```bash
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"
amsec parts && amsec build --seeds 3      # ~1 min, no API key
amsec rules && amsec ml                   # baselines
amsec llm --mode summary --n 30           # Claude detector (needs ANTHROPIC_API_KEY)
amsec obfuscate                           # Track B assets
```

## Attack classes (Track A)
| attack | effect | visible externally? |
|---|---|---|
| infill_reduction | lower infill density in a band of layers | no |
| void_insertion | extrusion removed inside a sphere → internal void | no |
| layer_height_change | thicker layers → weaker Z bonding | barely |
| temperature_shift | nozzle temperature lowered mid-print | no |
| scaling | uniform 3 % XY shrink | with calipers |
| under_extrusion | E scaled by 0.75 in a band | surface texture |
| toolpath_jitter | Gaussian XY noise on infill | no |

## Detectors
* **rules** — reference-vs-suspect feature comparison (the "design-to-G-code verification" baseline)
* **ml** — logistic / random-forest / gradient-boosting on 17 per-file features, leave-one-part-out
* **llm** — Claude on per-layer summaries (with reference) or raw G-code (no reference)
* **vlm** — Claude on rendered toolpath images

## Track B: obfuscation red-team
Toy re-implementation of design-based security (Chen & Gupta): decoy features and parameter-gated "key" ribs.
The question is whether an LLM/VLM given the obfuscated STL + renders recovers the intended part (IoU).

## Status
- [x] parts, slicer, 7 attacks, features, renders, rule + ML detectors, tests
- [x] LLM/VLM detector code, obfuscation generator
- [ ] LLM/VLM runs (needs key), de-obfuscation experiment, real-slicer (PrusaSlicer) variant, paper

MIT. Authors: Harsh Vardhan Gupta; collaboration with Prof. Nikhil Gupta and Prof. Ramesh Karri (NYU Tandon).
