# -*- coding: utf-8 -*-
"""
relation_solve -- structure-mapping 관점의 풀이 토대.

원칙(사용자 설계):
  - 출력을 무에서 생성하지 않는다. 출력 = **입력 G0 를 seed 로 관계(relation)를 적용**한 것.
  - 관계는 pair 안 (G0,G1) 의 property 비교(compare)를 DSL 조합으로 표현한 것.
  - 여러 pair 의 관계를 비교해 **표면값이 달라도 구조가 공통**인 것을 찾으면 그게 규칙
    (structure mapping / anti-unify). 공통 프로그램을 조합공간에서 찾는 것 = program synthesis.

이 모듈은 그 토대를 GRID 3속성(size·color·contents) 단위로 놓는다:
각 속성의 관계를 pair 간 일반화해 프로그램을 만든다. 지금 다루는 관계 종류:
  identity  -- 그 속성이 입력에서 보존됨 (COMM). 예: made000b 는 색·크기 보존.
  const     -- pair 무관 상수 (예: easy000a 는 출력 격자가 pair 간 완전히 같다).
  None      -- 아직 이 종류로는 못 잡음 = 합성(조합탐색) 필요 (contents 가 대부분 여기).
contents 가 정해지면 격자 전체가 정해진다(size/color 는 그 파생·narrowing 용).
"""
from __future__ import annotations


def grid_size(g):
    return (len(g), len(g[0]) if g else 0)


def grid_colors(g):
    return frozenset(v for row in g for v in row)


def _rel_size(ins, outs):
    if all(grid_size(o) == grid_size(i) for i, o in zip(ins, outs)):
        return ("identity",)                       # 출력 크기 = 입력 크기 (보존)
    if all(grid_size(o) == grid_size(outs[0]) for o in outs):
        return ("const", grid_size(outs[0]))       # pair 무관 상수 크기
    return None


def _rel_color(ins, outs):
    if all(grid_colors(o) == grid_colors(i) for i, o in zip(ins, outs)):
        return ("identity",)                       # 색집합 보존
    if all(grid_colors(o) == grid_colors(outs[0]) for o in outs):
        return ("const", sorted(grid_colors(outs[0])))
    return None


def _rel_contents(ins, outs):
    if all(o == i for i, o in zip(ins, outs)):
        return ("identity",)                       # 출력 = 입력 (복사)
    if all(o == outs[0] for o in outs):
        return ("const", outs[0])                  # 출력이 pair 간 동일 (easy000a)
    return None                                    # 합성 필요 (made/08ed6ac7 의 contents)


def generalize(train):
    """train: [{input, output}]. per-property 관계를 pair 간 일반화 → program dict.
    각 값: ('identity',) | ('const', v) | None(미해소=합성 필요)."""
    ins = [p["input"] for p in train]
    outs = [p["output"] for p in train]
    return {"size": _rel_size(ins, outs),
            "color": _rel_color(ins, outs),
            "contents": _rel_contents(ins, outs)}


def is_complete(prog):
    """contents 가 정해지면 격자가 완전히 정해진다(size/color 는 파생)."""
    return prog.get("contents") is not None


def apply(prog, test_input):
    """일반화된 관계를 test 입력에 적용 → 출력 격자. 미완이면 None."""
    c = prog.get("contents")
    if c is None:
        return None
    if c[0] == "identity":
        return [row[:] for row in test_input]      # 입력 seed 를 그대로
    if c[0] == "const":
        return [row[:] for row in c[1]]
    return None


def describe(prog):
    """대시보드 패널용: 각 속성의 관계를 사람이 읽는 문자열로."""
    def d(rel):
        if rel is None:
            return "미해소 (합성 필요)"
        if rel[0] == "identity":
            return "identity (입력 보존)"
        if rel[0] == "const":
            v = rel[1]
            return f"const {v if not isinstance(v, list) or len(v) < 6 else '격자'}"
        return str(rel)
    return {k: d(prog.get(k)) for k in ("size", "color", "contents")}
