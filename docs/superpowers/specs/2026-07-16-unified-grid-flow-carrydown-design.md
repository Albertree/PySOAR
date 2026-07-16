# 통일 흐름 — grid-level size/color 결론을 하강 후에도 유지 (설계)

> **정본 스펙.** 모든 문제의 풀이 흐름을 하나로 통일한다: grid-level 이 size/color/contents 를 예측 시도 →
> **결정된 슬롯(size/color 등)은 그대로 유지**하고 → 미결정 슬롯(주로 contents)만 object/pixel 로 하강해
> coloring 으로 채워 **덮어씌우되 결정된 슬롯은 남긴다.** 결과: **모든 PAIR.program 이 grid body 3슬롯**
> `set_grid_size ∘ set_grid_color ∘ set_grid_contents` 이고, contents_leaf 만 `const(grid)`(grid 완결=a/b)
> 이거나 `program(coloring 합성)`(하강=c–h) 으로 갈린다. c–h 도 앞부분에 `g.size`/`g.color`(grid-level)가
> 남고 `g.contents` 가 하강 coloring 으로 채워진다.
>
> 코드는 **단정**해야 한다 — `raise Impasse` 같은 마커를 program 텍스트에 넣지 않는다(impasse 는 SOAR
> substate 메커니즘 = 시스템 내부). 최종 program 은 깨끗한 3슬롯.
>
> 근거: ARBOR_HARNESS.md §2-3(통일 흐름·analogical) · §1-4/P1(막혀야 하강, 결정은 유지) · §5(impasse 정직) ·
> §1-1(새 atom 아님 — grid body + coloring body 의 *합성*) · §2-5(dashboard 반영). 선행: [[grid-property-program]]
> · [[program-ast]] · 라운드3 Grid 객체 모델.

## 1. 배경 — 지금 무엇이 버려지나 (경로 매핑 실측)

- `_grid_decide(train, paG0)`([program.py:66](../../../arbor/reasoning/program.py#L66)) 는 size/color/contents 를
  독립 판정. **c–h: size=DECIDE·color=DECIDE·contents=DESCEND** (a/b: 셋 다 DECIDE).
- `grid_program_from_decide(dec)`([program_ast.py:79](../../../arbor/reasoning/program_ast.py#L79)) 는 **셋 다
  DECIDE 일 때만** grid program 을 내고, 아니면 `None`.
- `hypothesize.py:71` — `gp is None`(c–h) → `create_hspace("GRID")` 로 **그냥 하강**. size/color 의 DECIDE 값은
  `size-hyp`/`color-hyp` 문자열(dashboard 표시용)로만 남고 **program 에 실리지 않는다**(버려짐).
- 하강: synthesize(H-space) → `propose*solve*grid`(solve.json) → `_do_descend` → OBJECT substate →
  hypothesize OBJECT 분기 → `_fg_correspondence` xform → `_op_coloring`([coloring.py:49-52](../../../procedural_memory/operators/coloring.py#L49))
  가 coloring AST(`PA.program(body)`) 를 `program-code` 로 → `_op_verify`([verify.py:25-31](../../../procedural_memory/operators/verify.py#L25))
  가 그걸 **`PAIR.property.program`(pixel body)** 로 기록.
- 정답: programs-ready → generalize(`antiunify_ast`)→resolve→apply_solution([apply_solution.py:31](../../../procedural_memory/operators/apply_solution.py#L31)
  `execute(sol["skeleton"], test_input, choice)` = **유일한 정답-실행 지점**). grid/pixel 분기는 전부
  `program_ast.execute` 내부([program_ast.py:199-201](../../../arbor/reasoning/program_ast.py#L199)).

→ **결론:** 솔버는 c–h 에서 size/color 를 이미 맞히지만(DECIDE), 하강 시 그 결정을 program 에 남기지 않고 버린다.
pixel body 만 PAIR.program 이 된다. 통일 흐름이 아니다.

## 2. 목표 / 비목표

**목표**
- **통일 표현**: 모든 PAIR.program 과 TASK.solution 이 grid body 3슬롯. `contents_leaf ∈ {const | program(coloring)}`.
- grid-level DECIDE(size/color)는 하강 후에도 **유지**되어 program 앞부분에 남는다. 하나만 결정/아무것도
  결정/모두 결정 — 어느 경우든 **같은 3슬롯 골격**으로 흐른다(부분 결정은 그만큼 유지, 나머지는 하강이 채움).
- c–h program = `g.size`(grid)·`g.color`(grid)·`g.contents`(하강 coloring 합성)·`output_grid=g` — 단정한 코드.
- 정답은 이 통일 program 실행에서 나온다(execute 가 nested coloring contents 를 실행). golden 재기준화(§2-4:
  c–h step 수가 carry-down 만큼 달라짐 — 의도된 변화).

**비목표**
- 새 operator/DSL/atom 발명(§1-1) — contents_leaf=program 은 기존 grid body + coloring body 의 *합성*.
- `to_source`/`as_source`/`parse_program`(pixel/blob 파싱 계약) 훼손 — grid 경로만 확장(파싱 안 됨).
- program 텍스트에 `raise Impasse`/에러 리터럴 — impasse 는 SOAR substate(시스템 내부)로 유지, 코드는 단정.
- object/pixel 하강 로직(_fg_correspondence·coloring xform) 자체의 변경 — 그 산출(coloring body)을 grid
  skeleton 의 contents 로 **감싸기만** 한다.

## 3. 통일 표현 (program_ast)

### 3-1. 새 contents leaf 종류: `program(body)`
- `contents_program(body) → {"program": {"body": [coloring steps…]}}` (기존 const/var/expr/ref 와 동형 leaf).
- grid body = `[set_grid_size(size_leaf), set_grid_color(color_leaf), set_grid_contents(contents_leaf)]`,
  `contents_leaf ∈ {const(grid), program(body)}` (+ 기존 expr 항등 등은 그대로).

### 3-2. execute (nested coloring contents)
- 현재 `execute`([program_ast.py:199-226](../../../arbor/reasoning/program_ast.py#L199)) 의 pixel/object 루프를
  **헬퍼 `_execute_pixel_body(body, grid_in, choice)`** 로 추출(execute 와 _execute_grid 양쪽에서 호출).
- `_execute_grid`([:229](../../../arbor/reasoning/program_ast.py#L229)): contents_leaf 가
  - `const` → 그 grid (현행)
  - `program` → `_execute_pixel_body(contents["program"]["body"], grid_in, choice)` (= 입력에 coloring 합성 적용)
  - 기타(expr 항등 등) → identity fallback (현행)
  - size/color 슬롯은 산출에 무영향(파생·검증용, 라운드3 객체모델 규칙과 일치).
- **정답 불변 보장:** c–h 의 nested coloring body 는 현재 pixel PAIR.program 의 body 와 **동일** →
  `_execute_pixel_body` 산출 = 현재 pixel execute 산출 = 같은 정답 grid. (정직성: 답이 program 실행에서 나옴.)

### 3-3. antiunify (nested contents 재귀)
- `_antiunify_ast_grid`([:322](../../../arbor/reasoning/program_ast.py#L322)) 의 contents property 처리 확장:
  - 전 pair 의 contents_leaf 가 `program` 이면 → 그 inner body 들을 **`_antiunify_ast_pixel` 로 재귀 anti-unify**
    → contents_leaf = `program(anti-unified coloring skeleton)`, inner slots(`?src_i`/`?color_i`)를 **top-level
    slots 로 승격**(prefix 로 충돌 회피, 예 `?c.src0`).
  - const/expr 는 현행(JSON 동등=COMM, 다르면 var slot).
- `resolve_slot`([antiunify.py:399](../../../arbor/reasoning/antiunify.py#L399)) 는 승격된 inner slot(kind=src/color)을
  **기존 로직 그대로** 처리(새 kind 불필요 — 승격 시 기존 src/color kind 유지). → resolve/apply_solution 무변경.

## 4. 통일 흐름 (solver)

### 4-1. hypothesize — 부분 결정도 skeleton 유지
- `grid_program_from_decide`: 셋 다 DECIDE 아니어도 **부분 skeleton** 반환(결정된 size/color leaf + 미결정
  contents 는 **placeholder leaf** `{"pending": "contents"}`). None 반환 폐기.
- `hypothesize.py:47-71`: 
  - 셋 다 DECIDE(a/b) → 현행(완결 program + programs-ready).
  - 부분(c–h) → **skeleton(size/color leaf + contents pending)을 WM 에 `grid-skeleton` 으로 stash** 후 하강
    (create_hspace). size/color 가설(H1,H2…)은 현행처럼 노출(버리지 않고 skeleton 에 실림).
- placeholder `{"pending":…}` 는 **program 텍스트로 렌더되지 않음**(display 는 하강완료 후 채워진 것만) —
  단정한 코드 유지. impasse 는 substate 로만.

### 4-2. verify/coloring — 하강 coloring 을 contents 로 감싸기
- `_op_verify`([verify.py:25-31](../../../procedural_memory/operators/verify.py#L25)) 가 PAIR.program 을 쓸 때:
  `grid-skeleton` 이 있으면 그 skeleton 의 contents 슬롯을 `contents_program(coloring_ast["body"])` 로 채워
  **grid body(3슬롯) 를 PAIR.program 으로** 기록(pixel body 통짜 대신). skeleton 없으면(순수 pixel 문제)
  현행 유지 — 단, easy a–h 는 항상 grid-skeleton 경유(size/color DECIDE).
- coloring.py 는 그대로 coloring body 를 만든다(하강 산출). 감싸기는 verify(조립) 지점에서.

## 5. display / runner / viz (라운드3 연장)

- `_display_grid`(라운드3 객체형): contents_leaf 가 `program` 이면 `g.contents = coloring(...) ∘ coloring(...)`
  (nested 를 coloring 합성으로 렌더). const 면 현행(2D 배열). → c–h 도 `g.size`/`g.color`/`g.contents` 3슬롯.
- 러너: `set_grid_contents` 인자가 coloring 합성이면 그 합성을 실행해 contents 산출(라운드3 `_arr`/valid 규칙
  그대로 — size/color 는 완성 contents 와 일관해야 valid). parity: `_arr(out)==expected` 유지.
- ③ viz: contents 슬롯을 coloring box-flow(pixel) 로 중첩 표시(기존 pixel viz 재사용).

## 6. golden 재기준화

- `tests/verify_refactor.py` + `tests/golden_steps.json`(a/b 1280·c–h 2760·i 2649) 은 n_steps 오라클.
- 이 변경은 c–h 에 carry-down 조립 step(skeleton stash + contents 감싸기 + size/color 가설 유지)을 더해
  **c–h step 수가 달라짐 = 의도된 변화**(§2-4: 다른 탐색·다른 step). a/b 는 이미 grid 완결 — skeleton 경로
  통일로 소폭 변동 가능.
- 구현 후 `golden_steps.json` **재생성(손편집 금지)** + delta 가 carry-down 에서만 왔는지 검토. 정답(정오)은
  전 태스크 **불변**이어야 함(정답 grid = 같은 coloring 산출).

## 7. 리스크 / 게이트

- **최대 리스크:** execute(단일 정답 지점)·antiunify·resolve 를 건드림 → 잘못되면 전 태스크 정답 붕괴.
  게이트: 각 task 후 **verify_refactor(정답 정오 불변)** + 대표 태스크 execute 산출 동등성 스냅샷.
- **정답 동등성 원칙(핵심):** nested coloring contents 실행 산출 == 현행 pixel body 실행 산출. 이걸 T당
  실측으로 증명(같은 body 이므로 동일해야). 어긋나면 STOP.
- **sequencing:** skeleton 은 decide 시점 생성(contents 미정) → 하강 후 verify 에서 contents 채움. WM 수명
  (H-space purge)과 skeleton stash 위치 주의(parent GRID substate 에 stash, H-space 아님).
- **antiunify 승격 충돌:** inner slot 이름 prefix 로 top-level 과 충돌 회피.
