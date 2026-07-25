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


# ── 선형(affine) 변환 탐색 (사용자 흐름 2026-07-26): 배경=0, 객체=비0. 같은 색 대응(color:COMM,
#    coord:DIFF)에서 좌표변환 공식을 찾는다. 회전·반전·이동은 전부 선형 `r'=a·r+b·c+e` (a,b∈{-1,0,1}
#    = +,-,* 조합) — 이걸 D4 8종으로 열거하고, 피벗(불변점)은 correspondence 가 밝히는 centroid 로.
#    train 은 자유 평행이동으로 D4 를 찾고(가설 여럿 OK), 다음 pair 가 좁힌다. test 는 centroid 로 배치.
_D4 = [("id", 1, 0, 0, 1), ("rot90", 0, 1, -1, 0), ("rot180", -1, 0, 0, -1), ("rot270", 0, -1, 1, 0),
       ("flipV", -1, 0, 0, 1), ("flipH", 1, 0, 0, -1), ("transpose", 0, 1, 1, 0), ("antitr", 0, -1, -1, 0)]


def _nonzero(grid):
    return {(r, c): v for r, row in enumerate(grid) for c, v in enumerate(row) if v != 0}


def _pivots2(cells):
    """피벗 후보(2배좌표): centroid(무게중심, 회전불변·입력계산) floor/ceil + bbox중심. 정수화 위해 2배."""
    cells = list(cells)
    n = len(cells)
    if n == 0:
        return set()
    sr = sum(r for r, _ in cells); sc = sum(c for _, c in cells)
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    prs = {(2 * sr) // n, -((-2 * sr) // n)}; pcs = {(2 * sc) // n, -((-2 * sc) // n)}
    cand = {(pr, pc) for pr in prs for pc in pcs}
    cand.add((min(rs) + max(rs), min(cs) + max(cs)))
    return cand


# 피벗 규칙 후보(이름 부여) — 강체변환(D4)의 불변점 가설. bbox중심을 앞에 둔다: 회전/반전은 도형의
# bounding box 를 그 상(image)의 bbox 로 옮기므로 bbox중심이 자연스러운 고정점(스파이크 2026-07-26 로
# 부류1 5문제 전부 train·test 정확재현 확인). centroid/그리드중심은 그다음 가설. 규칙을 **이름**으로 매기는
# 이유: pair 마다 셀·크기가 달라도 "같은 규칙"을 index 아닌 이름으로 정합시켜 train 검증한다.
def _pivot_named(cells, H, W):
    """규칙이름 → 2배피벗 dict. 각 pair 에서 같은 이름끼리 대조해 train 정확재현 규칙을 고른다."""
    cells = list(cells)
    n = len(cells)
    if n == 0:
        return {}
    sr = sum(r for r, _ in cells); sc = sum(c for _, c in cells)
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    rf, rc = (2 * sr) // n, -((-2 * sr) // n)       # centroid r floor/ceil
    cf, cc = (2 * sc) // n, -((-2 * sc) // n)       # centroid c floor/ceil
    return {
        "bbox": (min(rs) + max(rs), min(cs) + max(cs)),
        "cent_ff": (rf, cf), "cent_fc": (rf, cc), "cent_cf": (rc, cf), "cent_cc": (rc, cc),
        "grid": (H - 1, W - 1),
    }


_PIVOT_ORDER = ["bbox", "cent_ff", "cent_fc", "cent_cf", "cent_cc", "grid"]


def _verified_pivot_rule(ctx, train, M):
    """전 train pair 를 **정확히** 재현하는 피벗 규칙 이름을 우선순위대로 찾는다(없으면 None).
    _apply_pivot(입력, M, 규칙) == 출력 이 모든 pair 에서 성립해야 채택 — test 배치를 추측 아닌 검증으로."""
    for name in _PIVOT_ORDER:
        ok = True
        for (ci, co), (gi, _go) in zip(ctx, train):
            piv = _pivot_named(ci.keys(), len(gi), len(gi[0])).get(name)
            if piv is None or _apply_pivot(ci, M, piv) != co:
                ok = False
                break
        if ok:
            return name
    return None


def _apply_pivot(cells, M, piv2):
    """M 을 piv2(2배 피벗) 기준으로 적용. 정수 셀 안 떨어지면 None. {(r,c):color} 유지."""
    a, b, d, f = M[1:]; pr2, pc2 = piv2; out = {}
    for (r, c), col in cells.items():
        rr2, cc2 = 2 * r - pr2, 2 * c - pc2
        R2, C2 = a * rr2 + b * cc2 + pr2, d * rr2 + f * cc2 + pc2
        if R2 % 2 or C2 % 2:
            return None
        out[(R2 // 2, C2 // 2)] = col
    return out


def _match_free(cells, M, coset):
    """output(coset={(r,c):color}) 가 M(input) 의 평행이동인가 (색보존, 자유 평행이동)."""
    a, b, d, f = M[1:]
    tr = {(a * r + b * c, d * r + f * c): col for (r, c), col in cells.items()}
    if len(tr) != len(cells):
        return False
    tr0 = (min(r for r, _ in tr), min(c for _, c in tr)); o0 = (min(r for r, _ in coset), min(c for _, c in coset))
    dr, dc = o0[0] - tr0[0], o0[1] - tr0[1]
    return {(r + dr, c + dc): col for (r, c), col in tr.items()} == coset


def solve_by_linear(train, test_input):
    """배경=0 · 비0 객체를 하나의 선형 D4 로 변환. 전 train 쌍 공통 D4(자유 평행이동) → test centroid 배치."""
    ctx = [(_nonzero(gi), _nonzero(go)) for gi, go in train]
    if any(not ci or not co or len(ci) != len(co) for ci, co in ctx):
        return None
    common = [M for M in _D4 if all(_match_free(ci, M, co) for ci, co in ctx)]
    ti = _nonzero(test_input); H, W = len(test_input), len(test_input[0])

    def _materialize(pred):
        if pred is None or not all(0 <= r < H and 0 <= c < W for (r, c) in pred) or len(pred) != len(ti):
            return None
        out = [[0] * W for _ in range(H)]
        for (r, c), col in pred.items():
            out[r][c] = col
        return out

    for M in common:                                         # ① 피벗 규칙을 train 정확재현으로 검증 → test 적용
        name = _verified_pivot_rule(ctx, train, M)
        if name is not None:
            tp = _pivot_named(ti.keys(), H, W).get(name)
            got = _materialize(_apply_pivot(ti, M, tp)) if tp is not None else None
            if got is not None:
                return got
    for M in common:                                         # ② 폴백: 검증 규칙 없을 때 centroid-first-in-grid 추측
        for pv in sorted(_pivots2(ti.keys())):
            got = _materialize(_apply_pivot(ti, M, pv))
            if got is not None:
                return got
    return None


def solve_by_linear_percolor(train, test_input):
    """다객체(색이 다른 여러 객체)를 **색별로 각자 D4**. 배경=0. 색마다 자기 centroid 피벗.
    식 없는(정지) 색은 그대로. 색이 쌍마다 안 바뀌는(안정) 다객체에 유효."""
    colors = set(_nonzero(test_input).values())
    forms = {}
    for col in colors:
        ctx, ok = [], True
        for gi, go in train:
            ci = {k: v for k, v in _nonzero(gi).items() if v == col}
            co = {k: v for k, v in _nonzero(go).items() if v == col}
            if not ci or not co or len(ci) != len(co):
                ok = False
                break
            ctx.append((ci, co))
        if not ok:
            continue                                            # 색이 쌍마다 없거나 다름 → skip(정지 처리)
        common = [M for M in _D4 if all(_match_free(ci, M, co) for ci, co in ctx)]
        if common:
            forms[col] = common[0]
    if not any(M[0] != "id" for M in forms.values()):           # 움직인 색이 하나도 없으면 무의미
        return None
    ti = _nonzero(test_input); H, W = len(test_input), len(test_input[0])
    out = [[0] * W for _ in range(H)]
    for col in colors:
        cells = {k: v for k, v in ti.items() if v == col}
        if col in forms:
            placed = False
            for pv in sorted(_pivots2(cells.keys())):
                pr = _apply_pivot(cells, forms[col], pv)
                if pr is not None and all(0 <= r < H and 0 <= c < W for (r, c) in pr):
                    for (r, c), v in pr.items():
                        out[r][c] = v
                    placed = True
                    break
            if not placed:
                return None
        else:                                                   # 식 없는 색 = 정지(그대로)
            for (r, c), v in cells.items():
                out[r][c] = v
    return out


# ── 객체-선택 변환 (사용자 흐름 2026-07-26): 색이 쌍마다 바뀌는 다객체. 색별 exact 매칭이 안 되니
#    pair 내 in↔out 객체를 (색 COMM ∧ area COMM) 대응으로 잇는다(shape·position DIFF 여도 매칭 — 부분
#    일치). 대응쌍 중 shape 가 바뀐 것이 **mover**(제자리 D4), 나머지는 정지. mover 를 지목하는 **불변
#    property**(색 또는 area 가 train 쌍 전체에서 상수)를 structure mapping 으로 찾고, 그 규칙으로 test
#    객체를 골라 같은 D4 를 제자리(bbox 피벗)에 적용. train 만으로 안 갈리는 중의성(공통 D4 여럿·규칙 여럿·
#    후보객체 여럿)은 후보를 생성해 attempt 로 제출(any-correct; §P5 탐색은 train, 판정은 최종 채점).
def _components(cells):
    """비배경 셀의 8-연결 성분들. cells={(r,c):color}. 반환 [{(r,c):color},...] (배경분리 객체)."""
    from collections import deque
    remain = dict(cells); seen = set(); out = []
    for st in remain:
        if st in seen:
            continue
        q = deque([st]); seen.add(st); comp = {st: remain[st]}
        while q:
            r, c = q.popleft()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    p = (r + dr, c + dc)
                    if p in remain and p not in seen:
                        seen.add(p); comp[p] = remain[p]; q.append(p)
        out.append(comp)
    return out


def _ocolor(comp):
    return next(iter(sorted(set(comp.values()))))


def _oshape(comp):
    rs = [r for r, _ in comp]; cs = [c for _, c in comp]; r0, c0 = min(rs), min(cs)
    return frozenset((r - r0, c - c0) for r, c in comp)


def _correspond_by_prop(cin, cout):
    """in↔out 성분을 (색 COMM ∧ area COMM) greedy 대응(부분일치 허용 — shape/pos DIFF 여도). 반환 [(a,b)] 또는 None."""
    used = set(); pairs = []
    for a in cin:
        cand = [(j, b) for j, b in enumerate(cout)
                if j not in used and _ocolor(b) == _ocolor(a) and len(b) == len(a)]
        if not cand:
            return None
        j, _b = min(cand, key=lambda x: x[0]); used.add(j); pairs.append((a, cout[j]))
    return pairs


def object_transform_candidates(train, test_input):
    """색-varying 다객체: mover(제자리 D4) 를 불변 property 로 지목해 test 후보 격자들을 생성(≤3).
    반환 = 후보 격자 리스트(첫 유효부터, 객체 라운드로빈). 비해당/실패 시 []."""
    per_pair = []                                            # (mover_in, mover_out, D4후보집합) per pair
    for gi, go in train:
        cin = _components(_nonzero(gi)); cout = _components(_nonzero(go))
        mp = _correspond_by_prop(cin, cout)
        if mp is None:
            return []
        movers = [(a, b) for a, b in mp if _oshape(a) != _oshape(b)]   # shape 바뀐 대응쌍 = 이동/변환
        if len(movers) != 1:                                # pair 당 mover 정확히 1개(현행 가정)
            return []
        a, b = movers[0]
        d4 = {M[0] for M in _D4 if _match_free(a, M, b)}
        per_pair.append((a, b, d4))
    # mover 선택 규칙: area 불변? 색 불변? (train 쌍 전체에서 상수인 property) — area 우선
    cols = {_ocolor(a) for a, _b, _d in per_pair}; areas = {len(a) for a, _b, _d in per_pair}
    rules = []
    if len(areas) == 1:
        rules.append(("area", next(iter(areas))))
    if len(cols) == 1:
        rules.append(("color", next(iter(cols))))
    if not rules:
        return []
    common = set(per_pair[0][2])                             # 공통 D4 = 교집합
    for _a, _b, d4 in per_pair[1:]:
        common &= d4
    if not common:
        return []
    verified = []                                           # (M, pivot규칙): 전 train mover 를 정확재현
    for name in sorted(common):
        M = next(x for x in _D4 if x[0] == name)
        for pv in _PIVOT_ORDER:
            ok = True
            for a, b, _d in per_pair:
                piv = _pivot_named(a.keys(), 9, 9).get(pv)
                pr = _apply_pivot(a, M, piv) if piv is not None else None
                if pr is None or set(pr.keys()) != set(b.keys()):
                    ok = False
                    break
            if ok:
                verified.append((M, pv)); break
    if not verified:
        return []
    ti = _components(_nonzero(test_input)); H, W = len(test_input), len(test_input[0])
    per_obj = []; seen_obj = set()                          # 선택 객체별 후보(라운드로빈용)
    for kind, val in rules:
        for s in ti:
            key = id(s)
            if key in seen_obj:
                continue
            if not (_ocolor(s) == val if kind == "color" else len(s) == val):
                continue
            seen_obj.add(key)
            gl = []
            for M, pv in verified:
                piv = _pivot_named(s.keys(), H, W).get(pv)
                pr = _apply_pivot(s, M, piv) if piv is not None else None
                if pr is None or not all(0 <= r < H and 0 <= c < W for (r, c) in pr):
                    continue
                g = [[0] * W for _ in range(H)]
                for c in ti:
                    src = pr if c is s else c
                    for (r, cc), v in src.items():
                        g[r][cc] = v
                if g not in gl:
                    gl.append(g)
            if gl:
                per_obj.append(gl)
    out = []; i = 0                                          # 객체 라운드로빈(각 후보객체가 먼저 1개씩)
    while any(i < len(v) for v in per_obj):
        for v in per_obj:
            if i < len(v) and v[i] not in out:
                out.append(v[i])
        i += 1
    return out[:3]


def solve_by_object_transform(train, test_input):
    """object_transform_candidates 의 첫 후보(단일 답 필요 시). 없으면 None."""
    cs = object_transform_candidates(train, test_input)
    return cs[0] if cs else None


def solve_any(train, test_input):
    """심볼 좌표식 + 선형 D4(통째) + 선형 D4(색별) + 객체선택변환 순차 시도(첫 non-None)."""
    return (solve_by_transform(train, test_input) or solve_by_linear(train, test_input)
            or solve_by_linear_percolor(train, test_input) or solve_by_object_transform(train, test_input))
