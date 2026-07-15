# easy a–h program 뷰어 표현 통일 + 코드 실행기 (설계)

> **정본 스펙.** easy a–h program 뷰어에서 a·b(grid 3-property)와 c–h(pixel coloring)가 서로 다른
> "느낌"으로 보이는 문제를 해소한다. 단 **표현 계열(grid vs coloring)은 정직하게 유지**하고 — c–h 를
> `set_grid_contents(const 출력)` 로 굽는 것은 §1-5/§6 위반이므로 금지 — **표기·헤더·시각화 레이어만**
> 하나의 언어로 통일한다. 부수로, program body 가 참조하는 ARCKG accessor 를 *실제로 실행 가능*하게
> 만들고(`pixels_of` 실구현, `height`/`width` 추가), 무거운 ARCKG-build 보일러플레이트를 디스플레이에
> 넣는 대신 **순수 프런트엔드 코드 실행기**(동적 테스터)로 실행/검증을 분리한다.
>
> 근거: ARBOR_HARNESS.md §0.5(program=절차적 아티팩트) · §1-5/§6(정답 const-굽기 금지 — 표현 계열 유지) ·
> §2-1(정보는 ARCKG property 에서 — `pixels_of`/`height`/`width`) · §2-5(구조 변경은 대시보드에 반영) ·
> §1-1/§5(새 DSL 은 감사 후 승인 — 본 스펙이 그 절차) · §1-3/§4-1(H/W 원자를 조합·탐색). 선행:
> [[program-ast]]·[[grid-property-program]] 스펙.

## 1. 배경 — 무엇이 "다르게" 보이나 (실측)

`python -m debugger.reports.program_viewer` → `program_report_all.html`. 각 example pair 를 3-뷰(① text ·
② AST 트리 · ③ 시각화)로 렌더. 두 계열이 갈린다:

- **a·b = 3-property grid program** (`set_grid_size ∘ set_grid_color ∘ set_grid_contents`). ① text 예(a):
  ```
  G0 = input_grid
  G1 = set_grid_size(keep) ∘ set_grid_color([0,2]) ∘ set_grid_contents([[…출력 grid const…]])
  output_grid = G1
  ```
- **c–h = pixel coloring program**. ① text 예(c):
  ```
  in_px = pixels_of(input_grid)
  P0 = in_px[7]
  tfg0 = input_grid
  tfg1 = apply_DSL(tfg0, coloring, P0.coord, 0)
  output_grid = tfg2
  ```

사용자가 지적한 4개 차이 + 후속 발견:
1. **`G0` vs `tfg0`** — 계열별 to_source 프레이밍 차이.
2. **`set_grid_*` 유무** — 계열 자체가 다름(정직한 표현 차이. **유지**).
3. **`in_px[15]` 가 ARCKG 안 쓰는 듯** — 실은 PIXEL 접근 표기지만, **`pixels_of` 는 미구현 stub**
   ([selection/__init__.py:15](../../../procedural_memory/dsl/selection/__init__.py#L15) "pixel 은 pixels_of
   도입 시 추가"; `_LEVEL_CHILDREN` 에 pixel 없음). `.coord` accessor 도 없음. → **표기가 지금도 실행 불가**.
4. **다른 AST 구조·시각화** — AST(사설 typed-arg dict)는 계열별 body 가 실제로 달라 정직. 시각화는 통일 여지.

추가 (a 를 보며): `set_grid_size(keep)` 의 `keep`, `set_grid_contents` ③ 시각화 라벨 `grid[6×6]` 은 **불투명
토큰** — ARCKG 근거·실값이 안 보임. ① text 의 wrapper(header)는 DSL 시그니처를 *주석*으로만 나열해
**ARCKG 를 실제로 공급하지 않음** → wrapper+body 복붙 시 실행 불가.

**불변 계약(건드리면 안 됨):** `program_ast.to_source`/`as_source` 의 pixel 표기(`tfg`/`in_px`/`P{i}`/
`apply_DSL`)는 **표시용이 아니라 파싱 계약** — `compress.py:40 parse_program(as_source(code))`,
`generalize.py:34`, `coloring.py:34` 가 이 flat 텍스트를 되파싱. `antiunify.py:9,513` 에 포맷 명시. →
`to_source` 는 **불변**으로 두고, 통일은 뷰어 표시 레이어 + 실 accessor 구현으로 한다.

## 2. 목표 / 비목표

**목표**
- easy a–h program 뷰어의 ① text·③ 시각화가 **두 계열 공통 언어**로 보인다(G0/G1/output_grid 프레임,
  실 DSL 이름, 실값, 끝점 썸네일, color 스와치 — 전 프로그램 일관).
- program body 가 참조하는 accessor 가 **실제 실행 가능**: `pixels_of(grid)` 실구현, `height(grid)`/
  `width(grid)` 추가(§4-1 H/W 원자). `keep`→`size(input_grid)`, `grid[6×6]`→실 2D 배열.
- 무거운 ARCKG-build 는 디스플레이에 넣지 않고 **순수 프런트엔드 코드 실행기**가 공통 환경으로 제공 —
  body 를 붙여넣어 실행/검증(✓/✗).

**비목표**
- c–h 를 grid 3-property(`set_grid_contents(const)`)로 재표현 — **금지**(§1-5/§6 정답 const-굽기).
- `to_source`/`as_source`/parse 계약 변경 — **불변**.
- solver 파이프라인(hypothesize/synthesize/generalize)의 program *생성* 로직 변경 — 이번은 accessor 실구현 +
  뷰어 + 러너만. program 이 무엇을 담는지는 그대로.
- object h/w accessor(`height_of`/`width_of`), 임의 Python 전체 실행 — forward(필요 시 별건 §5).

## 3. Phase ② — 실 ARCKG accessor 완성

> 표기를 *참*으로 만든다. §1-1: 새 DSL 은 감사 후 승인 — §5 절차를 본 스펙이 이행(중복·이름·operator
> 감사 완료: `color_of`/`contents_of` 는 충돌로 제외, `pixels_of`/`height`/`width` 만 추가).

### 3-1. `height(grid)` · `width(grid)` — GRID-level 스칼라 (property DSL)
- 위치: [procedural_memory/dsl/property/__init__.py](../../../procedural_memory/dsl/property/__init__.py)
  GRID-level 블록(`size`/`color`/`contents` 옆).
- 구현 = **`size` 의 투영**(새 ARCKG 데이터 아님, §2-1 유지):
  ```python
  @dsl("property", ["grid"], "int")
  def height(grid): return size(grid)["height"]
  @dsl("property", ["grid"], "int")
  def width(grid):  return size(grid)["width"]
  ```
- 명명: grid-layer 맨이름 규약(`size`/`color`/`contents`) 준수. **`color_of`/`contents_of` 추가 안 함** —
  `color_of` 는 이미 OBJECT용([:70](../../../procedural_memory/dsl/property/__init__.py#L70)) → registry
  함수명 키 충돌; grid 는 `color`/`contents` 가 담당.

### 3-2. `pixels_of(grid)` — PIXEL selection 배선
- PIXEL 노드는 이미 ARCKG 에 존재([arbor/perception/arckg/pixel.py](../../../arbor/perception/arckg/pixel.py);
  `pixel_color`/`pixel_coordinate` property 가 `px.to_json()` 를 읽음). 미배선인 것은 *selection accessor* 뿐.
- 위치: [procedural_memory/dsl/util/__init__.py](../../../procedural_memory/dsl/util/__init__.py) 에 `pixels_of`
  추가(형제 `objects_of` 와 동형) + [selection/__init__.py:15](../../../procedural_memory/dsl/selection/__init__.py#L15)
  `_LEVEL_CHILDREN` 에 `"pixel": pixels_of` 배선.
- 반환: grid 아래 PIXEL 노드 리스트, **인덱스 = 행우선 셀 순서**(솔버 전역 규약 `idx = r*W + c` 와 일치 —
  `program_ast.execute` 의 `r,c = ix//W, ix%W`, `compress.py:22`). 즉 `pixels_of(g)[i]` 의 좌표 = `(i//W, i%W)`.
- 좌표 접근: pixel 노드의 좌표를 body 표기 `pixels_of(g)[i].coord` 로 쓰려면 노드가 `.coord`(=`(r,c)` 튜플)
  를 노출하거나, 러너/실행이 `pixel_coordinate(px)`→`(row_index,col_index)` 로 얻는다. **정합 기준:
  `coloring` 이 받는 position = `(row,col)` 튜플**(실호출 `coloring(grid,(r,c),col)`)이므로 `.coord` 는
  `(r,c)` 튜플을 내야 한다. (구현 시 pixel 노드에 `.coord` 프로퍼티가 없으면 얇게 추가 — 기존 to_json
  좌표의 튜플 투영, 새 데이터 아님.)

### 3-3. 계약 불변 확인
- `to_source`/`as_source`/`parse_program`/기존 테스트(`test_program_ast.py`, `test_grid_program.py`) **불변**.
- 신규는 순수 additive(registry 새 엔트리 2~3개 + selection 1줄). 회귀 없음 — 3-6 테스트로 게이트.

## 4. Phase ① — 뷰어 디스플레이 통일 (program_viewer.py)

> `to_source` 는 불변이므로 통일은 **뷰어 로컬 렌더**로 한다. 같은 AST 를 일관 프레이밍만 하므로 정직
> (표현 계열은 그대로 드러남).

### 4-1. `display_source(ast)` — ① text (뷰어 로컬)
- 두 계열 공통 프레임. **깨끗한 body 만**(ARCKG-build wrapper 제외 — 러너가 공급). 짧은 note:
  "공통 ARCKG 환경은 코드 실행기가 로드".
- **grid** body:
  ```python
  g = input_grid
  g = set_grid_size(g, size(input_grid))          # keep → ARCKG GRID.size (실행형)
  g = set_grid_color(g, [0, 2])                    # 출력끼리 고정 상수 color-set
  g = set_grid_contents(g, [[0,0,0,0,0,0], …, [0,0,0,0,0,2]])   # 상수 2D 배열 전체(grid[6×6] 폐기)
  output_grid = g
  ```
  - `keep("size")` → `size(input_grid)`. `keep("color"/"contents")` → 각각 `color(input_grid)`/
    `contents(input_grid)`. `expr("H1=…")` 류 size 식 → `height`/`width` 어휘로 번역(예 `{"height":
    height(input_grid), "width": width(input_grid)+3}`). `const` → 실값 그대로.
- **pixel** body:
  ```python
  g = input_grid
  g = coloring(g, pixels_of(input_grid)[7].coord, 0)
  g = coloring(g, pixels_of(input_grid)[35].coord, 2)
  output_grid = g
  ```
  - `∘`/`keep`/`tfg`/`grid[6×6]`/`in_px[i]`(별칭) 폐기. 순차 `g = …` 대입 = 실 DSL 2-arg 시그니처와 일치
    (`set_grid_size(grid, size)`, `coloring(grid, position, color)`) → 러너에서 그대로 실행.
- canonical `to_source` 는 **접어서(collapsible) 참조용**으로 함께 노출(숨기지 않음 — 정직).

### 4-2. `_viz(ast, ex)` — ③ 단일 box-flow (전 프로그램 공통)
- 하나의 골격: `[G0 = input_grid] [입력 썸네일]` → 스텝 박스들 → `[G1 = output_grid] [출력 썸네일]`.
  현 `_grid_viz`(끝점 인라인 썸네일)와 `_pixel_viz`(EV.flow, 썸네일 하단 뭉치기)를 **끝점 인라인**으로 통일.
- 스텝 박스: grid = `set_grid_size`/`set_grid_color`/`set_grid_contents` + leaf 라벨(**`size(input_grid)`**,
  color 는 **스와치 유지**, contents 는 **실 2D 배열**(grid[6×6] 폐기)); pixel = `coloring` +
  `pixels_of(input_grid)[i].coord` + 색 스와치.
- 같은 박스 클래스(.op/.tv/.cv)·세로 커넥터·썸네일·스와치를 **모든 프로그램**에 일관 적용.

### 4-3. ② AST 트리 — 유지
- 사설 typed-arg nested dict(`input`/`body`/`output`/`slots`)를 그대로 재귀 렌더. grid/coloring 의 dict
  구조 차이는 *정직한 표현 차이*라 유지(감추면 §1-5 취지 위반). Python `ast` 아님 — 문서 note 추가.

### 4-4. TASK.solution 블록
- `_pair_block` 재사용 → display_source·_viz 자동 적용. skeleton 도 같은 통일 뷰.

## 5. Phase ③ — 코드 실행기 (순수 프런트엔드 동적 테스터)

> 사용자 결정: 서버 없이 프런트엔드에서 처리. frozen DSL atom 이 소수·trivial 이라 JS 미러 인터프리터로
> 충분. 정직성은 **빌드타임 parity** 로 보장.

### 5-1. UI (HTML 패널; program 뷰어 페이지 내 또는 별 페이지)
- textarea(선택 프로그램 body 프리필) · Run 버튼 · input 격자 선택(그 태스크의 train/test 입력) · 출력 격자
  렌더 · **expected 대조 ✓/✗**.
- 공통 preamble/ARCKG-atom 은 러너에 **한 번** — 디스플레이 body 는 안 길어짐.

### 5-2. JS atom 인터프리터 (frozen atom 미러)
- 미러 대상(전부 trivial): `make_grid(size)`, `coloring(grid,(r,c),color)`, `set_grid_size/color/contents`,
  `size/height/width/color/contents(grid)`, `pixels_of(grid)[i].coord = (i//W, i%W)`, `divmod`.
- 파서: display_source 가 내는 **body 문법**(`g = fn(g, args…)` 순차 대입)만 해석. 임의 Python 전체 아님 —
  미지원 구문은 **"해석 불가"로 정직하게 표시**(조용히 틀린 값 내지 않음).

### 5-3. 정직성 가드 — 빌드타임 parity
- 빌드(Python)가 각 프로그램을 **실제** `program_ast.execute(ast, input)` 로 실행한 결과를 HTML 에
  `expected` 로 굽는다. 러너는 JS 로 계산한 결과를 로드 즉시 expected 와 대조 → **✓/✗ 배지**. JS↔Python
  드리프트가 화면에 바로 드러남.
- 추가: pytest parity 1개 — 대표 프로그램들에 대해 (baked expected) == `execute(ast,input)` 확인(빌드 산물
  무결성). JS 자체 실행은 브라우저 몫이라 파이썬 테스트는 expected 무결성까지 담당.

## 6. 파일별 변경 요약

| 파일 | 변경 |
|---|---|
| `procedural_memory/dsl/property/__init__.py` | `height(grid)`·`width(grid)` 추가(§3-1) |
| `procedural_memory/dsl/util/__init__.py` | `pixels_of(grid)` 추가(§3-2) |
| `procedural_memory/dsl/selection/__init__.py` | `_LEVEL_CHILDREN["pixel"]=pixels_of`(§3-2) |
| `arbor/perception/arckg/pixel.py` | 필요 시 `.coord`(=(r,c) 튜플) 얇은 프로퍼티(§3-2) |
| `debugger/reports/program_viewer.py` | `display_source`·단일 `_viz`·leaf 정직 렌더·러너 패널·parity 베이킹(§4·§5) |
| `debugger/reports/easy_antiunify_viz.py` | (선택) 공유 헬퍼 재사용 시 소폭 — 이번 범위 밖 기본 |
| `tests/` | accessor 테스트(§3) + parity 테스트(§5-3) |

## 7. 검증 (하네스 §2-5 — 화면에 드러나야 완료)

- Phase ②: `python -c` 로 `height/width/pixels_of` 실호출 → 값 확인. 기존 테스트 전부 green(계약 불변).
- Phase ①: `python -m debugger.reports.program_viewer` 재생성 → a–h 전 탭이 **동일 프레임**(G0/G1, 끝점
  썸네일, 스와치)로 보이고 c–h 의 `coloring`·`pixels_of[i].coord` 가 살아있음(계열 유지). `keep`/`grid[6×6]`/
  `∘`/`tfg` 부재 확인.
- Phase ③: 러너에서 a·c body 를 Run → 출력 격자가 그 pair 출력과 일치(✓). 로드 즉시 parity 배지 ✓.
- 정직성 자문: c–h 가 여전히 coloring 계열인가(§1-5 const-굽기 안 함)? body 가 실 DSL 로 실행되나?
  accessor 가 ARCKG property 투영인가(새 데이터 발명 아님)?

## 8. 리스크 / 미해결

- `pixels_of`·`.coord` 정합: pixel 노드 좌표 표현이 `coloring` position `(r,c)` 튜플과 정확히 맞아야 함 —
  구현 중 실제 실행으로 검증(§7 Phase②/③).
- JS 미러 드리프트: parity 배지로 가시화하되, atom 추가/변경 시 JS 미러도 갱신해야 함(문서 note).
- 러너 문법 범위: display_source body 문법만. 사용자가 임의 Python 붙이면 "해석 불가" — 명시.
