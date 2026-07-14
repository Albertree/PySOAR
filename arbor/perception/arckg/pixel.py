"""
PIXEL node — OBJECT 또는 GRID 아래 단일 픽셀.
Node ID 형식: T{hex}.P{p}.G{g}.O{o}.X{x}  (object-level)
            T{hex}.P{p}.G{g}.X{x}         (grid-level)
"""

import json
import os

from .memory_paths import id_to_json_path, node_id_to_folder_path


class Pixel:
    """
    INTENT: 단일 픽셀의 색상과 격자 내 절대 좌표를 나타내는 KG 노드.
            to_json()으로 E_X{x}.json 속성 파일을 기록한다.
    REF: ARC-solver/ARCKG/pixel.py PIXEL (line 11)
    """

    def __init__(self, pixel_id: str, color: int, row: int, col: int):
        """
        Args:
            pixel_id: 전체 node_id 문자열 (e.g. "T0a.P0.G0.O2.X5")
            color:    0-9 색상 값
            row:      격자 내 절대 행 인덱스
            col:      격자 내 절대 열 인덱스
        """
        self.node_id = pixel_id
        self.color = color
        self.row = row
        self.col = col

    def to_json(self) -> dict:
        """
        PIXEL 속성: color + coordinate(row_index, col_index).
        REF: ARC-solver/ARCKG/pixel.py  update_property → property['coordinate']
        """
        return {
            "color": self.color,
            "coordinate": {
                "row_index": self.row,
                "col_index": self.col,
            },
        }

    def save(self, semantic_memory_root: str):
        """to_json()을 E_X{x}.json으로 노드 폴더에 기록."""
        folder = node_id_to_folder_path(self.node_id, semantic_memory_root)
        os.makedirs(folder, exist_ok=True)
        path = id_to_json_path(self.node_id, semantic_memory_root)
        with open(path, "w") as f:
            json.dump({"id": self.node_id, "result": self.to_json()}, f, indent=2)

    def __repr__(self) -> str:
        return (f"Pixel(id={self.node_id}, color={self.color}, "
                f"pos=({self.row},{self.col}))")
