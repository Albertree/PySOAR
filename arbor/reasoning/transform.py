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


# ── 선형(affine) 픽셀 이동식 (사용자 흐름 2026-07-26): 배경=0, 객체=비0. 같은 색 픽셀 대응(color:COMM,
#    coord:DIFF)에서 **하나의 공통 이동식** `(r,c)→(a·r+b·c+e, d·r+f·c+g)` 을 찾는다. 선형부 (a,b,d,f)=D4
#    8종, 오프셋 (e,g)=정수. 배치는 **객체 bbox중심 보존**(제자리 회전/반전)으로 정하며, 오프셋이 반 칸을
#    요구하면(격자 칸 미적중; 예 h-w 홀수) **기각**한다. 회전축·대칭축은 이 식의 고정집합((r,c)=변환(r,c))으로
#    역산되는 *해석*일 뿐 — 식을 탐색/적용하는 데 축·피벗·2배좌표·소수점은 필요 없다.
_D4 = [("id", 1, 0, 0, 1), ("rot90", 0, 1, -1, 0), ("rot180", -1, 0, 0, -1), ("rot270", 0, -1, 1, 0),
       ("flipV", -1, 0, 0, 1), ("flipH", 1, 0, 0, -1), ("transpose", 0, 1, 1, 0), ("antitr", 0, -1, -1, 0)]


def _nonzero(grid):
    return {(r, c): v for r, row in enumerate(grid) for c, v in enumerate(row) if v != 0}


def _place_inplace(cells, M):
    """객체 픽셀에 M(D4 선형부)을 적용한 뒤, **bbox중심을 보존**하도록 정수 평행이동해 제자리에 놓는다.
    오프셋이 반 칸을 요구하면(격자 칸에 안 떨어짐 = h-w 홀수 등) None 으로 기각. 소수점·피벗·2배좌표 없음.
    반환 {(r,c):color}. — 이게 이동식 `(r,c)→(a·r+b·c+e, d·r+f·c+g)` 의 e,g 를 '중심 보존' 으로 정한 것."""
    _, a, b, d, f = M
    tr = {(a * r + b * c, d * r + f * c): col for (r, c), col in cells.items()}
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    tR = [r for r, _ in tr]; tC = [c for _, c in tr]
    num_r = (min(rs) + max(rs)) - (min(tR) + max(tR))     # 중심 정렬에 필요한 2·오프셋
    num_c = (min(cs) + max(cs)) - (min(tC) + max(tC))
    if num_r % 2 or num_c % 2:                            # 반 칸 이동 필요 = 격자 미적중 → 기각
        return None
    e, g = num_r // 2, num_c // 2
    return {(r + e, c + g): col for (r, c), col in tr.items()}


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
    """배경=0 · 비0 객체 전체를 하나의 공통 D4 이동식으로. 중심보존 배치가 전 train 쌍을 정확재현하는
    D4 를 찾아(추측 아닌 검증) test 에 적용. (제자리 회전/반전; 오프셋 e,g 는 중심보존으로 결정.)"""
    ctx = [(_nonzero(gi), _nonzero(go)) for gi, go in train]
    if any(not ci or not co or len(ci) != len(co) for ci, co in ctx):
        return None
    ti = _nonzero(test_input); H, W = len(test_input), len(test_input[0])
    for M in _D4:
        if not all(_place_inplace(ci, M) == co for ci, co in ctx):   # 중심보존이 전 train 정확재현?
            continue
        pred = _place_inplace(ti, M)
        if pred is None or not all(0 <= r < H and 0 <= c < W for (r, c) in pred) or len(pred) != len(ti):
            continue
        out = [[0] * W for _ in range(H)]
        for (r, c), col in pred.items():
            out[r][c] = col
        return out
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
        common = [M for M in _D4 if all(_place_inplace(ci, M) == co for ci, co in ctx)]
        if common:
            forms[col] = common[0]
    if not any(M[0] != "id" for M in forms.values()):           # 움직인 색이 하나도 없으면 무의미
        return None
    ti = _nonzero(test_input); H, W = len(test_input), len(test_input[0])
    out = [[0] * W for _ in range(H)]
    for col in colors:
        cells = {k: v for k, v in ti.items() if v == col}
        if col in forms:
            pr = _place_inplace(cells, forms[col])              # 중심보존 배치(반칸이면 None)
            if pr is None or not all(0 <= r < H and 0 <= c < W for (r, c) in pr):
                return None
            for (r, c), v in pr.items():
                out[r][c] = v
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
        d4 = {M[0] for M in _D4 if _place_inplace(a, M) == b}   # 중심보존 배치가 mover 를 정확재현하는 D4
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
    # common D4 는 이미 중심보존이 전 train mover 를 정확재현하는 것들(위 d4 교집합) → 별도 검증 불필요.
    verified = [next(x for x in _D4 if x[0] == name) for name in sorted(common)]
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
            for M in verified:
                pr = _place_inplace(s, M)                    # 중심보존 배치(반칸이면 None)
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


# ── 좌표식 해 물질화 (Stage 2, spec 2026-07-26): 변환 해를 **좌표식 (a·r+b·c+e, d·r+f·c+g)** 로 노출.
#    개념 이름(center/axis/rotate/flip/move) 없음 — 계수·정수오프셋뿐. 오프셋 유효성은 compare 로 관찰한
#    불변(mover in/out 의 r0+r1·c0+c1 이 COMM)에서만 나온다(가정 아님). 리포트가 이걸 coloring 으로 물질화.
def _bbox_arith(cells):
    """객체 bbox 좌표 산술값(이름 붙은 개념 아님): 코너 + 코너합."""
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    r0, c0, r1, c1 = min(rs), min(cs), max(rs), max(cs)
    return {"r0": r0, "c0": c0, "r1": r1, "c1": c1, "r0+r1": r0 + r1, "c0+c1": c0 + c1}


def _compare_invariant(pairs):
    """mover in/out 을 compare 해 COMM 인 bbox 산술값 집합을 **관찰**(가정 금지). 반환 = COMM key 집합."""
    comm = None
    for a, b in pairs:
        ab, bb = _bbox_arith(a.keys()), _bbox_arith(b.keys())
        this = {k for k in ab if ab[k] == bb[k]}
        comm = this if comm is None else (comm & this)
    return comm or set()


def _formula_params(M, cells):
    """D4 선형부 M + 객체 → 좌표식 (a,b,d,f,e,g). e,g = 중심보존 정수오프셋(이름 없음). 반칸이면 None."""
    _, a, b, d, f = M
    tr = [(a * r + b * c, d * r + f * c) for (r, c) in cells]
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    tR = [r for r, _ in tr]; tC = [c for _, c in tr]
    nr = (min(rs) + max(rs)) - (min(tR) + max(tR)); nc = (min(cs) + max(cs)) - (min(tC) + max(tC))
    if nr % 2 or nc % 2:
        return None
    return (a, b, d, f, nr // 2, nc // 2)


def transform_solution(train):
    """변환 해를 **좌표식 아티팩트**로 반환(리포트 물질화용). 없으면 None.
    반환 = {kind, per_pair:[{obj_in, params, color}], invariant(COMM집합)} — obj_in 이 변환되는 객체(들)."""
    # ① 통째(단일객체): 전 비0 을 한 객체로, 중심보존이 전 pair 재현하는 D4
    ctx = [(_nonzero(gi), _nonzero(go)) for gi, go in train]
    if all(ci and co and len(ci) == len(co) for ci, co in ctx):
        for M in _D4:
            if M[0] == "id":
                continue
            if all(_place_inplace(ci, M) == co for ci, co in ctx):
                inv = _compare_invariant([(ci, co) for ci, co in ctx])
                pp = [{"obj_in": ci, "params": _formula_params(M, ci), "color": None} for ci, co in ctx]
                if all(p["params"] for p in pp):
                    return {"kind": "whole", "per_pair": pp, "invariant": inv}
    # ② 객체선택(다객체): mover 대응 → 공통 D4 → 좌표식
    per = []
    for gi, go in train:
        cin = _components(_nonzero(gi)); cout = _components(_nonzero(go))
        mp = _correspond_by_prop(cin, cout)
        if mp is None:
            return None
        movers = [(a, b) for a, b in mp if _oshape(a) != _oshape(b)]
        if len(movers) != 1:
            return None
        per.append(movers[0])
    common = None
    for a, b in per:
        d4 = {M[0] for M in _D4 if _place_inplace(a, M) == b}
        common = d4 if common is None else (common & d4)
    if not common:
        return None
    name = sorted(common)[0]; M = next(x for x in _D4 if x[0] == name)
    inv = _compare_invariant(per)
    pp = [{"obj_in": a, "params": _formula_params(M, a), "color": _ocolor(a)} for a, b in per]
    if not all(p["params"] for p in pp):
        return None
    return {"kind": "object", "per_pair": pp, "invariant": inv}


def solve_any(train, test_input):
    """심볼 좌표식 + 선형 D4(통째) + 선형 D4(색별) + 객체선택변환 순차 시도(첫 non-None)."""
    return (solve_by_transform(train, test_input) or solve_by_linear(train, test_input)
            or solve_by_linear_percolor(train, test_input) or solve_by_object_transform(train, test_input))


def transform_solution_ast(train, test_input):
    """좌표식 해를 grid-body coloring AST + 테스트 answer 로. 없으면 None. 개념 이름 없음."""
    sol = transform_solution(train)
    if sol is None:
        return None
    answer = solve_any(train, test_input)
    if answer is None:
        return None
    H, W = len(test_input), len(test_input[0])
    # test 에서 변환되는 객체 = train 과 같은 kind/규칙으로 재도출(간단히: solve_any 가 이미 답을 알므로
    # 답 격자의 비배경을 객체색 coloring 으로 물질화; 정지객체 구분은 kind 로).
    def sel_target(coords):
        return {"coordinate_of": {"select": {"grid": "input", "level": "PIXEL",
                                             "pred": {"in": {"values": [list(c) for c in coords]}}}}}
    # 답 격자 셀을 색별로 묶어 coloring (전체 객체 재칠; op 수 = 객체 크기)
    from collections import defaultdict
    bycol = defaultdict(list)
    for r in range(H):
        for c in range(W):
            if answer[r][c]:
                bycol[answer[r][c]].append((r, c))
    inner = [{"call": "coloring", "args": {"target": sel_target(cs), "color": {"const": col}}}
             for col, cs in sorted(bycol.items())]
    body = [{"call": "set_grid_size", "args": {"size": {"const": {"height": H, "width": W}}}},
            {"call": "set_grid_color", "args": {"color": {"const": sorted({0, *bycol})}}},
            {"call": "set_grid_contents", "args": {"contents": {"program": {"body": inner}}}}]
    return {"input": {"grid": "G0"}, "body": body}, answer
