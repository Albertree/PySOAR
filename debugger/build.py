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


def render_transform_panel(wm):
    """WM 의 transform_search 흔적(procedural_memory/operators/transform_search.py 가 남기는
    required-effect·candidates·hypothesis(rule/args/src/verdict)·transform-survivor WME)을
    HTML 패널로 — 시도·기각된 후보까지 보여 §1-5 visibility 를 만족한다(Task 7, harness §2-5).

    브리프 원안은 조회 id 를 "s1" 로 하드코딩했지만, 실제 WM 에서 이 WME 들은 top state(S1)가
    아니라 transform_search 를 실행한 그 GRID goal 상태(예: S3, S5 …)에 쓰인다 — operator body
    가 substate 를 push 하지 않고 자신을 연 부모 상태(<s>)에 직접 쓰기 때문
    (procedural_memory/operators/transform_search.py:9-32 참조). 그래서 "s1" 을 하드코딩하지
    않고, required-effect 를 가진 모든 상태 id 를 찾아 각각 렌더한다 — 한 solve 에서
    transform_search 가 여러 상태(여러 GRID goal)에서 여러 번 열릴 수 있다."""
    def g(iid, attr):
        return [v for (i, a, v) in wm if i == iid and a == attr]
    state_ids, seen = [], set()
    for (i, a, v) in wm:
        if a == "required-effect" and i not in seen:
            seen.add(i)
            state_ids.append(i)
    if not state_ids:
        return ('<div class="transform-search-panel"><h3>transform_search</h3>'
                '<p class="hint">transform_search 흔적 없음</p></div>')
    sections = []
    for sid in state_ids:
        req = (g(sid, "required-effect") or ["(none)"])[0]
        cands = (g(sid, "candidates") or ["(none)"])[0]
        rows = []
        for (i, a, v) in wm:
            if i == sid and a == "hypothesis":
                rule = (g(v, "rule") or ["?"])[0]
                src = (g(v, "src") or [""])[0]
                verdict = (g(v, "verdict") or ["?"])[0]
                cls = "survive" if verdict == "survive" else "reject"
                rows.append(f'<tr class="{cls}"><td>{rule}</td><td>{src}</td><td>{verdict}</td></tr>')
        # survivor 는 정상적으로 sid 와 같은 id(parent==s) 에 쓰이지만(operator body 참조),
        # 방어적으로 못 찾으면 WM 전체에서 찾는다.
        surv = g(sid, "transform-survivor") or [v for (i, a, v) in wm if a == "transform-survivor"]
        surv_html = f'<p><b>survivor:</b> {surv[0]}</p>' if surv else "<p>survivor 없음</p>"
        sections.append(
            f'<div class="transform-search-state"><h4>{sid}</h4>'
            f'<p><b>required-effect:</b> {req}</p><p><b>candidates:</b> {cands}</p>'
            f'<table><tr><th>rule</th><th>arg src</th><th>verdict</th></tr>'
            f'{"".join(rows)}</table>{surv_html}</div>')
    return (f'<div class="transform-search-panel"><h3>transform_search</h3>'
            f'{"".join(sections)}</div>')


def _all_wm_triples(wm_states):
    """wm_states(각 원소 = 그 시점 full WM triple 리스트)의 합집합(첫 등장 순서 유지, dedup).
    substate 복귀로 나중에 지워진 WME(transform_search 의 시도·기각 hypothesis 등)도 한 번이라도
    존재했으면 포함 — render_transform_panel 이 최종 WM 스냅샷만 보고 시도 흔적을 놓치지
    않게 한다(§1-5 visibility: 기각된 후보도 보여야 함)."""
    seen, out = set(), []
    for st in wm_states:
        for t in st:
            k = tuple(t)
            if k not in seen:
                seen.add(k)
                out.append(list(t))
    return out


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
        # transform_search 패널(Task 7, §2-5): required-effect·후보·시도(verdict)·survivor.
        # 최종 wm_states 스냅샷 대신 전체 wm_states 의 합집합을 넘겨, substate 복귀로 나중에
        # 지워진 시도·기각 hypothesis 도 놓치지 않는다.
        "transform_panel": render_transform_panel(_all_wm_triples(wm_states)),
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
            "candidates": [], "correct_attempt": None, "n_steps": 0, "error": None,
            "transform_panel": render_transform_panel([])}
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
    # 상단 nav 링크(고정): 생성된 per-pair program 이 anti-unify 되어 일반화되는 별도 페이지로 이동
    # (사용자 2026-07-14). 공유 _HTML 를 오염시키지 않으려 focus 출력에만 주입한다.
    nav = ('<a href="easy_antiunify_report.html" onclick="try{location.href=\'easy_antiunify_report.html#\''
           '+D.tasks[ti].id;return false}catch(e){}" style="position:fixed;top:8px;right:12px;'
           'z-index:99999;background:#243b52;color:#bcd8f5;padding:6px 12px;border-radius:7px;'
           'text-decoration:none;font:13px/1 -apple-system,sans-serif;border:1px solid #3a5a7a;'
           'box-shadow:0 2px 8px #0006">▤ 이 문제 anti-unification →</a>')
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
    # companion 페이지: per-pair program → anti-unification 3분할 뷰 (nav 링크 대상)
    from debugger.reports.easy_antiunify_viz import build as _build_au
    au = _build_au()
    print(f"wrote {au}\nopen it:  open {out}")
