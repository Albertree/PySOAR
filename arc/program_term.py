# -*- coding: utf-8 -*-
"""
program_term -- PROTOTYPE (2026-07-13, seokki-windows). "program 을 nested-dict TERM
으로 올리면 compare/anti-unification 에 물린다"는 사용자 제안의 실현.

세 조각, 전부 **정직**(§1-5):
  1. observed_program(G0,G1) -- 한 pair 의 G0->G1 을 *관측만*으로 재구성한 program 소스.
     바뀐 셀을 목표색별로 묶어 coloring 스텝으로. 코너/순위/extremum 같은 정답 템플릿을
     전혀 모른다 -- compare(G0,G1) 를 실행가능 형태로 물질화한 것뿐.
  2. lift(code)  -- 그 소스를 **python `ast`** 로 파싱해, DSL 호출부만 nested-dict TERM 으로
     (사용자 제안: "실질적인 부분만 ast로"). term = {"op":sym,"args":[...]} · leaf = {"lit":v}.
  3. au_n(terms) -- N 개 program-term 의 **first-order anti-unification**(Plotkin/Reynolds의
     least general generalization): 같은 op·arity면 골격 유지+재귀, 다르면 **변수**. 변수는
     그 자리의 per-pair 구체값을 기록 -> 이후 resolve(표현식 탐색)의 대상.

anti-unifier 는 아무 도메인 지식이 없다. 추상화는 **오직 두 실제 program 이 같은/다른 위치**
에서 나온다 -- relation_solve 의 template-finder 와 정반대. 실행: `python arc/program_term.py`.
"""
from __future__ import annotations

import ast
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root


# --- 1. per-pair program: 관측만으로 G0->G1 재구성 -----------------------------
def _bg(grid):
    return Counter(v for row in grid for v in row).most_common(1)[0][0]


def observed_program(g0, g1):
    """G0->G1 을 재현하는 program 소스. 크기 보존이면 input 을 seed 로 바뀐 셀만 칠하고,
    크기가 바뀌면 make_grid(배경) 위에 비배경 셀을 칠한다. 목표색별로 coloring 스텝."""
    H0, W0 = len(g0), len(g0[0])
    H1, W1 = len(g1), len(g1[0])
    groups: dict = {}
    if (H0, W0) == (H1, W1):
        seed = "input_grid"
        for r in range(H1):
            for c in range(W1):
                if g1[r][c] != g0[r][c]:                 # 관측된 변화 = compare(G0,G1) at PIXEL
                    groups.setdefault(g1[r][c], []).append([r, c])
    else:
        bg = _bg(g1)
        seed = f"make_grid({H1}, {W1}, {bg})"
        for r in range(H1):
            for c in range(W1):
                if g1[r][c] != bg:
                    groups.setdefault(g1[r][c], []).append([r, c])
    lines = [f"t0 = {seed}"]
    k = 0
    for t in sorted(groups):                             # 목표색 오름차순 = 결정적 스텝 순서
        k += 1
        lines.append(f"t{k} = coloring(t{k - 1}, {groups[t]}, {t})")
    lines.append(f"output_grid = t{k}")
    return "\n".join(lines)


# --- 2. lift: python ast -> nested-dict TERM (실질적인 호출부만) ----------------
def _expr_to_term(node, env):
    if isinstance(node, ast.Name):
        if node.id == "input_grid":
            return {"op": "input", "args": []}
        return env.get(node.id, {"op": node.id, "args": []})   # 중간변수 tK 를 인라인
    if isinstance(node, ast.Call):
        return {"op": node.func.id, "args": [_expr_to_term(a, env) for a in node.args]}
    return {"lit": ast.literal_eval(node)}                # 상수 인자(셀목록·색·치수)


def lift(code):
    """observed_program 소스를 파싱해 output_grid 를 nested-dict TERM 으로 (tK 대입 인라인)."""
    env, out = {}, None
    for stmt in ast.parse(code).body:
        if isinstance(stmt, ast.Assign):
            name = stmt.targets[0].id
            env[name] = _expr_to_term(stmt.value, env)
            if name == "output_grid":
                out = env[name]
    return out


# --- 3. anti-unification (n-항, least general generalization) -------------------
def au_n(terms, counter, subst):
    """terms: 같은 위치의 서브텀 N개. 전부 같으면 그대로(COMM). 전부 같은 op·arity면 골격
    유지+각 인자 재귀. 아니면 **변수** 도입하고 per-pair 값 기록(=이후 resolve 대상)."""
    first = terms[0]
    if all(t == first for t in terms):
        return first                                     # COMM: 완전히 동일한 서브트리
    if (all(isinstance(t, dict) and "op" in t for t in terms)
            and all(t["op"] == first["op"] for t in terms)
            and all(len(t["args"]) == len(first["args"]) for t in terms)):
        return {"op": first["op"],
                "args": [au_n([t["args"][i] for t in terms], counter, subst)
                         for i in range(len(first["args"]))]}
    name = f"?{counter[0]}"                               # DIFF: 골격이 갈리는 지점 = 변수
    counter[0] += 1
    subst[name] = list(terms)
    return {"var": name}


def anti_unify(terms):
    counter, subst = [1], {}
    g = au_n(terms, counter, subst)
    return g, subst


# --- 실행: 생성된 program 을 frozen DSL 로 돌려 출력 격자를 얻는다 -----------------
def execute(code, input_grid):
    """program 소스를 frozen make_grid/coloring 로 exec → output_grid. 관측에서 지은
    program 이 정말 G0->G1 을 재현하는지 검증하는 데 쓴다."""
    import arc.dsl as _dsl                                   # sys.path 에 frozen DSL 경로 세팅
    from procedural_memory.DSL.make_grid import make_grid    # frozen (height,width,color)
    ns = {"input_grid": [row[:] for row in input_grid],
          "make_grid": make_grid, "coloring": _dsl.coloring}
    exec(code, ns)                                           # noqa: S102 (신뢰된 자체생성 코드)
    return ns.get("output_grid")


# --- 표시 --------------------------------------------------------------------
def term_to_str(t):
    if "var" in t:
        return t["var"]
    if "lit" in t:
        v = t["lit"]
        if isinstance(v, list):
            return f"[{len(v)} cells]" if v and isinstance(v[0], list) else repr(v)
        return repr(v)
    if t["op"] == "input":
        return "input"
    return f'{t["op"]}(' + ", ".join(term_to_str(a) for a in t["args"]) + ")"


def _val_str(t):
    if isinstance(t, dict) and "lit" in t and isinstance(t["lit"], list) \
            and t["lit"] and isinstance(t["lit"][0], list):
        return f"[{len(t['lit'])} cells]"
    return term_to_str(t) if isinstance(t, dict) else repr(t)


# --- 데모: 사다리 태스크에 실제로 돌린다 ---------------------------------------
def _load_ladder():
    from arc.dataset import list_tasks
    found = {}
    ea = dict(list_tasks("easy_a"))
    if "easy000a" in ea:
        found["easy000a"] = ea["easy000a"]
    for n in ("made000a", "made000b"):
        p = os.path.join(os.path.dirname(__file__), "data", "made", f"{n}.json")
        if os.path.exists(p):
            found[n] = p
    agi = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_AGI")
    for n in ("08ed6ac7", "0ca9ddb6"):
        hits = glob.glob(os.path.join(agi, "**", f"{n}.json"), recursive=True)
        if hits:
            found[n] = hits[0]
    return found


def main():
    for name, path in _load_ladder().items():
        task = json.load(open(path))
        print("=" * 78)
        print(f"{name}  ({len(task['train'])} train pairs)")
        progs = [observed_program(p["input"], p["output"]) for p in task["train"]]
        terms = [lift(code) for code in progs]
        for i, code in enumerate(progs):
            flat = code.replace("\n", "  ")
            print(f"  pair{i} program: {flat[:110]}{'…' if len(flat) > 110 else ''}")
        g, subst = anti_unify(terms)
        print(f"  ── anti-unified schema ──")
        print(f"    {term_to_str(g)}")
        if subst:
            print(f"  variables (DIFF slots → resolve 대상):")
            for v, vals in subst.items():
                print(f"    {v} = " + " | ".join(_val_str(x) for x in vals))
        else:
            print("  (변수 없음 — 두 program 이 구조적으로 동일 = 순수 COMM)")


if __name__ == "__main__":
    main()
