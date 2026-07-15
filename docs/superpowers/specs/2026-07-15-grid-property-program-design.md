# G1 3-property program — grid-level 결론을 program·solution 으로 (설계)

> **정본 스펙.** 모든 문제의 program 을 "G1 의 세 GRID property(size·color·contents)를 예측·설정"하는
> 보편 골격으로 재정의한다. 세 property setter DSL — `set_gridsize` · `set_gridcolor` · `set_gridcontents`
> — 를 도입(고차 DSL = frozen make_grid+coloring 조합; 하네스 §5 승인). arg 는 확장가능 표현식(단순:
> keep/const/expr/delta; 복잡: 재귀 DSL-조합, forward slot). grid-level 에서 결론나는 태스크(a/b)도
> 이 골격으로 **pair.program + task.solution** 이 나오게 한다. **의도된 행동 변화** → 골든 재기준화.
>
> 근거: ARBOR_HARNESS.md §2-1(ARCKG GRID = size/color/contents) · §1-1/§5(고차 DSL=조합, 승인) ·
> §1-3(값은 탐색으로) · §1-5(program 은 실행·검증) · §2-5(대시보드 반영). 선행: [[program-ast]] 스펙
> (`docs/superpowers/specs/2026-07-15-program-ast-design.md`) — program 은 이미 AST(typed-arg dict).

## 1. 배경 — 지금 grid-level 결론이 program 이 안 되는 이유

- `synthesize._op_synthesize`([synthesize.py](../../../procedural_memory/operators/synthesize.py))가 `_grid_decide`
  로 size/color/contents 를 판정.
- **size/color DECIDE** → 부모에 `size-hyp`/`color-hyp` + `set-size`/`set-color` → `set_grid_size`/`set_grid_color`
  operator([grid_slots.py](../../../procedural_memory/operators/grid_slots.py))가 `slot-grid_size`/`slot-grid_color`
  WM 슬롯에 적재. **그 슬롯을 읽는 코드가 없음**(dead scaffold; [solver.py:174](../../../arbor/solver.py#L174)
  "휴면… hypothesize 손볼 때 활성화"). → grid 결론이 program 으로 안 이어짐.
- **contents DECIDE** → 답을 `cv["value"]` 로 직접 내고 program 은 contents 것만:
  - 전역remap → `_global_recolor_program`(실제 pixel AST) · 항등 → `program([])`(빈 AST) ·
    **상수출력 → `"output_grid = <상수 출력>"` placeholder(실 program 아님)**.
- **easy000a/b** = 상수출력(모든 train 출력이 동일 고정 grid; size KEEP/CONST, color CONST, contents 상수출력)
  → placeholder 만 남고 **size/color 결론은 program 에 없음**. task.solution 도 없음.
- **easy000c+** = contents DESCEND → object/pixel 하강 → pixel/blob program 생성(현행).

**결론**: grid-level 에서 결정된 size/color/contents 가 **일관된 program 으로 물질화되지 않는다**.

## 2. 목표 / 비목표

**목표**
- 모든 program 의 보편 골격 = **G1 의 세 GRID property 예측**: `set_gridsize`·`set_gridcolor`·`set_gridcontents`
  (ARCKG GRID 노드의 3 property 와 1:1 대응, §2-1).
- 이 세 개를 **DSL**(program 어휘, 실행가능)로 도입 — 고차 DSL = frozen `make_grid`+`coloring` 조합(§dsl-taxonomy).
- arg = **확장가능 표현식**: 단순(keep/const/expr/delta, `_grid_decide` 산물) + 복잡(재귀 DSL-조합, 스키마만 open).
- grid-결론 태스크(a/b)가 이 골격으로 **pair.program + task.solution** 을 낸다(다른 문제와 동일 파이프라인).
- program 은 실행가능·train 검증(§1-5). 답은 program 실행에서 나온다.

**비목표(이번 아님 / forward slot)**
- 복잡 DSL-조합 값을 *탐색*하는 로직(예: "width = 빨간 object 수"의 자동 도출) — 스키마는 열되 **search 는 forward
  slot**(§7 의논 후). Phase 1 은 `_grid_decide` 의 단순 결론만 채운다.
- pixel/blob program 을 `set_gridcontents` arg 로 완전 흡수(= Phase 2; §11).
- `②` 대시보드 program 뷰어(별도 서브프로젝트; §12).
- 새 primitive transformation atom (make_grid·coloring 동결 유지 — set_grid* 는 그 *조합*).

## 3. 보편 program 골격 (핵심)

모든 program 은 G1 을 세 property setter 로 짓는다:

```
G0 = input_grid
G1 = set_gridsize( <size-expr> ) ∘ set_gridcolor( <color-expr> ) ∘ set_gridcontents( <contents-expr> )
output_grid = G1
```

AST(기존 typed-arg dict 확장 — program step 도 `{call,args}`):
```json
{
  "input": {"grid": "G0"},
  "body": [
    {"call": "set_gridsize",     "args": {"size":     <arg-expr>}},
    {"call": "set_gridcolor",    "args": {"color":    <arg-expr>}},
    {"call": "set_gridcontents", "args": {"contents": <arg-expr>}}
  ],
  "output": {"var": "grid"}
}
```
- **보편**: 문제 불문 body 는 이 3-step 골격. property 별로 arg-expr 이 달라질 뿐.
- **ARCKG 미러**: GRID 노드 property(size/color/contents)를 program 이 그대로 설정 → "program 은 ARCKG nested dict 의 일부".

## 4. 세 property setter DSL (고차 DSL, §5 승인)

`procedural_memory/dsl/` 에 등록(`@dsl("transformation", …)`). 각각 frozen atom 의 *조합* 으로 정의(새 원자 아님):

- **`set_gridsize(size)` → make_grid 의 size**: G1 의 차원을 정한다. 실행 = `make_grid(size=eval(size), fill=…)`.
- **`set_gridcolor(color)` → base/palette**: G1 의 배경 fill + 색 팔레트 제약. color 는 contents 에서 대부분
  파생되므로 실행 역할은 **base 색(make_grid fill) + 검증용 팔레트**. (전체 색집합 = fill ∪ contents 색.)
- **`set_gridcontents(contents)` → coloring/구성**: G1 의 셀 값. 실행 = coloring 조합(또는 상수/항등/remap).
  **contents-expr 이 곧 통일점**(§6): grid 결정이면 간단식, 하강이면 pixel/blob program 이 이 arg 로 들어감(Phase 2).

**실행 lowering(개념)**:
```
execute(set_gridsize(sz) ∘ set_gridcolor(c) ∘ set_gridcontents(ct), G0)
  = let base = make_grid(size=eval(sz,G0), fill=base_of(c))
    in  apply_contents(base, ct, G0)          # coloring 조합 / 상수 / 항등 / remap
```
- lowering 은 `execute`(interpreter) 안에서. 문자열 exec 없음(§ 기존 program-ast 계약).

## 5. 확장가능 arg 표현식 문법

각 property 의 arg 는 **재귀 표현식** — program step 과 동일한 노드 구조:

- **leaf(단순, Phase 1)**: `{"keep": <prop>}`(=G0.prop) · `{"const": v}` · `{"expr": "H-1"}` · `{"delta": {"remove":[…],"add":[…]}}`(집합변화).
- **DSL-조합 노드(복잡, forward slot)**: `{"call": <registered-dsl>, "args": [<arg-expr>…]}` — 재귀.
  예: width = `{"call":"count","args":[{"call":"select","args":[{"call":"objects_of","args":[{"ref":"input_grid"}]},{"pred":"color==red"}]}]}`.
- **하네스**: 조합에 쓰는 DSL 은 **등록된 것만**(property/selection/util/relation). 새 DSL 필요 시 §5. 값 *탐색*은
  forward slot — Phase 1 은 leaf 만 (`_grid_decide` 매핑: KEEP→keep, CONST→const, MAP[H1=H0-1]→expr,
  SET-MAP(−…+…)→delta).
- 새 leaf 종류 `keep`·`delta` 는 `program_ast.py` 생성자·`to_source`·`execute` 에 추가(cellset 확장과 동형).

## 6. contents 가 통일자

`set_gridcontents` 의 arg 가 문제 유형을 흡수한다:
- **상수출력**(a/b): `{"const": <고정 grid>}` — 실행 = 그 grid 를 make_grid+coloring 으로 물질화(모든 비배경 셀 채색).
  train-검증된 CONST 결론이라 §1-5 정직(실행하면 그 grid).
- **항등**: `{"keep": "contents"}` (=G0).
- **전역remap**: `{"call":"recolor_map","args":[…]}` 또는 기존 `_global_recolor` 산물(coloring 조합).
- **하강(Phase 2)**: contents DESCEND → object/pixel 하강 → **그 pixel/blob program 이 이 arg 로** 들어감.
  즉 지금의 coloring program 이 "contents 실현"으로 흡수. (Phase 1 은 grid-결정 case 만; 하강 case 는 현행 유지.)

## 7. 과정(operator) — compare 는 비교만, hypothesize 가 관계→program (골조 정정 2026-07-16)

> **구현 중 발견(중요):** 정답 예측이 두 곳에 흩어져 있고 compare 안에 **단락(shortcut)**이 있었다 —
> `compare.py::_predict_test_output`(분기①: 두 train 출력이 COMM(상수) → **답 직접** + placeholder
> `TASK.solution="output=상수(불변)"`; 분기②: size/color 부분예측 → 하강). **a/b 는 분기①에서 답이 나와
> synthesize 까지 안 내려감**(synthesize 의 contents-DECIDE 는 9태스크 통틀어 0회). c–h 는 분기②→하강→GRID
> hypothesize→`synthesize._grid_decide`(또 판정)→contents DESCEND→object/pixel. 판정이 compare 와 synthesize
> **두 곳**에 있다.

**정정된 골조 (사용자 2026-07-16 — 각 함수 임무 명확화):**
- **compare = 비교만.** cross-pair 관계(출력끼리 COMM/DIFF, size/color 의 within·change 등)를 WM/`ag.kg` 에
  남기고 **끝**. **정답 예측·answer-ready·branch 없음.** `_predict_test_output` 을 compare 에서 **제거**.
- **hypothesize = 비교 결과로 추론.** compare 가 남긴 관계를 읽어 G1 의 3속성(size/color/contents)을 정한다:
  - **셋 다 정해짐** → **3-property program(set_grid*) 생성**(per-pair) → verify/generalize/compose 로 답.
  - **하나라도 미결(부분예측)** → **하강.** 부분예측 program 은 contents 없이 동작 못 함 = "grid 를 예측했다"고
    볼 수 없음(§P1 막혀야 하강). a/b(상수출력)=셋 다 정해짐→program; c–h=contents 미결→하강(현행 pixel 경로).
- 즉 `_predict_test_output` 의 판정 로직(①·②)이 **hypothesize 로 이관**되고, 판정 결과가 **직접 답이 아니라
  program** 이 된다. GRID 하강 시의 `synthesize._grid_decide` 판정도 이 hypothesize 판정으로 통합(hypothesize 가
  `_grid_decide`/cross 관계를 써서 3속성 결정 → all-3: program / else: 하강).
- **operator ≠ DSL**: operator(compare=비교 / hypothesize=추론·생성)=과정, DSL(set_grid*)=program 어휘.
- per-pair 순회(`S1 ^pair-idx`)로 각 example pair 가 3-property program emit → generalize.

## 8. 실행 + anti-unify + compose

- `execute`(program_ast): set_gridsize/color/contents step 을 make_grid+coloring 으로 lowering 실행 → G1. train 검증.
- `antiunify_ast`: 3-property program 들을 **구조 비교** — 세 step 이 정렬돼 있으니 property 별로 arg-expr 비교
  (COMM=상수, DIFF=변수 slot). 기존 pixel/blob dispatch 에 **grid(3-property) 계열** 추가.
- `resolve`: DIFF slot(예: size expr 변수)을 G0 유래 식으로(기존 `resolve_slot` 확장 — expr/delta 대응).
- `compose`: task.solution(3-property, 변수)을 test G0 에 execute → 답. 기존 파이프라인 그대로.

## 9. 행동 변화 + 골든 재기준화 (사용자 승인)

- **구조 변경**(§7): compare 에서 `_predict_test_output` 단락 제거 + 판정을 hypothesize 로 이관 → a/b(상수출력)와
  c–h(grid 단계) **모두** solve 흐름·step 수가 바뀐다(a/b 는 compare 답→hypothesize program; c–h 는 판정 위치 이동).
- a/b 는 이제 3-property program→(generalize)→답. c–h 는 여전히 하강 pixel program(판정만 hypothesize 로).
- `tests/golden_steps.json` 을 **새 행동으로 재캡처**(재기준화). 재기준화 후 그 값이 새 오라클. **정답(✓풀림) 불변**이
  최우선 게이트(a/b·c–h 다 여전히 풀려야). made000b/survey 무크래시.
- 답 정확성: a/b 가 여전히 정답(✓풀림)이어야 한다(program 실행 결과 = 기존 cv 답과 일치). survey 17 렌더 무크래시.
- 하네스 §2-4 부합: a/b 가 답을 직접 뱉는 대신 정직한 과정(3-property 예측→program→solution)을 거침 → step 수가
  다른 문제와 달라지는 게 오히려 옳음.

## 10. 데이터 모델 요약 (program_ast.py 확장)

- 새 step op: `set_gridsize`·`set_gridcolor`·`set_gridcontents`(고차 DSL; body=make_grid/coloring 조합).
- 새 leaf: `{"keep": <prop>}`, `{"delta": {"remove","add"}}` (const/expr/var/ref/cellset 는 기존).
- arg 노드 재귀: leaf | `{"call","args"}`(DSL-조합).
- `to_source`: 3-property 를 `set_gridsize(…)∘set_gridcolor(…)∘set_gridcontents(…)` 로 렌더(사람이 읽는 형).
- `execute`: 3 step lowering; keep/delta/expr 해소.
- `ops_of_ast`/`antiunify_ast`: grid(3-property) 계열 dispatch.

## 11. 단계 (phasing)

- **Phase 1 (이번 스펙 핵심)**: grid-결론 태스크(a/b, 그리고 size/color/contents 가 grid 에서 결정되는 임의 태스크)에
  3-property program 물질화 — arg 는 leaf(keep/const/expr/delta)만. execute/antiunify/compose 로 solution·답.
  a/b 가 program+solution 을 갖고 여전히 ✓풀림. 골든 재기준화.
- **Phase 2 (후속)**: contents DESCEND case 흡수 — 하강 pixel/blob program 이 `set_gridcontents` arg 로. 모든 program
  이 3-property 골격. (기존 pixel/blob program 을 감싸는 작업.)
- **forward slot**: 복잡 DSL-조합 arg 의 *탐색*(§2 비목표).

## 12. 후속 서브프로젝트 ② — 대시보드 program 뷰어

별도 스펙. 우상단 "이 문제 anti-unification" 버튼 → **program 뷰어 companion 페이지**로 교체. PAIR.program 이
처음 생기는 cycle 부터: (1) text(`to_source`+`render_header`), (2) AST 트리, (3) 시각화(Task 10 렌더러 재사용).
per-pair program + task.solution.
- **범위 = easy a–h 전부**(사용자 2026-07-15): 이 페이지에서 easy000a…easy000h **각 태스크의 program 을 모두
  확인**할 수 있어야 한다. a/b 는 ③ Phase 1 의 3-property program, c–h 는 하강 pixel program. (i 는 미해결이라
  program 없음 → "미합성/크기변화" 표식.) 태스크 선택 탭 + 각 태스크의 per-pair program·solution 렌더.
- ③ Phase 1 완료 후 착수(그래야 a/b 도 실제 program 을 보여줄 수 있음).

## 13. Acceptance (Phase 1)

- easy000a/b 가 **3-property pair.program + task.solution** 을 물질화(WM 에 AST-json). 여전히 ✓풀림(정답).
- program 이 실행가능: `execute` 로 a/b program → 그 고정 grid 재현(train 검증).
- `set_gridsize/color/contents` DSL 이 `SPECS`/ontology 에 등록(고차 DSL, body=조합).
- `tests/golden_steps.json` 재기준화; 재캡처 시 동일(결정성). survey 17 렌더 무크래시.
- (하네스) 3-property 값이 `_grid_decide` 탐색 산물(손코딩 아님) — 시도·기각이 트레이스에 남음(§1-5).

## 14. 리스크 / 자가검증 (하네스)

- **§1-1/§5**: set_grid* 3개는 승인된 고차 DSL(조합) — 새 primitive atom 아님. `make_grid`/`coloring` 동결 유지.
- **§1-2/§1-3**: 값은 `_grid_decide`/`_size_expr_search` 탐색에서. 상수출력을 make_grid+coloring 으로 펴는 건
  "답 박기"가 아니라 train-검증 CONST 결론의 실행 물질화. size expr(H-1)은 탐색 산물.
- **§1-5**: program 실행·train 검증 필수 — 실행하면 G1 이 나와야. 안 나오면 그 arg 는 틀림(기각).
- **color 파생 애매성**: set_gridcolor 실행 역할(base/palette) 명세를 구현 시 확정 — color 집합이 fill+contents 로
  재현되는지 검증. 안 맞으면 멈추고 §7.
- **재기준화 위험**: golden 이 바뀌므로 "무엇이 왜 바뀌었나"를 커밋에 기록(회귀 vs 의도 구분). a/b 외 태스크
  step 수는 불변이어야(grid-결정 아닌 것은 경로 무변) — 바뀌면 조사.
- **범위 팽창**: Phase 1 은 grid-결정 case + leaf arg 만. 복잡 조합/pixel 흡수는 Phase 2/forward. 넘으면 멈춘다.
