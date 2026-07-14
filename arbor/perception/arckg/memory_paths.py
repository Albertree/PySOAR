"""
Path helpers — 노드 ID와 비교 쌍으로부터 semantic_memory 파일 경로를 계산한다.

Node ID 형식: T{hex}.P{p}.G{g}.O{o}.X{x}  (필요한 깊이까지만)
  예) "T0a1b2c3.P0"          → PAIR 노드
      "T0a1b2c3.P0.G0"       → GRID 노드
      "T0a1b2c3.P0.G0.O2"    → OBJECT 노드
      "T0a1b2c3.P0.G0.O2.X5" → PIXEL 노드 (Object 하위)

폴더 구조: N_{part}/ 계층
  semantic_memory_root/N_T{hex}/N_P{p}/N_G{g}/N_O{o}/N_X{x}/
속성 파일: E_{last_part}.json
  예) N_G0/E_G0.json
"""


def node_id_to_folder_path(node_id: str, semantic_memory_root: str) -> str:
    """
    노드 ID → 해당 노드 폴더(N_ 접두어) 절대 경로.
    파일을 실제로 생성하지 않는다 — 경로 계산만.
    예) "T0a.P0.G0", "semantic_memory" → "semantic_memory/N_T0a/N_P0/N_G0/"
    """
    root = semantic_memory_root.rstrip("/") + "/"
    parts = node_id.split(".")
    folder = root
    for part in parts:
        folder += f"N_{part}/"
    return folder


def id_to_json_path(node_id: str, semantic_memory_root: str) -> str:
    """
    노드 ID → 속성 JSON 파일 경로 (E_{last_part}.json).
    파일을 실제로 생성하지 않는다 — 경로 계산만.
    예) "T0a.P0.G0" → "semantic_memory/N_T0a/N_P0/N_G0/E_G0.json"
    """
    folder = node_id_to_folder_path(node_id, semantic_memory_root)
    last_part = node_id.split(".")[-1]
    return folder + f"E_{last_part}.json"


def _lca_node_id(id_a: str, id_b: str):
    """두 노드 ID의 LCA(Lowest Common Ancestor) 노드 ID를 반환."""
    parts_a = id_a.split(".")
    parts_b = id_b.split(".")
    if parts_a[0] != parts_b[0]:
        return None
    common = []
    for a, b in zip(parts_a, parts_b):
        if a == b:
            common.append(a)
        else:
            break
    return ".".join(common) if common else None


def _short_name(node_id: str, lca_id: str) -> str:
    """LCA 이후의 경로 세그먼트를 이어 붙인 단축 이름을 반환.
    예) LCA="T0a.P0", node_id="T0a.P0.G0.O2" → "G0O2"
    """
    lca_prefix = lca_id + "."
    if node_id.startswith(lca_prefix):
        suffix = node_id[len(lca_prefix):]
        return suffix.replace(".", "")
    # LCA와 동일한 노드인 경우 마지막 세그먼트만 반환
    return node_id.split(".")[-1]


def id_pair_to_comparison_path(id_a: str, id_b: str,
                                semantic_memory_root: str) -> str:
    """
    두 노드 ID로부터 비교 엣지 파일 경로를 반환한다.
    - 1차 비교 (노드 ID): LCA 폴더 아래 E_{short_a}-{short_b}.json
    - 고차 비교 (id가 이미 'E_...' 형식): E_(E_...)-(E_...).json을 root에 생성
    경로 계산만 수행하며, 파일을 실제로 생성하지 않는다.
    """
    # 고차(higher-order) 비교: 두 edge ID를 괄호로 감싼 형식
    if id_a.startswith("E_") and id_b.startswith("E_"):
        edge_name = f"E_({id_a})-({id_b}).json"
        root = semantic_memory_root.rstrip("/") + "/"
        return root + edge_name

    lca_id = _lca_node_id(id_a, id_b)
    if lca_id is None:
        raise ValueError(f"No LCA found for '{id_a}' and '{id_b}' — different task roots")

    short_a = _short_name(id_a, lca_id)
    short_b = _short_name(id_b, lca_id)
    edge_name = f"E_{short_a}-{short_b}.json"
    lca_folder = node_id_to_folder_path(lca_id, semantic_memory_root)
    return lca_folder + edge_name
