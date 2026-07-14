# -*- coding: utf-8 -*-
"""ARBOR env.survey — 태스크 묶음 로더(다양성 관찰용): easy + made + ARC-AGI."""
from __future__ import annotations
import glob, os
from arc.dataset import list_tasks, load_task

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_made_and_real():
    """대시보드에 띄울 태스크: 워크스루의 made000a/b + 실제 08ed6ac7 + easy000a."""
    here = os.path.join(_REPO, "arc")
    tasks = []
    for tid in ("made000a", "made000b"):
        p = os.path.join(here, "data", "made", f"{tid}.json")
        if os.path.exists(p):
            tasks.append((tid, load_task(p)))
    real = glob.glob(os.path.join(os.path.dirname(here), "data", "**", "08ed6ac7.json"), recursive=True)
    if real:
        tasks.append(("08ed6ac7", load_task(real[0])))
    etid, epath = list_tasks("easy_a")[0]
    tasks.append((etid, load_task(epath)))
    return tasks


def _load_survey(n_agi=20, area_cap=200, agi_ids=None, include_easy=True, include_made=True):
    """다양성 관찰용 묶음: easy 9 + made 2 + ARC-AGI 문제.
    - agi_ids 지정 시: **그 id 들 정확히** 사용(area 필터 무시) — 서브셋 재생성용.
    - 미지정 시: training 에서 **max(train grid area) ≤ area_cap** (≈≤14x14) 인 것 앞에서 n_agi 개.
      WM 정렬 병목이 격자크기 비례라 시간/크기 예산 보호. 정렬 결정적 — 재현 가능.
    목적은 풀이가 아니라 '현재 로직이 낯선 태스크에 어떻게 적용되나' 관찰(harness §2-4)."""
    here = os.path.join(_REPO, "arc")
    tasks = []
    if include_easy:
        tasks += [(tid, load_task(p)) for tid, p in list_tasks("easy_a")]     # easy 9
    if include_made:
        for tid in ("made000a", "made000b"):                                 # made 2
            p = os.path.join(here, "data", "made", f"{tid}.json")
            if os.path.exists(p):
                tasks.append((tid, load_task(p)))
    agi_root = os.path.join(os.path.dirname(here), "data", "ARC_AGI")   # vendored (was ~/Desktop/ARC-solver)
    if agi_ids:                                                              # 명시 id 셋
        for tid in agi_ids:
            hits = glob.glob(os.path.join(agi_root, "**", f"{tid}.json"), recursive=True)
            if hits:
                tasks.append((tid, load_task(hits[0])))
        return tasks
    picked = 0                                                              # 자동 선택
    for p in sorted(glob.glob(os.path.join(agi_root, "training", "*.json"))):
        if picked >= n_agi:
            break
        t = load_task(p)
        try:
            area = max(len(g["input"]) * len(g["input"][0]) for g in t["train"])
        except Exception:                                                    # noqa: BLE001
            continue
        if area > area_cap:
            continue
        tasks.append((os.path.splitext(os.path.basename(p))[0], t))
        picked += 1
    return tasks

SURVEY_AGI = ["08ed6ac7", "0ca9ddb6", "009d5c81", "11852cab", "845d6e51", "868de0fa"]
