# Part A: 레거시 expr_solver / make_grid / legacy 은퇴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** move/focus 솔버가 안 쓰는 레거시(단일객체 expr_solver 답생성·make_grid·helpers·옛 대시보드·`legacy/` 디렉터리)를 삭제해 변형 DSL 을 coloring 하나로 만든다.

**Architecture:** 죽은 것부터(A1) → 옛 대시보드(A2) → tracer setup 정리(A3) → expr_solver 레거시 블록(A4) → helpers/make_grid(A5) → legacy/ 디렉터리(A6). 각 단계 move 60/60 게이트. `build_arckg`/`_load_value`/`_tup` 은 focus 경로가 쓰므로 KEEP.

**Tech Stack:** Python 3, pytest.

## Global Constraints

- move 60/60 유지 — `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60` (seed 0/1/42)
- solve WM 형식은 안 바뀜(레거시 삭제) → 답·60/60 불변. 단 pytest 기준선은 **바뀐다**(레거시 테스트 은퇴). 각 태스크에서 새 pass/fail 수를 기록하고 "신규 회귀(현재 통과가 깨짐) 0" 을 확인.
- KEEP: `expr_solver.py`의 `build_arckg`·`_load_value`·`_tup`·`_WHOLE_VALUED`(+`Grid`), coloring/set_grid_color/set_grid_contents DSL, program_ast, operators/*, `dashboard.py`의 `_kg_detail`/`wm_deltas`/`_HTML`.
- 새 operator/DSL 금지(삭제만).
- 커밋 트레일러: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: 죽은 import 제거 (동작 0변경)

**Files:** Modify `arbor/engine/trace.py`, `arbor/reasoning/program_ast.py`

**Interfaces:** Produces: 없음(순수 삭제).

- [ ] **Step 1: 삭제**
  - `arbor/engine/trace.py:36` `from arbor.expr_solver import PRODUCTIONS, OPERATOR_BODIES` — trace.py 본문에서 미사용(grep 확인) → 삭제.
  - `arbor/reasoning/program_ast.py:317` `_execute_grid` 안 `from procedural_memory.dsl.transformation import make_grid, coloring` — 둘 다 미호출(모든 분기가 const/program/identity) → **줄 삭제**(make_grid·coloring 안 씀).
- [ ] **Step 2: 검증**
  - `PYTHONHASHSEED=0 python -c "import arbor.engine.trace, arbor.reasoning.program_ast; print('import ok')"`
  - `PYTHONHASHSEED=0 python -m pytest tests/ -q` → 현재 기준선(신규 실패 0) 확인 후 그 숫자 기록.
  - `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60`
- [ ] **Step 3: 커밋** `chore(retire): 죽은 expr_solver/make_grid import 제거(trace.py·program_ast.py)`

---

### Task 2: 옛 대시보드(task_data/build/main) 은퇴 + test_select 레거시부

**Files:** Modify `debugger/dashboard.py`, `tests/test_select.py`

**Interfaces:** Consumes: A1. Produces: `dashboard.py` 는 `_kg_detail`·`wm_deltas`·`_HTML` 만 export(레거시 진입 제거).

- [ ] **Step 1: 삭제**
  - `debugger/dashboard.py`: `task_data`(:93)·`rules_manifest`(:64)·`build`(:707 부근)·`main`(:713)·`__main__` 블록 삭제, 그와 함께 `from arbor.expr_solver import candidates`(:95)·`PRODUCTIONS`(:65) import 삭제. **KEEP**: `_kg_detail`·`wm_deltas`·`_HTML`.
  - `tests/test_select.py`: `from debugger.dashboard import task_data, build`(:75,78) 쓰는 테스트와 `fine_trace(...)` no-setup(:51-57) 테스트 삭제. `select_solver` 테스트(현재 경로)는 KEEP.
- [ ] **Step 2: 검증**
  - `PYTHONHASHSEED=0 python -c "from debugger.dashboard import _kg_detail, wm_deltas, _HTML; print('ok')"`
  - `PYTHONHASHSEED=0 python -m pytest tests/ -q` → 신규 회귀 0(삭제된 test 만큼 감소).
  - move 60/60.
- [ ] **Step 3: 커밋** `refactor(retire): 옛 대시보드 task_data/build/main + test_select 레거시부 제거`

---

### Task 3: tracer 기본 setup 제거(setup 필수화)

**Files:** Modify `arbor/engine/trace.py`

**Interfaces:** Consumes: A2. Produces: `_Tracer(task, tid, setup=...)` 에서 `setup` 필수(기본 `setup_arc_agent` 제거). live 는 다 전달.

- [ ] **Step 1: 확인 + 삭제**
  - grep: `_Tracer(` 를 no-setup 으로 부르는 live 호출이 없는지(A2 뒤). 있으면 STOP·보고.
  - `arbor/engine/trace.py:59-61`: `if setup is None: from arbor.expr_solver import setup_arc_agent as setup` 블록 삭제. `setup` 없이 호출되면 명시적 에러(또는 `setup_focus_agent` 기본 — 순환 import 주의: 필수화가 안전).
- [ ] **Step 2: 검증** import ok + `pytest -q` 신규 회귀 0 + move 60/60.
- [ ] **Step 3: 커밋** `refactor(retire): tracer setup 필수화(레거시 기본 setup_arc_agent 제거)`

---

### Task 4: expr_solver 레거시 블록 제거(build_arckg 3종만 남김)

**Files:** Modify `arbor/expr_solver.py`; Modify `legacy/run.py`(있으면, A6서 삭제 예정이라 최소), `tests/test_seokki_relations.py`, `tests/test_dsl.py`

**Interfaces:** Consumes: A3. Produces: `expr_solver.py` = `Grid` import + `_WHOLE_VALUED`·`_tup`·`_load_value`·`build_arckg` 만. 나머지 심볼 소비 0.

- [ ] **Step 1: 삭제**
  - `arbor/expr_solver.py`: 레거시 심볼 전부 삭제 — `_lone`·`_target_and_others`·`_fg_obj`·`_load_node`·`_visit_children`·`inject_task`·`setup_arc_agent`·`_op_observe/compare/generalize/compose`·`OPERATOR_BODIES`·`_propose`·`_apply`·`PRODUCTIONS`·`solve`·`_build_train`·`_pick_target`·`candidate_grids`·`predict`·`_bench*` + `from procedural_memory.dsl.helpers import ...`(:33). **KEEP**: `Grid` import·`_WHOLE_VALUED`·`_tup`·`_load_value`·`build_arckg`.
  - `tests/test_seokki_relations.py:57-59`: `from arbor.expr_solver import solve` + easy_a 9/9 회귀단언 삭제(그 테스트 함수). 나머지(setup_focus_agent·fine_trace) KEEP.
  - `tests/test_dsl.py`: `expr_solver` `_bench`/`candidates`/`solve` 쓰는 테스트 삭제(전 파일이 레거시면 파일 삭제 — A5서 helpers 도 지우니 test_dsl 전체 은퇴).
- [ ] **Step 2: 검증**
  - `PYTHONHASHSEED=0 python -c "from arbor.expr_solver import build_arckg, _load_value, _tup; print('ok')"`
  - focus 경로 import 전수: `python -c "import arbor.agent.focus, arbor.reasoning.program, arbor.perception.perception, procedural_memory.operators.coloring; print('ok')"`
  - `pytest -q` 신규 회귀 0 + move 60/60(seed 0/1/42).
- [ ] **Step 3: 커밋** `refactor(retire): expr_solver 레거시 단일객체 솔버 제거(build_arckg 3종만 유지)`

---

### Task 5: helpers.py + make_grid + set_grid_size(DSL) 제거

**Files:** Delete `procedural_memory/dsl/helpers.py`; Modify `procedural_memory/dsl/transformation/__init__.py`, `tests/test_grid_program.py`, `tests/test_dsl.py`(삭제), doc mirrors

**Interfaces:** Consumes: A4(expr_solver 가 helpers 안 씀). Produces: 변형 frozen 원자 = **coloring 하나**.

- [ ] **Step 1: 삭제**
  - `procedural_memory/dsl/helpers.py` **파일 삭제**(A4 뒤 importer 0 — 확인).
  - `procedural_memory/dsl/transformation/__init__.py`: `make_grid`(:14)·`set_grid_size`(:28-31, make_grid 로 lowering) `@dsl` 정의 삭제. **KEEP** `coloring`·`set_grid_color`·`set_grid_contents`.
  - `tests/test_grid_program.py:89-91` `test_frozen_atoms_still_two`: frozen 원자 = **coloring 하나**로 단언 수정(`assertIn("coloring", SPECS)`; make_grid 없음 `assertNotIn`).
  - `tests/test_dsl.py`: helpers/make_grid 쓰는 파일 → 전체 삭제(레거시).
  - doc mirror 갱신(문구만): `procedural_memory/dsl/__init__.py:9`·`effect.py:13`·`semantic_memory/build.py:35`·`arbor/reasoning/program_ast.py:8` docstring — "frozen 원자 2개(make_grid+coloring)" → "coloring 하나". `debugger/reports/program_viewer.py:847` JS 주석·`dashboard.py:59` 문구.
- [ ] **Step 2: 검증**
  - `python -c "from procedural_memory.dsl.transformation import coloring; from procedural_memory.dsl.registry import SPECS; assert 'coloring' in SPECS and 'make_grid' not in SPECS; print('ok, coloring only')"`
  - `pytest -q` 신규 회귀 0 + move 60/60.
  - 리포트 러너(JS): `program_viewer.py` 의 make_grid 참조가 실행 경로 아님 확인(coloring 만) — move 리포트 생성 후 parity 유지.
- [ ] **Step 3: 커밋** `refactor(retire): make_grid/helpers 제거 — 변형 DSL은 coloring 하나`

---

### Task 6: legacy/ 디렉터리 삭제 + 의존 테스트 은퇴

**Files:** Delete `legacy/` (dir); Delete `tests/test_arc.py`, `tests/test_soar_solver.py`, `tests/test_unified.py`

**Interfaces:** Consumes: A1-A5. Produces: legacy 참조 0.

- [ ] **Step 1: 확인 + 삭제**
  - grep: `import legacy`/`from legacy` 를 tests 밖에서 쓰는 곳 0 확인(있으면 STOP).
  - `git rm -r legacy/`
  - `git rm tests/test_arc.py tests/test_soar_solver.py tests/test_unified.py` (legacy import 하는 테스트).
- [ ] **Step 2: 검증**
  - `python -c "import arbor.agent.focus; print('ok')"` (legacy 무관 확인)
  - `pytest -q` — 새 기준선 기록(레거시 테스트 다 빠짐, 신규 회귀 0).
  - move 60/60(seed 0/1/42) + `python -m debugger.build move`·`program_viewer move` 정상 생성.
- [ ] **Step 3: 커밋** `chore(retire): legacy/ 디렉터리 + 의존 테스트(test_arc/soar_solver/unified) 삭제`

---

## 범위 밖
- Part B(xform 소멸) — 별도 plan.
- `set_grid_color`/`set_grid_contents` DSL 은 유지(선언용; make_grid 무관).

## Self-Review
- **Spec coverage**: A.2 RETIRE 6항목 → Task A1(dead import)·A2(대시보드)·A3(setup)·A4(expr_solver)·A5(helpers/make_grid)·A6(legacy/). KEEP 목록 각 태스크에서 명시 보존. 누락 없음.
- **Placeholder scan**: 삭제 대상 file:line 명시. NEW 코드 거의 없음(삭제+테스트 단언 수정).
- **의존 순서**: A4(expr_solver) 전에 A2/A3(소비자) 처리 → import 안 깨짐. A5(helpers) 는 A4(expr_solver 가 helpers 끊음) 뒤. A6(legacy/) 마지막.
- **게이트**: 각 태스크 move 60/60 + pytest 신규 회귀 0(레거시 테스트 감소는 회귀 아님).
