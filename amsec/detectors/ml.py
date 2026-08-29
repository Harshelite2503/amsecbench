"""Feature-based ML detector (no reference needed at test time): random forest / GBR on
featurize() vectors; leave-one-part-out so the model must generalise to unseen geometry."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from amsec.config import RESULTS_DIR
from amsec.features import FEATURES

MODELS = {
    "logreg": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
    "random_forest": lambda: RandomForestClassifier(n_estimators=400, random_state=0),
    "gbc": lambda: GradientBoostingClassifier(random_state=0),
}

def run(feat: pd.DataFrame) -> pd.DataFrame:
    """feat: one row per G-code file with FEATURES + 'part', 'attack' ('none' for clean)."""
    y = (feat.attack != "none").astype(int).values; X = feat[FEATURES].values; parts = feat.part.unique()
    rows = []
    for name, mk in MODELS.items():
        prob = np.zeros(len(feat))
        for part in parts:                              # leave-one-part-out
            te = (feat.part == part).values
            m = mk().fit(X[~te], y[~te]); prob[te] = m.predict_proba(X[te])[:, 1]
        pred = (prob > 0.5).astype(int)
        r = {"model": name, "auc": round(roc_auc_score(y, prob), 3), "f1": round(f1_score(y, pred), 3)}
        for atk in sorted(feat.attack.unique()):
            if atk == "none": continue
            mask = (feat.attack == atk).values
            r[f"recall_{atk}"] = round(float(pred[mask].mean()), 2)
        r["false_positive_rate"] = round(float(pred[y == 0].mean()), 2)
        rows.append(r)
    res = pd.DataFrame(rows); res.to_csv(RESULTS_DIR / "ml_detectors.csv", index=False)
    (RESULTS_DIR / "ml_detectors.json").write_text(json.dumps(rows, indent=2))
    return res
