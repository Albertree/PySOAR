"""
property DSL — ARCKG 노드 to_json() 키를 함수형으로 노출 (재계산 X, 노출 O).

규약(하나로 통일): **property accessor 는 `_of` 접미사**("노드의 X 를 꺼낸다"),
집계(개수)는 `_count`. accessor 는 *입력 노드의 계층*에 따라 결과가 달라진다
(같은 `color_of` 라도 grid/object=색집합, pixel=단일색). registry SPECS 의 in[] 이
그 property 가 적용되는 계층들을 밝힌다.

  COMMON (다계층):     color_of · size_of · contents_of · coordinate_of
  OBJECT 전용:          area_of · position_of · shape_of · symmetry_of
  라벨(카운팅 X):        type_of (계층: task/pair/grid/object/pixel) · subtype_of (pair→example/test, grid→input/output)
  PAIR:                 role_of
  집계(_count):          example_pair_count · test_pair_count
  하위투영:              height_of · width_of · hori_symm_of · verti_symm_of ·
                        diag_symm_of · anti_symm_of ·
                        left_top_of · right_top_of · left_bottom_of · right_bottom_of (모서리=단일좌표)
  좌표 성분:             row_of · col_of  (단일좌표 전용 — 좌표집합엔 적용 불가)
"""

from arbor.procedural_memory.dsl.registry import dsl


# ── COMMON: 입력 계층에 따라 결과가 달라지는 일반 property ─────────────────
@dsl("property", ["grid", "object", "pixel"], "color|color-set")
def color_of(node):
    """색. grid/object → 색집합 {0..9: bool} · pixel → 단일 색."""
    return node.to_json()["color"]


@dsl("property", ["grid", "object"], "size")
def size_of(node):
    """크기 {height, width}. grid/object."""
    return node.to_json()["size"]


@dsl("property", ["grid", "object"], "contents")
def contents_of(node):
    """원시 2D 배열. grid/object."""
    return node.to_json()["contents"]


@dsl("property", ["object", "pixel"], "coordinate|coordinate-set")
def coordinate_of(node):
    """좌표. object → 좌표집합 [[r,c], ...] · pixel → 단일좌표 {row_index, col_index}."""
    return node.to_json()["coordinate"]


# ── OBJECT 전용 ────────────────────────────────────────────────────────
@dsl("property", ["object"], "area")
def area_of(obj):
    """객체 셀 수 (bbox 내 비투명)."""
    return obj.to_json()["area"]


@dsl("property", ["object"], "position")
def position_of(obj):
    """bbox 네 모서리 {left_top, right_top, left_bottom, right_bottom} (각 단일좌표)."""
    return obj.to_json()["position"]


@dsl("property", ["object"], "shape")
def shape_of(obj):
    """bbox 모양 2D (비투명=1, 투명=-1)."""
    return obj.to_json()["shape"]


@dsl("property", ["object"], "symmetry")
def symmetry_of(obj):
    """대칭 {hori_symm, verti_symm, diag_symm, anti_symm}."""
    return obj.to_json()["symmetry"]


# ── 라벨(카운팅 X): type_of=계층(5) · subtype_of=계층 내 하위구분 ────────────
@dsl("property", ["task", "pair", "grid", "object", "pixel"], "layer")
def type_of(node):
    """노드의 계층 텍스트: task / pair / grid / object / pixel. (5계층 전부; 클래스에서 도출.)"""
    return node.__class__.__name__.lower()


@dsl("property", ["pair", "grid"], "label")
def subtype_of(node):
    """계층 내 하위구분. pair → example/test · grid → input/output. (node_id 에서 도출.)
    Node ID: T{hex}.P{p}(.G{g}) — P<digit>=example / P<letter>=test · G0=input / G1=output."""
    seg = node.node_id.split(".")[-1]
    if seg.startswith("P"):
        return "example" if seg[1:].isdigit() else "test"
    if seg.startswith("G"):
        return "input" if seg == "G0" else "output"
    return None


# ── PAIR ───────────────────────────────────────────────────────────────
@dsl("property", ["pair"], "role-set")
def role_of(pair):
    """pair 배선 presence {input: bool, output: bool}. '무엇이' 있고 빠졌는지 보존."""
    return pair.to_json()["roles"]


# ── 집계 (_count — accessor 가 아니라 개수) ────────────────────────────────
@dsl("property", ["task"], "int")
def example_pair_count(task):
    """example pair 수."""
    return len(task.example_pairs)


@dsl("property", ["task"], "int")
def test_pair_count(task):
    """test pair 수."""
    return len(task.test_pairs)


# ── 하위투영: 부모 property 를 투영 (새 데이터 아님) ────────────────────────
@dsl("property", ["grid", "object"], "int")
def height_of(node):
    """높이 = size_of(node).height. grid/object."""
    return size_of(node)["height"]


@dsl("property", ["grid", "object"], "int")
def width_of(node):
    """너비 = size_of(node).width. grid/object."""
    return size_of(node)["width"]


@dsl("property", ["object"], "bool")
def hori_symm_of(obj):
    """수평 대칭 = symmetry_of(obj).hori_symm."""
    return symmetry_of(obj)["hori_symm"]


@dsl("property", ["object"], "bool")
def verti_symm_of(obj):
    """수직 대칭."""
    return symmetry_of(obj)["verti_symm"]


@dsl("property", ["object"], "bool")
def diag_symm_of(obj):
    """주대각 대칭."""
    return symmetry_of(obj)["diag_symm"]


@dsl("property", ["object"], "bool")
def anti_symm_of(obj):
    """반대각 대칭."""
    return symmetry_of(obj)["anti_symm"]


@dsl("property", ["object"], "coordinate")
def left_top_of(obj):
    """좌상단 모서리 (단일좌표) = position_of(obj).left_top."""
    return position_of(obj)["left_top"]


@dsl("property", ["object"], "coordinate")
def right_top_of(obj):
    """우상단 모서리 (단일좌표)."""
    return position_of(obj)["right_top"]


@dsl("property", ["object"], "coordinate")
def left_bottom_of(obj):
    """좌하단 모서리 (단일좌표)."""
    return position_of(obj)["left_bottom"]


@dsl("property", ["object"], "coordinate")
def right_bottom_of(obj):
    """우하단 모서리 (단일좌표)."""
    return position_of(obj)["right_bottom"]


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
