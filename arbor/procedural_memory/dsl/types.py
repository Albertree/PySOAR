# -*- coding: utf-8 -*-
"""
DSL 타입 어휘 (LEGEND) — 이 시스템의 모든 DSL(property/relation/selection/transformation/util)이
주고받는 값의 타입을 **한 곳에** 정의한다. 각 DSL 페이지를 뒤지지 않고 여기서 전체 타입을 본다.

    python -m arbor.procedural_memory.dsl.types      # 레전드 + 실제 사용 현황 출력

5 구역:
  LAYER       ARCKG 노드 계층 (in 의 대상; grid 는 transformation 의 out 값이기도)
  VALUE       property 가 노드에서 꺼내는 값 (scalar · compound · collection-of-value · opaque)
  COLLECTION  노드의 모음 (list[T] · scope)
  RESULT      연산 결과 (compare → receipts)
  PARAM       DSL 인자 전용 (predicate · node)
"""
from __future__ import annotations

# ── LAYER: ARCKG 5계층 ──────────────────────────────────────
LAYERS = {
    "task":   "최상위 태스크 노드",
    "pair":   "example/test 쌍 노드",
    "grid":   "격자 노드 (input/output). transformation 의 out 값이기도(변환된 격자)",
    "object": "격자 내 연결성분 객체",
    "pixel":  "단일 셀",
}

# ── VALUE: property 가 노드에서 꺼내는 값 ────────────────────
VALUES = {
    "number":         "정수 — area·height·width·row·col·count",
    "color":          "색 값 0..9 (number 와 별개)",
    "boolean":        "참/거짓 — 대칭축",
    "symbol":         "열거 라벨 — 계층명(type_of)·example/test·input/output(subtype_of)",
    "coordinate":     "{row, col} 단일 위치 → row_of / col_of",
    "size":           "{height, width} → height_of / width_of",
    "color_set":      "{0..9: bool} 색 presence (= set of color)",
    "coordinate_set": "[[r,c], ..] (= set of coordinate)",
    "class":          "불투명 구조값 — 2D배열(contents·shape) · 다필드 번들(position·symmetry·role)",
}

# ── COLLECTION: 노드의 모음 ─────────────────────────────────
COLLECTIONS = {
    "list[T]": "T 계층 노드의 순서있는 목록 (T = task/pair/grid/object/pixel/node)",
    "scope":   "선택된 노드 범위 — select 산출 · compare/filter_ 입력",
}

# ── RESULT: 연산 결과 ───────────────────────────────────────
RESULTS = {
    "receipts": "compare 결과 — COMM/DIFF 비교 영수증",
}

# ── PARAM: DSL 인자 전용 ────────────────────────────────────
PARAMS = {
    "predicate": "술어 — 노드→bool 조건 (select / filter_ 인자)",
    "node":      "임의 계층 노드 — select / elements_at 의 앵커",
}

GROUPS = [("LAYER", LAYERS), ("VALUE", VALUES), ("COLLECTION", COLLECTIONS),
          ("RESULT", RESULTS), ("PARAM", PARAMS)]

_BASE = set(LAYERS) | set(VALUES) | set(RESULTS) | set(PARAMS) | {"scope"}


def is_known(t: str) -> bool:
    """타입 문자열이 어휘 안인가. 유니온(a|b)·list[T] 를 재귀 처리."""
    t = t.strip()
    if "|" in t:
        return all(is_known(p) for p in t.split("|"))
    if t.startswith("list[") and t.endswith("]"):
        inner = t[5:-1]
        return inner == "node" or inner in LAYERS
    return t in _BASE


def scan_specs() -> dict:
    """SPECS → {type: {'out':[dsl..], 'in':[dsl..]}}. in/out 양쪽 사용을 모은다."""
    from arbor.procedural_memory.dsl.registry import SPECS
    use: dict = {}
    for name, s in SPECS.items():
        for t in str(s.get("out", "")).split("|"):
            use.setdefault(t.strip(), {"out": [], "in": []})["out"].append(name)
        for t in s.get("in", []):
            use.setdefault(t.strip(), {"out": [], "in": []})["in"].append(name)
    return use


def _report() -> str:
    L = ["=" * 72, "DSL 타입 어휘 (LEGEND)", "=" * 72]
    for gname, members in GROUPS:
        L.append(f"\n[{gname}]")
        for t, desc in members.items():
            L.append(f"  {t:16} {desc}")
    use = scan_specs()
    L.append("\n" + "=" * 72)
    L.append("실제 사용 현황 (SPECS in/out)")
    L.append("=" * 72)
    for t in sorted(use):
        outs, ins = sorted(set(use[t]["out"])), sorted(set(use[t]["in"]))
        flag = "" if is_known(t) else "   <<< 어휘밖!"
        L.append(f"  {t:16}{flag}")
        if outs:
            L.append(f"       ← 산출: {', '.join(outs)}")
        if ins:
            L.append(f"       → 소비: {', '.join(ins)}")
    unknown = [t for t in use if not is_known(t)]
    L.append("\n" + ("모든 타입이 어휘 안 (OK)" if not unknown
                     else f"어휘밖 타입: {', '.join(sorted(unknown))}"))
    return "\n".join(L)


if __name__ == "__main__":
    print(_report())
