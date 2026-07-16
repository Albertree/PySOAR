#!/usr/bin/env python3
"""리팩터 행동보존 오라클 — easy_a 9태스크 step 수가 golden 과 완전 일치하는지 검증.

각 리팩터 단계(P1..P5) 종료 시 실행: `PYTHONPATH=. python3 tests/verify_refactor.py`
불일치가 하나라도 있으면 비-0 종료 → 그 단계는 행동을 바꾼 것(리팩터 실패).

솔버 진입점이 이동하면 아래 IMPORT 두 줄만 갱신한다(P5).
"""
import json
import os
import sys

sys.setrecursionlimit(100000)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- 진입점 (리팩터로 이동하면 여기만 바꾼다) ---
from debugger.build import _dash_data          # noqa: E402
from arbor.env.dataset import list_tasks, load_task     # noqa: E402


def main() -> int:
    golden = json.load(open(os.path.join(ROOT, "tests", "golden_steps.json")))
    fails = []
    tasks = list_tasks("easy")
    for tid, p in tasks:
        d = _dash_data(load_task(p), tid)
        want = golden.get(tid, {}).get("n_steps")
        got = d["n_steps"]
        ok = want == got
        print(f"  {tid}: n_steps={got} (golden {want}) {'OK' if ok else '### MISMATCH ###'}")
        if not ok:
            fails.append((tid, want, got))
    if fails:
        print(f"\nFAIL: {len(fails)} 태스크 step 불일치 — 리팩터가 행동을 바꿈:")
        for tid, w, g in fails:
            print(f"  {tid}: golden={w} got={g}")
        return 1
    print(f"\nPASS: {len(tasks)}/{len(tasks)} step 일치 — 행동보존 확인.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
