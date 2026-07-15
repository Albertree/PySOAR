# PAIR.program / TASK.solution 을 AST 로 — 설계

> **정본 스펙.** program/solution 의 canonical 저장형을 flat Python **문자열**에서 **균일 typed-arg
> nested-dict AST** 로 바꾼다. anti-unification 은 정규식 파싱 대신 `compare()` 기반 구조 비교로,
> 실행은 AST 인터프리터로, 시각화(anti-unify 뷰)는 실제 저장 AST + 실제 compare 결과로 렌더한다.
> **행동보존**: 리팩터 전/후 step 수 완전 일치가 acceptance gate (REFACTOR_PLAN.md 계승).
>
> 근거: ARBOR_HARNESS.md §0.5(anti-unify = compare(prog,prog)+변수화)·§2-2(항목·관계 비교)·
> §2-5(구조체 바꾸면 대시보드 반영)·§P7(모든 정보 symbolic dict+json) · REFACTOR_PLAN.md(step-gate).

## 1. 배경 — 지금 program 이 사는 방식

- program 은 `"\n".join(...)` 로 만든 **여러 줄 Python 문자열** 하나. AST·리스트·dict 아님.
  ```
  in_px = pixels_of(input_grid)
  P0 = in_px[5]
  tfg0 = input_grid
  tfg1 = apply_DSL(tfg0, coloring, P0.coord, 3)
  output_grid = tfg1
  ```
- 저장: WM 트리플 `(<pair>.property, "program", <문자열>)`, 빈 슬롯 sentinel `"{}"`.
  solution 은 `(<task>, "solution", <문자열>)`. 디스크 `program.json` 없음.
- 생성처 5곳: `arbor/reasoning/program.py::_pixel_residual_program`·`::_global_recolor_program` ·
  `procedural_memory/operators/coloring.py::_op_coloring` · `arbor/reasoning/antiunify.py::render_skeleton` ·
  `procedural_memory/operators/compose.py`.
- "AST 에 가장 가까운 것" = `antiunify.py::parse_program` — 정규식으로 텍스트를 `ops=[(idx,color)]` +
  `skeleton`/`slots` 로 되돌림. **단 `in_px`/`coloring` 형태만** 파싱, 나머지는 `None` (anti-unify 가
  그 한 계열에만 동작).
- program 속 `pixels_of`·`apply_DSL`·`.coord` 는 **실제 callable 이 아니라** 정규식+커스텀 인터프리터
  (`antiunify.py::execute_solution`)가 읽는 **문자열 토큰**. 이름도 어긋남: program `.coord` vs
  ARCKG Object `.coordinate`, Pixel `.row/.col`.
- "전체 구조" 3부(사용함수 정의 → `input_grid = …` → 본문)는 `debugger/reports/program_report.py::_PREAMBLE`
  에 이미 있고, 표시 시 `_PREAMBLE + program` 으로 prepend 한다(자동 앞단의 선례).
- 대시보드 3분열: ① `focus_dashboard.html` — program 이 40자 truncate WM leaf. ② `easy_antiunify_report.html`
  (`easy_antiunify_viz.py`) — 저장 program 을 **안 읽고** `easy_concepts` 에서 재계산해 손으로 그린
  coloring 전용 box-flow. ③ `program_report.html` — 저장 program 을 `<pre>`+▶실행(단 `__main__` 미연결).

## 2. 목표 / 비목표

**목표**
- program/solution 의 canonical 저장형 = **nested typed-arg AST** (JSON).
- anti-unification = 정렬된 AST 들의 `compare()` 기반 구조 비교(COMM=유지, DIFF=변수 slot).
- 실행 = **AST 인터프리터**(`execute(ast, arckg)`), 문자열 exec 없음.
- 표시용 header 자동생성: AST 가 실제 쓰는 op 만 DSL `SPECS` 에서 골라 시그니처 + `input_grid`(현 ARCKG
  스냅샷) prepend. **저장 안 함**, 렌더/복붙 시에만.
- 시각화: **anti-unify 뷰**(`easy_antiunify_viz`)를 실제 저장 AST + 실제 compare 결과(COMM/DIFF·slot)로 교체.

**비목표 (이번 아님)**
- 메인 `focus_dashboard.html` WM leaf 의 program 전용 리치 렌더 (저장형이 AST 가 되며 leaf 가 구조적
  값이 되는 부수효과는 허용). — *스펙 리뷰에서 넓힐 수 있음.*
- ARCKG 노드(Pixel/Object)에 `.coord` 등 accessor property 추가 (인터프리터가 이름차를 흡수하므로 불필요).
- 실제 Python `exec` 실행 경로.
- 새 transformation atom 추가 (frozen 2개 유지 — 하네스 §1-1).
- `dsl_library/` 학습 증착·활성화 규칙 등 forward slot.

## 3. 데이터 모델 — 균일 typed-arg AST

### 3.1 문법 (최소형)

compact 저장값 = **body 만**. 노드는 전부 dict:

- **program 루트**
  ```json
  { "input": {"grid": "G0"}, "body": [ <step>, ... ], "output": {"var": "grid"} }
  ```
  (solution 루트는 추가로 `"slots": { "?name": {"kind", "pos", ...} }` 를 가진다 — anti-unify 산물.
  pair.program 은 slots 없음.)
- **step** = `{"call": <op>, "args": { <argname>: <leaf|node> } }`
  - `op` ∈ frozen transformation atom (`coloring`, `make_grid`) 만. 그 외는 조합.
- **인자 leaf** (균일 — compare() 가 모든 leaf 에서 재귀):
  - `{"const": <값>}` — 상수 (색 정수, 좌표, size dict 등)
  - `{"var": "?name"}` — anti-unify 로 승격된 변수 slot
  - `{"expr": "<식>"}` — G0 유래 식 (예: `"H-1"`, `"r0"`, `"color_of_fg"`) — resolve 산물
  - `{"ref": <level>, "index": <leaf>}` — 노드 참조 (`level` ∈ `pixel|object|grid`), `index` 는 leaf
    (`{"const":5}` 또는 `{"expr":"r0*W+c0"}` 또는 `{"var":"?src0"}`)

### 3.2 예시

현행 pixel 재채색 program 의 AST:
```json
{
  "input": {"grid": "G0"},
  "body": [
    {"call": "coloring", "args": {
       "target": {"ref": "pixel", "index": {"const": 5}},
       "color":  {"const": 3}}},
    {"call": "coloring", "args": {
       "target": {"ref": "pixel", "index": {"const": 12}},
       "color":  {"const": 3}}}
  ],
  "output": {"var": "grid"}
}
```

anti-unify 후 TASK.solution (DIFF slot 승격 → resolve 식):
```json
{
  "input": {"grid": "G0"},
  "body": [
    {"call": "coloring", "args": {
       "target": {"ref": "pixel", "index": {"expr": "fg_index"}},
       "color":  {"expr": "color_of_fg"}}}
  ],
  "output": {"var": "grid"},
  "slots": {"?src0": {"kind": "src", "pos": 0}, "?color0": {"kind": "color", "pos": 0}}
}
```

### 3.4 blob/cellset 계열 (compress·object-level program) — 스키마 확장 (2026-07-15, §5 승인)

이 브랜치(seokki-refactor)는 `compress` operator 로 pixel program 을 **연결 덩어리(blob)** 로 축약한
object-level program 계열을 갖는다. 형식: `B0 = [7,8,13,14]` + `apply_DSL(tfg0, coloring, B0, 3)`
(cellset 을 한 덩어리로 채색, `.coord` 없음). anti-unify 는 `_antiunify_blobs`(색 COMM 정렬 → cellset
DIFF = `cellset` slot), resolve 는 `_resolve_cellset`(input object 유래 식). AST 는 이 계열도 담는다:

- **target 확장**: pixel = `{"ref":"pixel","index":<leaf>}` · **cellset = `{"ref":"cellset","cells":<leaf>}`**
  where `cells` leaf ∈ `{"const":[i,...]}` (concrete) | `{"var":"?cellsN"}` (anti-unified).
- op 은 `coloring` 그대로(frozen). 실행 시 cellset 의 각 셀을 단일셀 coloring 조합(compress 규약).
- 예:
  ```json
  {"call": "coloring", "args": {
     "target": {"ref": "cellset", "cells": {"const": [7, 8, 13, 14]}},
     "color":  {"const": 3}}}
  ```
- anti-unify 후: cells DIFF → `{"var": "?cells0"}`, color COMM → const 유지. slot kind = `cellset`.
- `to_source(blob AST)`: 전부 const cells → **compress def-형**(`B{j}=[...]` defs + steps; `_parse_blob_program`
  정규식 round-trip 보존) · var 포함(solution) → **render_skeleton inline-형**(defs 없이 `apply_DSL(..,[..]|?slot,c)`).
- pixel 계열과 blob 계열은 **섞이지 않는다**(antiunify 가 한 계열만 고른다) — 계열 내 구조는 균일.

### 3.3 저장/직렬화
- WM 키 불변: `(<pair>.property, "program", json.dumps(ast))`, `(<task>, "solution", json.dumps(ast))`.
- 빈 슬롯 sentinel: 현 `"{}"` 문자열 → `null` 로 통일 (모든 소비처가 `null`/빈 body 를 "미합성"으로 인식).
- P7 준수 (symbolic dict + json).

## 4. 인터프리터 + 표시용 header

### 4.1 `execute(ast, grid_in, arckg=None) -> grid`
- body step 순회. 각 step:
  - `target` 이 `{"ref": level, "index": leaf}` → `index` leaf 를 현 grid/ARCKG 로 해소해 노드 선택,
    그 노드의 좌표를 얻어 frozen atom 에 넘김.
  - `color`/기타 인자 leaf 해소: `const`→값, `expr`→G0 식 평가, `var`→(solution 실행 시) 선택 fn.
  - frozen `coloring`/`make_grid` **body 호출** (transformation atom 그대로).
- 문자열 exec 없음. 현 `execute_solution` 과 **동일 결과**(행동보존)를 내되 입력이 AST.
- accessor 매핑: `object.color`→`color_of`, `pixel.coord`→`coordinate_of`, `grid.objects[k]`→`objects_of(grid)[k]`
  를 인터프리터 내부 테이블로 SPECS body 에 연결. `.coord`↔`.coordinate` 이름차는 여기서 흡수.
- **cellset 분기 (§3.4)**: `target.ref=="cellset"` 이면 `cells` leaf 를 해소해(const list | var→choice fn)
  집합의 각 셀을 색칠 — 현 `execute_solution` 의 `skeleton.kind=="blob"` 분기(antiunify.py:463-476)와 동일 산술.

### 4.2 표시용 header 자동생성 `render_header(ast, arckg) -> str`
- AST 를 훑어 실제 등장하는 op·accessor 집합 수집 → 각각 `registry.spec(name)` 로 시그니처 라인 방출.
- `input_grid = <G0 contents>` (현 ARCKG 스냅샷의 pair G0) 한 줄 추가.
- **저장 안 함.** 렌더(anti-unify 뷰)·복붙 시에만 body 앞에 붙인다. `_PREAMBLE` 의 자동화 버전.

### 4.3 `to_source(ast) -> str` (이행 안전장치)
- AST → **현행 flat Python 문자열과 동일** 출력. 아직 문자열을 읽는 코드·기존 리포트·테스트가 안 깨지게
  하는 shim. 이행 완료 후에도 "복붙 실행용 Python" 렌더러로 존속.

## 5. anti-unification — `compare()` 기반

- 정규식 `parse_program`/`_STEP`/`_DEF` **은퇴**.
- 절차:
  1. **정렬(structure mapping)**: 현 `antiunify.py::_align` 의 "COMM 최대화 순열" 논리를 AST step 리스트에
     재사용 (step 수 ≤ 임계면 전수 순열, 크면 원순서).
  2. **구조 비교**: 정렬된 두 AST 를 위치별로 비교 — 같은 서브트리 = COMM(유지), 다른 leaf = DIFF →
     `{"var": "?slotN"}` 로 승격 + `slots[name] = {kind, pos, values:[per-pair]}`.
  3. **resolve**: `antiunify.py::resolve_slot`(G0 유래 식 생성→train 적용→대조→생존; §4-1) **그대로**. slot 이
     이미 `{var}` 형이라 입력 정리만.
- **compare 재사용 범위 (확정)**: ARCKG `comparison.compare` 직접 사용이 아니라 **얇은 program 전용 구조비교**
  (`ops_of_ast` + 검증된 `_align`)를 택한다(재귀 계약 불확실·행동보존 위험 회피). §2-2 의 COMM/DIFF 형태는 유지.
- **blob 계열 dispatch (§3.4)**: `antiunify_ast` 는 body 의 target.ref 로 계열을 판별 — 전부 `cellset` 이면
  blob 경로(`_align_blobs` 재사용·색 COMM 정렬·cellset slot), 아니면 pixel 경로. resolve 는 기존
  `resolve_slot`(cellset kind → `_resolve_cellset`) 를 **그대로 재사용**.

## 6. emit·consumer 이행 (행동보존)

- **emit 6곳** → 문자열 join 대신 AST 빌드:
  `program.py::_pixel_residual_program`·`::_global_recolor_program` · `coloring.py::_op_coloring` ·
  `antiunify.py::render_skeleton`(pixel+blob 분기, → AST 반환) · `compose.py` ·
  **`compress.py::_blob_program`(blob/cellset — §3.4)**.
- **consumer** → AST 소비:
  `antiunify.py::execute_solution`(→ `execute(ast)`) · `generalize`(AST 비교) · `verify` · `compose` · `resolve`.
- **안전장치**: `to_source(ast)` 유지 → 이행 중 아직 문자열 읽는 지점/기존 테스트·리포트 무손상.
- 신규 코드는 `arbor/reasoning/program_ast.py` (스키마·`execute`·`render_header`·`to_source`·compare/anti-unify)
  에 모으고, `antiunify.py`·`program.py` 는 이를 호출.

## 7. anti-unify 뷰 업그레이드 (§2-5)

- `debugger/reports/easy_antiunify_viz.py` 의 `easy_concepts` 재계산 제거 → **실제 저장 AST** 를 읽어 렌더.
- 3열 레이아웃(① 재료 ② 겹침 COMM/DIFF ③ TASK program) 유지. ②의 COMM/DIFF outline·③의 slot 을
  **실제 compare() 결과**로 그림 (손 계산 아님).
- 각 뷰 상단에 §4.2 자동 header(사용 accessor 시그니처 + input_grid) 표시 → "앞단이 ARCKG 와 연결"이
  눈에 보이게.
- coloring 전용 하드코딩 제거 → make_grid/color-map program 도 렌더 가능.
- `debugger/build.py` 의 companion 빌드 훅(`easy_antiunify_viz.build`) 은 그대로 사용.

## 8. 단계적 실행 (각 단계 = 커밋; 각 단계 종료 = step-count 골든 통과)

- **P0 — 골든 캡처** [비파괴]. easy_a 9 + survey 17 의 현재 step 수 캡처(`tests/golden_steps.json` 갱신/재사용).
- **P1 — AST 모듈 + `to_source`** [additive]. `program_ast.py` 스키마·`execute`·`to_source`(현행 문자열과
  바이트/실행 동일)·`render_header`. 아직 아무도 안 씀. 검증: `to_source(build(...))` == 현행 문자열.
- **P2 — emit 전환**. 5 emit 곳이 AST 를 만들고 저장. 소비처는 `to_source` shim 으로 계속 문자열 읽음.
  검증: **step-count 골든 일치**.
- **P3 — anti-unify 를 compare() 로**. 정규식 은퇴, 구조 비교+정렬+resolve. 검증: 골든 일치 + 산출 solution
  동치.
- **P4 — consumer 를 AST 로**. `execute_solution`·`generalize`·`verify`·`compose`·`resolve` 가 AST 직접 소비.
  `to_source` 는 복붙 렌더용으로만 잔존. 검증: 골든 일치.
- **P5 — anti-unify 뷰 업그레이드**. §7. 검증: 뷰가 실제 AST/compare 로 렌더, 크래시 없음.

## 9. Acceptance

- easy_a 9 + survey 17 step 수 = 골든 완전 일치 (P2~P4 매 단계).
- anti-unify 뷰가 **저장된 실제 AST + 실제 compare 결과**로 렌더 (재계산 코드 제거 확인).
- program/solution 이 WM 에 JSON AST 로 존재, 빈 슬롯 = `null`.
- `to_source(ast)` 로 복붙 실행 가능한 Python 재현.

## 10. 리스크

- **step-count 게이트 (최상)**: consumer 다수가 문자열 전제. `to_source` shim + 단계적 전환 + 매 커밋 골든으로 방어.
- **compare 재사용 계약**: ARCKG compare 가 일반 dict 를 어떻게 재귀하는지 불확실 → P3 첫 작업으로 확인,
  안 맞으면 얇은 program 전용 구조 compare 로 대체(§2-2 형태 유지).
- **과설계 (§1-1 / registry 경고)**: AST 문법은 현 program 이 실제 표현하는 것만. 새 op/식/변수 종류를
  "미리 풍부하게" 넣지 않는다. 필요가 생기면 §7 절차.
- **정렬 폭발**: step 수 큰 program 순열 전수 = 비쌈. 현 `_align` 의 임계(≤6) 규칙 유지.
