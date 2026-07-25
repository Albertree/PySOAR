# -*- coding: utf-8 -*-
"""arbor.reasoning.transform — 좌표식 변환 탐색 (rotate/flip/move 통합, 1차 통합).

원리(spec 2026-07-25): 같은 색 픽셀 대응에서 **하나의 공통 좌표식** `r'=F(r,c), c'=G(r,c)` 를
primitive 조합으로 탐색해 창발시킨다. 회전축·중심은 식의 상수/객체 bbox 원자에 인코딩된다(별도로 구하지 않음).

- 원자: per-pixel `r,c` + 객체 bbox `r0,c0,r1,c1,h,w` + grid `H,W` + 상수. 연산 `+,-,*,//`(중심 `(r0+r1)//2` 필수).
- 검증: 후보 `(F,G)` 를 각 색 입력셀에 적용 → 같은 색 출력셀과 **set 일치**, 전 train 쌍 공통.
- 채택: 일반성 tier(객체위치>크기>격자>상수) 우선, 그 안에서 단순성. test 입력에 적용해 답 격자 산출.

⚠️ 1차 통합 한계(후속): figure/ground 를 최빈색=배경 휴리스틱으로 가른다(§no-arbitrary-filters 완전준수는
후속에서 spelke/bounded 로). 단색 검출은 되나 다색 객체 검출은 미해결(spec §9).
"""
from __future__ import annotations

import re
from collections import Counter

_OPS = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b), ("*", lambda a, b: a * b),
        ("//", lambda a, b: (a // b) if b else None)]
_MAX_OPS = 2
_CONST_MAX = 8
_ATOMS = ["r", "c", "H", "W", "r0", "c0", "r1", "c1", "h", "w"] + [str(k) for k in range(_CONST_MAX + 1)]

_TOK = re.compile(r"r0|c0|r1|c1|[HWhwrc]|\d+")


def _tier(name: str) -> int:
    """일반성 tier(낮을수록 우선): 0=객체위치 · 1=객체크기 · 2=격자 · 3=상수."""
    toks = _TOK.findall(name)
    if any(t in ("r0", "c0", "r1", "c1") for t in toks):
        return 0
    if any(t in ("h", "w") for t in toks):
        return 1
    if any(t in ("H", "W") for t in toks):
        return 2
    return 3


def _gen_exprs():
    """primitive 원자에서 ≤_MAX_OPS 이항연산(좌결합) 표현식 전부. [(name, fn(env))]. 결정적."""
    base = [(n, (lambda d, n=n: d[n])) for n in _ATOMS]
    exprs = dict(base)
    frontier = list(base)
    for _ in range(_MAX_OPS):
        nxt = []
        for en, ef in frontier:
            for an, af in base:
                for osym, ofn in _OPS:
                    nm = f"({en}{osym}{an})"
                    if nm in exprs:
                        continue

                    def fn(d, ef=ef, af=af, ofn=ofn):
                        x = ef(d)
                        if x is None:
                            return None
                        y = af(d)
                        if y is None:
                            return None
                        return ofn(x, y)
                    exprs[nm] = fn
                    nxt.append((nm, fn))
        frontier = nxt
    return sorted(exprs.items())


_EXPRS = None   # 지연 생성(모듈 import 비용 회피)


def _exprs():
    global _EXPRS
    if _EXPRS is None:
        _EXPRS = _gen_exprs()
    return _EXPRS


def _bg(grid):
    return Counter(v for row in grid for v in row).most_common(1)[0][0]


def _by_color(grid, bg):
    m = {}
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v != bg:
                m.setdefault(v, []).append((r, c))
    return m


def _env(r, c, H, W, obj):
    d = {"r": r, "c": c, "H": H, "W": W}
    d.update({str(k): k for k in range(_CONST_MAX + 1)})
    if obj:
        d.update(obj)
    return d


def _bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    r0, c0, r1, c1 = min(rs), min(cs), max(rs), max(cs)
    return {"r0": r0, "c0": c0, "r1": r1, "c1": c1, "h": r1 - r0 + 1, "w": c1 - c0 + 1}


def find_formula(train):
    """train=[(gin,gout),...]. 전 쌍·전 색에 공통인 (row_expr, col_expr) 생존자를 tier·단순성순으로.
    반환 [(name_row, name_col, Fr, Fc)]. 없으면 []."""
    ctx = []
    for gin, gout in train:
        H, W = len(gin), len(gin[0])
        bi = _bg(gin)
        cin = {col: cells for col, cells in _by_color(gin, bi).items()}
        cout = {col: set(cells) for col, cells in _by_color(gout, _bg(gout)).items()}
        allc = [cell for cs in cin.values() for cell in cs]
        obj = _bbox(allc) if allc else None
        ctx.append((H, W, cin, cout, obj))

    def axis_ok(Fe, ax):
        for H, W, cin, cout, obj in ctx:
            for col, cells in cin.items():
                oc = cout.get(col)
                if oc is None or len(oc) != len(cells):
                    return False
                pred = [Fe(_env(r, c, H, W, obj)) for (r, c) in cells]
                if any(x is None for x in pred):
                    return False
                if sorted(pred) != sorted(p[ax] for p in oc):
                    return False
        return True

    rows = [(n, f) for n, f in _exprs() if axis_ok(f, 0)]
    cols = [(n, f) for n, f in _exprs() if axis_ok(f, 1)]
    surv = []
    for rn, Fr in rows:
        for cn, Fc in cols:
            ok = True
            for H, W, cin, cout, obj in ctx:
                for col, cells in cin.items():
                    pred = set()
                    for (r, c) in cells:
                        e = _env(r, c, H, W, obj)
                        rr, cc = Fr(e), Fc(e)
                        if rr is None or cc is None or not (0 <= rr < H and 0 <= cc < W):
                            ok = False
                            break
                        pred.add((rr, cc))
                    if not ok or pred != cout.get(col, set()):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                surv.append((rn, cn, Fr, Fc))
    surv.sort(key=lambda t: (_tier(t[0]) + _tier(t[1]), len(t[0]) + len(t[1]), t[0], t[1]))
    return surv


def apply_formula(Fr, Fc, gin):
    """식을 입력 격자의 비배경 셀에 적용해 예측 출력 격자. 충돌/범위이탈이면 None."""
    H, W = len(gin), len(gin[0])
    bi = _bg(gin)
    cin = _by_color(gin, bi)
    allc = [cell for cs in cin.values() for cell in cs]
    obj = _bbox(allc) if allc else None
    out = [[bi] * W for _ in range(H)]
    seen = set()
    for col, cells in cin.items():
        for (r, c) in cells:
            e = _env(r, c, H, W, obj)
            rr, cc = Fr(e), Fc(e)
            if rr is None or cc is None or not (0 <= rr < H and 0 <= cc < W) or (rr, cc) in seen:
                return None
            seen.add((rr, cc))
            out[rr][cc] = col
    return out


def solve_by_transform(train, test_input):
    """train 으로 좌표식을 찾아 test_input 에 적용한 답 격자. 없으면 None.
    상위 tier 후보를 순서대로 시도해 첫 유효(충돌 없는) 예측을 반환(결정적)."""
    surv = find_formula(train)
    for _rn, _cn, Fr, Fc in surv:
        pred = apply_formula(Fr, Fc, test_input)
        if pred is not None:
            return pred
    return None
