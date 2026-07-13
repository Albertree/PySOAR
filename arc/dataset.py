"""
dataset -- load REAL ARC tasks (no synthetic fixtures here). Points at the real
datasets in ~/Desktop/ARC-solver/data so PySOAR runs on actual ARC-AGI data, not
problems made to fit the solver.
"""

from __future__ import annotations

import glob
import json
import os

_ROOT = os.path.expanduser("~/Desktop/ARC-solver/data")
# ARC-solver/data lacks some datasets on this machine (e.g. ARC_easy_a, the 9
# single-pixel headline set) -- they live in the SOAR-ARC-test sibling repo, same
# split as the frozen DSL (see arc/dsl.py). Resolve each dataset against both
# roots, ARC-solver first.
_ROOTS = [_ROOT, os.path.expanduser("~/Desktop/SOAR-ARC-test/data")]


def _resolve(*parts):
    """First existing <root>/<*parts> across the sibling data roots; falls back
    to the primary root (may be empty) so `available()` still reports 0 honestly."""
    for root in _ROOTS:
        p = os.path.join(root, *parts)
        if os.path.isdir(p):
            return p
    return os.path.join(_ROOT, *parts)


DATASETS = {
    "easy_a": _resolve("ARC_easy_a"),               # 9  single-pixel (SOAR-ARC-test)
    "easy":   _resolve("ARC_easy"),                 # 16 single-pixel (ARC-solver)
    "human":  _resolve("ARC_human"),                # 8  (missing on this machine)
    "agi":    _resolve("ARC_AGI", "training"),      # full ARC-AGI-1 train (ARC-solver)
    "agi2":   _resolve("ARC_AGI_v2", "training"),   # full ARC-AGI-2 train (ARC-solver)
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
