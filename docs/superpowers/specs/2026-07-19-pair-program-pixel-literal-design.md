# PAIR.program 을 픽셀-리터럴로, 객체 grouping 은 TASK.solution 으로 설계

- 날짜: 2026-07-19
- 상태: 승인됨 (brainstorming — 좌표=리터럴(r,c) 확정, grouping=compress 별도 아티팩트 확정)
- 선행: [ARBOR_HARNESS.md](../../../ARBOR_HARNESS.md) §0.5(네 칸: PAIR.program=구현·TASK.solution=추상)
- 성공 불변조건: **arc_human/move 60/60 유지**(seed 0/1/42) · 전체 pytest 신규 회귀 0 · TASK.solution/resolve/apply_solution 산물 불변(답 불변)

## 0. 배경 — 무엇이 잘못됐나

`compress` operator 가 픽셀 단위 PAIR.program 을 **객체 단위 `coloring(cellset=[...], color)` 로 재작성해 PAIR.program 을 덮어쓴다**. 그래서:

- example pair 의 program 에까지 `cellset` 이 나타난다(1칸 이동도 `coloring(g0, cellset=[26], 0)`).
- 러너가 실행하지 못한다("해석 불가 — 다중좌표 미지원").
- **계층이 뒤바뀜**(하네스 §0.5 위반): PAIR.program 은 "한 pair 의 G0→G1 *구현*"(구체)이어야 하고, 픽셀→객체 grouping·추상화는 anti-unify → **TASK.solution**(task-일반)의 몫이다. 지금은 grouping 이 PAIR.program 단계에서 너무 일찍 일어난다.

## 1. 목표 표현

**PAIR.program = 픽셀 잔차, `coloring((r,c), color)` — 좌표·색이 리터럴 값 그자체.**

- 바뀐 셀(G0[r][c] ≠ G1[r][c])만, 각 셀을 그 출력색으로 칠하는 실행가능 G0→G1 (잔차 program 은 G0 에 적용하면 G1 이 됨 — 정직·구체).
- 좌표 = **리터럴 (r,c)**(사용자 확정). 지금은 `pixels_of(input_grid)[idx].coord`(index 간접참조)만 지원하므로, program_ast 에 **좌표-리터럴 coloring 타깃**을 추가한다.
  - 표현: `ref("coord", const([r, c]))` — 기존 `ref`+`const` 재사용(새 operator/finder 아님, §1-1). `ref("pixel", …)`(index)·`cellset(…)` 과 구분되는 세 번째 타깃 종류.
  - frozen coloring DSL 은 원래 `coloring(grid, (r,c), color)` 로 좌표를 직접 받으므로 base DSL 에 더 가깝다(간접참조 제거).
- **TASK.solution = 객체 단위 cellset + slot** — 지금과 동일(anti-unify 산물). cellset 은 오직 여기에만.

## 2. 파이프라인 변경 (grouping = compress 별도 아티팩트)

| operator | 지금 | 목표 |
|---|---|---|
| pixel emit (`_pixel_residual_program`, `coloring.py` PIXEL 경로) | `ref("pixel", const(idx))` | **`ref("coord", const([r,c]))`** (리터럴) |
| `compress` | `{pair}.property program` 을 cellset 으로 **덮어씀** | grouping 결과를 **`{pair}.property grouping` 새 slot** 에 씀. `program`(픽셀) 은 안 건드림 |
| `generalize` | `program`(cellset) 을 읽어 anti-unify | **`grouping`(cellset) slot** 을 읽어 anti-unify → TASK.solution. move-preempt 감지(`_all_pixel_residual`)는 리터럴-픽셀(`ref coord`) 형식 인식하도록 갱신 |
| `resolve` / `apply_solution` | TASK.solution 소비 | **불변** |

- **구조 마커 유지(§2-5):** compress 는 계속 발화하고, 그 산물(grouping)이 WM 에 `grouping` slot 으로 남아 트레이스·대시보드에서 보인다(structure mapping 이 보임, §0.5).
- grouping 계산은 이미 **G0/G1 격자**에서 한다(`_object_move_program`/`_object_moves(g0,g1)`) — PAIR.program 형식과 무관. 따라서 slot 만 바꿔 써도 grouping 결과·anti-unify 산물은 동일.

### 2b. 정합성 요구 — 비-이동 픽셀 anti-unify 경로 (중요)

이동(move) 태스크는 generalize 가 `grouping`(cellset)을 읽으므로 PAIR.program 의 픽셀 형식이 anti-unify 에 **영향 없다**. 그러나 **비-이동 픽셀 태스크**(easy recolor 등 — compress 안 함)는 generalize 가 `program`(픽셀)을 그대로 anti-unify 하므로, 픽셀 타깃을 `ref("pixel", idx)`→`ref("coord", [r,c])` 로 바꾸면 그 경로가 영향받는다:

- `ops_of_ast`·`_antiunify_ast_pixel`(program_ast): 픽셀 op 키를 `idx` 에서 뽑던 것을 **`coord` 타깃도 동등하게** 뽑도록(위치 COMM/DIFF 판정이 idx 때와 동일하게 나오도록) 갱신.
- `resolve_slot` src 경로(antiunify.py): slot 값이 `idx`(→ `//W, %W` 로 (r,c) 복원)였는데 이제 좌표 기반이 될 수 있으므로, 두 형식을 동등 처리.
- **불변 요구:** 비-이동 픽셀 태스크의 TASK.solution·답이 **바뀌지 않아야** 한다(형식만 바뀌고 의미 동일). 게이트 = 전체 pytest(픽셀 anti-unify·resolve 단위테스트 포함) 신규 회귀 0.

리스크 최소화: 좌표↔인덱스는 W 로 전단사이므로 anti-unify 는 **좌표를 키로** 써도 idx 때와 동일한 COMM/DIFF 를 낸다. 60/60 게이트(move)는 이 경로를 안 타므로 안전마진이 있고, 비-이동은 전체 스위트가 지킨다.

## 3. 60/60 보존 논리

- grouping(픽셀→객체)은 **원본 격자에서** 계산되므로 PAIR.program 을 픽셀-리터럴로 두어도 TASK.solution 구조가 그대로 나온다.
- resolve(version space)·apply_solution(TASK.solution 실행)이 **불변** → test 답 불변.
- **PAIR.program 은 solve 답 경로가 아니다** — 답은 TASK.solution 실행(`apply_solution`)에서 나오고, PAIR.program 은 아티팩트·리포트·러너 parity 용. 따라서 표현 변경의 solve 리스크가 낮다.
- 게이트: `python -m debugger.score move` = 60/60 (seed 0/1/42) · 전체 pytest 신규 회귀 0 · move_program_report.html 시각 확인(Step A 픽셀-리터럴·실행가능, Step C cellset, example pair 에 cellset 부재).

## 4. 결과(표시)

- **Step A · PAIR.program**: `g1 = coloring(g0, (2,8), 0)` / `g2 = coloring(g1, (3,8), 7)` — 리터럴, 러너 실행 가능.
- **Step C · TASK.solution**: cellset + slot(추상화 — 올바른 위치).
- example pair 에서 `cellset` 사라짐. 러너 "해석 불가" 해소(좌표-리터럴은 실행 가능).

## 5. 범위 (touch)

- `arbor/reasoning/program_ast.py`: `ref("coord", …)` 타깃 build/execute + AST helper.
- `arbor/reasoning/program.py` `_pixel_residual_program`: 리터럴 좌표 방출.
- `procedural_memory/operators/coloring.py`: PIXEL emit 을 리터럴 좌표로.
- `procedural_memory/operators/compress.py`: grouping 을 `grouping` slot 에 (PAIR.program 미변경).
- `procedural_memory/operators/generalize.py`: `grouping` slot 소비 + preempt 감지 갱신.
- `debugger/reports/program_viewer.py`: display_source 리터럴 좌표 렌더 + 러너(JS) coord 타깃 실행.

## 6. 범위 밖 (비목표)

- object 단위(비-이동) blob 경로의 리터럴화 이외 재설계 — 이번은 픽셀 좌표 리터럴 + grouping 이관에 한정.
- Part-2(op-body arg 탈절차화·규칙화) — 별건.
- `task_section:614` 기존 `tp` NameError, golden fixture 크기 — 별건.

## 7. 관련 파일

- 표현/실행: `arbor/reasoning/program_ast.py`(coloring 타깃·execute·antiunify_ast), `arbor/reasoning/program.py`(`_pixel_residual_program`)
- operator: `procedural_memory/operators/{coloring,compress,generalize}.py`
- 표시: `debugger/reports/program_viewer.py`(display_source·runner)
- 게이트: `debugger/score.py`(60/60), `tests/`(회귀)
