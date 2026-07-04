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

from arc.select_solver import fg_objects                        # 전경 object 추출(predefined)

# 선택(selection)에 쓰는 수치 property — role(extremum)을 이 위에서 도출한다.
_NUM_PROPS = {
    "area": lambda o: o["area"],
    "height": lambda o: (max(o["rows"]) - min(o["rows"]) + 1) if o.get("rows") else 0,
    "width": lambda o: (max(o["cols"]) - min(o["cols"]) + 1) if o.get("cols") else 0,
}


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


def _synth_contents_select(train, outs):
    """선택형 합성: 출력이 1×1 이고 그 색 = 입력 전경 object 중 어떤 extremum role
    (max/min of area·height·width)의 색. 그 role 을 pair 간 일반화(구조 불변)해 찾는다.
    표면값(색·object)은 pair 마다 달라도 '가장 큰 것의 색' 이라는 *구조*가 공통이면 규칙."""
    if not all(len(o) == 1 and len(o[0]) == 1 for o in outs):
        return None                                # 지금은 1×1 출력만
    per = []
    for p in train:
        objs = fg_objects(p["input"], "G0")
        if not objs:
            return None
        per.append(objs)
    tgt = [o[0][0] for o in outs]                   # 각 pair 의 출력 색
    for pname, key in _NUM_PROPS.items():
        for direction in ("max", "min"):
            pick = max if direction == "max" else min
            if all(pick(per[i], key=key)["color"] == tgt[i] for i in range(len(train))):
                return ("select", {"prop": pname, "dir": direction})  # emit = 1×1 of color
    return None


# object 를 grid 코너에 정렬하는 목적지 top-left (grid H,W · object h,w). 전수 탐색으로
# pair 간 일관된 코너를 찾는다(워크스루 Problem B 의 "우하단 정렬" = 코너 전수의 생존자).
_CORNERS = {
    "top-left":     lambda H, W, h, w: (0, 0),
    "top-right":    lambda H, W, h, w: (0, W - w),
    "bottom-left":  lambda H, W, h, w: (H - h, 0),
    "bottom-right": lambda H, W, h, w: (H - h, W - w),
}


def _bg(grid):
    from collections import Counter
    return Counter(v for row in grid for v in row).most_common(1)[0][0]


def _single_fg(grid):
    objs = fg_objects(grid, "G")
    return objs[0] if len(objs) == 1 else None


def _bbox(o):
    r0, c0 = min(o["rows"]), min(o["cols"])
    return r0, c0, max(o["rows"]) - r0 + 1, max(o["cols"]) - c0 + 1


def _rel_shape(o):
    r0, c0 = min(o["rows"]), min(o["cols"])
    return frozenset((r - r0, c - c0) for (r, c) in o["cells"])


def _synth_contents_move(train, ins, outs):
    """이동형: 각 pair 에 전경 object 1개, 입력→출력이 같은 shape·color 의 translation.
    출력 object 의 위치를 grid 코너 정렬로 pair 간 일반화(우하단 등). 표면 좌표는 pair
    마다 달라도 '어느 코너에 붙는다'는 구조가 공통이면 규칙(structure mapping)."""
    if not all(grid_size(o) == grid_size(i) for i, o in zip(ins, outs)):
        return None                                # size 보존형만
    per = []
    for p in train:
        io, oo = _single_fg(p["input"]), _single_fg(p["output"])
        if io is None or oo is None:
            return None
        if io["color"] != oo["color"] or _rel_shape(io) != _rel_shape(oo):
            return None                            # 같은 모양·색(translation)만
        H, W = grid_size(p["input"])
        _r, _c, h, w = _bbox(io)
        per.append((H, W, h, w, (min(oo["rows"]), min(oo["cols"]))))
    for name, fn in _CORNERS.items():
        if all(fn(H, W, h, w) == dest for (H, W, h, w, dest) in per):
            return ("move", {"anchor": name})
    return None


def _synth_contents_recolor_rank(train, ins, outs):
    """순위 재채색: 각 object 를 그 자리에서 색만 바꾼다. 새 색 = object 의 *순위*
    (property 로 정렬한 rank). "longest" DSL 없이 object 간 비교로 rank 를 도출하고,
    rank→color 매핑을 pair 간 일반화(표면 막대·높이는 달라도 'k번째로 긴 것=색k' 구조
    공통) = 08ed6ac7. size 보존형만."""
    if not all(grid_size(o) == grid_size(i) for i, o in zip(ins, outs)):
        return None
    per = []
    for p in train:
        objs = fg_objects(p["input"], "G")
        if len(objs) < 2:
            return None
        out = p["output"]
        recolored = []
        for o in objs:
            cols = {out[r][c] for (r, c) in o["cells"]}
            if len(cols) != 1:
                return None                        # object 가 통째로 한 색으로 recolor 돼야
            recolored.append((o, next(iter(cols))))
        per.append(recolored)
    for pname, key in _NUM_PROPS.items():
        for direction in ("desc", "asc"):
            mapping, ok = {}, True
            for recolored in per:
                order = sorted((o for o, _ in recolored), key=key,
                               reverse=(direction == "desc"))
                rank = {id(o): i + 1 for i, o in enumerate(order)}
                for o, newcol in recolored:
                    r = rank[id(o)]
                    if mapping.get(r, newcol) != newcol:   # rank→color 매핑 pair 간 일관?
                        ok = False
                        break
                    mapping[r] = newcol
                if not ok:
                    break
            if ok and len(mapping) >= 2:
                return ("recolor-rank", {"prop": pname, "dir": direction, "map": mapping})
    return None


def _rel_contents(train, ins, outs):
    if all(o == i for i, o in zip(ins, outs)):
        return ("identity",)                       # 출력 = 입력 (복사)
    if all(o == outs[0] for o in outs):
        return ("const", outs[0])                  # 출력이 pair 간 동일 (easy000a)
    sel = _synth_contents_select(train, outs)       # 선택형 (made000a: 가장 큰 색)
    if sel:
        return sel
    mv = _synth_contents_move(train, ins, outs)     # 이동형 (made000b: 우하단 정렬)
    if mv:
        return mv
    rk = _synth_contents_recolor_rank(train, ins, outs)   # 순위 재채색 (08ed6ac7)
    if rk:
        return rk
    return None                                    # 여전히 미해소 → 다음 (회전/반사 등)


def generalize(train):
    """train: [{input, output}]. per-property 관계를 pair 간 일반화 → program dict.
    각 값: ('identity',) | ('const', v) | None(미해소=합성 필요)."""
    ins = [p["input"] for p in train]
    outs = [p["output"] for p in train]
    return {"size": _rel_size(ins, outs),
            "color": _rel_color(ins, outs),
            "contents": _rel_contents(train, ins, outs)}


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
    if c[0] == "select":                           # 전경 extremum object 의 색 → 1×1
        objs = fg_objects(test_input, "G0")
        if not objs:
            return None
        key = _NUM_PROPS[c[1]["prop"]]
        chosen = (max if c[1]["dir"] == "max" else min)(objs, key=key)
        return [[chosen["color"]]]
    if c[0] == "move":                             # object 를 코너로 이동(입력 seed → 재배치)
        io = _single_fg(test_input)
        if io is None:
            return None
        H, W = grid_size(test_input)
        r0, c0, h, w = _bbox(io)
        dr, dc = _CORNERS[c[1]["anchor"]](H, W, h, w)
        out = [[_bg(test_input)] * W for _ in range(H)]
        for (r, cc) in io["cells"]:
            out[dr + (r - r0)][dc + (cc - c0)] = io["color"]
        return out
    if c[0] == "recolor-rank":                     # object 를 순위대로 재채색(입력 seed)
        objs = fg_objects(test_input, "G")
        if not objs:
            return None
        order = sorted(objs, key=_NUM_PROPS[c[1]["prop"]],
                       reverse=(c[1]["dir"] == "desc"))
        out = [row[:] for row in test_input]
        for i, o in enumerate(order):
            newcol = c[1]["map"].get(i + 1)
            if newcol is None:
                return None
            for (r, cc) in o["cells"]:
                out[r][cc] = newcol
        return out
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
        if rel[0] == "select":
            return f"select {rel[1]['dir']}({rel[1]['prop']}) → color (1×1)"
        if rel[0] == "move":
            return f"move object → {rel[1]['anchor']} corner"
        if rel[0] == "recolor-rank":
            return f"recolor by rank({rel[1]['dir']} {rel[1]['prop']}) → {rel[1]['map']}"
        return str(rel)
    return {k: d(prog.get(k)) for k in ("size", "color", "contents")}
