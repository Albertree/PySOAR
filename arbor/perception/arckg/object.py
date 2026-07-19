"""
OBJECT node — GRID 아래 연결 성분(connected component).
Node ID 형식: T{hex}.P{p}.G{g}.O{o}
"""

import json
import os

from .memory_paths import id_to_json_path, node_id_to_folder_path


class Object:
    """
    INTENT: spelke 객체검출(4-conn ∪ 같은색 8-conn)로 검출된 하나의 object.
            colorgrid(bbox 크기, 투명=13)와 격자 내 절대 좌표 pos로 초기화.
            8개 property(area/color/contents/coordinate/position/shape/size/symmetry)를
            to_json()으로 직렬화한다.
    MUST NOT: GRID 전체를 저장하지 마. bbox 범위만 가진다.
    REF: ARC-solver/ARCKG/object.py OBJECT.update_property (line 170)
         (2026-07-19) hodel find_all_objects 폐지 → arbor.perception.spelke.spelke_arckg_objects
    """

    def __init__(self, object_id: str, colorgrid: list, pos: tuple):
        """
        Args:
            object_id:  전체 node_id 문자열 (e.g. "T0a.P0.G0.O3")
            colorgrid:  list[list[int]], bbox 크기. 투명 셀 = 13.
            pos:        (row_min, col_min) — bbox left_top 절대 좌표
        """
        self.node_id = object_id
        self.colorgrid = colorgrid
        self.pos = pos
        self.pixels: list = []  # Pixel 객체 목록 (object-level)

        # --- transformation DSL selection 인터페이스 ---
        h = len(colorgrid)
        w = len(colorgrid[0]) if colorgrid else 0
        row_min, col_min = pos

        # bbox: colorgrid 의 별칭 (transformation.py 에서 selection.bbox 로 접근)
        self.bbox = colorgrid

        # coordinate: 비투명 셀의 절대 (row, col) 목록
        self.coordinate = [
            (row_min + r, col_min + c)
            for r, row in enumerate(colorgrid)
            for c, cell in enumerate(row)
            if cell != 13
        ]

        # bbox 내 전체 (row, col) — teleport 에서 grab 검증에 사용
        self.bbox_coordinate = [
            (row_min + r, col_min + c)
            for r in range(h)
            for c in range(w)
        ]

        # 꼭짓점 절대 좌표
        self.left_top     = (row_min,         col_min)
        self.right_top    = (row_min,         col_min + w - 1)
        self.left_bottom  = (row_min + h - 1, col_min)
        self.right_bottom = (row_min + h - 1, col_min + w - 1)

        # --- 하위 호환 속성 (bounding_box, mask, color) ---
        self.bounding_box = (row_min, col_min, row_min + h - 1, col_min + w - 1)
        self.mask = [[cell != 13 for cell in row] for row in colorgrid]
        colors = [cell for row in colorgrid for cell in row if cell != 13]
        self.color = colors[0] if colors else 0   # spelke 객체는 단색 → max/count 불필요

    # ------------------------------------------------------------------ #
    #  대칭성 헬퍼 (원본: ARC-solver/ARCKG/object.py)                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hori_symmetry(grid: list) -> bool:
        """좌우(수직 축) 대칭 — 각 행이 뒤집어도 동일."""
        return all(row == list(reversed(row)) for row in grid)

    @staticmethod
    def _verti_symmetry(grid: list) -> bool:
        """상하(수평 축) 대칭 — 뒤집어도 동일."""
        return grid == list(reversed(grid))

    @staticmethod
    def _diag_symmetry(grid: list) -> bool:
        """주 대각선 대칭 (정사각형 전용)."""
        n = len(grid)
        return all(grid[i][j] == grid[j][i] for i in range(n) for j in range(n))

    @staticmethod
    def _anti_symmetry(grid: list) -> bool:
        """반 대각선 대칭 (정사각형 전용)."""
        n = len(grid)
        return all(
            grid[i][j] == grid[n - 1 - j][n - 1 - i]
            for i in range(n) for j in range(n)
        )

    # ------------------------------------------------------------------ #
    #  직렬화                                                               #
    # ------------------------------------------------------------------ #

    def to_json(self) -> dict:
        """
        9개 OBJECT property dict 반환.

        area       : bbox 내 비투명(0-9) 셀 수
        color      : {0: bool, …, 9: bool}
        contents   : bbox 2D 색배열 (투명=13) — GRID.contents 의 object 판.
                     shape(형태 1/-1)·coordinate(셀 좌표목록)와 다른 *색* 정보.
        coordinate : [[row, col], …] — 비투명 셀의 절대 좌표 목록
        method     : {"univalued": bool, "diagonal": bool, "without_bg": bool}
        position   : left_top / right_top / left_bottom / right_bottom
        shape      : bbox 2D array, 비투명=1, 투명=-1
        size       : {"height": int, "width": int}
        symmetry   : {hori_symm / verti_symm / diag_symm / anti_symm}
        """
        h = len(self.colorgrid)
        w = len(self.colorgrid[0]) if self.colorgrid else 0
        row_min, col_min = self.pos

        # color
        color_dict = {i: False for i in range(10)}
        for row in self.colorgrid:
            for cell in row:
                if 0 <= cell <= 9:
                    color_dict[cell] = True

        # coordinate (절대 좌표)
        coordinate = [
            [row_min + r, col_min + c]
            for r, row in enumerate(self.colorgrid)
            for c, cell in enumerate(row)
            if cell != 13
        ]

        # shape: 비투명=1, 투명=-1
        shape = [
            [1 if cell != 13 else -1 for cell in row]
            for row in self.colorgrid
        ]

        # area
        area = sum(1 for row in shape for v in row if v == 1)

        # position
        position = {
            "left_top":     {"row_index": row_min,         "col_index": col_min},
            "right_top":    {"row_index": row_min,         "col_index": col_min + w - 1},
            "left_bottom":  {"row_index": row_min + h - 1, "col_index": col_min},
            "right_bottom": {"row_index": row_min + h - 1, "col_index": col_min + w - 1},
        }

        # symmetry
        hori_symm  = self._hori_symmetry(self.colorgrid)
        verti_symm = self._verti_symmetry(self.colorgrid)
        if h == w:
            diag_symm = self._diag_symmetry(self.colorgrid)
            anti_symm = self._anti_symmetry(self.colorgrid)
        else:
            diag_symm = False
            anti_symm = False

        return {
            "area":       area,
            "color":      color_dict,
            "contents":   [row[:] for row in self.colorgrid],   # bbox 색배열 (투명=13)
            "coordinate": coordinate,
            "position":   position,
            "shape":      shape,
            "size":       {"height": h, "width": w},
            "symmetry": {
                "hori_symm":  hori_symm,
                "verti_symm": verti_symm,
                "diag_symm":  diag_symm,
                "anti_symm":  anti_symm,
            },
        }

    def save(self, semantic_memory_root: str):
        """to_json()을 E_O{o}.json으로 기록하고, 하위 Pixel도 모두 save."""
        folder = node_id_to_folder_path(self.node_id, semantic_memory_root)
        os.makedirs(folder, exist_ok=True)
        path = id_to_json_path(self.node_id, semantic_memory_root)
        with open(path, "w") as f:
            json.dump({"id": self.node_id, "result": self.to_json()}, f, indent=2)
        for pixel in self.pixels:
            pixel.save(semantic_memory_root)

    def __repr__(self) -> str:
        return (f"Object(id={self.node_id}, color={self.color}, "
                f"pos={self.pos}, pixels={len(self.pixels)})")
