"""AMSecBench CLI.
    amsec parts            # generate STL parts
    amsec build            # slice, attack, featurize, render -> data/
    amsec rules            # rule-based reference-comparison detector
    amsec ml               # leave-one-part-out ML detectors
    amsec llm --mode summary|raw   # Claude detector (needs API key)
    amsec obfuscate        # Track B: build obfuscated STLs
"""
from __future__ import annotations

import json

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="AMSecBench: AI vs. sabotage in additive manufacturing")
console = Console()

@app.command()
def parts():
    from amsec.models import generate_all
    console.print(generate_all())

@app.command()
def build(seeds: int = 3, renders: bool = True):
    from amsec.dataset import build as _b
    df = _b(seeds=seeds, renders=renders)
    console.print(f"{len(df)} G-code files; attacks: {df.attack.value_counts().to_dict()}")

@app.command()
def rules():
    from pathlib import Path

    import pandas as pd

    from amsec.config import RESULTS_DIR
    from amsec.dataset import load_manifest
    from amsec.detectors.rules import detect
    m = load_manifest(); rows = []
    for _, r in m.iterrows():
        flag, reasons = detect(Path(r.reference_path).read_text(), Path(r.path).read_text())
        rows.append({"part": r.part, "attack": r.attack, "flagged": flag, "reasons": ";".join(reasons)})
    out = pd.DataFrame(rows); out.to_csv(RESULTS_DIR / "rules_detector.csv", index=False)
    summ = out.groupby("attack").flagged.mean().round(2).to_dict()
    (RESULTS_DIR / "rules_detector_summary.json").write_text(json.dumps(summ, indent=2))
    console.print("detection rate by attack (none = false-positive rate):"); console.print(summ)

@app.command()
def ml():
    from amsec.dataset import load_manifest
    from amsec.detectors.ml import run
    console.print(run(load_manifest()).to_string())

@app.command()
def llm(mode: str = "summary", n: int = typer.Option(None)):
    from amsec.dataset import load_manifest
    from amsec.detectors.llm import run
    run(load_manifest(), mode=mode, n=n)

@app.command()
def obfuscate():
    from amsec.obfuscate import obfuscate_all
    console.print(f"{len(obfuscate_all())} obfuscated models written")

if __name__ == "__main__":
    app()
