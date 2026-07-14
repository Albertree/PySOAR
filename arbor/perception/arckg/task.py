"""
TASK node — 지식 그래프 최상위 레이어.
Node ID 형식: T{hex}
"""

import json
import os

from .memory_paths import id_to_json_path, node_id_to_folder_path


class Task:
    """
    INTENT: ARC 태스크 하나를 나타내는 KG 노드.
            task_hex ID, example pairs, test pairs, 태스크 레벨 속성을 보유한다.
            to_json()으로 semantic_memory에 E_T{hex}.json 속성 파일을 기록한다.
    MUST NOT: pair-specific 관측값을 여기에 저장하지 마 (PAIR 레이어 책임).
              어떤 solve 로직도 두지 마.
    REF: ARC-solver/ARCKG/task.py TASK (line 12)
    """

    def __init__(self, task_hex: str, example_pairs: list, test_pairs: list):
        """
        INTENT: task_hex, example_pairs(Pair 목록), test_pairs(Pair 목록)를 받아
                노드를 초기화한다.
        MUST NOT: 파일 I/O를 생성자 내에서 수행하지 마.
        REF: ARC-solver/ARCKG/task.py TASK.__init__ (line 13)
        """
        self.task_hex = task_hex
        self.node_id = f"T{task_hex}"
        self.example_pairs = example_pairs
        self.test_pairs = test_pairs

    def to_json(self) -> dict:
        """
        INTENT: 이 노드의 0th-order 속성(E_T{hex}.json 내용)을 dict로 반환한다.
                반환 결과는 semantic_memory에 기록된다.
        MUST NOT: 비교(comparison) 결과를 포함하지 마. 속성만.
        REF: CLAUDE.md § Edge Creation Timing; wiki arbor-execution-trace §3-3
        property = roles (구조 계층의 배선 = 어느 pair-슬롯이 점유됐나). 개수는 edge(example/test) 로.
        """
        return {
            "roles": {
                "example": len(self.example_pairs) > 0,
                "test": len(self.test_pairs) > 0,
            },
        }

    def save(self, semantic_memory_root: str):
        """
        INTENT: to_json()을 semantic_memory_root/N_T{hex}/E_T{hex}.json에 기록한다.
                하위 모든 Pair → Grid → Object도 재귀적으로 저장한다.
        MUST NOT: solve 루프 내부에서 호출하지 마 (task load 시점에만).
        REF: ARCKG/memory_paths.py id_to_json_path()
        """
        folder = node_id_to_folder_path(self.node_id, semantic_memory_root)
        os.makedirs(folder, exist_ok=True)
        path = id_to_json_path(self.node_id, semantic_memory_root)
        with open(path, "w") as f:
            json.dump({"id": self.node_id, "result": self.to_json()}, f, indent=2)

        for pair in self.example_pairs:
            pair.save(semantic_memory_root)
        for pair in self.test_pairs:
            pair.save(semantic_memory_root)

    def __repr__(self) -> str:
        return (
            f"Task(hex={self.task_hex}, "
            f"examples={len(self.example_pairs)}, "
            f"tests={len(self.test_pairs)})"
        )
