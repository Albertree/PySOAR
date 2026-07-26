# Stage 3 — 변환을 anti-unify impasse-resolution 으로 내재화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** rotate/flip 을 푸는 `_try_transform_fallback`(SOAR 루프 밖)을 은퇴시키고, 그 로직을 **anti-unify 가
실패(diff program 안 맞음)한 impasse 의 resolution operator** 로 메인 파이프라인에 넣는다. 결과는 WM
`TASK.solution` 아티팩트(좌표식 coloring)로 물질화되어 리포트가 자동 렌더한다.

**Architecture:** generalize 실패 브랜치에서 `needs-transform` 신호 emit(기존 `needs-compress` 패턴 복제) →
새 `transform` operator 가 발화해 `transform_solution` 을 grid-body coloring AST 로 물질화하고 WM
`f"{tid}.property" ^solution` + 테스트 answer 를 쓴다 → 기존 submit 이 채점. 개념 이름(center/rotate/…) 없음.

**Tech Stack:** Python SOAR 커널(`arbor/soar/`), operator body(`arbor/procedural_memory/operators/`), JSON
production(`arbor/procedural_memory/production_rules/`), `arbor/reasoning/transform.py`(좌표식 해).

## Global Constraints

- **게이트 불변(하드):** `python -m debugger.score move` = **60/60**, `rotate` = **36/36**, `flip` = **24/24**.
  각 Task 끝에서 검증. HASHSEED 무관 결정적(§2-6).
- **개념 이름 금지:** solution·operator·WM 어디에도 `center/axis/pivot/rotate/flip/move` symbol 없음. 좌표 산술만.
- **불변은 compare 관찰:** offset 유효성은 `transform_solution` 의 `invariant`(mover in/out bbox합 COMM)에서만.
- **fallback 은 마지막에만 은퇴:** Task 4 전까지 `_try_transform_fallback` 을 안전망으로 유지(회귀 방지).
- **캐시:** 리포트 재생성 전 `debugger.solve_cache.clear_cache()` (솔버 로직 바뀌면 캐시 낡음).

---

### Task 1: 좌표식 해 → 실행 가능한 grid-body coloring AST + 테스트 answer

**Files:**
- Modify: `arbor/reasoning/transform.py` (add `transform_solution_ast`)
- Test: `tests/test_transform_solution_ast.py` (create)

**Interfaces:**
- Consumes: `transform_solution(train)` (transform.py:435 — `{kind, per_pair:[{obj_in,params,color}], invariant}`),
  `_components`, `_nonzero`, `_ocolor`.
- Produces: `transform_solution_ast(train, test_input) -> (solution_ast: dict, answer: list[list[int]]) | None`.
  `solution_ast` = grid-body AST `{"body":[set_grid_size, set_grid_color, set_grid_contents(program=[coloring...])]}`
  where each coloring target = `coordinate_of(select("input","PIXEL", in([dest coords])))`, color = 객체색 or 0.
  `answer` = test 입력에 F 적용(선택객체만, 나머지 정지)한 격자.

- [ ] **Step 1: 실패하는 테스트 작성** — `transform_solution_ast` 가 rota000b/rota000z/flip000m 에서
  (AST, answer) 를 반환하고 answer == test 출력, AST 가 grid-body(`PA._is_grid_body`)인지.

```python
import pytest
from env.dataset import list_tasks, load_task
from arbor.reasoning.transform import transform_solution_ast
import arbor.reasoning.program_ast as PA

@pytest.mark.parametrize("ds,tid", [("rotate","rota000b"),("rotate","rota000z"),("flip","flip000m")])
def test_ast_and_answer(ds, tid):
    t = load_task(dict(list_tasks(ds))[tid])
    train = [(p["input"], p["output"]) for p in t["train"]]
    tin, tout = t["test"][0]["input"], t["test"][0]["output"]
    res = transform_solution_ast(train, tin)
    assert res is not None
    ast, answer = res
    assert answer == tout
    assert PA._is_grid_body(ast.get("body") or [])
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_transform_solution_ast.py -x` → `AttributeError: transform_solution_ast`.

- [ ] **Step 3: 최소 구현** — `transform.py` 에 추가. 테스트 answer 는 기존 `solve_any` 재사용(정답 격자).
  AST 는 test 객체의 목적지 좌표(F 적용)로 coloring 스텝 구성(선택객체) + 정지객체는 손대지 않음(=diff 아님,
  객체 전체 재칠). 좌표는 grid-무관이라 `input` 기준 통일(§pixelize 규약).

```python
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
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_transform_solution_ast.py -v` → 3 PASS.

- [ ] **Step 5: 커밋** — `git add arbor/reasoning/transform.py tests/test_transform_solution_ast.py &&
  git commit -m "feat(transform): transform_solution_ast — 좌표식 해를 실행 AST+answer 로"`

---

### Task 2: transform operator body + 등록

**Files:**
- Create: `arbor/procedural_memory/operators/transform.py` (`_op_transform`)
- Modify: `arbor/procedural_memory/operators/__init__.py` (register)
- Test: `tests/test_op_transform.py` (create)

**Interfaces:**
- Consumes: `ag.kg` (task/tid), `ag.wm`, `transform_solution_ast` (Task 1). 패턴 참조: `synthesize.py:11-72`
  (answer 직접 계산·answer-ready), `generalize.py:112-117`(solution WME 쓰기), `compress.py:251-253`(신호 clear).
- Produces: `_op_transform(ag)` — WM 에 `f"{tid}.property" ^solution`(AST json), test answer(`ag.kg["answer"]`
  + `ag.add_output_wme` + `^answer-ready yes`), `^transformed yes`, `needs-transform` 제거. 해 없으면
  `^generalized failed`(정직한 impasse) + `needs-transform` 제거.

- [ ] **Step 1: 실패 테스트** — 최소 agent 를 rota000b 로 build→run 후 WM 에 `T{tid}.property ^solution` 존재 확인.

```python
from env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve
def test_transform_writes_solution():
    t = load_task(dict(list_tasks("rotate"))["rota000b"])
    r = run_solve("rota000b", t, use_cache=False)
    sol = next((v for (i,a,v) in r["wm"] if i == "Trota000b.property" and a == "solution"), None)
    assert sol is not None
```

- [ ] **Step 2: 실패 확인** (solution 아직 None).
- [ ] **Step 3: 구현** — `_op_transform(ag)` 작성(위 Interfaces). `operators/__init__.py:19-22` `OPERATOR_BODIES`
  에 `"transform": _op_transform` 추가, import 추가.
- [ ] **Step 4: 통과 확인** — 단, 이 Task 는 operator body 만 등록(아직 production 없으면 발화 안 함).
  테스트는 Task 3 후 통과 → 이 Step 은 "import·등록 성공 + body 단위호출 시 solution 쓴다" 로 좁혀 검증
  (body 를 직접 호출하는 단위테스트로).
- [ ] **Step 5: 커밋** — operator body + 등록.

---

### Task 3: production rule + generalize 실패 브랜치 신호

**Files:**
- Create: `arbor/procedural_memory/production_rules/transform.json`
- Modify: `arbor/procedural_memory/operators/generalize.py:107` (신호 emit)

**Interfaces:**
- Consumes: `generalize.py` 실패 지점(`generalized=failed` 직전). 패턴 = `compress.json:9-10` + `generalize.py:104-106`.
- Produces: `transform.json` propose(`needs-transform=yes ∧ ¬transformed ∧ ¬answer-ready` → `^operator transform`).
  generalize.py: `generalized=failed` **대신** `ag.wm.add(sid,"needs-transform","yes")` 를 먼저 두고, transform
  operator 가 해 없을 때만 `generalized=failed` 로 되돌린다(무한루프 방지 위해 `transformed` 가드).

- [ ] **Step 1: 실패 확인** — Task 2 의 `test_transform_writes_solution` 이 아직 실패(발화 안 됨).
- [ ] **Step 2: 구현** — `transform.json` 작성(`compress.json` 골격 복제, name=transform). `generalize.py:107`
  주변 수정: 실패 시 `needs-transform` emit(단 `transformed` 아직 아닐 때만). move 경로(`needs-compress`)는
  건드리지 않음 — compress 분기가 먼저 처리되므로 transform 신호는 compress 도 실패한 뒤에만.
- [ ] **Step 3: 통과 확인** — `pytest tests/test_op_transform.py -v` → PASS (rota000b 가 WM solution 생성).
- [ ] **Step 4: 게이트** — `python -m debugger.score move` == 60/60 (transform 신호가 move 를 안 건드림 확인),
  `rotate` == 36/36, `flip` == 24/24. 실패 시 롤백·진단.
- [ ] **Step 5: 커밋** — production + generalize 신호.

---

### Task 4: fallback 은퇴 + 리포트 확인 + 최종 게이트

**Files:**
- Modify: `arbor/agent.py:462-498` (`_try_transform_fallback` 은퇴)
- Modify: `debugger/reports/program_report.py` (필요 시 `_transform_solution_block` 조건 조정 — 이제 real
  solution 이 나오면 표준 렌더가 뜨므로, 블록 중복/누락 점검)

**Interfaces:**
- Consumes: Task 3 완료(rotate/flip 이 WM solution 생성). Produces: fallback 제거 후에도 게이트 유지.

- [ ] **Step 1: fallback 제거** — `agent.py:462-463` 호출 삭제(또는 `if not solution` 안전망만 남김). def 은
  transform operator 로 대체됐으니 제거.
- [ ] **Step 2: 최종 게이트** — move 60/60 · rotate 36/36 · flip 24/24, HASHSEED 재시드 1회 동일.
- [ ] **Step 3: 리포트** — `clear_cache()` 후 rotate/flip program_report 재생성. rotate 태스크가 이제 **real
  TASK.solution**(WM ^solution)으로 렌더되는지, `_transform_solution_block` 과 중복 안 되는지 확인. 중복이면
  `_transform_solution_block` 을 `solution is None` 조건 그대로 두어 자동 비활성(real solution 있으면 안 뜸).
- [ ] **Step 4: 커밋** — fallback 은퇴 + 리포트.

---

## Self-Review 체크

- **Spec 커버:** spec §4 Stage 3(impasse→transform operator, fallback 제거, move 통일)을 Task 1-4 가 구현. ✓
- **개념 이름:** solution AST 는 좌표(`in([coords])`)·색만; operator/production 이름 "transform" 은 변환 종류가
  아니라 "좌표식 해 도출" 을 뜻(move/rotate/flip 구분 안 함). ✓
- **게이트 가드:** 매 Task 끝에 게이트. fallback 은 Task 4 까지 안전망. ✓
- **리스크:** generalize.py 수정이 move 를 건드릴 위험 → compress 분기가 먼저라 transform 신호는 compress 실패
  후에만. Task 3 Step 4 게이트로 확인. move 가 깨지면 즉시 롤백.
