# -*- coding: utf-8 -*-
"""ARBOR perception.perception — 객체검출·대응(fg_correspondence)·scoring (focus_solver 분리)."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.reasoning.compare_engine import _compare


def _obj_cc(node):
    """ARCKG object node → (절대 셀 목록, 색). color dict 중 True 인 것이 그 object 색."""
    j = node.to_json()
    return [tuple(c) for c in j["coordinate"]], next((k for k, v in j["color"].items() if v), 0)


def objects_of(grid):
    """grid 의 객체 = **spelke 합집합**(4-conn 동색 ∪ 같은색 8-conn) — (셀목록, 색) 리스트.
    (2026-07-19 사용자) hodel·구 4-conn objects_of 를 폐지하고 spelke 원리로 통일. 배경 특권화·
    count/max 없음. 구현은 arbor.perception.spelke.spelke_union 로 위임."""
    from arbor.perception.spelke import spelke_union
    return spelke_union(grid)


def _fg_correspondence(ag, gid0, gid1, g0grid, g1grid):
    """G0 ↔ G1 object 를 유사도 greedy 1-1 대응(중복 없이). **색0 도 하나의 색**으로 포함하되,
    object 정의상 **단색 성분만** 쓴다(격자 전체 같은 비단색 복합노드는 제외 — '0=배경' 가정이 아니라
    '객체=한 색'이라는 원칙). 닫힌 내부영역=구멍(단색 색0)도 정당한 재채색 대상이 된다. 각 대응쌍의
    속성별 COMM/DIFF 도 반환 — 어떤 DSL 을 쓸지 **규칙이 판단**할 근거. 반환 = [(g0obj, g1obj, category)].
    (kg_compare 는 원자연산; 대응·COMM/DIFF 는 데이터, 조립·arg결정은 이후 **규칙**이 한다.)"""
    kg_compare = _compare              # 단일 진입점(노드→property·관계→agreement 자동분기)
    idx = ag.kg["idx"]; nodes = idx["nodes"]

    def _mono(o, grid):     # object 셀이 격자에서 실제로 한 색인가 — 비단색(격자/복합 노드)은 배제
        cells, _ = _obj_cc(nodes[o])
        cols = {grid[r][c] for (r, c) in cells if 0 <= r < len(grid) and 0 <= c < len(grid[0])}
        return len(cols) <= 1
    o0 = [o for o in idx["children"].get(gid0, []) if _mono(o, g0grid)]   # 0 도 색; 단색만
    o1 = [o for o in idx["children"].get(gid1, []) if _mono(o, g1grid)]
    scored = []
    for a in o0:
        for b in o1:
            rel = kg_compare(nodes[a], nodes[b])
            n, tot = _score_frac(rel["result"].get("score", "0/1"))
            scored.append((n / tot, a, b, rel["result"].get("category", {})))
    scored.sort(key=lambda x: -x[0])
    usedA, usedB, out = set(), set(), []
    for _s, a, b, cat in scored:
        if a in usedA or b in usedB:
            continue
        usedA.add(a); usedB.add(b); out.append((a, b, cat))
    return out


def _score_frac(s):
    """kg_compare result.score('n/total' = COMM수/전체속성) → (n, total). robust."""
    try:
        n, tot = str(s).split("/")
        return int(n), int(tot) or 1
    except Exception:                                              # noqa: BLE001
        return 0, 1
