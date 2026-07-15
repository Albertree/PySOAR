"""
util DSL — 노드 계층 항해·필터 (Slice 1, SLICE_1_DEV §6).

ARCKG 노드 구조를 함수형으로 노출만 한다 (계산 로직 없음).
"""

from procedural_memory.dsl.registry import dsl


@dsl("util", ["task"], "list[pair]")
def pairs_of(task):
    """task 의 모든 pair (example 먼저, 그다음 test)."""
    return list(task.example_pairs) + list(task.test_pairs)


@dsl("util", ["pair"], "list[grid]")
def grids_of(pair):
    """pair 의 grid 들 (G0=input, 있으면 G1=output)."""
    grids = [pair.input_grid]
    if pair.output_grid is not None:
        grids.append(pair.output_grid)
    return grids


@dsl("util", ["grid"], "role")
def role_of(grid):
    """grid 역할 — node_id 끝 세그먼트로 판정: G0=input, G1=output."""
    last = grid.node_id.split(".")[-1]
    if last == "G0":
        return "input"
    if last == "G1":
        return "output"
    return last


@dsl("util", ["set", "pred"], "set")
def filter_(items, pred):
    """pred(x) 가 참인 원소만 남긴다."""
    return [x for x in items if pred(x)]


@dsl("util", ["grid"], "list[object]")
def objects_of(grid):
    """grid 의 객체들 (lazy: 비어있으면 extract_objects() 1회).
    hodel 다중 추출이 [전경 / 배경 / 전체] 등 여러 view 를 줄 수 있다 —
    전경만 쓰려면 is_foreground 로 select."""
    if not grid.objects:
        grid.extract_objects()
    return grid.objects


@dsl("util", ["grid"], "list[pixel]")
def pixels_of(grid):
    """grid 의 모든 셀을 행우선 PIXEL 노드 리스트로 (index i = r*width + c).
    pixels_of(g)[i] 의 좌표 = (i // width, i % width) — 솔버 전역 idx 규약과 일치.
    (grid.pixels 는 객체추출 파생이라 index 비정렬 → raw 에서 직접 생성.)"""
    from arbor.perception.arckg.pixel import Pixel
    W = grid.width
    out = []
    for i in range(grid.height * W):
        r, c = divmod(i, W)
        out.append(Pixel(pixel_id=f"{grid.node_id}.X{i}", color=grid.raw[r][c], row=r, col=c))
    return out


def is_foreground(obj) -> bool:
    """배경(색 0)이 아닌 전경 객체인지 (select predicate). ARC 관례: 0=배경."""
    c = obj.to_json()["color"]
    return (not c.get(0)) and any(v for k, v in c.items() if k != 0)
