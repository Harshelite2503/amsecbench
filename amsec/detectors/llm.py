"""LLM detector: give Claude the reference and suspect G-code (or a compact layer summary)
and ask for a tamper verdict with attack class. Also a VLM variant on rendered layer images."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field
from rich.progress import track

from amsec.config import MODEL, RESULTS_DIR, anthropic_client
from amsec.gcode import layer_summary, parse


class Verdict(BaseModel):
    tampered: bool
    attack_class: str = Field(description="one of: none, infill_reduction, void_insertion, layer_height_change, "
                                          "temperature_shift, scaling, under_extrusion, toolpath_jitter, other")
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(description="what in the data supports the verdict, 1-2 sentences")

SYSTEM = """You are an additive-manufacturing security analyst. You are given G-code for a part
(either a raw excerpt or a per-layer summary table) and must decide whether it has been
sabotaged relative to the trusted reference. Typical sabotage: reduced infill in a band of layers,
internal voids (extrusion removed in a region), changed layer height, lowered nozzle temperature,
uniform scaling, under-extrusion, toolpath jitter. Be precise and cite the layers/values."""

def _summary_text(text: str, max_rows: int = 200) -> str:
    s = layer_summary(parse(text)); temps = [l for l in text.splitlines() if l.startswith(("M104", "M109", "M140"))]
    return "temperature commands: " + "; ".join(temps) + "\n" + s.round(4).head(max_rows).to_string()

def judge(reference: str, suspect: str, mode: str = "summary", client=None) -> Verdict | None:
    client = client or anthropic_client()
    if mode == "summary":
        content = f"REFERENCE (trusted) per-layer summary:\n{_summary_text(reference)}\n\nSUSPECT per-layer summary:\n{_summary_text(suspect)}"
    else:  # raw: suspect only, no reference (harder, realistic for a print farm)
        content = "SUSPECT G-code (no reference available):\n" + suspect[:120_000]
    resp = client.messages.parse(model=MODEL, max_tokens=4000, thinking={"type": "adaptive"}, system=SYSTEM,
                                 messages=[{"role": "user", "content": content + "\n\nVerdict?"}], output_format=Verdict)
    return resp.parsed_output

def judge_image(reference_png: Path, suspect_png: Path, client=None) -> Verdict | None:
    client = client or anthropic_client()
    def img(p):
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.b64encode(p.read_bytes()).decode()}}
    resp = client.messages.parse(model=MODEL, max_tokens=4000, thinking={"type": "adaptive"}, system=SYSTEM,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": "Reference toolpath render (trusted):"}, img(reference_png),
            {"type": "text", "text": "Suspect toolpath render:"}, img(suspect_png),
            {"type": "text", "text": "Has the suspect been sabotaged? Verdict?"}]}], output_format=Verdict)
    return resp.parsed_output

def run(manifest: pd.DataFrame, mode: str = "summary", n: int | None = None) -> pd.DataFrame:
    client = anthropic_client(); rows = []
    items = manifest if n is None else manifest.sample(min(n, len(manifest)), random_state=0)
    for _, r in track(list(items.iterrows()), description=f"LLM detector ({mode})"):
        ref = Path(r.reference_path).read_text(); sus = Path(r.path).read_text()
        v = judge(ref, sus, mode=mode, client=client)
        if v is None: continue
        rows.append({"path": r.path, "part": r.part, "attack": r.attack, "pred_tampered": v.tampered,
                     "pred_class": v.attack_class, "confidence": v.confidence, "evidence": v.evidence})
    out = pd.DataFrame(rows); out.to_csv(RESULTS_DIR / f"llm_detector_{mode}.csv", index=False)
    y = (out.attack != "none"); p = out.pred_tampered
    summ = {"n": len(out), "accuracy": float((y == p).mean()), "tpr": float(p[y].mean()), "fpr": float(p[~y].mean()),
            "class_acc_on_tampered": float((out.pred_class[y] == out.attack[y]).mean())}
    (RESULTS_DIR / f"llm_detector_{mode}_summary.json").write_text(json.dumps(summ, indent=2)); print(summ)
    return out
