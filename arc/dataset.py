"""
dataset -- load REAL ARC tasks (no synthetic fixtures here). Points at the real
datasets in ~/Desktop/ARC-solver/data so PySOAR runs on actual ARC-AGI data, not
problems made to fit the solver.
"""

from __future__ import annotations

import glob
import json
import os

# vendored into the repo (self-contained; raw task JSON only). was
# ~/Desktop/ARC-solver/data — external hook removed so the repo runs standalone.
_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

DATASETS = {
    "easy_a": os.path.join(_ROOT, "ARC_easy_a"),          # 9  single-pixel
    "easy":   os.path.join(_ROOT, "ARC_easy"),            # 16 single-pixel
    "human":  os.path.join(_ROOT, "ARC_human"),           # 8
    "agi":    os.path.join(_ROOT, "ARC_AGI", "training"),       # full ARC-AGI-1 train
    "agi2":   os.path.join(_ROOT, "ARC_AGI_v2", "training"),    # full ARC-AGI-2 train
}


def list_tasks(dataset: str, limit: int | None = None) -> list[tuple[str, str]]:
    """Return [(task_id, path), ...] for a named dataset."""
    d = DATASETS.get(dataset, dataset)
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    if limit is not None:
        files = files[:limit]
    return [(os.path.basename(f).replace(".json", ""), f) for f in files]


def load_task(path: str) -> dict:
    """Load one ARC task as {'train': [...], 'test': [...]} with input/output."""
    return json.load(open(path))


def available() -> dict:
    return {name: len(glob.glob(os.path.join(path, "*.json")))
            for name, path in DATASETS.items()}
