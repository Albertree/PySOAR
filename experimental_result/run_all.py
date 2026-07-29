#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""experimental_result — 12 ARC_human 데이터셋을 **캐시 없이 독립적으로** 돌려 결과를 깨끗이 보관.

각 데이터셋마다:
  1) solve 캐시 clear (신선 재계산 강제)
  2) program_report.html 생성(솔버 1회 solve + ①code ②AST ③시각화 렌더)
  3) experimental_result/ 로 이동
  4) 리포트 탭의 solved/unsolved 로 SCORE 집계
마지막에 result.md(요약표) 작성.

    python experimental_result/run_all.py [dataset ...]   # 인자 없으면 12셋 전부

12셋 = 4개념(move·flip·rota·objc) × 3변형(원본·트윈2·트윈3).
"""
from __future__ import annotations
import os
import re
import sys
import time
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # PySOAR/
sys.path.insert(0, ROOT)

# 12 데이터셋을 런타임에 등록(폴더 직결) — env/dataset.py 는 건드리지 않는다.
from env.dataset import DATASETS, list_tasks                        # noqa: E402
HUMAN = os.path.join(ROOT, "data", "ARC_human")
SETS = ["move", "mov2", "mov3", "flip", "fli2", "fli3",
        "rota", "rot2", "rot3", "objc", "obj2", "obj3"]
for _s in SETS:
    DATASETS[_s] = os.path.join(HUMAN, _s)
DATASETS.setdefault("rotate", DATASETS["rota"])                     # report 별칭

from debugger.solve_cache import clear_cache                        # noqa: E402
from debugger.reports.program_report import build                   # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))                    # experimental_result/
REPORTS = os.path.join(ROOT, "debugger", "reports")


def score_from_html(html: str):
    """리포트 상단 탭(<a data-t=… class="solved|unsolved">)에서 정오 집계."""
    tabs = re.findall(r'data-t="[^"]+"\s+class="(solved|unsolved)"', html)
    return tabs.count("solved"), len(tabs)


def run_one(s: str):
    clear_cache()                                                  # ← 캐시 없이 신선
    n = len(list_tasks(s))
    name = f"{s}_program_report.html"
    t0 = time.time()
    build(dataset=s, out_name=name, title=f"{s} program 뷰어 (arc_human/{s})",
          back_href="#", back_label="experimental_result")
    shutil.move(os.path.join(REPORTS, name), os.path.join(OUT, name))
    ok, tot = score_from_html(open(os.path.join(OUT, name), encoding="utf-8").read())
    dt = time.time() - t0
    print(f"  {s:6} {ok:>3}/{tot:<3}  ({dt:5.1f}s)  → {name}", flush=True)
    return {"set": s, "ok": ok, "total": tot, "declared": n, "seconds": dt}


CONCEPT = {"move": "이동(translation·anchor 정렬)", "flip": "대칭(반사)",
           "rota": "회전", "objc": "객체 재채색"}
GROUP = {"move": ["move", "mov2", "mov3"], "flip": ["flip", "fli2", "fli3"],
         "rota": ["rota", "rot2", "rot3"], "objc": ["objc", "obj2", "obj3"]}


def write_result_md(rows, elapsed):
    by = {r["set"]: r for r in rows}
    lines = ["# ARC_human 12셋 실험 결과", "",
             "12 데이터셋(4개념 × 원본·트윈2·트윈3)을 **캐시 없이 독립 실행**한 결과. "
             "각 셋은 `run_all.py` 가 solve 캐시를 지운 뒤 솔버 1회 solve → program_report 생성.", "",
             f"- 실행기: `run_all.py`  ·  총 소요 {elapsed:.0f}s", "",
             "## 요약", "",
             "| 개념 | 원본 | 트윈2 | 트윈3 |",
             "|---|---|---|---|"]
    for concept, sets in GROUP.items():
        cells = []
        for s in sets:
            r = by.get(s)
            cells.append(f"{s} {r['ok']}/{r['total']}" if r else f"{s} —")
        lines.append(f"| **{CONCEPT[concept]}** | {cells[0]} | {cells[1]} | {cells[2]} |")
    tot_ok = sum(r["ok"] for r in rows); tot = sum(r["total"] for r in rows)
    lines += ["", f"**합계: {tot_ok} / {tot}**", "",
              "## 데이터셋별 상세", "",
              "| 데이터셋 | 정답/전체 | 소요(s) | 리포트 |",
              "|---|---|---|---|"]
    for s in SETS:
        r = by.get(s)
        if not r:
            continue
        lines.append(f"| {s} | {r['ok']}/{r['total']} | {r['seconds']:.1f} | "
                     f"[{s}_program_report.html]({s}_program_report.html) |")
    lines += ["", "## 비고",
              "- 각 리포트의 Step C(TASK.solution)는 ①code(실행형) ②AST ③시각화 갤러리 3-표현. "
              "Step A/A.5/A.6/B(pixelize·objectize·anti-unification)도 함께 렌더.",
              "- SCORE 는 리포트 상단 탭의 solved/unsolved(=정답 attempt 존재) 집계 — "
              "`python -m debugger.score <set>` 게이트와 동일 기준.",
              "- 재실행: `python experimental_result/run_all.py` (전체) 또는 `... run_all.py move flip` (선택)."]
    open(os.path.join(OUT, "result.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main(argv):
    sets = [a for a in argv[1:] if a in SETS] or SETS
    print(f"experimental_result — {len(sets)}셋 캐시 없이 독립 실행", flush=True)
    t0 = time.time()
    rows = [run_one(s) for s in sets]
    write_result_md(rows, time.time() - t0)
    tot_ok = sum(r["ok"] for r in rows); tot = sum(r["total"] for r in rows)
    print(f"\n합계 {tot_ok}/{tot}  · result.md 작성 완료 ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main(sys.argv)
