"""
PAIR node — TASK 아래 한 예시 쌍 (input grid + output grid).
Node ID 형식: T{hex}.P{p}  (test는 Pa, Pb, ...)
"""

import json
import os

from .memory_paths import id_to_json_path, node_id_to_folder_path


class Pair:
    """
    INTENT: input_grid와 output_grid 한 쌍을 담는 KG 노드.
            pair-specific 관측값(관계 결과 캐시 등)을 보유할 수 있다.
            to_json()으로 E_P{p}.json 속성 파일을 기록한다.
    MUST NOT: task-level 일반화를 여기에 저장하지 마 (TASK 레이어 책임).
              input/output 외의 원시 픽셀 좌표를 직접 보유하지 마.
    REF: ARC-solver/ARCKG/pair.py PAIR (line 12)
    """

    def __init__(self, pair_id: str, input_grid, output_grid=None):
        """
        INTENT: pair_id, input_grid(Grid), output_grid(Grid|None)으로 초기화.
                test pair는 output_grid가 None이다.
        MUST NOT: 파일 I/O를 생성자에서 수행하지 마.
        REF: ARC-solver/ARCKG/pair.py PAIR.__init__ (line 13)
        """
        self.node_id = pair_id
        self.input_grid = input_grid
        self.output_grid = output_grid

    def to_json(self) -> dict:
        """
        PAIR property: roles — 자기 배선 시그니처 (어느 역할 grid 로 채워졌나).
        수치(grid_count) 대체: presence-dict 라 '무엇이' 빠졌는지 보존 (color 와 같은 꼴).
        REF: CLAUDE.md § Edge Creation Timing; wiki arbor-execution-trace §3-3
        """
        return {
            "roles": {
                "input": self.input_grid is not None,
                "output": self.output_grid is not None,
            },
        }

    def save(self, semantic_memory_root: str):
        """
        INTENT: to_json()을 해당 PAIR 노드 폴더에 E_P{p}.json으로 기록한다.
                저장 위치는 LCA 규칙에 따라 부모 TASK 폴더 아래.
        MUST NOT: solve 루프 내부에서 호출하지 마.
        REF: ARCKG/memory_paths.py
        """
        folder = node_id_to_folder_path(self.node_id, semantic_memory_root)
        os.makedirs(folder, exist_ok=True)
        path = id_to_json_path(self.node_id, semantic_memory_root)
        with open(path, "w") as f:
            json.dump({"id": self.node_id, "result": self.to_json()}, f, indent=2)

        if self.input_grid is not None:
            self.input_grid.save(semantic_memory_root)
        if self.output_grid is not None:
            self.output_grid.save(semantic_memory_root)

    def __repr__(self) -> str:
        out = self.output_grid is not None
        return f"Pair(id={self.node_id}, has_output={out})"
