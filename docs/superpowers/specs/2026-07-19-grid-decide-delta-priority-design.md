# _grid_decide 해소 규칙: delta-const 우선 + 재분류 (pending 뿌리 제거) 설계

- 날짜: 2026-07-19
- 상태: 승인됨 (brainstorming — 범위 A: 재분류 + delta 우선만; version-space/genuine-tie 는 이후)
- 선행: spec `2026-07-19-pair-program-literal-gridprops-design.md`(#1, 최종 PAIR.program 리터럴)
- 성공 불변조건: **arc_human/move 60/60 유지**(seed 0/1/42) · 전체 pytest 신규 회귀 0 · 답 불변 · move 중간산물(grid-skeleton)·대시보드에서 `pending:size` 제거

## 0. 배경 — 남은 pending 의 뿌리

spec #1 이 최종 PAIR.program 을 리터럴로 만들어 **program_report Step A 의 pending 은 사라졌다**(60태스크 0개). 그러나 **대시보드(`move_dashboard.html`)의 중간산물 `grid-skeleton` 에는 아직 `pending:size` 가 72개** 남아 있다.

뿌리: `_grid_decide` 가 move size 를 **AMBIGUOUS** 로 낸다.
- `KEEP` → **(5,5)** (출력=입력을 test 5×5 에 적용)
- `CONST` → **(8,8)** (train 출력 공통)

`_dec(preds)` 가 서로 다른 예측 2개를 무조건 AMBIGUOUS 로 → `grid_program_from_decide` 가 `_slot_leaf` 로 size=pending → hypothesize 가 그 skeleton 을 WM 에 stash → 대시보드가 그대로 표시. spec #1 은 이 뿌리를 안 건드렸다.

## 1. 목표 — 해소 규칙을 카테고리 우선으로

여러 후보가 train 을 맞추면 **더 큰 범위를 포용하는 구조적 일반화(delta-const)를 표면 일치(output-const)보다 우선** 채택한다.

- **재분류**: 후보 kind 를 두 카테고리로.
  - **output-const** = 출력값 자체가 pair 마다 같음 = `CONST`
  - **delta-const** = 입력→출력 *변화*가 pair 마다 같음 = `KEEP`(Δ0)·`MAP[…]`(size 식)·`SET-MAP(…)`(색 가감)·`MAP`(전역색맵)
- **해소 `_resolve_decision(cands)`**: valid 후보 중 delta-const 예측이 있으면 그것으로만 판정, 없으면 output-const(CONST)로. 단일 예측 → **DECIDE(값)**, 여럿(delta 끼리 갈림) → **AMBIGUOUS(하강)**, 없음 → **DESCEND**.

→ move size: `KEEP=(5,5)`(delta) 우선 → **DECIDE (5,5)** (CONST=(8,8) 무시). test 5×5 에도 올바르게 일반화.

## 2. 결과 — pending 제거 흐름

- `_grid_decide["size"]["decision"] = DECIDE`, value=(5,5) → `_slot_leaf` 가 pending 대신 `_size_leaf` 로 → move KEEP 이면 `expr("size(input_grid)")`.
- `grid_program_from_decide` 의 skeleton = `grid_program(size(input_grid), color(input_grid), pending(contents))` — **size 는 이제 pending 아님**. (contents 는 여전히 DESCEND → pending → 하강; 흐름 불변.)
- hypothesize 가 이 skeleton 을 stash → 대시보드가 `size: {expr: size(input_grid)}` 로 표시 → **`pending:size` 사라짐**.
- 최종 PAIR.program 은 spec #1 대로 **리터럴 유지**(`_assemble_pair_program` 이 그 pair 출력값으로 덮음) — skeleton(일반화 스캐폴드)=`size(input_grid)`, PAIR.program(구체)=`(8,8)` 로 계층별 정합.

## 3. 왜 60/60 이 안전한가

- move 흐름 불변: size 가 pending→DECIDE 여도 `is_full_grid_program` 은 여전히 False(contents=DESCEND)라 **partial → 하강** 그대로. 답은 grouping/TASK.solution 에서(불변).
- `_resolve_decision` 은 delta 가 있으면 delta, 없으면 output — 기존 단일-예측 DECIDE 케이스는 값 동일(delta든 output이든 하나뿐이면 그대로). 바뀌는 건 **KEEP≠CONST 로 갈리던 AMBIGUOUS 만 delta(keep)로 DECIDE**.
- a/b(게이트 밖): 이전 AMBIGUOUS 였다면 이제 delta(keep) 로 결정 — 더 나은 일반화(회귀 아님). 전체 pytest 로 확인.

## 4. 재분류 이름 노출 (light)

내부 kind 문자열(`KEEP`/`CONST`/`MAP`/`SET-MAP` — `_size_leaf`·synthesize·hypothesize 가 파싱)은 **유지**(깨지 않음). 대신:
- `_cat(kind) = "output-const" if kind=="CONST" else "delta-const"` 헬퍼.
- `_grid_decide` 결과에 `category`(채택된 kind 의 카테고리) 필드 추가 → 대시보드/리포트의 grid-verdict·hypothesis 표시가 이 이름을 쓸 수 있게. (표시 반영은 최소 — verdict 문자열에 카테고리 병기.)

## 5. 범위 (touch)

- `arbor/reasoning/program.py`: `_grid_decide`(size·color 의 `decision`/`value` 를 `_resolve_decision(cands)` 로), 새 헬퍼 `_resolve_decision`·`_cat`. `_dec` 는 유지(contents·기타 사용처) 또는 size/color 만 교체.
- 표시(light): `procedural_memory/operators/hypothesize.py`/`synthesize.py` 의 grid-verdict 문자열에 category 병기, 또는 `debugger` 표시부. (필수는 아님 — pending 제거가 핵심 게이트.)

## 6. 범위 밖 (이후)

- **version-space**: delta-const 끼리 갈리는 genuine few-shot 애매 → 3-try (move 엔 안 생김).
- `_grid_decide` 를 TASK.solution 층(anti-unify)으로 완전 이관 — PAIR.program 은 이미 리터럴(#1)이나, 일반화 도출 자체를 generalize 로 옮기는 큰 재설계.
- color SET-MAP 의 delta 구조화.

## 7. 검증

- `PYTHONHASHSEED=0 python -m debugger.score move` → 60/60 (seed 0/1/42).
- 전체 pytest 신규 회귀 0. solve WM 형식 바뀌면 `engine_golden.pkl` 은 60/60·pending-부재 확인 후 재생성.
- **대시보드 재생성 후 `pending:size` 개수 확인** (`move_dashboard.html` 에서 skeleton 유래 `{"pending": "size"}` 부재; RETE match 주석의 "pending" 은 무관).
- move000a `_grid_decide["size"]["decision"] == "DECIDE"`, value==(5,5) 단위 확인.

## 8. 관련 파일

- 결정: `arbor/reasoning/program.py`(`_grid_decide`·`_dec`·`_size_leaf`·`_slot_leaf`)
- 소비: `arbor/reasoning/program_ast.py`(`grid_program_from_decide`·`is_full_grid_program`), `procedural_memory/operators/hypothesize.py`
- 게이트: `debugger/score.py`, `debugger/build.py`(대시보드), `tests/`
