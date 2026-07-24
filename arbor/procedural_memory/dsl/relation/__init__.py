"""
relation DSL — 모듈 C: 비교 (두 노드의 관계 = 공통점·차이점).

compare(scope_a, scope_b)   두 scope(노드 list)의 N:N 비교 → [(x, y, receipt), ...].
  · 한 범위 *안* 끼리 비교 = scope_a == scope_b → 자기·중복 제외 pairwise.
  · 서로 다른 범위면 → cross product (N:N).
  · 단일 노드는 [x] 로 자동 wrap (1:1 = N=1 특수).  (구 compare_set = compare(scope, scope))

비교할 *범위* 는 selection 의 select 로 정해 넘긴다: compare( select(...), select(...) ).
compare 자체는 ARCKG/comparison.py 재사용. receipt 요약은 verdict.
"""

from itertools import combinations

from arbor.perception.arckg.comparison import compare as _kg_compare
from arbor.procedural_memory.dsl.registry import dsl


@dsl("relation", ["scope", "scope"], "receipts")
def compare(scope_a, scope_b):
    """두 scope 의 N:N 비교 → [(x, y, receipt), ...]. 같은 범위면 안끼리 pairwise."""
    a = scope_a if isinstance(scope_a, list) else [scope_a]
    b = scope_b if isinstance(scope_b, list) else [scope_b]
    if a == b:
        return [(x, y, _kg_compare(x, y)) for x, y in combinations(a, 2)]
    return [(x, y, _kg_compare(x, y)) for x in a for y in b]


def verdict(receipt) -> tuple:
    """receipt 판정 요약: (type, score=comm/total, COMM 인 property 키 목록)."""
    res = receipt["result"]
    comm = [k for k, v in res.get("category", {}).items()
            if isinstance(v, dict) and v.get("type") == "COMM"]
    return res["type"], res["score"], comm


def localize(ref: dict, cur: dict) -> dict:
    """비교 *심화*: 통째 DIFF 를 받아도 '어디가' 다른지 모름 → 막힘. 그 막힘의
    근거로 두 presence-dict 를 *이름정렬* 해 항목별로 비교, 다른 키만 집어낸다.

    ref = 기준(완전한 example), cur = 대상(불완전한 test).
    반환 {key: (cur_val, ref_val)}  — cur 를 ref 에 맞추려면 cur_val→ref_val.
    (정렬이 이름으로 공짜인 presence-dict 라 쉬움. grid·object 면 정렬이 비싸짐.)
    """
    return {k: (cur.get(k), ref[k]) for k in ref if cur.get(k) != ref[k]}
