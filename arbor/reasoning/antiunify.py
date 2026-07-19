# -*- coding: utf-8 -*-
"""ARBOR reasoning.antiunify — per-pair program 을 anti-unify 해 TASK.solution 골격+변수 도출.

하네스 §0.5/§2-3: anti-unification = 정렬된 per-pair program 들을 공통 골격 + 변수 스키마로
일반화. 실체 = compare(prog,prog) + DIFF slot 변수화. 정렬(structure mapping)이 선행조건이라,
program 들의 연산을 **COMM 최대화 순열**로 맞춘 뒤 비교한다(0=bg 가정 없이, §no-arbitrary-filters).
resolve(변수→G0 유래 식)는 **train pair 로만** 검증(§1-3/§4-1, test 오라클 금지 §P5).

program 포맷(coloring.py 생성, level-1 flat): P{i}=in_px[idx]; tfg=apply_DSL(...,P{i}.coord,color).
op i = (pixel_index, color). 내부 표현 skeleton={'ops':[(idx|None, color|None)]}.

Task 8 (program-ast 경로): `generalize`/`apply_solution` operator 는 이제 정규식 파싱이 아니라
`arbor.reasoning.program_ast`(antiunify_ast/execute, AST-json 기반)를 쓴다. 구 flat-text
anti-unify(`antiunify`/`_antiunify_blobs`/`_parse_blob_program`/`render_skeleton`/`execute_solution`)
는 program_ast 로 완전히 대체돼 삭제됐다(2026-07-18, 호출자 0 검증). 남은 flat-text 도구는 아직
쓰이는 것만: `parse_program`(compress.py 가 호출)·`_STEP`/`_DEF`/`_BLOB_DEF`·`_is_blob_program`
(compressible 이 호출)·`_align`/`_align_blobs`(program_ast 가 재사용). `resolve_slot`/`_resolve_cellset`/
`solution_candidates`/`compressible` 이하 resolve 계열은 program_ast 경로에서도 그대로 쓰인다
(§0.5 근거: compare(prog,prog)).
"""
from __future__ import annotations

import itertools
import re

# 정규식 기반 flat-text 파서 — generalize/apply_solution 는 program_ast(AST-json) 경로를 쓰지만
# parse_program 은 compress.py 가 여전히 호출(as_source 로 정규화된 flat 텍스트 파싱), _BLOB_DEF 는
# _is_blob_program(compressible 호출)이 쓴다.
_DEF = re.compile(r"^\s*(\w+)\s*=\s*in_px\[(\d+)\]\s*$")
_STEP = re.compile(r"apply_DSL\([^,]+,\s*coloring,\s*(\w+)\.coord,\s*(\d+)\)")
# blob(=object-level) 프로그램: compress 가 쓰는 형식. 셀 묶음 하나를 한 색으로 칠한다.
#   B0 = [7, 8, 13, 14]                          (연결 덩어리 = 픽셀 인덱스 집합)
#   apply_DSL(tfg0, coloring, B0, 3)             (.coord 없음 → 픽셀 형식과 구분)
_BLOB_DEF = re.compile(r"^\s*(\w+)\s*=\s*\[([\d,\s]*)\]\s*$")


def parse_program(code: str):
    """DEPRECATED (Task 8): generalize/apply_solution 는 더 이상 이 정규식 파서를 쓰지 않는다
    (program_ast.antiunify_ast/execute 로 대체). compress.py(_blob_program)가 여전히 호출하므로
    삭제하지 않는다. flat program → ops=[(pixel_index, color)] (step 순서). 파싱 불가면 None."""
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
    # DEPRECATED (Task 8): 구 antiunify()/compressible() 의 정규식 판별 헬퍼 — program_ast 경로는
    # _is_cellset_body(AST) 로 판별한다. compressible() 이 여전히 호출하므로 유지.
    return bool(code) and any(_BLOB_DEF.match(ln) for ln in code.splitlines())


def compressible(programs):
    """pixel 프로그램들이 **op 수 불일치**로 anti-unify 불가한가 (= compress 로 덩어리화하면 도움).
    같은 색 픽셀들이 객체 크기만큼 늘어난 케이스(이동 등)를 잡는다. blob 형식이면 이미 압축됨→False."""
    ps = [parse_program(p) for p in programs if not _is_blob_program(p)]
    ps = [p for p in ps if p]
    if len(ps) < 2:
        return False
    return len({len(p) for p in ps}) > 1        # op 수가 서로 다름


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


def _shape_key(cells):
    """셀 목록 → 평행이동 불변 모양 키 (좌상단 정규화)."""
    rs = min(r for r, _ in cells); cs = min(c for _, c in cells)
    return frozenset((r - rs, c - cs) for r, c in cells)


def _selectors(comps_list):
    """소스-객체 선택자 = **변화객체 비교(COMM/DIFF)로 도출**한다. 우선순위:
      1. 속성값 COMM (색·모양·크기의 특정 값이 각 grid 에서 유일) — '같은 것'으로 바로 해결.
      2. 크기 **비교** 극값(모두보다 큼/작음 = 유일 최대/최소) — §4-2 요소간 larger_than 비교로 도출.
         (M2 처럼 '전경 객체 1개'는 '바탕보다 작은 것'=smallest 로, M4/크기 mover 는 largest 로 잡힌다.)
    §2-2/사용자(2026-07-17): 객체를 **나열해 N번째**를 집는 rank 열거(min/max/#2 메뉴)는 추가 편향이라
    안 쓴다 — 극값은 나열이 아니라 '모두와 비교' 결과다. #2 류 임의 순위는 제거.
    반환 = [(name, fn(comps)->cells|None)]. resolve 가 train mover 재현하는 선택자만 채택."""
    # 선택자 = comps → **매치되는 모든 객체 리스트**(scan 순, 결정적). 모호(여러 개)해도 버리지 않는다:
    # train 은 그 중 mover 를 포함하면 유효(사용자 2026-07-18 "유일 아니어도 mover 를 포함"), test 는
    # 후보를 열거해 시도(apply→오답→다음 후보). 예전 '유일=None' 대신 리스트 → 호출측이 후보를 다룬다.
    def by_color(c):
        return lambda comps: [cells for cells, col in comps if col == c]

    def by_shape(shp):
        return lambda comps: [cells for cells, _ in comps if _shape_key(cells) == shp]

    def by_size(z):
        return lambda comps: [cells for cells, _ in comps if len(cells) == z]

    def by_row(rv):                                       # 위치 값: top-row 앵커 == rv (극값 아님)
        return lambda comps: [cells for cells, _ in comps if min(r for r, _ in cells) == rv]

    def by_col(cv):                                       # 위치 값: left-col 앵커 == cv
        return lambda comps: [cells for cells, _ in comps if min(c for _, c in cells) == cv]

    def by_extreme(largest):
        # 크기 극값 = 모두와 비교해 더 큼/작음(§4-2). 동률이면 그 동률 전부(모호 → 열거).
        def pick(comps):
            if not comps:
                return []
            tgt = max(len(c) for c, _ in comps) if largest else min(len(c) for c, _ in comps)
            return [c for c, _ in comps if len(c) == tgt]
        return pick

    prop, rel = [], []
    if comps_list:                                        # 전 grid 공통 값만(선택자가 test 에도 성립하려면)
        common_col = set.intersection(*[{col for _, col in cs} for cs in comps_list])
        for c in sorted(common_col):
            prop.append((f"color={c}", by_color(c)))
        common_shp = set.intersection(*[{_shape_key(cells) for cells, _ in cs} for cs in comps_list])
        for i, shp in enumerate(sorted(common_shp, key=lambda s: (len(s), sorted(s)))):
            prop.append((f"shape#{i}", by_shape(shp)))
        rel = [("smallest", by_extreme(False)), ("largest", by_extreme(True))]   # 크기 비교 극값(§4-2)
        common_sz = set.intersection(*[{len(cells) for cells, _ in cs} for cs in comps_list])
        for z in sorted(common_sz):
            prop.append((f"size={z}", by_size(z)))
        # 위치 **값** selector (극값 아님 — 좌표값 비교): 전 grid 공통인 top-row·left-col 앵커.
        # color=/size= 와 동형으로, '그 행/열에 있는 객체'를 지목(objc_000i=row 값, 000j=col 값).
        common_r = set.intersection(*[{min(r for r, _ in cells) for cells, _ in cs} for cs in comps_list])
        for rv in sorted(common_r):
            prop.append((f"row={rv}", by_row(rv)))
        common_c = set.intersection(*[{min(c for _, c in cells) for cells, _ in cs} for cs in comps_list])
        for cv in sorted(common_c):
            prop.append((f"col={cv}", by_col(cv)))
    return prop + rel                                     # 속성값 COMM 우선, 크기비교 극값은 fallback


def _one(ms):
    """선택자 매치 리스트 → 유일하면 그 cells, 아니면 None (레거시 color/src 경로 = 단일 객체 전제)."""
    return ms[0] if len(ms) == 1 else None


def _color_of_sel(sfn, k=0):
    def fn(g):
        cands = sfn(_components(g))
        if k >= len(cands):
            return None                                 # 그 후보 없음(이 grid 모호도가 낮음)
        r, c = sorted(cands[k])[0]
        return g[r][c]
    return fn


def _coord_index_fn(sfn, rf, cf):
    """(선택자, row식, col식) → fn(grid): 선택 객체 원자로 픽셀 인덱스(row*W+col)."""
    def fn(g):
        cells = _one(sfn(_components(g)))
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


# 객체 이동(placement)의 **앵커-Δ 좌표문법**: dest 셀집합의 앵커(min r, min c) 를 좌표식 문법
# (_axis_matches/_COORD_TEMPLATES, §180-184 의 자유조합 brute-force) 로 그대로 resolve 한다 — pixel
# src slot(resolve_slot 하단)과 동일한 탐색을 앵커 좌표 1점에 적용해 relative(r0+2)·absolute(0,H-1)·
# corner(H-h,W-w) 를 **한 문법에서 창발**시킨다. 손으로 만든 named 앵커(keep/top/bottom, 2026-07-15
# 설계)는 이제 이 문법의 특수사례로 흡수되어 폐기(DEPRECATED, Task4 M-1) — 우연 상수 과적합은
# tier(_axis_tier: 객체위치>객체크기>격자>상수) 로 억제한다.

# ── canonical 구조 prior: 객체가 grid 코너/모서리/제자리에 정렬 (few-shot 과적합 방지) ──
# 앵커식 자유탐색이 2 pair 에서 우연 상수(2*5-r0 등)를 뽑아 코너(H-h,W-w)를 놓치므로, 아래 구조식이
# train 을 재현하면 일반문법보다 **우선** 채택(tier -1). keep=제자리·0=위/왼끝·H-h/W-w=아래/오른끝(코너).
_CANON_ROW = [("r0", lambda a: a["r0"]), ("0", lambda a: 0), ("H-h", lambda a: a["H"] - a["h"])]
_CANON_COL = [("c0", lambda a: a["c0"]), ("0", lambda a: 0), ("W-w", lambda a: a["W"] - a["w"])]


def _canon_matches(atoms, targets, cands, axis):
    """canonical 앵커 후보 중 전 pair targets[axis] 재현하는 (name, fn) — 구조적 prior."""
    return [(nm, fn) for nm, fn in cands
            if all(fn(atoms[i]) == targets[i][axis] for i in range(len(atoms)))]


def _resolve_cellset(vals, train, comps, sels, test_comps=None):
    """cellset slot → (survivors, tried). 소스객체(selector·모양평행이동 일치) 를 dest 로 강체 이동.
    dest 앵커(min r,min c)를 좌표문법(_axis_matches)으로 resolve → relative/absolute/corner 통합. §P5.
    test_comps: 있으면 선택자를 test 입력에도 걸어 (a)0개 고르면 무효로 스킵, (b)여러 개면 그 수만큼
    후보 열거(train 유일이라도) — 사용자 #2: 추상화가 test 에서 유일 선택 가능한지 검증."""
    N = len(vals)
    dests = []
    for i in range(N):
        W = len(train[i]["input"][0])
        dests.append(sorted((idx // W, idx % W) for idx in vals[i]))
    dest_anchor = [(min(r for r, _ in d), min(c for _, c in d)) for d in dests]  # (dr0, dc0) per pair
    keyed, tried = [], []
    for si, (sname, sfn) in enumerate(sels):
        cands = [sfn(comps[i]) for i in range(N)]          # 각 pair 후보 리스트(모호 시 여러 개)
        tnc = len(sfn(test_comps)) if test_comps is not None else None
        if tnc == 0:                                       # test 에서 못 고르는 선택자 = 무효 추상화 → 스킵
            tried.append((f"move@{sname}: test 선택0", False)); continue
        atoms, ok_shape, ncand = [], True, 1
        for i in range(N):
            d = dests[i]; dr, dc = min(r for r, _ in d), min(c for _, c in d)
            dshape = sorted((r - dr, c - dc) for r, c in d)
            match = None                                    # dest 와 평행이동 일치하는 후보 = mover
            for cand in cands[i]:                           # (사용자: 유일 아니어도 mover 를 포함하면 유효)
                if len(cand) != len(d):
                    continue
                sr, sc = min(r for r, _ in cand), min(c for _, c in cand)
                if sorted((r - sr, c - sc) for r, c in cand) == dshape:
                    match = cand; break
            if match is None:
                ok_shape = False; break
            atoms.append(_obj_atoms(match, train[i]["input"]))
            ncand = max(ncand, len(cands[i]))               # test 모호도(후보 수) 상한
        if not ok_shape:
            tried.append((f"move@{sname}: mover 미포함", False)); continue
        K = min(max(ncand, tnc or 1), 3)                     # train·test 모호도 최대치로 후보 열거(ar: train유일·test2개)

        def _push(nm, rf, cf, tier, depth=0, sfn=sfn, si=si, K=K):
            for k in range(K):
                nk = f"{nm}#{k}" if K > 1 else nm
                keyed.append(((tier, k, depth, si, len(nk)), nk, _translate_obj_fn(sfn, rf, cf, k)))
        # canonical 구조 prior — train 재현 시 일반문법(≥0)보다 우선. 구조식(제자리/모서리/코너=격자·객체
        # 상대라 크기 달라도 일반화, tier -2) > 상수(absolute, tier -1).
        # ── 절대/상대 모델 판별(few-shot 모호성 해소): src const & dst const 인 축은 절대(=v)와 상대(src+Δ)
        #    가 train 서 둘 다 맞아 우연. 이를 **source 가 varies 인 '정보축'** 이 밝힌 모델로 확정한다:
        #    정보축 dst const → 절대신호(점으로 감), dst varies 인데 Δ const → 상대신호(Δ 만큼 이동).
        #    am: col(src varies)→dst const=절대 ⇒ row(모호)도 절대(=2). ak: row(src varies)→Δ const=상대
        #    ⇒ col(모호)도 상대(c0+1). vacate(미이동)면 keep 이 정답이라 약화하지 않는다.
        moved = any(dest_anchor[i] != (atoms[i]["r0"], atoms[i]["c0"]) for i in range(N))
        src_var = [len({a[k] for a in atoms}) > 1 for k in ("r0", "c0")]
        dst_var = [len({t[ax] for t in dest_anchor}) > 1 for ax in (0, 1)]
        drs = [dest_anchor[i][0] - atoms[i]["r0"] for i in range(N)]
        dcs = [dest_anchor[i][1] - atoms[i]["c0"] for i in range(N)]
        d_const = [len(set(drs)) == 1, len(set(dcs)) == 1]
        abs_sig = any(src_var[ax] and not dst_var[ax] for ax in (0, 1))       # 정보축 절대신호
        rel_sig = any(src_var[ax] and dst_var[ax] and d_const[ax] for ax in (0, 1))  # 정보축 상대신호
        model = "abs" if (abs_sig and not rel_sig) else ("rel" if (rel_sig and not abs_sig) else "amb")

        # 절대(=const)·격자상대(모서리 0/코너 H-h)는 원래 tier 유지(-1/-2 — 코너가 절대상수를 이김: 크기불변
        # 일반화, made000b 코너 prior). 모델은 **source-상대(keep/offset)** 를 약화할지만 정한다: arrive 인데
        # 절대모델이면 keep/offset 이 우연(정보축이 '점으로 감'이라 밝힘) → 약화(+2). 상대모델/vacate 면 그대로.
        def _rel_tier(base):                                  # source-상대(keep/offset) tier
            return 2 if (moved and model == "abs") else base
        cr = [(rn, rf, _rel_tier(-2) if rn == "r0" else -2)
              for rn, rf in _canon_matches(atoms, dest_anchor, _CANON_ROW, 0)]
        cc = [(cn, cf, _rel_tier(-2) if cn == "c0" else -2)
              for cn, cf in _canon_matches(atoms, dest_anchor, _CANON_COL, 1)]
        if not dst_var[0]:                                    # absolute 행 앵커(dst 행 불변)
            v = dest_anchor[0][0]; cr.append((f"={v}", (lambda a, v=v: v), -1))
        if not dst_var[1]:                                    # absolute 열 앵커(dst 열 불변)
            v = dest_anchor[0][1]; cc.append((f"={v}", (lambda a, v=v: v), -1))
        # 우하단(BR) 앵커: dest BR = dest_TL + (h-1, w-1). BR 이 전 pair 상수면 TL = BR - (h-1)
        # (§4-2 "네 코너"; BR 이 격자 코너 H-1 이면 이미 H-h 로 커버). 크기 다른 test 객체도 BR 고정.
        dbr = [(dest_anchor[i][0] + atoms[i]["h"] - 1, dest_anchor[i][1] + atoms[i]["w"] - 1)
               for i in range(N)]
        if len({t[0] for t in dbr}) == 1:
            br = dbr[0][0]; cr.append((f"BR={br}", (lambda a, br=br: br - a["h"] + 1), -1))
        if len({t[1] for t in dbr}) == 1:
            bc = dbr[0][1]; cc.append((f"BR={bc}", (lambda a, bc=bc: bc - a["w"] + 1), -1))
        # relative(상대이동): dest − source = Δ. 전 pair 상수면 source+Δ (좌표 DIFF 아래 숨은 COMM=Δ).
        # 상대모델/vacate 면 최우선(-3), 절대모델 arrive 면 약화(우연). keep(Δ=0) 포함.
        if d_const[0]:
            d = drs[0]; cr.append((f"r0{d:+d}", (lambda a, d=d: a["r0"] + d), _rel_tier(-3)))
        if d_const[1]:
            d = dcs[0]; cc.append((f"c0{d:+d}", (lambda a, d=d: a["c0"] + d), _rel_tier(-3)))
        for rn, rf, rt in cr:
            for cn, cf, ct in cc:
                _push(f"move[{rn},{cn}]@{sname}", rf, cf, max(rt, ct))
        r_hits, r_tr = _axis_matches(atoms, dest_anchor, 0)    # dest 앵커 행식 (일반문법 fallback)
        c_hits, c_tr = _axis_matches(atoms, dest_anchor, 1)    # dest 앵커 열식
        if not r_hits or not c_hits:
            if not (cr and cc):
                tried.append((f"move@{sname}: 앵커식 없음", False))
            continue
        for rn, rf, rd in r_hits:
            for cn, cf, cd in c_hits:
                _push(f"move({rn},{cn})@{sname}", rf, cf, _axis_tier(rn, 0) + _axis_tier(cn, 1), rd + cd)
    keyed.sort(key=lambda t: t[0])
    for _k, name, fn in keyed[:_MATCH_CAP]:
        tried.append((name, True))
    survivors = [(name, fn) for _k, name, fn in keyed[:_MATCH_CAP]]
    if not survivors:
        tried.append(("<no anchor-delta>", False))
    return survivors, tried


def _translate_obj_fn(sfn, rf, cf, k=0):
    """(선택자, 앵커행식, 앵커열식, 후보k) → fn(grid): 선택자 매치 중 **k-번째 후보**(scan 순)를 (rf,cf)
    앵커로 강체 이동한 cells(idx). 모호(여러 후보) 시 version space 가 k=0,1,.. 를 각기 시도(apply→오답→다음)."""
    def fn(g):
        cands = sfn(_components(g))
        if k >= len(cands):
            return None                                 # 그 후보 없음(이 grid 의 모호도가 낮음)
        cells = sorted(cands[k])
        a = _obj_atoms(cells, g)
        tr, tc = rf(a), cf(a)
        if tr is None or tc is None:
            return None
        sr = min(r for r, _ in cells); sc = min(c for _, c in cells)
        W = len(g[0])
        return [(r - sr + tr) * W + (c - sc + tc) for (r, c) in cells]
    return fn


def resolve_slot(slot, train, test_input=None):
    """slot(kind='src'|'color'|'cellset') → (survivors=[(name, fn(grid))], tried=[(name, ok)]).
    소스 객체는 기하 선택자로(배경 가정 없이), 값은 좌표식/객체색/객체이동 자유조합 탐색. train 으로만 검증(§P5).
    test_input: 있으면 **선택자를 test 입력에도 걸어** 유일성/후보수를 확인(§사용자 #2 — 추상화가 test 에서
    실제로 그 객체를 고를 수 있어야 유효; test *입력*은 봐도 됨, P5 는 test *출력*만 금지)."""
    vals = slot["values"]
    N = len(vals)
    if N != len(train):
        return [], [("<len-mismatch>", False)]
    # grid-declarative slot(G1 의 size/color): `_execute_grid` 은 **contents 만** 산출하므로 이 값은
    # 실행에 전혀 안 쓰인다. per-pair 리터럴이 pair 마다 달라 slot(변수)이 됐어도 답과 무관 → 입력관계로
    # 일반화해 survivor 를 낸다(옛 버그: size 핸들러 없음→dict//int; grid color→set(vals) unhashable).
    # kind='size' 는 grid 전용. kind='color' 는 grid(값=AST dict)와 pixel(값=int)이 kind 를 공유하니
    # **dict 값일 때만** grid-color 로 처리(pixel 정수색은 아래 기존 경로 유지).
    if slot["kind"] == "size":
        return ([("size(input_grid)", lambda g: {"height": len(g), "width": len(g[0])})],
                [("size(input_grid)", True)])
    if slot["kind"] == "color" and any(isinstance(v, dict) for v in vals):
        return ([("color(input_grid)", lambda g: sorted({x for row in g for x in row}))],
                [("color(input_grid)", True)])
    comps = [_components(e["input"]) for e in train]
    sels = _selectors(comps)
    test_comps = _components(test_input) if test_input else None
    tried, survivors = [], []
    if slot["kind"] == "cellset":
        return _resolve_cellset(vals, train, comps, sels, test_comps)

    if slot["kind"] == "color":
        for k in sorted(set(vals)):                       # 상수색 후보
            ok = all(v == k for v in vals)
            tried.append((f"const {k}", ok))
            if ok:
                survivors.append((f"const {k}", (lambda g, k=k: k)))
        for sname, sfn in sels:                           # 선택자-객체의 색(color_of_fg 의 bg-free 대체)
            tnc = len(sfn(test_comps)) if test_comps is not None else None
            if tnc == 0:                                  # test 에서 못 고르는 선택자 = 무효 추상화
                tried.append((f"color@{sname}: test 선택0", False)); continue
            ncand, ok = 1, True
            for i in range(N):
                cs = sfn(comps[i]); ncand = max(ncand, len(cs))
                # 후보 중 색이 mover 색(vals[i])인 것이 있으면 유효(유일 아니어도; k-일관성으로 mover 확정)
                if not any(train[i]["input"][c[0][0]][c[0][1]] == vals[i] for c in cs):
                    ok = False; break
            tried.append((f"color@{sname}", ok))
            if not ok:
                continue
            K = min(max(ncand, tnc or 1), 3)              # train·test 모호도 최대치로 후보 열거
            for k in range(K):                            # 모호 시 후보 열거(cells 와 같은 @선택자#k 로 일관)
                nm = f"color@{sname}" + (f"#{k}" if K > 1 else "")
                survivors.append((nm, _color_of_sel(sfn, k)))
        return survivors, tried

    # --- src / 픽셀 인덱스 slot: 선택자 × 좌표식 자유조합 ---
    def _rc(v, W):
        return (tuple(v) if isinstance(v, (list, tuple)) else (v // W, v % W))
    targets = [_rc(vals[i], len(train[i]["input"][0])) for i in range(N)]
    keyed = []                                         # (정렬키, name, fn) — 최선 조합이 앞
    for si, (sname, sfn) in enumerate(sels):
        atoms, ok_sel = [], True
        for i in range(N):
            cells = _one(sfn(comps[i]))
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
    """resolved version space → [(label, choice{name:fn})] (≤limit; few-shot 애매성=3-attempt).

    **선택자-일관 우선(사용자 2026-07-18):** 한 mover 를 가리키는 슬롯들(cellset·color)은 **같은 선택자**를
    써야 한다. 그래서 각 COMM 선택자(shape#·size=·color=…)를 **하나의 가설로 통째** 시도한다 — anchor 변형을
    product 로 돌려 3-try 를 소진하지 않게. 우선순위: **속성값 일치(색·크기·모양)** 먼저, **관계 극값
    (smallest/largest = DIFF 분해)** 나중. 남으면 기존 product fallback."""
    slots, resolved = sol["slots"], sol.get("resolved") or {}
    names = list(slots.keys())
    if not names:
        return [("(변수 없음)", {})]
    pools = [resolved.get(n) or [] for n in names]
    if any(not pool for pool in pools):
        return []
    out, seen = [], set()

    def _sel(nm):                                   # survivor 이름의 @선택자 ("..@size=4"→"size=4"), 없으면 None
        return nm.rsplit("@", 1)[1] if "@" in nm else None

    def _emit(combo):
        key = tuple(id(fn) for _, fn in combo)
        if key in seen:
            return
        seen.add(key)
        out.append((", ".join(f"{names[i]}={combo[i][0]}" for i in range(len(names))),
                    {names[i]: combo[i][1] for i in range(len(names))}))

    all_sels = []                                   # 등장 선택자 (중복 제거, 순서 보존)
    for pool in pools:
        for nm, _ in pool:
            s = _sel(nm)
            if s and s not in all_sels:
                all_sels.append(s)
    # 속성값 일치(관계 극값 아님) 를 먼저. stable → 그 안에서는 등장순서(=선택자 우선순위) 유지.
    all_sels.sort(key=lambda s: s in ("smallest", "largest"))
    for s in all_sels:                              # 각 COMM 선택자 = 슬롯 전체 일관 조합 하나
        combo = [next(((nm, fn) for nm, fn in pool if _sel(nm) == s), pool[0]) for pool in pools]
        _emit(combo)
        if len(out) >= limit:
            return out
    for combo in itertools.product(*pools):         # fallback: 기존 곱(선택자 없는 슬롯·잔여 조합)
        _emit(combo)
        if len(out) >= limit:
            break
    return out


