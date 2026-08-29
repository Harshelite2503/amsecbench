from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODELS_DIR, GCODE_DIR, RENDER_DIR, RESULTS_DIR = DATA / "models", DATA / "gcode", DATA / "renders", DATA / "results"
for _d in (MODELS_DIR, GCODE_DIR, RENDER_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
MODEL = os.getenv("AMSEC_MODEL", "claude-opus-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("MATERIALS_API_KEY")
ANTHROPIC_WORKSPACE_ID = os.getenv("ANTHROPIC_WORKSPACE_ID") or os.getenv("MATERIALS_WORKSPACE_ID") or ""
def anthropic_client():
    import anthropic
    headers = {"anthropic-workspace-id": ANTHROPIC_WORKSPACE_ID} if ANTHROPIC_WORKSPACE_ID else None
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, default_headers=headers)
