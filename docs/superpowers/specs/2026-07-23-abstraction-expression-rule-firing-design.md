# 설계문서 — abstraction 표현식 재설계 + 규칙발화 정화

- 날짜: 2026-07-23
- 브랜치: seokki-refactor
- 상태: 설계 합의 대기 (구현 전)
- 선행 참조: [ARBOR_HARNESS.md](../../../ARBOR_HARNESS.md) §0.5·§1·§2·§4·§5, CLAUDE.md
- 관련 메모리: [[seokki-refactor]] · [[no-arbitrary-filters]] · [[solution-expression-viz]]

---

## 0. 한 줄 목적

abstraction 산출물(pair.program·TASK.solution)의 **표현을 `cellset`/`@shape#0`/WM-외부 리스트/임의
변수명에서 → ARCKG-경로 참조 + 함수 래핑 property + `select`-술어(Grammar A)** 로 바꾸고, 그 과정에서
어긋나 있던 **규칙발화를 정화**한다. move 60/60 + objc 성능을 유지한다. rotate/flip 은 **이 작업의
다음 청크**이며 여기 포함하지 않는다.

> 이 문서는 "문제의 정답"이 아니라 "지능체의 생각 단위 모듈"을 다듬는다(하네스 §0·§2-4). 어떤 ARC
> 문제든 같은 규칙이 같은 순서로 발화해야 하고, 문제마다 갈라지는 요소만 표현·검증으로 도출한다.

---

## 1. 배경 — 현재 무엇이 어긋나 있나 (실측)

move000a 를 debug 로 돌려 확인한 현행 산출물:

```
(TASK.property ^slot) = ?c.cells0[cellset]=DIFF[[26],[48]]
(TASK.property ^slot) = ?c.cells1[cellset]=DIFF[[35],[57]]
(TASK.property ^resolved) = ?c.cells0=move[r0+0,c0+0]@shape#0
(TASK.property ^resolved) = ?c.cells1=move[r0+1,c0+1]@shape#0
```

문제점(사용자 지적):

1. **`cellset`** — 픽셀 index 리스트를 WM 밖에서 굽어 변수화·저장한다. 이 모델의 동작원칙(필요할 때
   WM/ARCKG 에서 찾아 조립)에 어긋난다. (report 계층은 커밋 `0e04ded`·`7565931` 에서 이미
   cellset→select/coordinate 로 은퇴시켰으나 **솔버는 여전히 cellset 을 emit**한다 — 시각화만
   바꾸고 솔버는 안 바꿈.)
2. **`@shape#0`** — 선택자를 이름-해킹 문자열로 표기. 실제 property accessor 의 술어가 아니다.
3. **`move[...]` / `translate`** — 이동을 이름 원자로 포장하면 "정답을 아는 채로 박는" 것(하네스 §1-2).
   move 는 `coloring` 조합이 이루는 **창발적 패턴**이어야 하고 primitive 는 `coloring` 뿐이어야 한다.
4. **임의 변수명** — `input_grid`·`dest`·`src_anchor` 류. output grid 도 이제 program 에서 쓰이므로
   "어느 grid 인지"가 참조에 드러나야 한다.
5. **object-level 가짜 종결** — [hypothesize.py OBJECT 분기](../../../procedural_memory/operators/hypothesize.py)
   가 `colored-all yes` 를 명시적으로 세우고 "2026-07-19 원천차단" 주석으로 *일부러 막았다*고 서술.
   원칙상으로는 "object 비교결과를 소비하는 발화 규칙이 없어서 아무 program 도 안 생기고 verify 가
   자연 실패" 여야 한다 — 인위적 차단·플래그가 아니라.
6. **`advance_or_finish`** — [verify.py](../../../procedural_memory/operators/verify.py) 가
   `(S1 ^pair-idx +1)` 을 명시적으로 올려 per-pair 순회를 **절차적으로 몰고** 있다. 원칙: "P0 에서
   볼일 다 봄 → hypothesis space 를 나온다(pop) → 다음 미처리 pair 가 자연히 잡힌다."
7. **`sim` / `recolor-rel`** — pixel 비교결과 → pair.program 을 잇는 scaffolding. 원칙: 비교결과(1/2
   픽셀)에서 **규칙이 발화해 곧장 `coloring` 줄을 emit**하고, 실행은 verify 가 한다.

---

## 2. 개념 모델 (합의)

### 2.1 세 계층의 표현 (Grammar A)

- **노드 참조 = ARCKG 경로**: `P0.G0`, `P0.G1` (`idx["nodes"]` 로 해소). 바 변수(`input_grid`) 금지.
- **property = 함수 래핑**: `color_of(P0.G1)` · `contents(P0.G1)` · `size(P0.G1)` · `coordinate_of(…)`.
  객체속성 접근(`node.contents`)이 아니라 property DSL 함수 적용. (`P0.G1` 까지만 노드로 쓰고 감싼다.)
- **선택 = `select(<노드경로>, level, eq(<accessor>, <값>))`** — 실행 시 ARCKG 를 읽어 on-demand 조립.
  `cellset`·`@shape#0`·WM-외부 리스트 금지.
- **변형 primitive = `coloring(coordinate_of(…), color)` 하나.** `translate`/`move` 이름 원자 금지.

move000a 예:
```
# pair.program (P0 · 구체 · in/out 경로 참조 허용)
coloring(coordinate_of(select(P0.G0,"pixel", eq(pixel_coordinate,(3,2)))), 0)
coloring(coordinate_of(select(P0.G1,"pixel", eq(pixel_coordinate,(4,3)))),
         color_of(select(P0.G0,"pixel", eq(pixel_coordinate,(3,2)))))

# TASK.solution (일반 · anti-unify 가 DIFF 를 input-계산식으로 재표현·검증)
obj = select(P.G0,"object", eq(color_of, ?C))          # ?C: 살아남은 선택자
coloring(coordinate_of(obj), ?vac)                      # 비움
coloring(<obj·격자 원자의 좌표식>, color_of(obj))        # 채움 (좌표식은 탐색에서 창발)
```

### 2.2 output grid 사용과 test 실행가능성 (하네스 §P5 완화)

- **abstraction 재료 확대**: 이제 TASK.solution 도출 과정은 example pair 의 **in/out grid 및 그 하위
  요소(object·pixel·좌표·색) 전부**를 재료로 쓸 수 있다.
- **제약**: test 실행 시엔 test **input** 만 존재하므로, 최종 TASK.solution 은 **test-input 만으로
  실행가능**해야 한다. output-참조는 *탐색·fitting 의 근거*로만 쓰고, 결과식은 input-계산가능하도록
  다시 쓴다.
- 이 rewrite 는 **별도 단계가 아니라 anti-unification 그 자체**다(§2.3). 강제는 **verify**가 한다.
- **하네스 갱신 필요**: §P5("변수 출처는 G0, test 엔 G1 없음")를 위와 같이 완화한다. `ARBOR_HARNESS.md`
  에 이 결정과 근거(verify 가 등가·selectability 를 강제)를 §5 절차대로 기록한다.

### 2.3 파이프라인 단계 매핑 (사용자 교정 반영)

- **compress** — pixel pair.program → **object 단위**. 변화(객체가 어디로 갔는지 포함)를 **관측 요소로
  구체 서술**하며 이 단계에서 `P{k}.G1`(output) 참조 허용. 동시에 두 pair.program 의 **길이·동작을
  일치**시켜 정렬 가능하게 한다.
- **generalize = anti-unification** — 길이 맞은 두 object program 을 정렬해 `compare(prog,prog)`.
  **COMM 지점 = 상수 고정**, **DIFF 지점 = 그 표현식을 input-계산식으로 재표현**하여 하나의
  TASK.solution 으로 합친다. output 으로 서술됐던 지점이 여기서 input-유래 식으로 바뀐다.
- **resolve / verify** — anti-unify 는 DIFF 재표현 **가설을 여러 개** 낳는다. 걸러야 한다:
  (a) **train pair 전부 만족**이 우선, (b) object/pixel **selection 이 test input 에서도 가능**한지
  확인해 안 되는 가설 탈락. 살아남은 것이 version space.

---

## 3. 컴포넌트 설계

각 단위는 하나의 목적 · 명확한 인터페이스 · 독립 검증(하네스 §2-5 시각화 포함)을 갖는다.

### C1. Grammar A 표현 노드 (`arbor/reasoning/program_ast.py`)

- 추가: `select(node, level, pred)` · `coordinate_of(x)` · `color_of(x)` · property-accessor 참조 ·
  `eq(accessor, value)` 술어 노드 — 전부 **json 직렬화되는 AST 노드**(Python 람다 아님).
- 폐기(신규 emit 중단): `cellset`. (레거시 실행 호환은 C4 전환 완료 시 제거.)
- 노드 참조는 ARCKG 경로 문자열(`"Txxx.P0.G1"`)을 값으로 갖는다.
- 대시보드/report 는 이미 select/coordinate 렌더를 하므로(커밋 `0e04ded`) **표기가 자연히 일치**한다.

### C2. Grammar A 실행기 (`program_ast.execute` 확장)

- 입력: program AST + ARCKG(`idx`) + 대상 grid(경로 또는 격자). 출력: 결과 격자.
- `select(P.Gx, level, pred)` → `idx` 에서 그 노드의 level-자식(pixels_of/objects_of)을 읽어 `pred`
  (eq accessor) 로 필터. `coordinate_of` → (r,c) 또는 (r,c) 리스트. `coloring(coords, color)` →
  해당 좌표(들) 재채색.
- 현행 `cellset`/`ref` 해소 경로를 이 경로가 대체한다. **verify 는 이 실행기로만 실행**한다(§2.3).

### C3. compress — Grammar A object 서술 (`operators/compress.py`)

- `_object_change_program` 이 `cellset(const([...]))` 대신 **Grammar A** 를 emit:
  변화 객체를 `select(P{k}.G0,"object", eq(<accessor>, <value>))` 로 서술, 목적지는 `P{k}.G1` 관측을
  근거로 구체 서술. erase/paint 각각 `coloring(coordinate_of(...), color_of(...))`.
- 대응(`_object_changes`)의 static/recolor/move 판정 로직은 유지(이동/재채색 통합). 바뀌는 것은
  **출력 표현**뿐.

### C4. generalize — DIFF 재표현 = anti-unify (`operators/generalize.py`, `reasoning/antiunify.py`)

- 정렬된 두 object program 을 `compare(prog,prog)`(2차 `_compare`) → COMM 상수 / DIFF slot.
- **DIFF 재표현**: output-참조(`P{k}.G1` 유래) 슬롯을 input-계산식(`select(P.G0,…)` + 좌표식)으로
  다시 쓴다. 선택자는 `@shape#0` 문자열이 아니라 `eq(shape_of, <값>)` 등 **실제 accessor 술어**로.
- 좌표식(이동량 등)은 기존 `_gen_exprs` 좌표문법(원자 {H,W,r0,c0,h,w,…}×{+,−,∗,//})에서 창발.
  `translate` 이름 없이 **좌표 산술식**으로 표현.

### C5. resolve/verify — 가설 검증 (`operators/resolve.py`, `reasoning/antiunify.py`)

- DIFF 재표현 후보(version space)를 검증: (a) train 전 pair 만족, (b) `select` 가 **test input**
  에서도 대상을 고를 수 있는지(0개면 무효 → 탈락). 시도·기각을 트레이스/대시보드에 남긴다(§1-5).
- 이미 `_resolve_cellset` 이 test_comps 로 test-selectability 를 부분 확인 중 — 이를 Grammar A
  선택자 기준으로 재정렬.

### C6. 규칙발화 정화 (risk 高 — 별도 검증)

- **object-level**: `colored-all yes` 강제·"원천차단" 주석을 걷어낸다. object 비교결과를 소비하는
  coloring 규칙이 없으므로 program 이 안 생기고, verify 가 (항등 실행 → G0≠G1) 자연 실패한다.
  ⚠️ **얽힘**: 현행 object→pixel 하강 트리거는 `hypothesized failed`([trace.py `_do_descend`
  to_pixel](../../../arbor/engine/trace.py#L477))에 의존한다. object verify 가 정직히 실패해
  `hypothesized failed` 를 세우도록 경로를 보존한다(가짜 `colored-all` 은 없애되 "항등 program →
  verify 실패" 경로는 유지).
- **`advance_or_finish` → 자연 순회**: P0 program 완성·verify 후 hypothesis space 를 **pop**하고,
  다음 미처리(program 공백) pair 가 자연히 잡히도록 한다. `pair-idx`를 명시적으로 미는 절차 제거.
  ⚠️ **얽힘**: pop 후 "미처리 pair" 재진입이 규칙 조건(program 공백 감지)으로 발화하도록 게이트 정리.
- **`sim`/`recolor-rel` 재구성**: pixel 비교결과(`E_G0Xi-G1Xi`, color DIFF)에서 **규칙 발화**로
  `coloring(coordinate_of(select(P.G0,"pixel", eq(pixel_coordinate,<coord>))), <out>)` 줄을 emit.
  `sim`(증분 페인팅 scratch)은 제거하고 **verify 가 실행기(C2)로 program 을 실행해 대조**한다.
  `recolor-rel` 재라벨링 제거 — coloring operator 가 pair 의 relation 을 직접 읽어 한 번에 처리
  (단일 operator 유지; 예전 TIE 회피를 위한 단일 scalar 게이트는 보존).

---

## 4. 단계(phase) & 행동보존 게이트

각 phase 통과 조건 = **`python -m debugger.score move` = 60/60** + objc 유지. 회귀 시 그 phase 에서
멈추고 진단(하네스 §2-4: 함수에 탐색이 숨지 않았는지도 함께 확인).

- **P1 — 표현 노드·실행기**: C1 + C2. 기존 cellset 경로와 **동작 동치**를 먼저 확보(순수 리팩터,
  green 유지).
- **P2 — compress emit 전환**: C3. cellset → Grammar A. green 유지.
- **P3 — generalize/resolve 전환**: C4 + C5. `@shape#0` 제거, DIFF 재표현·검증을 Grammar A 로. green.
- **P4 — 규칙발화 정화**: C6. object-level·advance·sim/recolor-rel. **가장 회귀 위험 큼** — phase 를
  잘게 쪼개 각 소변경마다 score 확인.
- **P5 — 하네스 갱신**: §2.2 의 §P5 완화를 `ARBOR_HARNESS.md`·이 문서에 확정 기록.

> P1–P3 는 표현만 바꾸는 리팩터(행동 동치)라 상대적으로 안전. P4 는 제어구조를 건드리므로 마지막.

---

## 5. 범위 밖 (이 문서 아님)

- **rotate/flip** — 다음 청크. 단, C6 의 `translate` 폐기·좌표식 창발 구조는 rotate/flip 이 꽂힐
  seam 을 미리 열어둔다(per-cell 좌표사상으로 일반화하면 `(c,H−1−r)` 등이 같은 탐색공간에서 창발).
- **pixel compare 전조합** — "같은 좌표끼리"의 인위적 제약을 전조합으로 푸는 것은 성능 이슈로 보류.
- **object coloring 을 규칙으로 소비** — object 좌표집합을 coloring arg 로 넣는 규칙 신설은 별도 논의
  (하네스 §5). 이 문서에선 object-level 은 "발화 규칙 없음 → 자연 실패" 로만 정직화한다.

---

## 6. 성공 판정

- move 60/60 + objc 유지(각 phase).
- 산출물에서 `cellset`·`@shape#0`·`move[...]`·바 `input_grid` 변수 **소멸**, 대신 `select(P.Gx,…)`·
  `coordinate_of`·`color_of` 등 Grammar A 표현이 WM·대시보드에 나타난다.
- object-level 이 `colored-all`/"원천차단" 없이 "규칙 없음 → verify 자연 실패 → 하강" 으로 읽힌다.
- pair.program 이 pixel 비교결과에서 **규칙 발화**로 생성되고, verify 는 실행기로 실행·대조한다.
- 서로 다른 문제가 서로 다른 하강 깊이·step 을 낳는다(탐색이 함수에 숨지 않음, 하네스 §2-4).
