"""
compare() — 지식 그래프 핵심 관계 생성 함수.
두 노드 또는 두 관계 결과를 받아 COMM/DIFF 관계를 반환하고 선택적으로 저장한다.

관계 파일 ID 구조 (중첩 dict, 차수에 무관하게 동일 패턴):

  1차 (노드 vs 노드):
    "id": {"id1": "T0a.P0.G0", "id2": "T0a.P0.G1"}

  2차 (1차 relation vs 1차 relation):
    "id": {
      "id1": {"id1": "T0a.P0.G0.O0", "id2": "T0a.P0.G0.O1"},
      "id2": {"id1": "T0a.P1.G0.O0", "id2": "T0a.P1.G0.O1"}
    }

  n차: id1/id2 값이 (n-1)차 id dict이므로 재귀적으로 추적 가능.
"""

import json
import os

from .memory_paths import id_pair_to_comparison_path, node_id_to_folder_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_relation_result(obj) -> bool:
    """이전 compare() 반환값인지 여부 판별 — "result" key를 가진 dict."""
    return isinstance(obj, dict) and "result" in obj


def _id_to_edge_str(id_val) -> str:
    """
    id 필드(str 또는 중첩 dict)를 edge 문자열로 변환한다.
    저장 경로 계산 시 id_pair_to_comparison_path()에 전달하기 위해 사용.

    예) "T0a.P0.G0"                            → "T0a.P0.G0"
        {"id1": "T0a.P0.G0", "id2": "T0a.P0.G1"}
                                               → "E_T0a.P0.G0-T0a.P0.G1"
        {"id1": {"id1": "G0.O0", "id2": "G0.O1"},
         "id2": {"id1": "G1.O0", "id2": "G1.O1"}}
                                               → "E_E_G0.O0-G0.O1-E_G1.O0-G1.O1"
    """
    if isinstance(id_val, str):
        return id_val
    return f"E_{_id_to_edge_str(id_val['id1'])}-{_id_to_edge_str(id_val['id2'])}"


def _compare_values(a, b) -> dict:
    """두 값을 재귀적으로 비교한다. 반환값은 {type, ...} 구조."""
    if isinstance(a, dict) and isinstance(b, dict):
        return _compare_dicts(a, b)
    if isinstance(a, list) and isinstance(b, list):
        return _compare_lists(a, b)
    return _compare_scalars(a, b)


def _compare_lists(a: list, b: list) -> dict:
    """두 리스트를 비교한다.
    - 2D(중첩 리스트): 원소 단위 정확 비교 (행/열 순서 유지)
    - 1D: 순서 유지 정확 비교
    """
    if len(a) != len(b):
        return {"type": "DIFF", "comp1": a, "comp2": b}

    is_2d = any(isinstance(item, list) for item in a) or any(isinstance(item, list) for item in b)
    if is_2d:
        for row_a, row_b in zip(a, b):
            if not isinstance(row_a, list) or not isinstance(row_b, list):
                if row_a != row_b:
                    return {"type": "DIFF", "comp1": a, "comp2": b}
                continue
            if len(row_a) != len(row_b):
                return {"type": "DIFF", "comp1": a, "comp2": b}
            for va, vb in zip(row_a, row_b):
                if va != vb:
                    return {"type": "DIFF", "comp1": a, "comp2": b}
        return {"type": "COMM", "comp1": a, "comp2": b}
    else:
        t = "COMM" if a == b else "DIFF"
        return {"type": t, "comp1": a, "comp2": b}


def _compare_scalars(a, b) -> dict:
    """
    INTENT: 두 스칼라 값을 비교해 COMM/DIFF 결과를 반환.
            scalar leaf에서는 comp1, comp2 값도 결과에 포함된다.
    MUST NOT: 리스트나 dict 타입을 이 함수로 보내지 마.
    REF: CLAUDE.md § Relation result format
    """
    if a is None and b is None:
        return {"type": "COMM", "comp1": a, "comp2": b}
    if type(a) != type(b):
        return {"type": "DIFF", "comp1": a, "comp2": b}
    return {"type": "COMM" if a == b else "DIFF", "comp1": a, "comp2": b}


def _compare_dicts(a: dict, b: dict) -> dict:
    """
    INTENT: 두 dict의 각 key에 대해 재귀적으로 compare를 수행해
            category 구조를 구성한다.
    MUST NOT: key 집합이 다른 경우를 무시하지 마 — 누락 key도 DIFF로 처리.
    REF: CLAUDE.md § Relation result format
    """
    all_keys = sorted(set(a.keys()) | set(b.keys()), key=str)
    if not all_keys:
        return {"type": "COMM", "score": "0/0", "category": {}}

    category: dict = {}
    for key in all_keys:
        has_a = key in a
        has_b = key in b
        if not has_a:
            category[key] = {"type": "DIFF", "comp1": None, "comp2": b[key]}
        elif not has_b:
            category[key] = {"type": "DIFF", "comp1": a[key], "comp2": None}
        else:
            category[key] = _compare_values(a[key], b[key])

    comm = sum(1 for v in category.values() if v.get("type") == "COMM")
    total = len(category)
    overall = "COMM" if comm == total else "DIFF"
    return {
        "type": overall,
        "score": f"{comm}/{total}",
        "category": category,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare(a, b, save: bool = False, semantic_memory_root: str = None) -> dict:
    """
    INTENT: 두 KG 노드(또는 이전 compare 결과)를 비교하여
            {"id": {...}, "result": {"type": "COMM|DIFF", "score": "n/total", "category": {...}}}
            형태의 관계 결과 dict를 반환한다.

            id 필드는 차수에 따라 재귀적으로 중첩된다:
              1차: id = {"id1": str, "id2": str}
              2차: id = {"id1": {1차 id dict}, "id2": {1차 id dict}}
              n차: id = {"id1": {(n-1)차 id dict}, "id2": {(n-1)차 id dict}}

            save=True일 때만 LCA 규칙에 따라 E_*-*.json을 파일시스템에 기록한다.
    MUST NOT: save=True를 기본값으로 쓰지 마 — 수만 개 파일 생성 위험.
              레이어 경계를 넘는 비교(예: GRID와 PIXEL 직접 비교)를 수행하지 마.
    REF: CLAUDE.md § Knowledge Graph Architecture, § Edge Creation Timing
         ARCKG/memory_paths.py id_pair_to_comparison_path()
    """
    if _is_relation_result(a) and _is_relation_result(b):
        # 2차 이상: 두 compare 결과 dict의 result를 비교
        raw = _compare_dicts(a["result"], b["result"])
        result = {
            "type": raw["type"],
            "score": raw.get("score", "0/0"),
            "category": raw.get("category", {}),
        }
        # id는 각 입력 relation의 id를 그대로 중첩
        id_dict = {
            "id1": a.get("id"),
            "id2": b.get("id"),
        }
        comparison = {"id": id_dict, "result": result}

        if save and semantic_memory_root is not None:
            edge_a = _id_to_edge_str(a.get("id"))
            edge_b = _id_to_edge_str(b.get("id"))
            path = id_pair_to_comparison_path(edge_a, edge_b, semantic_memory_root)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(comparison, f, indent=2)

        return comparison

    # 1차: KG 노드 비교 — to_json() 속성 dict를 비교
    props_a = a.to_json()
    props_b = b.to_json()
    raw = _compare_dicts(props_a, props_b)
    result = {
        "type": raw["type"],
        "score": raw.get("score", "0/0"),
        "category": raw.get("category", {}),
    }
    id_a = getattr(a, "node_id", None)
    id_b = getattr(b, "node_id", None)
    id_dict = {"id1": id_a, "id2": id_b}
    comparison = {"id": id_dict, "result": result}

    if save and semantic_memory_root is not None and id_a and id_b:
        path = id_pair_to_comparison_path(id_a, id_b, semantic_memory_root)
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w") as f:
            json.dump(comparison, f, indent=2)

    return comparison
