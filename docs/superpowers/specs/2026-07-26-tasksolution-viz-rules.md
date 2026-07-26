# pair.program / TASK.solution 시각화 — 고정 규칙 (2026-07-26 확정)

> program_report ③ 시각화가 pair.program·TASK.solution 을 그릴 때 **반드시** 따르는 규칙. 사용자 승인
> (2026-07-26 반복 검토). 렌더러(`debugger/reports/solution_expr.py`)·리포트(`program_report.py`)가 이 규칙을
> 구현한다. 새 표현을 추가하거나 렌더를 고칠 때 이 규칙을 어기지 않는다.

## 1. 데이터플로우 박스 그래프 (값 아래 · 함수 위 · 선은 가로·세로만)
- 정의 `name = f(args…)` 는 **값 노드(name)를 아래**, **함수 노드(f)를 그 위**(세로 v 선)에 두고, **args 는
  함수와 같은 줄**(가로 h 선)에 둔다. 대각선 금지 — 모든 선은 h(가로) 또는 v(세로).
- 노드 kind: `var`(보라, ?p·obj0·이름) · `fn`(파랑, 실존 함수) · `lit`(크림, 값) · `end`(회색, result·grid).

## 2. placeholder 는 `?p` 뿐 · 그 외는 전부 실존 심볼
- 코드에 등장하는 심볼은 **오직 셋 중 하나**: (a) placeholder **`?p`** (b) **실존 함수명**(DSL registry `SPECS`
  의 것: size_of·color_of·objects_of·pixels_of·select·area_of·row_of·col_of·left_top_of·right_bottom_of·coloring
  ·coordinate_of·set_grid_* 등) (c) **값**(0·6·8 …) 또는 **기존 symbol**(input_grid·obj0·r·c·r0…).
- `?size`·`?color` 같은 **설명형 placeholder 이름 금지**. placeholder 는 `?p{n}` 만.
- **ARCKG 레벨 약자**: task=**t** · pair=**p** · grid=**g** · object=**o** · **pixel=x**. 픽셀 변수는 `x`
  (`x = pixels_of(obj0)`, `r = row_of(x)`, `c = col_of(x)`). `p` 는 pair 이므로 픽셀에 쓰지 않는다.

## 3. 함수조합 arg 는 `?p` 로 층을 올린다
- 어떤 함수의 arg 가 **또 함수 조합**(kids 있는 call/op)이면, 그 arg 를 **`?p` 로 대체해 윗줄**에 별도로
  정의한다. 한 함수의 줄에는 **그 함수의 arg(개수만큼)** 박스만 온다.
  - 예: `r0 = row_of(left_top_of(obj0))` → `left_top_of(obj0)` 는 조합이므로 `?p{k}` 로 승격 →
    `row_of ── ?p{k}` (arg 1개), `?p{k} = left_top_of ── obj0` (윗줄).
  - 예: `obj0 = select(objects_of(input_grid), area_of == 6)` → `select ── ?p{i} ── ?p{j}` (arg 2개),
    `?p{i}=objects_of(input_grid)` · `?p{j}=area_of==6` 는 각각 윗줄.
- 잎(leaf: 값·기존 symbol)은 승격하지 않고 그 줄에 그대로 둔다.

## 4. 튜플 `( , )` 는 infix
- 좌표 튜플 `(F_row, F_col)` 는 **infix**로: `?p ── ( , ) ── ?p` (양옆 operand, `( , )` 가운데), 값을
  **아래로**. 좌표류 leaf-튜플(예 `(2,3)`)은 단일 박스로 둔다(simple_tuple).

## 5. `?p` 전역 유일 번호
- placeholder 번호 `?p{n}` 은 **한 solution 전체에서 전역 유일**·순차. 골격이 `?p1~?p4` 를 쓰면, `?p3`
  내부 조합은 `?p5, ?p6…` 로 이어진다. 하위식이 상위 번호를 재사용하지 않는다.

## 6. TASK.solution 표현 = 골격 1장 + 정의 N장 (분리)
- **골격**(assembly): `set_grid_size(?p1)·set_grid_color(?p2)·coloring(g0, ?p3, ?p4)` — 값은 전부 `?p`
  (anti-unify DIFF 슬롯).
- **각 `?p`·이름의 정의**를 **개별 그림**으로 분리(그림이 여러 장이어도 무방): `?p1=size_of(input_grid)`,
  `?p2=color_of(input_grid)`, `?p3=목적지 좌표식(튜플 infix)`, `?p4=color_of(obj0)`,
  `obj0=select(objects_of(input_grid), <불변 property>)`, `x=pixels_of(obj0)`, `r,c=row_of/col_of(x)`,
  `r0,c0,r1,c1=row_of/col_of(left_top_of/right_bottom_of(obj0))`.
- **rotate·flip(및 각 태스크)은 독립적으로** 각자의 골격+정의 전체를 갖는다.
- 좌표식(선형부·오프셋)은 anti-unify 로 도출된 **공통 구조**이며, 오프셋은 객체 bbox 원자식(중심 보존).

## 7. 구현 위치
- 렌더러: `debugger/reports/solution_expr.py` — 튜플 infix(§4), 함수조합→?p(§3), 전역 번호(§5)를 반영한
  per-expression 트리 렌더 + `_grid_render`(§1) 재사용. move 등 기존 pair.program 렌더를 깨지 않게 분리.
- 리포트: `program_report.py::_transform_solution_block` 이 변환-해 태스크에 이 골격+정의 갤러리(§6)를 렌더.
