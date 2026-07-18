# PAIR.program 의 size/color 를 per-pair 리터럴로 (pending 아티팩트 제거) 설계

- 날짜: 2026-07-19
- 상태: 승인됨 (brainstorming — 범위 B: 리터럴화 먼저, output-const/delta-const 재분류는 spec #2 로 분리)
- 선행: [ARBOR_HARNESS.md](../../../ARBOR_HARNESS.md) §0.5 (PAIR.program=구현·구체 / TASK.solution=추상), 직전 spec `2026-07-19-pair-program-pixel-literal-design.md`(contents 픽셀-리터럴)
- 성공 불변조건: **arc_human/move 60/60 유지**(seed 0/1/42) · 전체 pytest 신규 회귀 0 · 답(TASK.solution 실행) 불변

## 0. 배경 — 무엇이 잘못됐나

move000a 의 PAIR.program 이 `set_grid_size = {"pending": "size"}` 로 나온다. move 는 8×8→8×8(크기 KEEP)이라 size 가 결정돼야 하는데 pending 이다.

**근본 원인:** `_grid_decide(train, test_input)` 이 **test 출력크기를 *예측*** 하려다 AMBIGUOUS 가 된다:
- `KEEP` → **(5,5)** — "출력=입력" 을 *test 입력*(5×5)에 적용
- `CONST` → **(8,8)** — train 출력이 전부 8×8

둘이 달라서(5,5 vs 8,8) AMBIGUOUS → `_slot_leaf` 가 pending 처리 → 하강. 즉 **test 예측 기계(TASK.solution 층)를 per-pair PAIR.program 채우는 데 잘못 쓴 계층 오류**다. 한 train pair 의 size 는 예측할 게 아니라 **그 pair 출력의 실제값(8,8)** 이다.

## 1. 목표

**PAIR.program 의 size/color leaf = 그 pair 출력의 리터럴값.**
- `set_grid_size(const({"height": H, "width": W}))` — 그 pair 출력 크기
- `set_grid_color(const(sorted(색집합)))` — 그 pair 출력 색집합
- contents = 현행(coord coloring / 하강 산출)

→ move Step A 가 `g.size = (8, 8)` · `g.color = {0, 4}` 리터럴로 뜨고 **pending 사라짐**. 예측/일반화(KEEP·`size(input_grid)`)는 TASK.solution 의 몫으로 남긴다.

## 2. 왜 60/60 이 자명하게 안전한가 (핵심)

- **`_execute_grid` 은 출력을 오직 `set_grid_contents` 로만 결정한다** (size/color leaf 는 실행에 안 쓰임 — Round-3 Grid 객체모델의 "검증되는 주장", primary=contents). 확인: `_execute_grid` 은 `parts["set_grid_contents"]` 만 읽고 size/color 는 안 읽는다. → size/color 리터럴화는 **선언/표시 전용, 답 경로 0 영향**.
- **move 답 경로**: generalize 가 `grouping` blob(=`_object_move_program` 산출, size=`expr(size(input_grid))`)을 anti-unify → TASK.solution → apply_solution 실행. PAIR.program 은 이 경로에 없다(아티팩트·리포트·러너 parity 용).
- **move-preempt**: `_all_pixel_residual`/`grid_inner_op_counts` 는 `_is_grid_body` + inner contents(pixel/coord) 만 보고 size/color leaf 는 안 본다 → 리터럴화 무영향.

따라서 이 변경은 표현/표시만 바꾸고 solve 결과·60/60 을 건드리지 않는다.

## 3. 범위 (touch) — 부분-하강(move/c–h) 경로만

- `procedural_memory/operators/verify.py` `_assemble_pair_program`: grid-skeleton 을 pair 프로그램으로 조립할 때, `set_grid_size`/`set_grid_color` leaf 를 **그 pair(`pair_cursor`) 출력의 리터럴 const** 로 교체. (기존엔 skeleton 의 pending/expr 를 그대로 뒀음.)
- 필요 시 `arbor/reasoning/program_ast.py`: size const 는 `{"height":H,"width":W}` dict, color const 는 색 리스트 — **a/b CONST 경로가 이미 쓰는 형식**이므로 execute/display 가 이미 처리(확인 필요, 안 되면 최소 보강).
- `debugger/reports/program_viewer.py`: display_source 가 const size(`{"height","width"}`)를 `(H, W)` 로, const color 를 `{색…}` 로 렌더하는지 확인(a/b const 경로 재사용). 안 되면 보강.

**범위 밖 (spec #2 / 이후):**
- full 경로(a/b, 게이트 밖)의 size/color 리터럴화 — 현행 유지.
- output-const/delta-const **재분류 + delta 우선 + ambiguous 해소(version-space)** — 일반화 로직 재설계는 별도 spec #2.
- `_grid_decide` 의 test 예측 로직 자체 — spec #2 에서 TASK.solution 층으로 정돈.

## 4. 결과(표시)

- **Step A · PAIR.program (move)**: `g.size = (8, 8)` · `g.color = {0, 4}` · `g.contents = coloring((r,c), 색) …` — 전부 리터럴, pending 없음.
- **Step C · TASK.solution**: 현행(size=`size(input_grid)` 등 grouping 유래 일반화) 유지.

## 5. 검증

- `PYTHONHASHSEED=0 python -m debugger.score move` → 60/60 (seed 0/1/42). size/color 는 실행 무관이라 자명하지만 확인.
- 전체 pytest 신규 회귀 0 (기존 10 failed 유지). solve WM 가 바뀌면(size/color leaf 형식) `tests/fixtures/engine_golden.pkl` 은 그 안에서 60/60·pending-부재 확인 후 재생성(직전 spec 들과 동일 관례).
- move 리포트 재생성: Step A 에 `pending` 부재 + `g.size = (H, W)` 리터럴 확인.

## 6. 관련 파일

- operator: `procedural_memory/operators/verify.py`(`_assemble_pair_program`), 참조 `hypothesize.py`(grid-skeleton stash)
- 표현/실행: `arbor/reasoning/program_ast.py`(`_execute_grid`·size/color const), `program.py`(`_grid_decide`·`_size_leaf`/`_color_leaf` — 이번엔 읽기만)
- 표시: `debugger/reports/program_viewer.py`(display_source size/color 렌더)
- 게이트: `debugger/score.py`, `tests/`
