# TASK.solution 표현식 시각화 — 설계 문서

> 작성 2026-07-20 · 상태: 설계 승인 대기 · 다음 단계: writing-plans

## 1. 목표 (Goal)

program report 의 **TASK.solution**(그리고 Step B 의 anti-unification 영역)을, 지금의 불투명한
`cellset` 대신 **직관적 symbol·함수 조합의 표현식**으로 시각화한다. anti-unification 이 DIFF 부분을
변수화하고 그 변수를 함수식으로 일반화하는 **과정 전체**가 겉으로 드러나야 한다.

**최종 지향**: 이 표현식이 cellset 을 대체하는 generalize 의 매개체가 된다(cellset 은퇴).
**이번 범위**: **시각화 먼저** — 솔버가 이미 가진 survivor/슬롯/resolved 데이터로 **리포트가 표현식을
재구성**한다. 솔버의 탐색 로직은 바꾸지 않는다(§P: 찾는 과정은 동작부 소관). 표현 문법을 먼저 검증한
뒤, 솔버 generalize 가 이 표현식을 실제로 산출하도록 교체하는 것은 **후속 작업**(비목표, §9).

## 2. 배경 — 현재 solution 구조 (실측)

`run_solve` 후 WM 에는 TASK.solution 관련으로 다음이 있다 (예: move000a):

- `T.property ^solution` = grid body AST:
  `set_grid_size = {expr: size(input_grid)}`, `set_grid_color = {expr: color(input_grid)}`,
  `set_grid_contents = {program: [coloring(target={ref:cellset, cells:{var:"?c.cells0"}}, color={const:0}),
   coloring(target={ref:cellset, cells:{var:"?c.cells1"}}, color={var:"?c.color1"})]}`
- `T.property ^slot` = DIFF 변수 원본:
  `?c.cells0[cellset]=DIFF[[26],[48]]` · `?c.cells1[cellset]=DIFF[[35],[57]]` · `?c.color1[color]=DIFF[7,4]`
- `T.property ^resolved` = 각 슬롯의 채택 표현식:
  `?c.cells0=move[r0+0,c0+0]@shape#0` · `?c.cells1=move[r0+1,c0+1]@shape#0` · `?c.color1=color@shape#0`
- `T.Pk.property ^program` = pair k 의 **픽셀** program · `^grouping` = **blob(객체)** program

즉 survivor 이름이 이미 표현식꼴이고 선택자는 단일 속성(`shape#0`)이다. COMM 은 forward expr
(`color(input_grid)`)로, DIFF 는 `?c.` 슬롯 + resolved 표현식으로 이미 나뉘어 있다. 리포트는 이 데이터를
사람이 읽는 함수식으로 **재표기**하면 된다.

## 3. 표현 문법 (display DSL — §7 승인됨)

### 3-1. 심볼·함수 어휘
- 원자: `input_grid`, 정수 리터럴, 좌표쌍 `(r, c)`
- **속성 = 함수** (속성 접근자 `o.x` 폐기 — 사용자): `color(o)` · `area(o)` · `shape(o)` ·
  `top_left(o)` · `bottom_right(o)` · `size(o)` · `coordinate(o)`
  - grid 인자도 허용: `color(input_grid)` · `size(input_grid)` · `bottom_right(input_grid)`
  - 인자 타입이 안 맞으면 못 받는다(타입 체크 — 예: `area(input_grid)` 불가)
- 선택: **`select(type, 조건)`** — type 우선 인자. 예: `select(object, <조건>)`
- 조건 연산: `==` · `!=` · `and` · `not`
- 좌표 산술: 좌표집합 `coordinate(o)` 에 점 `(a,b)` 를 **broadcast** 더하기/빼기.
  `coordinate(o) + (a,b)` · `coordinate(o) - bottom_right(o) + (v,w)` 등.

### 3-2. 선택자 → 조건 (충실 렌더, 채택된 선택자 그대로)
| 솔버 선택자 | 조건 표현 |
|---|---|
| `color=k` | `color(o) == k` |
| `size=z` | `area(o) == z` |
| `shape#i` | `shape(o) == shapei` (별도 `shapei = <2d array>` 정의줄) |
| `bounded` | `color(o) != 0` |
| `row=r` / `col=c` | (move 60문제 미사용 — 이번 범위 밖) |

- **`bounded → color(o) != 0`**: bounded 태스크는 Spelke 객체가 (큰 색0 영역 + 비-0 figure) 2개이고,
  figure 의 색·크기·모양이 pair 마다 달라 속성값으로 못 집는다. 유일하게 일관된 구분은 "색0 이 아님".
  이는 [[no-arbitrary-filters]] 의 '색0=배경 금지'를 **표현 계층에 한해 완화**한 것(사용자 승인 2026-07-20,
  사용자 원 예시에도 `color != 0` 있었음). 솔버 내부는 여전히 prior-free boundedness 를 쓴다 —
  리포트 표기만 `color(o) != 0` 로 한다.

### 3-3. shape 변수화
`shape#i` 는 `shapei = [[1, -1], [1, 1]]` (2d array; 1=채움/-1=빈칸, ARCKG object `shape` property)로
따로 정의하고, 조건에서 `shape(o) == shapei` 로 참조한다. (S0 은 state 와 혼동 → `shape0` 표기.)
shape 2d array 는 mover 객체의 ARCKG `shape` property 에서 얻는다(리포트가 mover 를 resolved cellset
DIFF 값으로 역추적 → 그 객체의 shape).

### 3-4. 이동(move) = 벡터 산술 (translate/place/count 폐기)
resolved `move[ROW,COL]@sel` 을 축별 앵커에 따라:

| 앵커(축별) | 표현 |
|---|---|
| 제자리 `r0+0` (지우기) | `coordinate(obj)` |
| 상대 `r0+Δ` | `coordinate(obj) + (Δr, Δc)` |
| 절대 `=v` | `coordinate(obj) - top_left(obj) + (r, c)` |
| 끝 `0` | `coordinate(obj) - top_left(obj) + (0, c)` |
| 코너 `H-h`/`W-w` | `coordinate(obj) - bottom_right(obj) + bottom_right(input_grid)` |
| BR `BR=v` | `coordinate(obj) - bottom_right(obj) + (v, w)` |

- 두 축이 **같은 모델**이면 위 깔끔한 형태로 렌더(대부분).
- 두 축이 **다른 모델**(예: `move[=1,BR=2]`)이면 축별로 anchor 점과 target 을 분리:
  `coordinate(obj) - (top_left(obj).row 또는 bottom_right(obj).row, …col) + (target_row, target_col)`.
  (60문제 중 혼합은 소수 — as/be류. 축별 규칙으로 일반 처리.)

### 3-5. 객체 바인딩
한 mover 를 가리키는 슬롯들은 **같은 선택자**(솔버 §선택자-일관)이므로
`obj0 = select(object, <조건>)` 로 한 번 묶고 `coordinate(obj0)`·`color(obj0)`·`bottom_right(obj0)` 로 재사용.

### 3-6. 금지 준수
- **count 금지**: 어휘에 없음.
- **output_grid symbol 금지**: 모든 식은 `input_grid` 의 객체·속성과 그 좌표 변환으로만 표현한다.
  이동 결과도 input 객체 + 변환으로 나타내고 output grid 객체는 절대 참조하지 않는다(P5:
  변수 출처는 G0/input, test 엔 G1 없음).

## 4. 변수화 규칙 (Step C · TASK.solution)

- 한 위치의 per-pair 값이 **다르면(DIFF)** → 그 줄 **바로 위**에 `?varN = <expr>` 정의를 놓고, 본문 줄은
  `?varN` 을 쓴다. **같으면(COMM)** → 리터럴 값을 인라인.
- 판정은 기존 `_compare_asts`(pair0 vs pair1 program 의 위치별 COMM/DIFF)를 재사용.
- **주석 없음**(사용자). 변수 정의로 길게 늘어진 코드가 정상.
- 변수 종류: `?varN`(값 슬롯), `objN`(select 결과), `shapeN`(2d array). 정의는 사용 전에 나온다.

## 5. 워크드 예시

### move000a (shape#0 · 상대 Δ)
```
shape0 = [[1, -1], [1, 1]]
obj0   = select(object, shape(o) == shape0)
set_grid_size  = (8, 8)
?var1 = color(input_grid)
set_grid_color = ?var1
?var2 = coordinate(obj0)
coloring(?var2, 0)
?var3 = coordinate(obj0) + (+1, +1)
?var4 = color(obj0)
coloring(?var3, ?var4)
```

### move000o (bounded→color!=0 · BR 앵커)
```
obj0 = select(object, color(o) != 0)
set_grid_size  = (6, 9)
?var1 = color(input_grid)
set_grid_color = ?var1
?var2 = coordinate(obj0)
coloring(?var2, 0)
?var3 = coordinate(obj0) - bottom_right(obj0) + (2, 2)
?var4 = color(obj0)
coloring(?var3, ?var4)
```

### move000q (bounded→color!=0 · 격자 코너)
```
obj0 = select(object, color(o) != 0)
...
?var3 = coordinate(obj0) - bottom_right(obj0) + bottom_right(input_grid)
...
```

## 6. compress 단계 시각화 (Step B, 가로 확장)

- **모든** pair program 을 **픽셀 단계부터 균일하게** 보인다(coord+color raw value = 픽셀 1:1).
- 진행: `픽셀 program (coloring([r,c], col) ×N)` → `4-인접 동색 그룹핑` → `blob/객체 program
  (coloring(객체좌표, col) ×M)` → 객체 표현식(§3).
- Step B(anti-unification)의 pair 비교 이미지 **오른쪽에** 이 단계들을 가로로 이어붙인다.
- 데이터: `P{k}.program`(픽셀) + `P{k}.grouping`(객체). 픽셀→객체 그룹핑은 compress 연산자의
  region-growing(4-인접·동색)을 그대로 표시.

## 7. 레이아웃

- Step C(solution): 세로(변수 정의 여러 줄) + 가로(함수 조합) 확장 허용.
- Step B: 가로(compress 단계) 확장 허용.
- 컨테이너는 가로 스크롤(기존 `.stepsrow`/`.scroll` 관례) — 본문 가로 스크롤 금지, 내부 컨테이너만.

## 8. 데이터 소스 (구현 근거)

| 필요 정보 | 출처 |
|---|---|
| solution 골격(set_grid_*, coloring, cellset var) | `T.property ^solution` AST |
| DIFF/COMM 위치 판정 | `_compare_asts(P0, P1)` (기존) + `^slot` DIFF 값 |
| 슬롯 채택 표현식(move/color@sel) | `T.property ^resolved` (기존 `_collect` 가 이미 수집) |
| 선택자→조건, mover 객체, shape 2d array | resolved 의 `@sel` 파싱 + mover 객체 역추적(cellset DIFF→객체→ARCKG shape) |
| 픽셀/객체 program(compress) | `T.Pk.property ^program` / `^grouping` |

## 9. 비목표 / 후속 (Non-goals)

- **솔버 generalize 를 이 표현식으로 실제 교체**(cellset 매개체 은퇴)는 이번 범위 밖. 이번엔 리포트 재구성으로
  표현 문법을 검증한다. 검증 후 별도 설계·계획으로 솔버 교체.
- 선택자 **조합(conjunctive predicate) 탐색**(`color!=0 and area==z`)은 솔버 작업 — 이번엔 채택된 단일
  선택자를 충실 렌더(bounded 만 `color!=0` 로 표기).
- row=/col= 선택자 렌더(move 미사용).

## 10. 제약·리스크

- 혼합 앵커(축별 다른 모델) 렌더가 다소 장황 — 축별 규칙으로 처리, 소수 태스크.
- shape 2d array 역추적이 mover 식별에 의존 — resolved cellset DIFF 값으로 pair0 객체를 특정.
- `color(o) != 0` 표기는 색0=배경 완화 — **표현 계층 한정**, 솔버 내부는 boundedness 유지(문서에 근거 명시).
- 러너: solution 은 러너가 실행하지 않으므로(PAIR program 만 실행) 표현식 자유. PAIR program 렌더는
  기존 러너-안전 형태 유지(slot_exprs=None).

## 11. 성공 판정

- move 60문제의 TASK.solution 이 §3 문법 표현식으로 렌더되고 `cellset=?c.` raw 표기가 사라진다.
- 각 태스크가 자기 앵커 모델(상대/절대/끝/코너/BR)·선택자(color/size/shape/color!=0)를 정확히 표기.
- Step B 에 픽셀→객체 compress 단계가 가로로 표시된다.
- 기존 회귀 0(pytest·move 60/60·PAIR program 러너 parity 불변).
