# 레거시 expr_solver 은퇴 + xform 소멸 (coloring 이 relation 에서 직접 발화) 설계

- 날짜: 2026-07-19
- 상태: 승인됨 (brainstorming — A 은퇴 전부 삭제(legacy/ 포함) + B xform·관련 symbol 소멸, 함께)
- 선행: `2026-07-19-grid-decide-delta-priority-design.md`, ARBOR_HARNESS §0.5(relation=서술·edge / program=절차), §2-2(근거는 compare 결과에서)
- 성공 불변조건: **arc_human/move 60/60 유지**(seed 0/1/42) · 답 불변 · 새 operator/DSL 금지(coloring 만)

이 문서는 성격이 다른 두 파트를 담는다. **Part A(기계적 삭제, 저리스크)를 먼저, Part B(solve 발화 재작성, 60/60 리스크)를 나중에** 실행한다.

---

## Part A — 레거시 expr_solver / make_grid / legacy 은퇴

### A.0 배경
`expr_solver.py`는 옛 단일객체 솔버(make_grid+coloring 조합으로 답 격자 생성)다. 현재 move/focus 솔버는 `program_ast.execute` + `_op_coloring`(coloring 만)으로 답을 낸다 — make_grid·helpers·expr_solver 답생성은 **레거시 잔재**(move 답 경로 밖). "변형 DSL은 coloring 하나"로 정리한다.

### A.1 KEEP (focus/move 가 씀)
- `arbor/expr_solver.py` → **`build_arckg`·`_load_value`·`_tup`·`_WHOLE_VALUED`(+`Grid`)만** 남긴다(ARCKG 빌더로 축소). arbor 전반이 `:7` import.
- DSL: `coloring`·`set_grid_color`·`set_grid_contents` + registry.
- `program_ast` 실행기 전체, `procedural_memory/operators/*`, `dashboard.py`의 `_kg_detail`/`wm_deltas`/`_HTML`, `trace.py` 코어.

### A.2 RETIRE (레거시 전용) + 고칠 소비자
1. **`procedural_memory/dsl/helpers.py` 파일 전체** → `expr_solver.py:33` import 제거, `tests/test_dsl.py` 은퇴.
2. **`expr_solver.py` 레거시 블록**: `_lone`·`_target_and_others`·`_fg_obj`·`_load_node`·`_visit_children`·`inject_task`·`setup_arc_agent`·`_op_observe/compare/generalize/compose`·`OPERATOR_BODIES`·`_propose`·`_apply`·`PRODUCTIONS`·`solve`·`_build_train`·`_pick_target`·`candidate_grids`·`predict`·`_bench*` → 소비자 수정: `trace.py:36,61`·`dashboard.py:65,95,98`·`legacy/run.py`.
3. **`make_grid` 함수 + `set_grid_size`(DSL, make_grid 로 lowering) + @dsl 등록** → `program_ast.py:317` dead import 제거, `transformation/__init__.py:14,29-31`, `test_grid_program.py:91`(frozen 원자 2→1), doc mirror(`semantic_memory/build.py:35`·`program_viewer.py:847` JS·`dsl/__init__.py:9`·`effect.py:13`·`dashboard.py:59`).
4. **`dashboard.py`의 `task_data`·`rules_manifest`·`build`·`main`**(옛 대시보드, `python -m debugger.dashboard` 로만 도달) + 그 `expr_solver` import.
5. **`trace.py`**: `:36`(죽은 import) 즉시, `:61`(기본 setup) 은 A.4 뒤 → `setup` 필수화(live 는 다 전달).
6. **`legacy/` 디렉터리 전체 삭제** + 그에 의존하는 테스트 은퇴: `test_arc.py`·`test_soar_solver.py`·`test_unified.py`, `test_seokki_relations.py`의 expr_solver 회귀단언(`:57-59`), `test_select.py`의 레거시부(`:51-57` no-setup fine_trace, `:75-78` task_data), `test_dsl.py`.

### A.3 게이트
- move 60/60(seed 0/1/42) 불변, `program_ast`/`select_solver`/coloring 관련 테스트 유지.
- **기존 10 failed 가 줄어든다**(retire 되는 test_dsl 2 + test_seokki 회귀단언 등) — 은퇴 후 새 기준선을 기록.
- `python -m debugger.build move`(대시보드)·`program_viewer move`(리포트) 정상 생성.

---

## Part B — xform 소멸: coloring 이 pixel relation 에서 직접 발화

### B.0 배경 (왜)
`_compare_pixels`(compare)가 이미 **변화 셀(color DIFF)만 pixel relation** 으로 저장한다(E_G0Xi-G1Xi). 그 relation 은 coloring arg 를 스칼라로 다 갖는다(실측): `category.color.comp2`=출력색, `coordinate.…row_index/col_index.comp1`=(r,c). 그런데 hypothesize 가 이걸 `xform`(+`g0cells`·`g1color`·`comm`·`diff`)로 **재포장**해 coloring body 가 소비한다 — relation 의 복제라 낯선 중간 symbol 이 생긴다(§2-2 위반 소지: 근거는 relation 하나여야).

### B.1 목표
- **`xform`·`g0cells`·`g1color`·`comm`·`diff` symbol 소멸.**
- **coloring 이 relation 에서 직접 발화**: propose*coloring 이 pixel relation(color DIFF)을 조건으로 걸고, **arg(좌표·색)를 relation 의 comp1/comp2 에서 규칙이 결정**. apply body 는 원자연산(그 (r,c)에 그 색을 frozen coloring 으로 칠함)만.
- **hypothesize 는 H-space 를 연다**: 재채색 후보 pixel relation 들을 H substate(가설공간)에 노출 → **대시보드에서 가설공간·후보가 보임**(사용자 오랜 요청). coloring 은 그 H-space 안 relation 에 스코프.

### B.2 발화 메커니즘 (규칙이 arg 를 relation 으로 결정)
pixel relation 저장 구조(실측):
```
E ^category C
  C ^color <col>      (<col> ^type DIFF ^comp1 <in> ^comp2 <out>)
  C ^coordinate <crd> (<crd> ^category <cc>)
      <cc> ^row_index <ri>  (<ri> ^comp1 <r>)   ← COMM 이라 comp1=comp2
      <cc> ^col_index <ci>  (<ci> ^comp1 <cx>)
```
`propose*coloring` 조건(개략):
```
(<h> ^recolor-rel <E>)                    ← hypothesize 가 H-space 에 넣은 후보(스코프)
(<E> ^category <C>)(<C> ^color <col>)(<col> ^type DIFF)(<col> ^comp2 <out>)
(<C> ^coordinate <crd>)(<crd> ^category <cc>)
(<cc> ^row_index <ri>)(<ri> ^comp1 <r>)
(<cc> ^col_index <ci>)(<ci> ^comp1 <cx>)
→ (o ^name coloring)(o ^row <r>)(o ^col <cx>)(o ^color <out>)(o ^from-relation <E>)
```
`apply*coloring` body(원자연산만): sim grid 의 `(<r>,<cx>)` 를 `<out>` 로 frozen coloring 적용 + program 에 coloring step 한 줄 방출(§좌표-리터럴, spec pixel-literal 과 정합). **배열 없음**(픽셀 단위 스칼라라 규칙이 arg 결정 가능).

### B.3 hypothesize 재작성 (H-space)
- OBJECT/PIXEL 경로에서 `xform`/`g0cells`/`g1color`/`comm`/`diff` 생성 **삭제**.
- 대신 `ag.create_hspace(...)` 로 H substate 를 열고, 재채색 후보 relation(pixel color-DIFF; object 경로면 object color-DIFF relation)을 `(<h> ^recolor-rel <E>)` 로 노출. → coloring 규칙이 그 H-space 에서 발화.
- H-space 완료(모든 후보 coloring 적용)면 `hspace-done` → 부모 복귀(기존 synthesize H-space 관례 재사용).

### B.4 60/60 보존
- pixel relation = compare 가 낸 변화 셀 = 현행 xform 이 칠하던 셀과 **동일 집합**. 출력색=comp2. → coloring 산물(PAIR.program)이 동일해야 함.
- **리스크**: 발화 순서·H-space 배선·object 경로(현재 object xform→coloring→verify 실패→pixel 하강)의 재현. move 는 결국 pixel 잔차로 PAIR.program 을 내므로 pixel relation 경로가 정확하면 60/60 유지. 각 단계 60/60·PAIR.program byte 대조로 검증.

### B.5 범위 밖
- object-level coloring(다중 셀)의 규칙-only arg — 픽셀은 스칼라라 되지만 객체는 배열이라 노드참조 필요(이번은 pixel 경로 우선; object recolor 는 후속).
- compare arg 선택(`_build_agenda`) 규칙화 — Part 2 의 다른 항목.

---

## 실행 순서 (plan 에서 태스크로)
1. **Part A** (기계적, 저리스크): A.2 항목을 단계별로 삭제·소비자 수정, 각 단계 60/60. legacy/ 삭제.
2. **Part B** (behavioral, 60/60 리스크): compare 가 pixel relation 을 남기는지 확인 → hypothesize H-space + recolor-rel 노출 → propose/apply*coloring 을 relation 기반으로 → xform 계열 symbol 제거 → 60/60·PAIR.program 대조.

## 관련 파일
- A: `arbor/expr_solver.py`·`procedural_memory/dsl/{helpers.py,transformation/__init__.py}`·`debugger/dashboard.py`·`arbor/engine/trace.py`·`legacy/`·tests
- B: `procedural_memory/operators/{hypothesize,coloring}.py`·`production_rules/coloring.json`·`arbor/reasoning/compare_engine.py`(relation)·`soar/agent.py`(create_hspace)·`debugger`(H-space 표시)
