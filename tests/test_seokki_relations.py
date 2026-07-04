# -*- coding: utf-8 -*-
"""
seokki slice 1 -- compare→refine→aggregate 관계 도출이 규칙으로 동작하는지.

검증하는 것(문제 풀이가 아니라 *구조*):
  1. 회귀: expr_solver 옛 파이프라인 easy_a 9/9 불변.
  2. focus_solver 가 TASK→PAIR→GRID→OBJECT 로 하강한다(고정 시나리오 아님, impasse 산물).
  3. object 레벨에서 compare 가 orderable property 를 greater/less 로 refine 하고,
     aggregate 가 extremum role 을 도출한다(= "가장 큼"을 카탈로그 없이 만든다).
  4. 도출된 관계·역할이 WM 에 WME 로 남는다(대시보드가 렌더할 재료).
  5. 같은 규칙이 다른 태스크에서도 발화한다(시나리오 고정 아님).

run:  python3 tests/test_seokki_relations.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arc.dataset import list_tasks, load_task                       # noqa: E402
from arc.focus_solver import setup_focus_agent                      # noqa: E402
from arc.fine_trace import fine_trace                               # noqa: E402
from arc.thinking_ops import components, derive_relations, derive_roles  # noqa: E402


def _run(tid, task, cyc=40):
    return fine_trace(task, tid, setup=setup_focus_agent, max_cycles=cyc)


def _answer(ev):
    for e in ev[::-1]:
        for (i, a, v) in e["wm"]:
            if i == "I3" and a == "answer":
                return [list(r) for r in v]
    return None


def test_expr_regression():
    from arc.expr_solver import solve as esolve
    ok = sum(1 for tid, p in list_tasks("easy_a") if esolve(load_task(p), tid=tid))
    assert ok == 9, f"expr_solver regression: {ok}/9"


def test_focus_pipeline_solves_easy_a():
    # 규칙주도(impasse 기반) focus_solver 가 각 operator(propose+apply)로 easy_a 를 푼다.
    ok = 0
    for tid, path in list_tasks("easy_a"):
        t = load_task(path)
        ev = _run(tid, t, cyc=60)
        ok += (_answer(ev) == t["test"][0]["output"])
    assert ok == 9, f"focus_solver(rule-driven) easy_a: {ok}/9"


def test_full_operator_pipeline_fires():
    # easy 풀이에 생각 operator 전 과정이 규칙으로 발화 (몇 개 없던 문제 해소)
    tid, path = list_tasks("easy_a")[0]
    ops = [e["label"].split("name=")[-1].rstrip("]")
           for e in _run(tid, load_task(path), cyc=60) if e["kind"] == "op-select"]
    for want in ("observe", "compare", "hypothesize", "predict", "evaluate", "verify",
                 "compose", "submit"):
        assert want in ops, f"{want} operator 가 발화 안 함: {ops}"


def test_descent_and_aggregate_on_made000a():
    # made000a(선택형)는 이 레벨 풀이 실패 → 하강 → object 레벨 compare→aggregate 로
    # 관계·역할 도출 (문제 못 풀어도 탐색이 진행됨).
    ev = _run("made000a", load_task("arc/data/made/made000a.json"), cyc=60)
    ops = [e["label"] for e in ev if e["kind"] == "op-select"]
    assert any("hypothesize" in o for o in ops), "풀이 시도(hypothesize) 있어야"
    assert any("aggregate" in o for o in ops), "실패 후 하강해 compare→aggregate 로 관계 도출"
    depth = max(len(e["goal_stack"]) for e in ev)
    assert depth >= 3, f"pair 아래로 하강 안 됨 (depth={depth})"


def test_pure_functions_derive_extremum():
    # 3 노드, area 서로 다름 → 최대/최소 role 도출 (지어낸 DSL 없이)
    props = {"A": {"area": 1}, "B": {"area": 6}, "C": {"area": 4}}
    rels = derive_relations(["A", "B", "C"], props)
    roles = derive_roles(["A", "B", "C"], rels)
    top = {(r["node"], r["role"]) for r in roles if r["on"] == "area"}
    assert ("B", "extremum+") in top and ("A", "extremum-") in top


def test_components_only_from_real_schema():
    # orderable 분해는 실제 스키마 모양에서만 (presence/categorical → 빈 목록)
    assert components("area", 5) == [("area", 5)]
    assert dict(components("size", {"height": 2, "width": 3})) == {"size.height": 2, "size.width": 3}
    assert components("color", {0: True, 2: True}) == []     # presence → 순서 없음
    assert components("shape", [[1, -1]]) == []              # categorical


def test_relations_land_in_wm():
    # made000a 는 하강해 object 레벨에서 관계·역할을 WM 에 남긴다(대시보드 렌더 재료).
    ev = _run("made000a", load_task("arc/data/made/made000a.json"), cyc=60)
    wm = ev[-1]["wm"]
    greaters = [(i, a, v) for (i, a, v) in wm if a == "greater"]
    roles = [(i, a, v) for (i, a, v) in wm if a == "role"]
    assert greaters, "greater 관계 WME 가 WM 에 없음"
    assert any("extremum+" in v for (_i, _a, v) in roles), "extremum role WME 가 WM 에 없음"


def test_rule_driven_not_scenario_fixed():
    # 태스크마다 operator 발화가 다르다(시나리오 고정 아님): easy 는 pair 레벨에서
    # 풀이 완주(submit), made 는 실패→하강. 같은 규칙셋이 상황에 따라 다르게 발화.
    etid, epath = list_tasks("easy_a")[0]
    easy = _run(etid, load_task(epath), cyc=60)
    made = _run("made000a", load_task("arc/data/made/made000a.json"), cyc=60)
    e_ops = {e["label"].split("name=")[-1].rstrip("]") for e in easy if e["kind"] == "op-select"}
    m_ops = {e["label"].split("name=")[-1].rstrip("]") for e in made if e["kind"] == "op-select"}
    assert "submit" in e_ops and "submit" not in m_ops       # 같은 규칙, 다른 경로
    assert "aggregate" in m_ops and "aggregate" not in e_ops


def test_submission_captured_and_scored():
    # 제출된 답 격자가 대시보드 후보로 잡히고, 3회 환경이 채점해 정답 표시.
    from arc.focus_solver import _dash_data
    tid, path = list_tasks("easy_a")[0]
    t = load_task(path)
    d = _dash_data(t, tid)
    assert d["candidates"], "제출 답이 후보로 안 잡힘"
    assert d["correct_attempt"] == 0, "첫 제출이 정답으로 채점 안 됨"
    assert d["candidates"][0]["answer"] == [t["test"][0]["output"]], "제출 격자가 정답과 다름"
    # feedback 이벤트(환경 채점)가 트레이스에 있음
    assert any(e["kind"] == "feedback" for e in d["events"]), "환경 피드백 이벤트 없음"


def test_retry_env_alive_and_bounded():
    # 오답이면 다음 후보로 재시도하되 3회로 제한(무한루프 없음). 환경을 항상-오답으로.
    import arc.environment as E
    from arc.fine_trace import _Tracer
    from arc.focus_solver import setup_focus_agent
    orig = E.ARCEnvironment.step
    # 항상-오답 ∧ can_retry True 로 강제 → 후보 소진으로만 멈춰야(무한루프 없음)
    E.ARCEnvironment.step = lambda self, g: (
        0.0, None, False, {"correct": False, "attempts_left": 2, "can_retry": True})
    try:
        tid, path = list_tasks("easy_a")[0]
        tr = _Tracer(load_task(path), tid, setup=setup_focus_agent)
        tr.run(max_cycles=120)
        assert 1 <= len(tr.attempts) <= 3, f"재시도 경계 위반: {len(tr.attempts)}"
    finally:
        E.ARCEnvironment.step = orig


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
