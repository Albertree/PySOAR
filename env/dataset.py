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

# (2026-07-17 사용자 데이터 정리) ARC_easy_a → ARC_easy 로 rename(구 ARC_easy 삭제); made·multi 삭제;
# ARC_human 은 사용자 제작 문제(flip/move/rotate 하위폴더)로 교체.
DATASETS = {
    "easy":   os.path.join(_ROOT, "ARC_easy"),                 # a-h 8
    "human":  os.path.join(_ROOT, "ARC_human"),                # (하위폴더 flip/move/rotate)
    "move":   os.path.join(_ROOT, "ARC_human", "move"),        # 사용자 제작 move 문제
    "flip":   os.path.join(_ROOT, "ARC_human", "flip"),
    "rotate": os.path.join(_ROOT, "ARC_human", "rotate"),
    "objc":   os.path.join(_ROOT, "ARC_human", "object_coloring"),  # 사용자 제작 object 재채색 18문제
    "agi":    os.path.join(_ROOT, "ARC_AGI", "training"),           # full ARC-AGI-1 train
    "train":  os.path.join(_ROOT, "ARC_AGI", "training"),           # ARC-AGI-1 train set
    "eval":   os.path.join(_ROOT, "ARC_AGI", "evaluation"),         # ARC-AGI-1 eval set
}


def list_tasks(dataset: str, limit: int | None = None) -> list[tuple[str, str]]:
    """Return [(task_id, path), ...] for a named dataset."""
    d = DATASETS.get(dataset, dataset)
    # 자연 순서: 접미 길이 → 알파벳 (a,b,…,z,aa,ab,…). 문자열 정렬이면 a 다음 aa 가 와서 뒤섞임.
    # 길이 균일한 데이터셋(easy/agi)은 알파벳 순과 동일 → 영향 없음.
    files = sorted(glob.glob(os.path.join(d, "*.json")),
                   key=lambda f: (len(os.path.basename(f)), os.path.basename(f)))
    if limit is not None:
        files = files[:limit]
    return [(os.path.basename(f).replace(".json", ""), f) for f in files]


def load_task(path: str) -> dict:
    """Load one ARC task as {'train': [...], 'test': [...]} with input/output."""
    return json.load(open(path))
