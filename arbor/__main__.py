"""python -m arbor — ARBOR 에이전트 진입점.
env 가 data/ 에서 문제를 제시 → arbor 가 풀이 → env 채점(3회 재시도). 기록은 debugger 가 후처리.
러너(run_solve)는 현재 debugger 에 있어 이를 재사용한다(후속 계획에서 arbor 로 이관)."""
from __future__ import annotations
import argparse
import sys
from debugger.score import score_dataset
from debugger.solve_cache import run_solve
from env.dataset import list_tasks, load_task


def main(argv=None):
    ap = argparse.ArgumentParser(prog="arbor")
    ap.add_argument("--dataset", default="move", help="풀 데이터셋 (기본 move)")
    ap.add_argument("--tasks", default=None, help="단일 task id (지정 시 그 문제만)")
    ap.add_argument("--max-cycles", type=int, default=500)
    args = ap.parse_args(argv)

    if args.tasks:
        hit = [(t, p) for t, p in list_tasks(args.dataset) if t == args.tasks]
        if not hit:
            print(f"NOT FOUND: {args.tasks} in {args.dataset}"); return 1
        tid, path = hit[0]
        r = run_solve(tid, load_task(path), max_cycles=args.max_cycles, mode="score")
        ok = any(a["correct"] for a in r["attempts"])
        print(f"{tid}: {'SOLVED' if ok else 'FAIL'}")
        return 0 if ok else 1

    r = score_dataset(args.dataset, max_cycles=args.max_cycles)
    print(f"SCORE: {r['ok']}/{r['total']}  ({r['seconds']:.1f}s)")
    if r["fail"]:
        print("FAIL:", r["fail"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
