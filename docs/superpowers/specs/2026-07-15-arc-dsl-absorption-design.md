# arc-dsl 흡수 — GRID transform 어휘 + effect-구동 propose + arg search

- 브랜치: `seokki-dsl`
- 출처: michaelhodel/arc-dsl (`dsl.py` ~160함수, `arc_types.py`, `constants.py`)
- 승인: 사용자 발의(§5/§7). 새 DSL/operator 추가는 이 문서로 근거를 남긴다.
- 하네스 정합: §1-1(finder 금지)·§1-3(수식은 탐색)·§1-5(시도·기각 잔존)·§2-1(정보는 ARCKG)·§2-2(compare 근거)·§2-4/§2-5(다른 step·dashboard).

---

## 0. 문제 & 목표

현재 program synthesis(`arbor/reasoning/program.py`·`procedural_memory/dsl/helpers.py`)는 **`make_grid`+`coloring` 두 atom만 하드코딩**해 argument-expression tree만 탐색한다. `SPECS` 레지스트리는 `semantic_memory/build.py`의 온톨로지 덤프에만 쓰이고 **솔버가 런타임에 읽지 않는다**. 결과적으로 GRID 변환 어휘가 없어, `synthesize`가 contents를 항등/전역remap으로 못 풀면 그냥 `grid-descend`로 내려가 **막힌다**.

목표: arc-dsl의 **transform/select/relation 어휘를 `SPECS`에 흡수**하고, **compare 의 COMM/DIFF 가 effect 일치로 DSL 을 제안(propose)**, **arg 는 즉시결정 또는 탐색으로 채운 뒤 train 으로 검증**하는 경로를 만든다. DSL 은 **finder 가 아니라 search 가 열거하는 어휘**다.

## 0.5 확정된 설계 결정 (사용자 승인)

1. **통합 방식** = 레지스트리 등록 + search 어휘 확장 (per-primitive SOAR operator 폭증 회피).
2. **범위** = solving 어휘 우선: transformation + selection + relation. util 산술/컨테이너/고차조합자(GLUE)는 후속.
3. **ARCKG 중복** = `to_json()` WRAP (재구현 금지, §2-1).
4. **propose 드라이버** = **effect 일치** (`effect.py`의 `matches` 활성화). 하드매핑 아님.

---

## 1. 어휘 등록 — WRAP / VENDOR

기존 5 카테고리 `procedural_memory/dsl/{transformation,selection,relation,property}/__init__.py` 에 `@dsl(kind, sig_in, sig_out, effect=...)` 로 추가. 이름은 `SPECS[fn.__name__]` 유일 키. `sig_in/out` 은 `arc_types.py` 타입명을 ARBOR informal 문자열로 매핑. grid 표현은 ARBOR 내부 표현(list[list])으로 이식(arc-dsl 은 tuple[tuple]).

### 1-1. transformation (VENDOR ~38) — effect 선언 필수
`effect(verb, kind="grid")`. verb 어휘(신설, §3-1 표와 정합):
- 회전/전치: `rot90 rot180 rot270 dmirror cmirror` → `effect("transpose","grid")` / 회전은 `effect("rotate","grid")`
- 반사: `hmirror vmirror` → `effect("reflect","grid")`
- 재채색: `replace switch recolor` → `effect("recolor","grid")`
- 확대: `upscale hupscale vupscale` → `effect("upscale","grid")`
- 축소: `downscale compress trim` → `effect("downscale","grid")`
- 크롭/부분: `crop subgrid tophalf bottomhalf lefthalf righthalf` → `effect("crop","grid")`
- 이동: `move shift` → `effect("translate","grid")`
- 채움/그리기: `fill paint underfill underpaint cover` → `effect("fill","grid")`
- 결합: `hconcat vconcat` → `effect("concat","grid")`
- 구성: `canvas` → `effect("create","grid")`; `normalize toobject asobject cellwise` → 보조.

### 1-2. selection (WRAP 3 + VENDOR ~20)
- **WRAP**: `objects partition fgpartition` → ARCKG `grid.extract_objects()` 결과를 반환(재구현 금지).
- **VENDOR**: `box corners backdrop delta inbox outbox neighbors dneighbors ineighbors connect shoot frontiers colorfilter sizefilter ofcolor asindices toindices occurrences vfrontier hfrontier`.
- 이들은 arg 바인딩 소스 ②(selection)로 쓰인다.

### 1-3. relation (VENDOR 7)
`hmatching vmatching manhattan adjacent bordering position gravitate` — 기존 `compare`와 상보(공간관계). `read-only`(effect=None).

### 1-4. property WRAP (~18) — 재구현 금지
`mostcolor leastcolor palette numcolors color height width shape colorcount uppermost lowermost leftmost rightmost ulcorner urcorner llcorner lrcorner center centerofmass square portrait vline hline` → 전부 ARCKG 노드 `to_json()` 래퍼(기존 `property/color`, `shape_of` 패턴). 이름만 등록해 arg 표현식/조합자가 참조 가능하게 함. `hperiod vperiod index` 는 신규 VENDOR.

### 1-5. constants / types
- `constants.py`(방향벡터 `DOWN/RIGHT/UP/LEFT/…`, 스칼라) → `semantic_memory` 상수 테이블(arg 탐색 §3-3의 상수 어휘).
- `arc_types.py` → sig 타입명 정합 참조표(문서/온톨로지).

### 1-6. 등록 배선
- 기존 카테고리 파일에 추가하면 `dsl/__init__.py:19-23`·`semantic_memory/build.py:19-24`가 이미 import → 데코레이터 발화. 새 카테고리는 안 만듦.
- 검증: `python -c "import procedural_memory.dsl as d; print(len(d.SPECS))"` 로 등록수 확인. `python -m semantic_memory.build` 로 `ontology.json` 재생성.

---

## 2. 통합 지점 — synthesize 의 contents 공백

`_op_synthesize`(`procedural_memory/operators/synthesize.py`)는 이미 size/color/contents 가설을 `H1,H2…`(`^rule ^predict ^verdict survive|reject`)로 WM에 물질화한다. **contents 가 항등/전역remap 이 아닐 때**(현재 `grid-descend`로 종료되는 `else` 분기, synthesize.py:69-74)가 신규 transform search 진입점이다.

```
_grid_decide → contents 결정
  ├ 항등/remap        → 기존 경로(종결)
  └ 그 외(구조적 변화) → transform_search:
       required-effect ← derive(compare COMM/DIFF)          (§3-2)
       candidates      ← [d for d in SPECS.transformation if matches(required, d.effect)]   (§3-1)
       for prim in candidates:
           args, ok  ← resolve_args(prim, compare, train)   (§3-3: ①relation ②selection ③search)
           if not ok: WM += H{k}(rule=prim, verdict=reject, why="arg 미해결"); continue
           g' = prim(G0, *args); v = compare(g', G1)
           WM += H{k}(rule=prim, predict=g', verdict = survive if train_all_pass else reject)
       survivor → PAIR.program (program.json)
```

시도·기각 후보가 전부 `hypothesis` WME 로 남아 §1-5 를 만족한다.

---

## 3. 탐색 메커니즘

### 3-1. propose = effect 일치
`effect.py:26 matches(required, provided)` 활성화(현재 solving 경로 미사용). `required` = COMM/DIFF 에서 도출한 `{verb, kind}`(ANY="*" 허용). `provided` = 각 DSL 의 선언 effect. 일치하는 DSL 이 **후보 집합**(단일 아님)으로 propose 되어 operator-tie = 변환 탐색 프런티어가 된다. 새 DSL 을 등록하면 effect 범주로 자동 편입(하드매핑 수정 불필요).

### 3-2. required-effect 도출 (COMM/DIFF → verb) — finder-risk 관리 지점
**generic 규칙만**(문제특이 값 금지). 입력 = `compare(G0,G1)` 의 property COMM/DIFF + 파생 스칼라(H,W,h,w, 색집합, object수):

| COMM/DIFF 관찰(generic) | required verb |
|---|---|
| size DIFF & (H',W')=(W,H) | transpose\|rotate |
| size COMM & 팔레트 DIFF(집합보존, 매핑존재) | recolor |
| size DIFF & (H',W')=(kH,kW), k∈ℤ⁺ | upscale |
| size DIFF & (H',W')=(H/k,W/k) | downscale |
| size COMM & contents DIFF & 픽셀집합 보존 | reflect\|transpose\|translate |
| size DIFF & 부분영역 픽셀 COMM | crop |
| object수 COMM & 일부 obj position DIFF & shape COMM | translate |

여러 verb 가 동시 도출될 수 있음(예: 픽셀보존 → reflect/transpose/translate 모두) → 후보군이 넓어지고, 그 넓힘 자체가 정직한 탐색. **한 관찰이 한 DSL 로 곧장 가지 않는다.**

### 3-3. arg 결정 — 즉시(①②) 우선, 나머지 탐색(③)
DSL 의 각 formal arg 마다 바인딩 소스를 순서대로:

- **① from-relation (즉시)**: compare 가 값을 직접 주는 arg.
  - `replace(g,a,b)`: a,b = color-DIFF 의 변경 색쌍.
  - `canvas(v,dims)`·`crop(...,dims)`: dims = size-DIFF 의 (H',W').
  - `upscale(_,k)`: k = 크기비 H'/H.
- **② from-selection**: patch/object arg → selection DSL 로 선택. 어느 object 인지는 **relational profile(structure mapping §4-2)**: 각 grid 내 object 끼리 비교해 `longer_than/larger_than` 관계 프로파일이 pair 간 일치하는 것을 고른다(하드 rank 금지). 후보 obj 가 여럿이면 각각 시도.
  - `fill(g,v,patch)`·`move(g,obj,off)` 의 patch/obj.
- **③ from-search (표현식 탐색, §4-1)**: 남은 스칼라/벡터 arg. 어휘 = `{H,W,h,w, obj.property(uppermost/leftmost/height/…), constants(§1-5), +, -, *}`. 후보식 생성→G0 적용→G1 대조→기각/생존.
  - `move/shift` 의 offset=(Δr,Δc): `H-h, W-w, H-1, -uppermost(obj)…` 등 후보 생성·검증. 정답 `(H-h,W-w)` 를 손계산해 박지 않는다.
- **④ verify**: 바인딩 완성된 (prim, args) 를 **train 전체** G0 에 적용→G1 대조. 전부 통과해야 survive.

arg 해결 순서·시도식은 WM 에 남겨 대시보드에서 읽힌다.

### 3-4. SOAR 배선
- 새 operator `transform_search`: `production_rules/transform_search.json`(set_grid_color.json 템플릿 복제, 새 `order`), `procedural_memory/operators/transform_search.py`(`_op_transform_search`), `operators/__init__.py:17 OPERATOR_BODIES` 등록.
- propose condition: synthesize 가 남긴 contents-미결 신호 + compare COMM/DIFF WME. apply: body 가 §2 루프 수행.
- arg 표현식 탐색은 **기존 `helpers.py` argument-expression 합성기 재사용**(신 탐색기 신설 금지).

---

## 4. 대시보드 (§2-5)
`focus_dashboard.html` 생성부(focus_solver)에 **transform_search 패널** 추가:
- required-effect(도출된 verb 집합)
- propose 된 후보 DSL 목록
- 각 후보의 arg 바인딩(소스 ①/②/③·시도식) 과 verdict(survive/reject·이유)
- survivor → PAIR.program
화면에 안 보이면 미완.

## 5. 테스트 & 성공 판정
- 사다리: `easy000a → made000b → 08ed6ac7 → made000a` (`python -m debugger.build`).
- 수직 슬라이스로 arg 파이프라인 전부 증명: **param-free**(rot/mirror, arg 없음) · **immediate-arg**(replace, ①) · **searched-arg**(move/shift offset, ③).
- 성공 = 문제마다 **후보 수·arg 탐색량·step 수·하강 깊이가 서로 다르고**, 시도·기각 후보가 WM+대시보드에 잔존, survivor 가 `program.json` 에 기록. 모든 문제가 같은 step 이면 탐색이 함수에 숨은 것 → 실패.

## 6. 스코프 경계 (YAGNI — 이번 스펙 밖)
- Tier-1 전면화(모든 파라미터 변환의 selection-arg 자동화), depth-2+ 변환 체이닝(GLUE 조합자 `compose/chain/fork`), util 산술/컨테이너 전량 등록 → **후속 스펙**.
- property WRAP 는 이름 등록 + 최소 래퍼까지만(전 property 완비는 후속).

## 7. 리스크 & 완화
- **R1 finder-화(§1-1)**: required-effect 도출(§3-2)이 문제특이 값이나 1:1 하드매핑이면 finder. → generic 관찰만, 한 관찰이 후보 *집합*을 내도록, arg 는 탐색으로.
- **R2 ARCKG 중복(§2-1)**: property/selection 일부를 재구현하면 ARCKG 와 경쟁. → WRAP 강제(§1-2·1-4).
- **R3 탐색 은닉(§1-5)**: arg 결정을 함수로 즉답하면 탐색이 사라짐. → 시도식·기각을 WM/대시보드에 물질화, 성공판정을 step 다양성으로.
- **R4 effect 어휘 빈약**: verb 가 너무 coarse 하면 후보군이 과대. → §3-1 verb 표를 최소 discriminating 하게, 필요시 §5/§7 로 확장.

## 8. 산출물 체크리스트
- [ ] transform/select/relation `@dsl` 등록 (effect 선언 포함) · property WRAP
- [ ] `effect.matches` 활성화 + required-effect 도출기 (§3-2)
- [ ] `transform_search` operator + propose/apply json + OPERATOR_BODIES 배선
- [ ] arg resolver (①relation ②selection ③search) — helpers 재사용
- [ ] synthesize contents-공백 → transform_search 진입 연결
- [ ] focus_dashboard transform_search 패널
- [ ] constants/types → semantic_memory
- [ ] 테스트 사다리 4문제 step 다양성 확인 + program.json 잔존
