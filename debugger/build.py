# -*- coding: utf-8 -*-
"""ARBOR debugger.build — 풀이 과정 시각화(대시보드) 빌더 + 진입점.
setup_focus_agent 으로 태스크를 SOAR 로 구동, 트레이스를 focus_dashboard.html 로 렌더.

    python -m debugger.build        # -> debugger/traces/focus_dashboard.html
"""
from __future__ import annotations
import json, os, sys
from procedural_memory.loader import PRODUCTIONS, OP_DOCS
from arbor.agent.focus import setup_focus_agent
from arbor.env.survey import _load_made_and_real, _load_survey, SURVEY_AGI

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cycle_tree(events):
    """git dev-tree 용 **cycle 별 요약 노드** 목록. 각 노드 = 한 decision cycle:
      depth  = substate 깊이(S1=0, 하강할수록 +1) → 그래프의 lane(가로 위치)
      branch = 이 cycle 에 substate 가 생겼나(가지 침 = impasse)
      summary= 한 줄 요약 (무엇이 선택·적용됐나 / 뭐가 안돼 substate 가 났나)
      step   = 이 cycle 의 첫 이벤트 seq (노드 클릭 시 stepper 점프 대상)."""
    import re
    from itertools import groupby
    nodes = []
    for c, grp in groupby(events, key=lambda e: e["cycle"]):
        ec = list(grp)
        stk = ec[-1].get("goal_stack") or ["S1"]              # cycle 끝 시점의 goal 스택(=살아있는 lane 들)
        depth, gid = max(0, len(stk) - 1), stk[-1]
        op = None
        for e in ec:
            if e["kind"] == "op-select":
                m = re.search(r"name=([a-z]+)", e["label"])
                if m:
                    op = m.group(1)
        sub = [e for e in ec if e["kind"] == "substate"]
        applied = any(e["kind"] == "op-apply" and "새 substate" not in e["label"] for e in ec)
        subd = next((e for e in ec if e["kind"] == "substate" and "생성" in e["label"]), None)
        if sub:                                                   # 가지 침 (impasse → substate)
            lab = (subd or sub[-1])["label"]
            lv = re.search(r"level=([A-Z]+)", lab)
            if "하강" in lab:
                summ = f"‹{op or 'solve'}› 미구현 → 하강" + (f" · {lv.group(1)} 관측 시작" if lv else "")
            elif "arg" in lab:
                summ = f"‹{op or 'observe/compare'}› 대상 미정 → 대상 선택 substate"
            elif "자식 없음" in lab:
                summ = "더 하강할 계층 없음 → 종료"
            else:
                summ = lab[:70]
            knd = "branch"
        elif applied:
            summ, knd = f"‹{op}› 선택 → 적용", "apply"
        elif op:
            summ, knd = f"‹{op}› 제안·선택", "select"
        elif any(e["kind"] == "output" and "answer" in e["label"].lower() for e in ec):
            summ, knd = "답 제출(output)", "output"
        else:
            summ, knd = (ec[-1]["label"] or "")[:70], "phase"
        nodes.append({"cycle": c, "depth": depth, "goal": gid, "op": op or "", "kind": knd,
                      "branch": bool(sub), "summary": summ, "step": ec[0]["seq"], "stack": stk})
    return nodes


def _dash_data(task, tid="0a", max_cycles=1000):   # observe+compare+aggregate+find+solve+…×levels
    from arbor.engine.trace import _Tracer
    tr = _Tracer(task, tid, setup=setup_focus_agent)
    events = tr.run(max_cycles=max_cycles)
    wm_states = tr._wm_states           # emit 이 연속중복 병합해 이미 축소·인덱싱(events 는 wm_state 보유)
    # 제출 시도(3회 환경)를 대시보드 후보로: 각 시도의 답 격자 + 정답 여부.
    # HTML 은 c.answer 를 *테스트 pair 별 격자들의 리스트* 로 렌더(c.answer.map(grid)) →
    # 단일 test 답을 리스트로 감싼다.
    candidates = [{"answer": [a["answer"]] if a["answer"] else [],
                   "position": f"attempt {i + 1}: {a['hyp']}",
                   "color": "✓" if a["correct"] else "✗"}
                  for i, a in enumerate(tr.attempts)]
    correct_i = next((i for i, a in enumerate(tr.attempts) if a["correct"]), None)
    from debugger.dashboard import wm_deltas
    return {
        "id": tid, "events": events, "wm_states": wm_deltas(wm_states),
        "cycle_tree": _cycle_tree(events),                  # git dev-tree(좌측 패널) — cycle 노드 + substate 가지
        "grids": {"train": task["train"],
                  "test": [{"input": tp["input"]} for tp in task["test"]]},
        "candidates": candidates, "correct_attempt": correct_i, "n_steps": len(events),
    }


def _rules_manifest():
    return [{"name": p.name,
             "if": [{"id": c.id, "attr": c.attr, "val": c.value, "neg": c.negated} for c in p.conditions],
             "then": [{"id": a.id, "attr": a.attr, "val": a.value, "pref": a.pref} for a in p.actions]}
            for p in PRODUCTIONS]


def _safe_dash_data(task, tid, timeout_s=180):   # 제출 예산과 동일한 문제당 3분
    """_dash_data 를 **태스크당 타임아웃 + 예외 격리**로 감싼다. 일반 ARC-AGI 태스크는 솔버가
    가정한 구조(2 train + 1 test 등)와 달라 크래시하거나 오래 걸릴 수 있으므로, 한 태스크가
    전체 생성을 죽이지 않게 한다. 실패/초과 시 빈 이벤트 stub + ^error 필드 → 대시보드는 그
    태스크를 '무진행(n_steps=0)'으로 표시한다 (다양성 관찰이 목적이라 실패도 하나의 데이터)."""
    import signal
    class _TO(Exception):
        pass
    def _h(sig, frm):
        raise _TO()
    stub = {"id": tid, "events": [], "wm_states": [],
            "grids": {"train": task.get("train", []),
                      "test": [{"input": tp["input"]} for tp in task.get("test", [])]},
            "candidates": [], "correct_attempt": None, "n_steps": 0, "error": None}
    old = signal.signal(signal.SIGALRM, _h)
    try:
        signal.alarm(timeout_s)
        d = _dash_data(task, tid)
        signal.alarm(0)
        return d
    except _TO:
        stub["error"] = f"timeout>{timeout_s}s"
        return stub
    except Exception as e:                               # noqa: BLE001 (관찰용, 어떤 실패든 stub)
        stub["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return stub
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def make_dashboard(tasks, dataset="focus (slice 1)"):
    """tasks: [(tid, task_dict), ...] — 대시보드 TASK BROWSER 에 카드로 나열."""
    from debugger.dashboard import _HTML
    if isinstance(tasks, dict):                        # 단일 태스크 하위호환: make_dashboard(task_dict)
        tasks = [("task", tasks)]
    dash = []
    for i, (tid, t) in enumerate(tasks, 1):
        d = _safe_dash_data(t, tid)
        term = "" if d["n_steps"] == 0 else ("✓풀림" if d.get("correct_attempt") is not None else "종료/중지")
        print(f"  [{i:2}/{len(tasks)}] {tid:12} n_steps={d['n_steps']:6} {d.get('error') or term}", flush=True)
        dash.append(d)
    data = {"dataset": dataset, "tasks": dash,
            "rules": _rules_manifest(), "op_docs": OP_DOCS}
    out = os.path.join(_REPO, "debugger", "traces", "focus_dashboard.html")
    doc = _HTML.replace("__DATA__", json.dumps(data))
    # 상단 nav 링크(고정): easy a-h 각 태스크의 PAIR.program(text+AST+시각화)+TASK.solution 을
    # 확인하는 program 뷰어로 이동(스펙 §12 / 2026-07-16 버튼 교체 — 이전엔 anti-unify 3분할 뷰).
    # 공유 _HTML 를 오염시키지 않으려 focus 출력에만 주입한다.
    nav = ('<a href="program_report_all.html" onclick="try{location.href=\'program_report_all.html#\''
           '+D.tasks[ti].id;return false}catch(e){}" style="position:fixed;top:8px;right:12px;'
           'z-index:99999;background:#243b52;color:#bcd8f5;padding:6px 12px;border-radius:7px;'
           'text-decoration:none;font:13px/1 -apple-system,sans-serif;border:1px solid #3a5a7a;'
           'box-shadow:0 2px 8px #0006">▤ 이 문제 program 보기 →</a>')
    doc = doc.replace("<body>", "<body>" + nav, 1)
    with open(out, "w") as f:
        f.write(doc)
    return out


if __name__ == "__main__":
    # 사용자 지정(2026-07-14): dashboard = **17-survey** (easy 9 + made 2 + ARC-AGI 6).
    # 옛 seokki 대시보드(786369f→081463c)의 다양성 관찰 묶음을 복원 — 낯선 태스크에 현재
    # 로직이 어떻게 적용되나 관찰(harness §2-4). easy000i·미해결·크래시도 하나의 데이터로 남긴다
    # (_safe_dash_data 가 태스크당 타임아웃+예외 격리). easy 는 survey 안에 그대로 포함.
    tasks = _load_survey(agi_ids=SURVEY_AGI)                 # 9 + 2 + 6 = 17
    print(f"survey: {len(tasks)} 태스크 ({', '.join(t for t, _ in tasks)}) — max_cycles=1000")
    out = make_dashboard(tasks, dataset="survey 17 = easy 9 + made 2 + ARC-AGI 6")
    sz = os.path.getsize(out) / 1e6
    print(f"wrote {out}  ({sz:.1f} MB)")
    # companion 페이지: easy a-h program 뷰어 (nav 링크 대상; 스펙 §12)
    from debugger.reports.program_viewer import build as _build_pv
    pv = _build_pv()
    print(f"wrote {pv}\nopen it:  open {out}")
