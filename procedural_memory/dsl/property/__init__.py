"""
property DSL — ARCKG 노드 to_json() 키를 함수형으로 노출 (재계산 ✗, 노출 ○).

*계층별로* 묶는다 (property 는 그 입력 노드의 계층에 속한다):

  TASK-level   : roles {example,test} (배선; pair_count 는 edge 파생)        (Task)
  PAIR-level   : roles {input,output} (배선; grid_count 는 roles 파생)        (Pair)
  GRID-level   : size, color, contents                                  (ARCKG Grid 3)
  OBJECT-level : area_of, color_of, coordinate_of, position_of,         (ARCKG Object 8)
                 position_of, shape_of, size_of, symmetry_of
  PIXEL-level  : pixel_color, pixel_coordinate                          (ARCKG Pixel 2)

(각 함수의 입력 타입 = 그 property 의 계층. registry SPECS 의 in[0] 으로도 계층을 안다.)
"""

from procedural_memory.dsl.registry import dsl


# ── TASK-level ──────────────────────────────────────────────
@dsl("property", ["task"], "int")
def pair_count(task):
    """task 의 pair 수 (example + test). (to_json 이 roles presence 로 바뀜 → edge 에서 셈.)"""
    return len(task.example_pairs) + len(task.test_pairs)


# ── PAIR-level ──────────────────────────────────────────────
@dsl("property", ["pair"], "role-set")
def roles(pair):
    """pair 가 *어떤 역할의 grid 로 채워졌나* = 자기 배선 시그니처 (color 와 같은 꼴).

    수치(grid_count)가 아니라 presence-dict {input:bool, output:bool}. '무엇이'
    빠졌는지를 보존해, 통째 비교 후 localize 로 빠진 역할을 집어낼 수 있다.
    """
    return pair.to_json()["roles"]                  # 단일 출처: pair 의 정식 property


@dsl("property", ["pair"], "int")
def grid_count(pair):
    """pair 의 grid 수 (2=in+out, 1=in only). roles presence 에서 파생 (구 수치 속성, roles 로 대체됨)."""
    return sum(pair.to_json()["roles"].values())


# ── GRID-level ──────────────────────────────────────────────
@dsl("property", ["grid"], "size")
def size(grid):
    """grid 크기 {height, width}."""
    return grid.to_json()["size"]


@dsl("property", ["grid"], "color-set")
def color(grid):
    """grid 에 등장하는 색 집합 {0..9: bool}."""
    return grid.to_json()["color"]


@dsl("property", ["grid"], "contents")
def contents(grid):
    """grid 의 원시 2D 배열."""
    return grid.to_json()["contents"]


@dsl("property", ["grid"], "int")
def height(grid):
    """grid 높이 (size 의 투영 — 새 데이터 아님)."""
    return size(grid)["height"]


@dsl("property", ["grid"], "int")
def width(grid):
    """grid 너비 (size 의 투영 — 새 데이터 아님)."""
    return size(grid)["width"]


# ── OBJECT-level (ARCKG Object 8 property) ──────────────────
@dsl("property", ["object"], "area")
def area_of(obj):
    """객체 셀 수 (bbox 내 비투명)."""
    return obj.to_json()["area"]


@dsl("property", ["object"], "color-set")
def color_of(obj):
    """객체 색 집합 {0..9: bool}."""
    return obj.to_json()["color"]


@dsl("property", ["object"], "coordinate")
def coordinate_of(obj):
    """객체가 차지한 셀 절대좌표 목록 [[r,c],...]."""
    return obj.to_json()["coordinate"]


@dsl("property", ["object"], "position")
def position_of(obj):
    """객체 bbox 네 모서리 좌표 {left_top, right_top, left_bottom, right_bottom}."""
    return obj.to_json()["position"]


@dsl("property", ["object"], "shape")
def shape_of(obj):
    """객체 bbox 모양 2D (비투명=1, 투명=-1)."""
    return obj.to_json()["shape"]


@dsl("property", ["object"], "size")
def size_of(obj):
    """객체 bbox 크기 {height, width}."""
    return obj.to_json()["size"]


@dsl("property", ["object"], "symmetry")
def symmetry_of(obj):
    """객체 대칭 {hori, verti, diag, anti}."""
    return obj.to_json()["symmetry"]


# ── PIXEL-level (ARCKG Pixel 2 property) ────────────────────
@dsl("property", ["pixel"], "color")
def pixel_color(px):
    """픽셀 색 (단일 값)."""
    return px.to_json()["color"]


@dsl("property", ["pixel"], "coordinate")
def pixel_coordinate(px):
    """픽셀 좌표 {row_index, col_index}."""
    return px.to_json()["coordinate"]
