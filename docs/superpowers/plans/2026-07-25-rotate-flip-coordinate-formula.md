# rotate/flip 픽셀 공통 좌표식 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (또는 executing-plans) 로 태스크별 실행. 스텝은 `- [ ]` 체크박스.

**Goal:** 단일 객체 rotate/flip 을, 같은 색 픽셀 대응에서 창발하는 **공통 좌표식 `r'=F(r,c), c'=G(r,c)`** 로 풀되, coloring 만 쓰고 단일 run(`resolve` additive)을 유지한다. move 60/60 불변.

**Architecture:** primitive 원자(per-pixel `r,c` + `H,W` + 상수 + `{+,-,*}`)로 좌표식 공간을 brute-force 생성 → 색별 입력 셀집합에 적용 → 출력 셀집합과 **set 일치**로 검증 → train 전 쌍 공통식 채택. `arbor/reasoning/antiunify.py` 의 기존 `_gen_exprs`/`_axis_matches`(객체 anchor·스칼라·축독립) 를 **per-pixel·set 기반**으로 확장하고, `resolve` 가 기존 평행이동 후보와 **병렬로** 시도해 이기는 것을 채택.

**Tech Stack:** Python3 stdlib. `env.dataset`(태스크 로드), `arbor/reasoning/antiunify.py`(탐색), `arbor/procedural_memory/operators/resolve.py`(operator), `coloring` DSL(동결).

## Global Constraints (spec §6 에서 verbatim)

- **손코딩 0**: 회전행렬·`dr→dc` 지름길 금지. 식은 primitive `r,c,H,W,±,*` 조합에서 **탐색으로 발견**(§1-3/§4-1). 축·회전·중심은 창발.
- **임의 필터 0**: "색0=배경"·"비배경 선택" 금지(§1-4, [[no-arbitrary-filters]]). 색 그룹핑 + 균일배경 자동불변.
- **단일 run·additive**: `ArborAgent.run` 안 `resolve` 확장만. 새 run/operator/DSL/property 신설 금지(§1-6/§1-1). 필요 시 §5 절차로 별도 승인.
- **coloring 만**: 변환 DSL은 동결 `coloring` 하나.
- **탐색 가시성**: generate→apply→set-compare→verify. 시도·기각 후보가 트레이스/로그에 남는다(§1-5, no-silent-caps).
- **결정성**: 결과 영향 반복은 정렬(§2-6). `PYTHONHASHSEED` 무관하게 동일.
- **move 60/60 불변** — 주 게이트. 검증은 테스트파일이 아니라 **행동 게이트**(점수·트레이스)로.

## File Structure

- **Create (spike, 임시)** `<scratchpad>/spike_pixel_formula.py` — 실데이터 검증 스파이크. 솔버 미결합. Task 1 산출.
- **Modify** `arbor/reasoning/antiunify.py` — per-pixel 원자·set 기반 좌표식 탐색 `search_pixel_formula(...)` + 형제 배치 fn `_transform_obj_fn(...)` 추가 (기존 `_gen_exprs`/`_translate_obj_fn` 옆). Task 3.
- **Modify** `arbor/procedural_memory/operators/resolve.py` (및 `_resolve_cellset` 호출 경로) — per-pixel 식 후보를 기존 평행이동 후보와 병렬 생성·검증·채택. Task 4.
- **검증** — `arbor/__main__.py`(`python -m arbor --dataset`) 로 rotate/flip/move 점수. 테스트파일 신설 없음.

---

## Task 1: 검증 스파이크 — per-pixel 좌표식 탐색이 실 rotate/flip 을 푸는가 (DECISION GATE)

**목적:** 솔버에 손대기 전에, primitive 좌표식 탐색이 실제 단일객체 rotate/flip 을 **몇 개나** 푸는지, 어떤 식이 나오는지, 어디서 깨지는지(특히 배경식별)를 **실데이터로 확정**한다. §8 미해결(원자·상수범위·효율)을 경험적으로 닫는다. 결과가 통합 여부·범위를 가른다.

**Files:**
- Create: `<scratchpad>/spike_pixel_formula.py`

**Interfaces (produces):**
- `search_pixel_formula(train_pairs, *, max_ops=2, const_max=8, cap=200000) -> list[(name_row, name_col, Frow, Gcol)]` — train 전 쌍에서 색별 set 일치하는 좌표식 쌍 생존자(단순성순).
- CLI: `python <scratchpad>/spike_pixel_formula.py rotate` → 집계 리포트.

- [ ] **Step 1: 스파이크 작성**

`<scratchpad>/spike_pixel_formula.py` 전체:

```python
# -*- coding: utf-8 -*-
"""SPIKE(솔버 미결합): per-pixel 공통 좌표식 탐색이 단일객체 rotate/flip 을 푸는지 실데이터 검증.
   객체 격리는 임시 스파이크 휴리스틱(최빈색=배경)만 씀 — 탐색 알고리즘 검증용, 솔버엔 안 들어감.
   실행: python <이 파일> rotate|flip [limit]"""
import sys
from collections import deque, Counter
from env.dataset import list_tasks, load_task

_OPS = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b), ("*", lambda a, b: a * b)]

def _atom_names(const_max):
    return ["r", "c", "H", "W"] + [str(k) for k in range(const_max + 1)]

def _env(r, c, H, W, const_max):
    d = {"r": r, "c": c, "H": H, "W": W}
    d.update({str(k): k for k in range(const_max + 1)})
    return d

def gen_exprs(names, max_ops=2):
    """primitive 원자에서 ≤max_ops 이항연산(좌결합) 표현식 전부. [(name, fn(env))]. 결정적."""
    base = [(n, (lambda d, n=n: d[n])) for n in names]
    exprs = dict(base)                                   # name->fn, 중복 제거
    frontier = list(base)
    for _ in range(max_ops):
        nxt = []
        for en, ef in frontier:
            for an, af in base:
                for osym, ofn in _OPS:
                    nm = f"({en}{osym}{an})"
                    if nm in exprs:
                        continue
                    fn = (lambda d, ef=ef, af=af, ofn=ofn: ofn(ef(d), af(d)))
                    exprs[nm] = fn
                    nxt.append((nm, fn))
        frontier = nxt
    return sorted(exprs.items())                         # 결정적 순서

def _by_color(grid):
    m = {}
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            m.setdefault(v, set()).add((r, c))
    return m

def _bg(grid):                                           # SPIKE 휴리스틱 only (솔버 미사용)
    return Counter(v for row in grid for v in row).most_common(1)[0][0]

def search_pixel_formula(train_pairs, max_ops=2, const_max=8):
    """train 전 쌍에서 색별 set 일치하는 (row식, col식) 생존자. 객체=비최빈색(스파이크 격리)."""
    names = _atom_names(const_max)
    exprs = gen_exprs(names, max_ops)                     # [(name, fn)]
    # pair 별: 객체 색그룹(입력) + 출력 색그룹 + (H,W)
    ctx = []
    for gin, gout in train_pairs:
        H, W = len(gin), len(gin[0])
        bi = _bg(gin)
        cin = {col: cells for col, cells in _by_color(gin).items() if col != bi}
        cout = _by_color(gout)
        ctx.append((H, W, cin, cout))
    def _fits(Fr, Fc):
        for H, W, cin, cout in ctx:
            for col, cells in cin.items():
                pred = set()
                for (r, c) in cells:
                    e = _env(r, c, H, W, const_max)
                    rr, cc = Fr(e), Fc(e)
                    if not (0 <= rr < H and 0 <= cc < W):
                        return False
                    pred.add((rr, cc))
                if pred != cout.get(col, set()):
                    return False
        return True
    surv = []
    for rn, Fr in exprs:
        for cn, Fc in exprs:
            if _fits(Fr, Fc):
                surv.append((rn, cn, Fr, Fc))
    surv.sort(key=lambda t: (len(t[0]) + len(t[1]), t[0], t[1]))   # 단순성 우선
    return surv

def main(argv):
    ds = argv[1] if len(argv) > 1 else "rotate"
    limit = int(argv[2]) if len(argv) > 2 else None
    solved, total, examples = 0, 0, []
    from collections import deque as _dq
    def comps(g):                                        # 4-conn 성분수(단일객체 필터용)
        H, W = len(g), len(g[0]); seen = [[False]*W for _ in range(H)]; n = 0
        bg = _bg(g)
        for i in range(H):
            for j in range(W):
                if g[i][j] != bg and not seen[i][j]:
                    n += 1; q = _dq([(i, j)]); seen[i][j] = True
                    while q:
                        r, c = q.popleft()
                        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
                            nr, nc = r+dr, c+dc
                            if 0<=nr<H and 0<=nc<W and g[nr][nc]!=bg and not seen[nr][nc]:
                                seen[nr][nc]=True; q.append((nr,nc))
        return n
    for tid, p in list_tasks(ds, limit=limit):
        t = load_task(p)
        if comps(t["train"][0]["input"]) != 1:           # 1차 범위 = 단일객체
            continue
        total += 1
        pairs = [(pr["input"], pr["output"]) for pr in t["train"]]
        surv = search_pixel_formula(pairs)
        if surv:
            solved += 1
            if len(examples) < 12:
                rn, cn, _, _ = surv[0]; examples.append((tid, rn, cn, len(surv)))
    print(f"[{ds}] 단일객체 {total} 중 좌표식 발견 {solved}  ({100*solved/max(total,1):.0f}%)")
    for tid, rn, cn, k in examples:
        print(f"  {tid}: r'={rn}  c'={cn}   (생존식 {k})")

if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 2: 스파이크 실행 — rotate**

Run: `cd /Users/sir_k/Desktop/PySOAR && python3 <scratchpad>/spike_pixel_formula.py rotate 60`
Expected: `[rotate] 단일객체 N 중 좌표식 발견 M (…%)` + 예시 식들. **판정 기준:** M>0 이고 예시 식이 회전꼴(`r'=(...c...)`, `c'=(...r...)` 처럼 축 교차)이면 원리 성립.

- [ ] **Step 3: 스파이크 실행 — flip + move(비회귀 감각)**

Run:
```bash
cd /Users/sir_k/Desktop/PySOAR
python3 <scratchpad>/spike_pixel_formula.py flip 60
python3 <scratchpad>/spike_pixel_formula.py move 30
```
Expected: flip 에서 `c'=(W-1)-c` 류 반전식, move 에서 `r'=r±k` 류 평행이동식이 나오면 통일 원리 확인. 상수범위(`const_max`)·`max_ops` 가 부족해 0%면 Step 1 의 파라미터를 키워 재실행(§8 상수범위 논점 경험적 확정).

- [ ] **Step 4: 리포트 + DECISION GATE**

`<scratchpad>/spike_report.md` 에 기록: (a) rotate/flip/move 발견율, (b) 대표 식, (c) **실패 모드** — 특히 배경식별(off-center 객체에서 최빈색≠배경이거나 다색 배경) 과 상수범위/탐색폭 폭발. 
**게이트:** 사용자에게 리포트 제시 → 통합(Task 2~4) 진행할지, 스파이크 결과로 설계 수정할지 결정. (발견율이 낮거나 실패모드가 근본적이면 여기서 멈추고 재설계 — 솔버 미오염.)

- [ ] **Step 5: 커밋(스파이크는 scratchpad 라 미추적; 리포트만 필요 시 docs 로)**

스파이크 파일은 scratchpad(미추적). 결과 요약을 `docs/superpowers/specs/2026-07-25-rotate-flip-coordinate-formula-design.md` §8 하단에 "스파이크 결과" 로 append 후 커밋:
```bash
cd /Users/sir_k/Desktop/PySOAR && git add docs/superpowers/specs/2026-07-25-rotate-flip-coordinate-formula-design.md && git commit -m "docs(spec): rotate/flip 좌표식 스파이크 결과 기록"
```

---

> **Tasks 2–4 는 Task 1 게이트 통과 후 확정한다.** 스파이크가 원자·상수범위·배경처리의 실제 형태를 정하므로, 통합 코드는 그 결과에 맞춰 아래 골격을 구체화한다. (지금 완전코드로 박으면 미검증 알고리즘을 조기 고정 — writing-plans 는 검증된 산출을 다음 태스크의 입력으로 삼는다.)

## Task 2: (게이트 후) 배경·객체 격리 방식 확정

**목적:** 스파이크의 임시 휴리스틱(최빈색=배경)을 대체할 **임의필터 없는** 격리를 확정. 후보: (a) 색 그룹핑 전체를 매핑하되 "F,G 를 만족하는 색들의 최대 정합" 으로 배경이 창발, (b) compare(COMM/DIFF) 로 변화 관여 색 도출. 스파이크 실패모드 리포트가 어느 쪽인지 정한다. **산출:** 격리 규약 1개 + 근거.

## Task 3: antiunify.py 에 per-pixel 탐색·배치 fn 추가

**Files:** Modify `arbor/reasoning/antiunify.py`
**Interfaces:**
- Consumes: Task 1 의 `search_pixel_formula` 알고리즘(검증본), Task 2 격리 규약.
- Produces: `search_pixel_formula(train, comps, ...) -> [(name, cellset_fn(grid))]` — 좌표식 생존자를 grid→예측셀집합 fn 으로. `_transform_obj_fn(Fr, Fc)` — 기존 `_translate_obj_fn`(438행 강체이동)의 형제로, 각 셀 `(r,c)→(Fr(env),Fc(env))` 매핑.
- 원자: 기존 `_obj_atoms`(스칼라)와 별도로 **per-pixel env**(r,c 포함) 를 쓰는 `_gen_exprs` 확장(원자에 r,c 추가). `_ATOM_NAMES` 는 건드리지 않고 새 리스트로(기존 anchor 탐색 회귀 0).

(구체 코드·정확한 시그니처는 Task 1 산출 확정 후 이 태스크에서 작성. 검증: `python3 -c "from arbor.reasoning.antiunify import search_pixel_formula"` import 스모크 + 스파이크와 동일 태스크에서 동일 식 재현.)

## Task 4: resolve additive 결합 + 물질화 + 행동 게이트

**Files:** Modify `arbor/procedural_memory/operators/resolve.py`, `arbor/reasoning/antiunify.py`(`_resolve_cellset`/`resolve_slot` 후보 병합부)
**Interfaces:** Consumes Task 3 산출.
- `resolve` 가 기존 평행이동/anchor 후보(`_resolve_cellset`)와 **per-pixel 식 후보를 병렬 생성** → train 검증 → keyed 정렬로 이기는 것 채택. 식 후보는 `_transform_obj_fn` 으로 cellset 산출 → 기존 coloring 물질화·`apply_solution` 경로 그대로.
- move 는 평행이동이 이겨 무변.

**행동 게이트(테스트파일 없음):**
```bash
cd /Users/sir_k/Desktop/PySOAR
python -m arbor --dataset move     # SCORE 60/60 불변 (회귀 0)
python -m arbor --dataset rotate   # SCORE 신규 >0
python -m arbor --dataset flip      # SCORE 신규 >0
python -m arbor --dataset object_coloring   # objc 게이트 불변
python3 -c "import arbor, debugger.reports.dashboard; print('import OK')"
```
Expected: move/objc 불변, rotate/flip 신규 해결 >0, 트레이스에 시도·기각 좌표식 잔존. 결정성(seed 무관) 확인.

---

## Self-Review (플랜 작성자)

- **Spec coverage:** §2 원리→Task1 스파이크가 실증 · §4.1 원자→Task1/3 · §4.2 set매핑→Task1 `_fits`/Task3 · §4.3 additive→Task4 · §4.4 물질화→Task4 · §8 미해결(원자/상수/효율/배경)→Task1 게이트+Task2. 커버됨.
- **Placeholder:** Task1 완전코드. Task2~4 는 "게이트 후 확정" 을 **명시적 설계결정**으로 둠(미검증 알고리즘 조기고정 회피) — 빈칸 아님, 의존관계 명시.
- **Type consistency:** `search_pixel_formula` 시그니처가 Task1(train_pairs)→Task3(train,comps) 로 진화함을 Task3 Interfaces 에 명시(스파이크→솔버 문맥 반영).
