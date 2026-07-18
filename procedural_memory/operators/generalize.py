# -*- coding: utf-8 -*-
"""ARBOR operator body: generalize (anti-unification, procedural LTM leaf).

per-pair `PAIR.program`(AST) 들을 anti-unify 해 `TASK.solution`(골격 + 변수 slot)을 물질화한다.
COMM=상수 고정, DIFF=변수 slot(per-pair 값=근거). resolve(G0 유래 식)는 다음 operator. (§0.5·§2-2)

Task 8 보강: op 수 불일치로 antiunify_ast 가 (None,None) 을 내면, 정직히 실패하기 전에
`compressible`(레거시 antiunify.py 재사용 — 그 함수는 flat 텍스트 program 을 받으므로 `as_source`
로 렌더한 표현을 넘긴다)로 compress 신호 여부를 판정한다. 이 신호(needs-compress)가 없으면
compress operator 가 발화하지 않아 blob(object-level) program 이 만들어지지 않고, made000b 같은
op-수-불일치 태스크의 generalize 가 영구 실패한다(§2-5 행동보존).

브랜치리뷰(Task4 이후) 보강: pixel coloring 이 ref("coord",[r,c]) 리터럴로도 emit 되면서, `compressible`
가 쓰는 flat-텍스트 정규식(VAR.coord 형만 인식)이 coord 리터럴을 못 잡아 op-수-불일치 flat 재채색
태스크가 needs-compress 없이 곧장 generalized:failed 로 떨어지는 공백이 생겼다(§2b 위반). AST 는 이미
coord-aware(ops_of_ast)이므로, flat(non-grid) asts 의 op 수는 그 결과를 문자열로 되돌리지 않고 직접
비교한다(`flat_mismatch`) — compressible/grid_mismatch 는 그대로 두고 OR 로만 보강.
"""
from __future__ import annotations

import json
from arbor.reasoning.antiunify import compressible
from arbor.reasoning.program_ast import antiunify_ast, as_source


def _all_pixel_residual(asts):
    """모든 ast 가 grid>pixel(contents=nested pixel coloring) 인가 — 아직 blob 화 전(낱개 픽셀 잔여)."""
    from arbor.reasoning.program_ast import _is_grid_body
    if not asts:
        return False
    for a in asts:
        body = a.get("body") or []
        if not _is_grid_body(body):
            return False
        inner = None
        for s in body:
            if s.get("call") == "set_grid_contents":
                leaf = s["args"]["contents"]
                inner = (leaf.get("program") or {}).get("body") if "program" in leaf else None
        if not (inner and all(x["args"]["target"].get("ref") in ("pixel", "coord") for x in inner)):
            return False
    return True


def _train_all_moves(ag):
    """모든 train pair 가 객체 이동(같은 모양·색·다른 위치)을 포함하는가 (대응 존재 여부)."""
    from procedural_memory.operators.compress import _object_moves
    train = ag.task.get("train") or []
    return bool(train) and all(_object_moves(e["input"], e["output"]) for e in train)


def _op_generalize(ag):
    sid = ag.stack[-1].id
    root = ag.kg.get("arckg_root")
    if root is None:
        ag.wm.add(sid, "generalized", "failed")
        return
    tid = root.node_id
    # 존재하는 example-pair program(AST-json)들을 순서대로 수집 (+ compressible 용 flat 표현)
    asts, progs = [], []
    for p in getattr(root, "example_pairs", []) or []:
        ppid = f"{p.node_id}.property"
        v = next((v for (i, a, v) in ag.wm if i == ppid and a == "grouping"), None)   # 있으면 객체 grouping
        if v in (None, "{}"):
            v = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)  # 없으면 픽셀 program
        if v in (None, "{}"):
            continue
        progs.append(as_source(v))            # compressible() 은 레거시 flat 텍스트를 받는다
        try:
            ast = json.loads(v)
        except (ValueError, TypeError):
            continue
        if ast and ast.get("body"):
            asts.append(ast)
    # ── 이동 preempt (mism 무관): grid>pixel 낱개-픽셀 잔여인데 train 이 객체 이동이면, per-pixel
    #    anti-unify(강체 이동을 못 잡아 과적합; move000g/i/m/p) 대신 compress(전체객체 복원)로 라우팅.
    #    한 번만(compressed 가드). 이동 아니면(대응 없음) 기존 per-pixel 경로 유지.
    if (not ag.wm.contains(sid, "compressed", "yes")
            and _all_pixel_residual(asts) and _train_all_moves(ag)):
        ag.wm.add(sid, "needs-compress", "yes")
        return
    # 이동(move) 프로그램이면 cellset 을 const 로 굽지 않고 항상 slot 화(train 우연일치 방지): dest 가
    # 절대(공통 좌상단)여도 mover 모양은 test 마다 달라 move@anchor 로 일반화해야 함(am).
    # (color 강제 slot화는 보류: 배경색까지 slot 이 되면 version space 가 부풀어 3-try 안에 정답 조합을
    #  놓쳐 g/o/p/ah/ak 회귀. au 색-baking 은 '도착색만' 강제하는 수술적 수정 필요 — 후속.)
    sk, slots = antiunify_ast(asts, force_slots=_train_all_moves(ag))
    if sk is None:                                        # 구조 불일치/부족
        # op 수 불일치(객체 크기 차이 등)면 정직히 포기하기 전에 compress(덩어리화) 를 신호한다.
        # compress 가 blob 으로 재작성 → generalize 재발화 → blob anti-unify. 한 번만(compressed 가드).
        # grid-래핑(move 등) 이면 flat compressible() 이 못 읽으므로 inner(contents) op 수를 직접 비교.
        from arbor.reasoning.program_ast import grid_inner_op_counts, ops_of_ast, _is_grid_body
        inner = [grid_inner_op_counts(a) for a in asts]
        grid_mismatch = (all(x is not None for x in inner)
                         and len({x[0] for x in inner if x}) > 1)
        # flat(non-grid) 경로의 op 수 불일치는 AST 에서 직접 판정한다(coord-aware, §finding). 레거시
        # compressible(progs) 는 as_source 로 렌더된 flat 텍스트를 정규식(_STEP=VAR.coord 만 인식)으로
        # 파싱하므로 ref("coord",[r,c]) 리터럴(Task4 emit)은 못 잡아 op-수-달라도 False 를 냈다.
        # ops_of_ast 는 pixel(idx)·coord((r,c)) 를 문자열 재렌더 없이 그대로 세므로 그 공백을 메운다.
        flat_asts = [a for a in asts if not _is_grid_body(a.get("body") or [])]
        flat_counts = [len(ops_of_ast(a)) for a in flat_asts]
        flat_mismatch = len(flat_counts) > 1 and len(set(flat_counts)) > 1
        if not ag.wm.contains(sid, "compressed", "yes") and (compressible(progs) or grid_mismatch or flat_mismatch):
            ag.wm.add(sid, "needs-compress", "yes")
            return
        ag.wm.add(sid, "generalized", "failed")
        return
    sk_with = dict(sk); sk_with["slots"] = slots
    solution = json.dumps(sk_with)
    tpid = f"{tid}.property"
    old = next((v for (i, a, v) in ag.wm if i == tpid and a == "solution"), None)
    if old in (None, "{}"):
        ag.wm.remove(tpid, "solution", old)               # 실제 저장된 sentinel(None 또는 구 "{}") 제거
    ag.wm.add(tpid, "solution", solution)                 # TASK.solution 물질화(§2-5)
    for name, s in slots.items():                         # slot 근거 = DIFF per-pair 값
        ag.wm.add(tpid, "slot", f"{name}[{s['kind']}]=DIFF{s['values']}")
    ag.kg["solution"] = {"skeleton": sk, "slots": slots, "programs": asts, "tid": tid}
    ag.kg["generalize"] = {"solution": as_source(solution),   # 대시보드용은 flat 문자열
                           "slots": {n: s["values"] for n, s in slots.items()}}
    ag.wm.add(sid, "generalized", "yes")
