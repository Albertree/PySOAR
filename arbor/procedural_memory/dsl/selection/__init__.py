"""
selection DSL — 조건 맞는 요소를 *찾는다* (탐색/선택).

select(anchor, level, pred) = "anchor 아래 level 에서 pred 맞는 요소".
*범위 지정*(compare 에 넘김)과 *객체/픽셀 선택*(transformation arg)에 **공용** —
본질이 하나라 둘로 나누지 않는다. level 인자가 object/pixel/grid/pair 를 가른다.

relation(비교)·transformation(변형) 양쪽이 빌려 쓰므로 독립 카테고리. 재료는 util.
"""

from arbor.procedural_memory.dsl.registry import dsl
from arbor.procedural_memory.dsl.util import pairs_of, grids_of, objects_of, filter_, pixels_of

# level → anchor 아래 그 level 원소를 주는 util
_LEVEL_CHILDREN = {"pair": pairs_of, "grid": grids_of, "object": objects_of, "pixel": pixels_of}


@dsl("selection", ["anchor", "level"], "list[node]")
def elements_at(anchor, level):
    """anchor 아래 level 의 원소들."""
    return _LEVEL_CHILDREN[level](anchor)


@dsl("selection", ["anchor", "level", "pred"], "scope")
def select(anchor, level, pred=None):
    """anchor 아래 level 에서 pred 맞는 요소 (pred 없으면 전체).
    예: select(pair,"grid",role==out)=비교 범위 / select(grid,"object",pred)=객체 선택."""
    items = elements_at(anchor, level)
    return filter_(items, pred) if pred is not None else list(items)
