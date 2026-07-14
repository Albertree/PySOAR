# -*- coding: utf-8 -*-
"""ARBOR reasoning.antiunify — per-pair program 을 anti-unify 해 TASK.solution 골격+변수 도출.

하네스 §0.5/§2-3: anti-unification = 정렬된 per-pair program 들을 공통 골격 + 변수 스키마로
일반화. 실체 = compare(prog,prog) + DIFF slot 변수화. 정렬(structure mapping)이 선행조건이라,
program 들의 연산을 **COMM 최대화 순열**로 맞춘 뒤 비교한다(0=bg 가정 없이, §no-arbitrary-filters).
resolve(변수→G0 유래 식)는 **train pair 로만** 검증(§1-3/§4-1, test 오라클 금지 §P5).

program 포맷(coloring.py 생성, level-1 flat): P{i}=in_px[idx]; tfg=apply_DSL(...,P{i}.coord,color).
op i = (pixel_index, color). 내부 표현 skeleton={'ops':[(idx|None, color|None)]}.
"""
from __future__ import annotations

import itertools
import re

_DEF = re.compile(r"^\s*(\w+)\s*=\s*in_px\[(\d+)\]\s*$")
_STEP = re.compile(r"apply_DSL\([^,]+,\s*coloring,\s*(\w+)\.coord,\s*(\d+)\)")
# blob(=object-level) 프로그램: compress 가 쓰는 형식. 셀 묶음 하나를 한 색으로 칠한다.
#   B0 = [7, 8, 13, 14]                          (연결 덩어리 = 픽셀 인덱스 집합)
#   apply_DSL(tfg0, coloring, B0, 3)             (.coord 없음 → 픽셀 형식과 구분)
_BLOB_DEF = re.compile(r"^\s*(\w+)\s*=\s*\[([\d,\s]*)\]\s*$")
_BLOB_STEP = re.compile(r"apply_DSL\([^,]+,\s*coloring,\s*(\w+),\s*(\d+)\)")


def parse_program(code: str):
    """flat program → ops=[(pixel_index, color)] (step 순서). 파싱 불가면 None."""
    if not code or code.strip() in ("{}", ""):
        return None
    idx_of, steps = {}, []
    for ln in code.splitlines():
        m = _DEF.match(ln)
        if m:
            idx_of[m.group(1)] = int(m.group(2))
            continue
        m = _STEP.search(ln)
        if m:
            steps.append((m.group(1), int(m.group(2))))
    ops = [(idx_of.get(v), int(col)) for v, col in steps]
    if not ops or any(o[0] is None for o in ops):
        return None
    return ops


def _align(ref, ops):
    """ops 를 ref 에 **COMM(idx·color 일치) 최대화**하는 순열로 정렬 (structure mapping).
    연산 수가 작을 때만(≤6) 전수; 크면 원순서."""
    n = len(ref)
    if n > 6:
        return ops
    best, bestscore = ops, -1
    for perm in itertools.permutations(ops):
        score = sum((perm[i][0] == ref[i][0]) + (perm[i][1] == ref[i][1]) for i in range(n))
        if score > bestscore:
            bestscore, best = score, list(perm)
    return best


def _is_blob_program(code):
    return bool(code) and any(_BLOB_DEF.match(ln) for ln in code.splitlines())


def _parse_blob_program(code):
    """blob 프로그램 → ops=[(cells=frozenset(idx), color)] (step 순서). 파싱 불가면 None."""
    if not code or code.strip() in ("{}", ""):
        return None
    sets, ops = {}, []
    for ln in code.splitlines():
        m = _BLOB_DEF.match(ln)
        if m:
            sets[m.group(1)] = frozenset(int(x) for x in m.group(2).split(",") if x.strip())
            continue
        m = _BLOB_STEP.search(ln)
        if m and m.group(1) in sets:
            ops.append((sets[m.group(1)], int(m.group(2))))
    if not ops:
        return None
    return ops


def compressible(programs):
    """pixel 프로그램들이 **op 수 불일치**로 anti-unify 불가한가 (= compress 로 덩어리화하면 도움).
    같은 색 픽셀들이 객체 크기만큼 늘어난 케이스(이동 등)를 잡는다. blob 형식이면 이미 압축됨→False."""
    ps = [parse_program(p) for p in programs if not _is_blob_program(p)]
    ps = [p for p in ps if p]
    if len(ps) < 2:
        return False
    return len({len(p) for p in ps}) > 1        # op 수가 서로 다름


def antiunify(programs):
    """per-pair program 문자열들 → (skeleton, slots).
    pixel: skeleton={'ops':[(idx|None,color|None)]}; blob: skeleton={'kind':'blob','ops':[(cells|None,color|None)]}.
    slots={name:{kind:'src'|'color'|'cellset', pos, values}}. 위치별 COMM=상수, DIFF=변수. 불가 시 (None,None)."""
    if all(_is_blob_program(p) for p in programs if p and p != "{}"):
        blobs = [_parse_blob_program(p) for p in programs]
        blobs = [b for b in blobs if b]
        if len(blobs) >= 2:
            return _antiunify_blobs(blobs)
    progs = [parse_program(p) for p in programs]
    progs = [p for p in progs if p]
    if len(progs) < 2:
        return None, None
    n = len(progs[0])
    if any(len(p) != n for p in progs):
        return None, None                       # 연산 수 다르면 이 골격으론 불가 (→ compress 후보)
    ref = progs[0]
    aligned = [ref] + [_align(ref, p) for p in progs[1:]]
    ops, slots = [], {}
    for i in range(n):
        idxs = [a[i][0] for a in aligned]
        cols = [a[i][1] for a in aligned]
        sk_idx = idxs[0] if len(set(idxs)) == 1 else None
        sk_col = cols[0] if len(set(cols)) == 1 else None
        if sk_idx is None:
            slots[f"?src{i}"] = {"kind": "src", "pos": i, "values": idxs}
        if sk_col is None:
            slots[f"?color{i}"] = {"kind": "color", "pos": i, "values": cols}
        ops.append((sk_idx, sk_col))
    return {"ops": ops}, slots


def _align_blobs(ref, ops):
    """blob ops 를 ref 에 **색 COMM 최대화** 순열로 정렬(셀집합은 pair 마다 다르니 색으로 대응). ≤6 전수."""
    n = len(ref)
    if n > 6 or len(ops) != n:
        return ops
    best, bestscore = ops, -1
    for perm in itertools.permutations(ops):
        score = sum((perm[i][1] == ref[i][1]) + (perm[i][0] == ref[i][0]) for i in range(n))
        if score > bestscore:
            bestscore, best = score, list(perm)
    return best


def _antiunify_blobs(blobs):
    """blob 프로그램들(ops=[(cells,color)]) → (skeleton{'kind':'blob'}, slots). 위치별 COMM=상수, DIFF=slot.
    cellset DIFF → cellset slot(값=pair 별 셀집합; resolve 가 input object 유래 식으로 재표현 = P5 다음단계)."""
    n = len(blobs[0])
    if any(len(b) != n for b in blobs):
        return None, None
    ref = blobs[0]
    aligned = [ref] + [_align_blobs(ref, b) for b in blobs[1:]]
    ops, slots = [], {}
    for i in range(n):
        cellsets = [a[i][0] for a in aligned]
        cols = [a[i][1] for a in aligned]
        sk_cells = cellsets[0] if len({tuple(sorted(c)) for c in cellsets}) == 1 else None
        sk_col = cols[0] if len(set(cols)) == 1 else None
        if sk_cells is None:
            slots[f"?cells{i}"] = {"kind": "cellset", "pos": i,
                                   "values": [sorted(c) for c in cellsets]}
        if sk_col is None:
            slots[f"?color{i}"] = {"kind": "color", "pos": i, "values": cols}
        ops.append((sorted(sk_cells) if sk_cells is not None else None, sk_col))
    return {"kind": "blob", "ops": ops}, slots


# ── resolve: 변수 slot → G0 유래 표현식 (generate → train 적용 → 대조 → 생존) ──────
# 배경(색0) 을 특권화하지 않는다(§no-arbitrary-filters·사용자 2026-07-15): "전경" 개념 없이 grid 의
# 4-연결 동색 성분(objects_of 와 동일 알고리즘)을 전부 뽑고, **기하 선택자**(면적 순위 — 색이 아니라
# 기하, train 이 채택)로 소스 객체를 고른 뒤 그 객체의 {r0,c0,h,w,anchor}+grid{H,W}+상수로 좌표식을
# **자유조합 brute-force**(±/*//·좌결합 ≤2연산) 로 만든다. H-h·W-w·H-1·(0,0) 이 전부 이 문법에서
# 창발한다(손열거 코너·fg_index·color_of_fg 제거). 배경색은 오직 ARCKG 생성에서만 count 로 라벨링.

def _components(grid):
    """grid 의 4-연결 동색 성분 전부 = [(cells, color)] (색0 도 하나의 색; objects_of 와 동일)."""
    H, W = len(grid), len(grid[0])
    seen, objs = set(), []
    for r in range(H):
        for c in range(W):
            if (r, c) in seen:
                continue
            col, stack, cells = grid[r][c], [(r, c)], []
            while stack:
                y, x = stack.pop()
                if (y, x) in seen or not (0 <= y < H and 0 <= x < W) or grid[y][x] != col:
                    continue
                seen.add((y, x)); cells.append((y, x))
                stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
            objs.append((sorted(cells), col))
    return objs


def _obj_atoms(cells, grid):
    """소스 객체 → 좌표식 원자: bbox(r0,c0,h,w) + anchor(scan 순 첫 셀 ar,ac) + grid(H,W) + 상수 0..5."""
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    r0, c0, r1, c1 = min(rs), min(cs), max(rs), max(cs)
    ar, ac = cells[0]
    d = {"H": len(grid), "W": len(grid[0]), "r0": r0, "c0": c0, "r1": r1, "c1": c1,
         "h": r1 - r0 + 1, "w": c1 - c0 + 1, "ar": ar, "ac": ac}   # r1,c1=bbox 우하단 모서리
    d.update({str(k): k for k in range(6)})
    return d


_ATOM_NAMES = ["H", "W", "r0", "c0", "h", "w", "ar", "ac", "0", "1", "2", "3", "4", "5"]
_EXPR_OPS = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b),
             ("*", lambda a, b: a * b), ("//", lambda a, b: (a // b) if b else None)]


def _gen_exprs(names, max_ops=2):
    """원자 names 에서 이항연산 ≤max_ops 회(좌결합)로 만들 수 있는 표현식 전부. [(설명, fn(atoms), 깊이)]."""
    base = [(n, (lambda d, n=n: d[n]), 0) for n in names]
    exprs = list(base)
    frontier = list(base)
    for _ in range(max_ops):
        nxt = []
        for en, ef, ed in frontier:
            for an, af, _ad in base:
                for osym, ofn in _EXPR_OPS:
                    def fn(d, ef=ef, af=af, ofn=ofn):
                        x = ef(d)
                        if x is None:
                            return None
                        y = af(d)
                        if y is None:
                            return None
                        return ofn(x, y)
                    nxt.append((f"{en}{osym}{an}", fn, ed + 1))
        exprs.extend(nxt)
        frontier = nxt
    return exprs


_COORD_TEMPLATES = _gen_exprs(_ATOM_NAMES, max_ops=2)   # ≈4.5만 후보식(원자 14 × ≤2연산)
_MATCH_CAP = 8   # 축별 생존식 상한(단순식 우선). 넘으면 tried 에 절단 기록(§no-silent-caps).


def _selectors(comps_list):
    """bg-free 기하 소스-객체 선택자: 면적 순위(최소·최대·2번째). 색이 아니라 면적(=기하)으로 고른다.
    반환 = [(name, fn(comps)->cells|None)]. train 전 pair 에서 결정적(같은 순위)."""
    def by_rank(j, rev):
        def pick(comps):
            if j >= len(comps):
                return None
            return sorted(comps, key=lambda cc: (len(cc[0]), cc[0][0]),
                          reverse=rev)[j][0]
        return pick
    return [("min_area", by_rank(0, False)), ("max_area", by_rank(0, True)),
            ("min_area#2", by_rank(1, False)), ("max_area#2", by_rank(1, True))]


def _color_of_sel(sfn):
    def fn(g):
        cells = sfn(_components(g))
        if cells is None:
            return None
        r, c = cells[0]
        return g[r][c]
    return fn


def _coord_index_fn(sfn, rf, cf):
    """(선택자, row식, col식) → fn(grid): 선택 객체 원자로 픽셀 인덱스(row*W+col)."""
    def fn(g):
        cells = sfn(_components(g))
        if cells is None:
            return None
        a = _obj_atoms(cells, g)
        r, c = rf(a), cf(a)
        if r is None or c is None:
            return None
        return r * len(g[0]) + c
    return fn


_ATOM_RE = re.compile(r"r0|c0|r1|c1|ar|ac|H|W|h|w")
_POS = ({"r0", "ar", "r1"}, {"c0", "ac", "c1"})   # 축별 객체-위치 원자(행/열; r1,c1=우하단)


def _axis_tier(name, axis):
    """좌표식의 일반성 tier(낮을수록 우선): 0=객체위치(r0/c0/ar/ac) · 1=객체크기(h,w) · 2=격자(H,W) ·
    3=상수전용. 객체-상대 식이 격자-상대·상수보다 일반화가 좋다(같은 train 값이라도 test 로 잘 옮겨감).
    단 진짜 corner(H-h) 는 r0-식이 train 에 안 맞아 탈락하므로 tier 우선이 corner 탐색을 막지 않는다."""
    toks = _ATOM_RE.findall(name)
    if not toks:
        return 3
    t = 0
    for a in toks:
        if a in _POS[axis]:
            t = max(t, 0)
        elif a in ("h", "w"):
            t = max(t, 1)
        else:                                           # H,W 또는 반대축 위치원자
            t = max(t, 2)
    return t


def _axis_matches(atoms, targets, axis):
    """전 pair 에서 targets[i][axis] 를 맞추는 좌표식들(일반성 tier·단순성 우선 ≤_MATCH_CAP). (이름, fn, 깊이, 절단수).
    (전부 생성·검증한 뒤 '먼저 제출할 순서'만 정한다 — 탐색은 그대로, §1-3.)"""
    n = len(targets)
    hits = [(en, ef, ed) for en, ef, ed in _COORD_TEMPLATES
            if all(ef(atoms[i]) == targets[i][axis] for i in range(n))]
    hits.sort(key=lambda t: (_axis_tier(t[0], axis), t[2], len(t[0])))
    trunc = max(0, len(hits) - _MATCH_CAP)
    return [(en, ef, ed) for en, ef, ed in hits[:_MATCH_CAP]], trunc


# 객체 이동(placement)의 **정준 배치**: 축별로 grid 랜드마크(위/아래·좌/우 모서리)에 정렬하거나 제자리.
# few-shot 좌표식 탐색은 우연 상수(4+ac, 7-w…)로 과적합하기 쉬워, 사용자 설계(2026-07-15)대로
# "output object 를 비교해 그 위치의 불변(우하단이 grid 코너와 정렬)을 찾는" 것을 직접 구현한다:
# 각 축의 앵커(모서리)를 grid 경계/제자리에 맞춰 보고 train 전 pair 를 재현하는 조합을 채택.
#   fn(atoms) = 그 앵커가 놓일 좌표. (H-1=아래끝·W-1=오른끝·0=위/왼끝·r0/c0=제자리)
_ROW_ANCHORS = [("keep", "min", lambda a: a["r0"]), ("top", "min", lambda a: 0),
                ("bottom", "max", lambda a: a["H"] - 1)]
_COL_ANCHORS = [("keep", "min", lambda a: a["c0"]), ("left", "min", lambda a: 0),
                ("right", "max", lambda a: a["W"] - 1)]


def _place_canonical_fn(sfn, redge, rtgt, cedge, ctgt):
    """(선택자, row 앵커모서리·목표, col 앵커모서리·목표) → fn(grid): 객체의 그 모서리를 목표에 맞춰 이동."""
    def fn(g):
        cells = sfn(_components(g))
        if cells is None:
            return None
        a = _obj_atoms(cells, g)
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        src_r = min(rs) if redge == "min" else max(rs)
        src_c = min(cs) if cedge == "min" else max(cs)
        dr, dc = rtgt(a) - src_r, ctgt(a) - src_c
        W = len(g[0])
        return [(r + dr) * W + (c + dc) for (r, c) in cells]
    return fn


def _resolve_cellset(vals, train, comps, sels):
    """cellset slot → (survivors, tried). 셀집합 = 어떤 input object 를 이동한 것. §P5: output 좌표 직접 안 씀.
    선택자로 고른 input object 의 모양이 셀집합과 **평행이동으로 일치**하면, 축별 정준 앵커(grid 모서리/제자리)
    조합 중 train 전 pair 를 재현하는 것을 채택(우하단 코너 등이 여기서 창발). train 으로만 검증."""
    N = len(vals)
    dests = []                                            # pair 별 dest 셀 (r,c)
    for i in range(N):
        W = len(train[i]["input"][0])
        dests.append(sorted((idx // W, idx % W) for idx in vals[i]))
    keyed, tried = [], []
    for si, (sname, sfn) in enumerate(sels):
        objs = [sfn(comps[i]) for i in range(N)]
        if any(o is None for o in objs):
            continue
        atoms, ok_shape = [], True
        for i in range(N):
            src = sorted(objs[i]); d = dests[i]
            if len(src) != len(d):
                ok_shape = False; break
            sr, sc = min(r for r, _ in src), min(c for _, c in src)
            dr, dc = min(r for r, _ in d), min(c for _, c in d)
            if sorted((r - sr, c - sc) for r, c in src) != sorted((r - dr, c - dc) for r, c in d):
                ok_shape = False; break                    # 모양(평행이동 불변) 불일치 → 이 객체론 설명 불가
            atoms.append(_obj_atoms(objs[i], train[i]["input"]))
        if not ok_shape:
            tried.append((f"place@{sname}: 모양 불일치", False)); continue
        for rname, redge, rtgt in _ROW_ANCHORS:
            for cname, cedge, ctgt in _COL_ANCHORS:
                ok = True
                for i in range(N):
                    cells = sorted(objs[i]); a = atoms[i]
                    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
                    sr = min(rs) if redge == "min" else max(rs)
                    sc = min(cs) if cedge == "min" else max(cs)
                    dr, dc = rtgt(a) - sr, ctgt(a) - sc
                    if sorted((r + dr, c + dc) for (r, c) in cells) != dests[i]:
                        ok = False; break
                if not ok:
                    continue
                nkeep = (rname != "keep") + (cname != "keep")   # 제자리(identity) 를 이동보다 우선
                name = f"place[{rname},{cname}]@{sname}"
                keyed.append(((nkeep, si, len(name)), name,
                              _place_canonical_fn(sfn, redge, rtgt, cedge, ctgt)))
    keyed.sort(key=lambda t: t[0])
    for _k, name, fn in keyed[:_MATCH_CAP]:
        tried.append((name, True))
    survivors = [(name, fn) for _k, name, fn in keyed[:_MATCH_CAP]]
    if not survivors:
        tried.append(("<no canonical placement>", False))
    return survivors, tried


def resolve_slot(slot, train):
    """slot(kind='src'|'color'|'cellset') → (survivors=[(name, fn(grid))], tried=[(name, ok)]).
    소스 객체는 기하 선택자로(배경 가정 없이), 값은 좌표식/객체색/객체이동 자유조합 탐색. train 으로만 검증(§P5)."""
    vals = slot["values"]
    N = len(vals)
    if N != len(train):
        return [], [("<len-mismatch>", False)]
    comps = [_components(e["input"]) for e in train]
    sels = _selectors(comps)
    tried, survivors = [], []
    if slot["kind"] == "cellset":
        return _resolve_cellset(vals, train, comps, sels)

    if slot["kind"] == "color":
        for k in sorted(set(vals)):                       # 상수색 후보
            ok = all(v == k for v in vals)
            tried.append((f"const {k}", ok))
            if ok:
                survivors.append((f"const {k}", (lambda g, k=k: k)))
        for sname, sfn in sels:                           # 선택자-객체의 색(color_of_fg 의 bg-free 대체)
            picks = [sfn(comps[i]) for i in range(N)]
            if any(p is None for p in picks):
                tried.append((f"color@{sname}", False)); continue
            cols = [train[i]["input"][picks[i][0][0]][picks[i][0][1]] for i in range(N)]
            ok = cols == list(vals)
            tried.append((f"color@{sname}", ok))
            if ok:
                survivors.append((f"color@{sname}", _color_of_sel(sfn)))
        return survivors, tried

    # --- src / 픽셀 인덱스 slot: 선택자 × 좌표식 자유조합 ---
    targets = [(vals[i] // len(train[i]["input"][0]), vals[i] % len(train[i]["input"][0]))
               for i in range(N)]
    keyed = []                                         # (정렬키, name, fn) — 최선 조합이 앞
    for si, (sname, sfn) in enumerate(sels):
        atoms, ok_sel = [], True
        for i in range(N):
            cells = sfn(comps[i])
            if cells is None:
                ok_sel = False; break
            atoms.append(_obj_atoms(cells, train[i]["input"]))
        if not ok_sel:
            continue
        r_hits, r_tr = _axis_matches(atoms, targets, 0)
        c_hits, c_tr = _axis_matches(atoms, targets, 1)
        if r_tr or c_tr:
            tried.append((f"<{sname}: {r_tr}+{c_tr}개 우선순위 밖 절단>", True))
        for rn, rf, rd in r_hits:
            for cn, cf, cd in c_hits:
                name = f"({rn},{cn})@{sname}"
                key = (_axis_tier(rn, 0) + _axis_tier(cn, 1), rd + cd, si, len(name))
                keyed.append((key, name, _coord_index_fn(sfn, rf, cf)))
    keyed.sort(key=lambda t: t[0])                     # 일반적·단순·min_area 우선 → product 첫 후보=최선
    for _k, name, fn in keyed[:_MATCH_CAP]:
        survivors.append((name, fn))
        tried.append((name, True))
    if not survivors:
        tried.append(("<no coord expr>", False))
    return survivors, tried


# ── 실행 + version space ─────────────────────────────────────────────────────
def solution_candidates(sol, limit=3):
    """resolved version space 곱 → [(label, choice{name:fn})] (≤limit; few-shot 애매성=3-attempt)."""
    slots, resolved = sol["slots"], sol.get("resolved") or {}
    names = list(slots.keys())
    if not names:
        return [("(변수 없음)", {})]
    pools = [resolved.get(n) or [] for n in names]
    if any(not pool for pool in pools):
        return []
    out = []
    for combo in itertools.product(*pools):
        choice = {names[i]: combo[i][1] for i in range(len(names))}
        label = ", ".join(f"{names[i]}={combo[i][0]}" for i in range(len(names)))
        out.append((label, choice))
        if len(out) >= limit:
            break
    return out


def execute_solution(skeleton, slots, choice, grid_in):
    """skeleton + slot별 선택 fn → grid_in 실행 → 답 격자."""
    H, W = len(grid_in), len(grid_in[0])
    if skeleton.get("kind") == "blob":                    # 덩어리(객체) 단위: 각 셀에 단일셀 coloring 조합
        cell_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "cellset"}
        col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
        grid = [list(r) for r in grid_in]
        for i, (cells, col) in enumerate(skeleton["ops"]):
            cs = cells if cells is not None else choice[cell_at[i]](grid_in)
            c = col if col is not None else choice[col_at[i]](grid_in)
            if cs is None:
                continue
            for ix in cs:
                r, cc = ix // W, ix % W
                if 0 <= r < H and 0 <= cc < W:
                    grid[r][cc] = c
        return grid
    src_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "src"}
    col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
    grid = [list(r) for r in grid_in]
    for i, (idx, col) in enumerate(skeleton["ops"]):
        ix = idx if idx is not None else choice[src_at[i]](grid_in)
        c = col if col is not None else choice[col_at[i]](grid_in)
        if ix is None:
            continue
        r, cc = ix // W, ix % W
        if 0 <= r < H and 0 <= cc < W:
            grid[r][cc] = c
    return grid


def render_skeleton(skeleton, slots) -> str:
    """골격+변수 → TASK.solution 문자열(대시보드·저장)."""
    if not skeleton:
        return "{}"
    if skeleton.get("kind") == "blob":                    # 덩어리(객체) 단위 program
        cell_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "cellset"}
        col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
        lines = ["tfg0 = input_grid"]
        for i, (cells, col) in enumerate(skeleton["ops"]):
            cs = str(cells) if cells is not None else cell_at[i]
            c = str(col) if col is not None else col_at[i]
            lines.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {cs}, {c})  # 객체 덩어리")
        lines.append(f"output_grid = tfg{len(skeleton['ops'])}")
        return "\n".join(lines)
    src_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "src"}
    col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
    lines = ["in_px = pixels_of(input_grid)"]
    for i, (idx, col) in enumerate(skeleton["ops"]):
        ix = str(idx) if idx is not None else src_at[i]
        lines.append(f"P{i} = in_px[{ix}]")
    lines.append("")
    lines.append("tfg0 = input_grid")
    for i, (idx, col) in enumerate(skeleton["ops"]):
        c = str(col) if col is not None else col_at[i]
        lines.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, P{i}.coord, {c})")
    lines.append(f"output_grid = tfg{len(skeleton['ops'])}")
    return "\n".join(lines)
