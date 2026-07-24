"""
property DSL — ARCKG 노드 to_json() 키를 함수형으로 노출 (재계산 X, 노출 O).

설계 = **일반(polymorphic) + 계층전용 + 하위투영**. property 함수는 *입력 노드의 계층*에
따라 결과가 달라진다(같은 `color` 라도 grid/object=색집합, pixel=단일색). registry SPECS 의
in[] 이 그 property 가 적용되는 계층들을 밝힌다.

  COMMON (다계층):   color · size · contents · coordinate
  OBJECT 전용:        area · position · shape · symmetry
  TASK:               example_pair_count · test_pair_count
  라벨(카운팅 X):      type (pair→example/test, grid→input/output)
  PAIR:               role
  하위투영(_of/_symm): height_of · width_of · hori_symm · verti_symm · diag_symm · anti_symm ·
                       left_top · right_top · left_bottom · right_bottom (모서리 = 단일좌표)
  좌표 성분:           row_of · col_of  (단일좌표 전용 — 좌표집합엔 적용 불가)
"""

from arbor.procedural_memory.dsl.registry import dsl


# ── COMMON: 입력 계층에 따라 결과가 달라지는 일반 property ─────────────────
@dsl("property", ["grid", "object", "pixel"], "color|color-set")
def color(node):
    """색. grid/object → 색집합 {0..9: bool} · pixel → 단일 색."""
    return node.to_json()["color"]


@dsl("property", ["grid", "object"], "size")
def size(node):
    """크기 {height, width}. grid/object."""
    return node.to_json()["size"]


@dsl("property", ["grid", "object"], "contents")
def contents(node):
    """원시 2D 배열. grid/object."""
    return node.to_json()["contents"]


@dsl("property", ["object", "pixel"], "coordinate|coordinate-set")
def coordinate(node):
    """좌표. object → 좌표집합 [[r,c], ...] · pixel → 단일좌표 {row_index, col_index}."""
    return node.to_json()["coordinate"]


# ── OBJECT 전용 ────────────────────────────────────────────────────────
@dsl("property", ["object"], "area")
def area(obj):
    """객체 셀 수 (bbox 내 비투명)."""
    return obj.to_json()["area"]


@dsl("property", ["object"], "position")
def position(obj):
    """bbox 네 모서리 {left_top, right_top, left_bottom, right_bottom} (각 단일좌표)."""
    return obj.to_json()["position"]


@dsl("property", ["object"], "shape")
def shape(obj):
    """bbox 모양 2D (비투명=1, 투명=-1)."""
    return obj.to_json()["shape"]


@dsl("property", ["object"], "symmetry")
def symmetry(obj):
    """대칭 {hori_symm, verti_symm, diag_symm, anti_symm}."""
    return obj.to_json()["symmetry"]


# ── TASK ───────────────────────────────────────────────────────────────
@dsl("property", ["task"], "int")
def example_pair_count(task):
    """example pair 수."""
    return len(task.example_pairs)


@dsl("property", ["task"], "int")
def test_pair_count(task):
    """test pair 수."""
    return len(task.test_pairs)


# ── 라벨: type (카운팅 대상 아님, node_id 구조에서 도출) ───────────────────
@dsl("property", ["pair", "grid"], "label")
def type(node):  # noqa: A001  — SPECS 이름 "type" 을 위해 의도적으로 builtin shadow(모듈-국소)
    """계층 라벨. pair → example/test · grid → input/output. (node_id 구조에서 도출.)
    Node ID: T{hex}.P{p}(.G{g}) — P<digit>=example / P<letter>=test · G0=input / G1=output."""
    seg = node.node_id.split(".")[-1]
    if seg.startswith("P"):
        return "example" if seg[1:].isdigit() else "test"
    if seg.startswith("G"):
        return "input" if seg == "G0" else "output"
    return None


# ── PAIR ───────────────────────────────────────────────────────────────
@dsl("property", ["pair"], "role-set")
def role(pair):
    """pair 배선 presence {input: bool, output: bool}. '무엇이' 있고 빠졌는지 보존."""
    return pair.to_json()["roles"]


# ── 하위투영: 부모 property 를 투영 (새 데이터 아님) ────────────────────────
@dsl("property", ["grid", "object"], "int")
def height_of(node):
    """높이 = size(node).height. grid/object."""
    return size(node)["height"]


@dsl("property", ["grid", "object"], "int")
def width_of(node):
    """너비 = size(node).width. grid/object."""
    return size(node)["width"]


@dsl("property", ["object"], "bool")
def hori_symm(obj):
    """수평 대칭 = symmetry(obj).hori_symm."""
    return symmetry(obj)["hori_symm"]


@dsl("property", ["object"], "bool")
def verti_symm(obj):
    """수직 대칭."""
    return symmetry(obj)["verti_symm"]


@dsl("property", ["object"], "bool")
def diag_symm(obj):
    """주대각 대칭."""
    return symmetry(obj)["diag_symm"]


@dsl("property", ["object"], "bool")
def anti_symm(obj):
    """반대각 대칭."""
    return symmetry(obj)["anti_symm"]


@dsl("property", ["object"], "coordinate")
def left_top(obj):
    """좌상단 모서리 (단일좌표) = position(obj).left_top."""
    return position(obj)["left_top"]


@dsl("property", ["object"], "coordinate")
def right_top(obj):
    """우상단 모서리 (단일좌표)."""
    return position(obj)["right_top"]


@dsl("property", ["object"], "coordinate")
def left_bottom(obj):
    """좌하단 모서리 (단일좌표)."""
    return position(obj)["left_bottom"]


@dsl("property", ["object"], "coordinate")
def right_bottom(obj):
    """우하단 모서리 (단일좌표)."""
    return position(obj)["right_bottom"]


# ── 좌표 성분: 단일좌표 전용 (좌표집합엔 적용 불가) ─────────────────────────
def _single_coord(coord):
    """단일좌표만 (r, c) 로 정규화. 좌표집합([[r,c],...])이면 거부한다.
    허용: {row_index, col_index} (pixel·모서리) 또는 [r, c] (정수쌍)."""
    if isinstance(coord, dict):
        return (coord.get("row_index", coord.get("row")),
                coord.get("col_index", coord.get("col")))
    if (isinstance(coord, (list, tuple)) and len(coord) == 2
            and all(isinstance(v, int) for v in coord)):
        return coord[0], coord[1]
    raise TypeError("row_of/col_of 는 단일좌표만 받는다 (좌표집합엔 적용 불가)")


@dsl("property", ["coordinate"], "int")
def row_of(coord):
    """단일좌표의 행. object.coordinate 같은 좌표집합엔 적용 불가."""
    return _single_coord(coord)[0]


@dsl("property", ["coordinate"], "int")
def col_of(coord):
    """단일좌표의 열. 좌표집합엔 적용 불가."""
    return _single_coord(coord)[1]
