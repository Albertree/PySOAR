"""
util DSL — 노드 계층 항해·필터 (Slice 1, SLICE_1_DEV §6).

ARCKG 노드 구조를 함수형으로 노출만 한다 (계산 로직 없음).
"""

from arbor.procedural_memory.dsl.registry import dsl


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


@dsl("util", ["scope", "predicate"], "scope")
def filter_(items, pred):
    """pred(x) 가 참인 원소만 남긴다."""
    return [x for x in items if pred(x)]


@dsl("util", ["grid"], "list[object]")
def objects_of(grid):
    """grid 의 객체들 (lazy: 비어있으면 extract_objects() 1회).
    (2026-07-19) grid.objects = spelke 합집합(4-conn ∪ 같은색 8-conn). hodel 8-method 폐지."""
    if not grid.objects:
        grid.extract_objects()
    return grid.objects


@dsl("util", ["grid", "object"], "list[pixel]")
def pixels_of(node):
    """셀들을 PIXEL 노드 리스트로. **입력 계층에 따라 달라짐**:
      grid   → 모든 셀 (행우선, index i = r*width + c; 좌표 = (i // width, i % width)).
      object → 객체의 비투명 셀들 (색 포함, coordinate 순서).
    둘 다 grid.pixels / obj.pixels(객체추출 파생) 를 안 쓰고 raw/colorgrid 에서 즉석 생성한다
    → arckg build 가 pixel 을 미리 안 지어도 됨(경량 build 와 호환)."""
    from arbor.perception.arckg.pixel import Pixel
    if node.__class__.__name__ == "Object":                  # object: 비투명 셀만
        rmin, cmin = node.pos
        out, i = [], 0
        for r, row in enumerate(node.colorgrid):
            for c, cell in enumerate(row):
                if cell != 13:                               # 13 = 투명
                    out.append(Pixel(pixel_id=f"{node.node_id}.X{i}", color=cell,
                                     row=rmin + r, col=cmin + c))
                    i += 1
        return out
    W = node.width                                           # grid: 모든 셀 행우선
    out = []
    for i in range(node.height * W):
        r, c = divmod(i, W)
        out.append(Pixel(pixel_id=f"{node.node_id}.X{i}", color=node.raw[r][c], row=r, col=c))
    return out

