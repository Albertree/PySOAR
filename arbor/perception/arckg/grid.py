"""
GRID node — PAIR 아래 한 격자.
Node ID 형식: T{hex}.P{p}.G{g}  (G0=input, G1=output)
"""

import json
import os

from .memory_paths import id_to_json_path, node_id_to_folder_path
from arbor.perception.spelke import spelke_arckg_objects
from .object import Object
from .pixel import Pixel


class Grid:
    """
    INTENT: 2D 정수 격자와 그 격자에서 추출된 Object 목록을 보유하는 KG 노드.
            to_json()으로 E_G{g}.json 속성 파일을 기록한다.
    MUST NOT: object-level 관계 추론을 여기서 수행하지 마 (OBJECT 레이어 책임).
    REF: ARC-solver/ARCKG/grid.py GRID (line 14)
    """

    def __init__(self, grid_id: str, raw: list):
        self.node_id = grid_id
        self.raw = raw
        self.objects: list = []
        self.pixels: list = []   # grid-level Pixel 노드 (절대 좌표 기준)

    @property
    def height(self) -> int:
        return len(self.raw)

    @property
    def width(self) -> int:
        return len(self.raw[0]) if self.raw else 0

    def extract_objects(self):
        """
        INTENT: spelke 객체검출(4-conn 동색 ∪ 같은색 8-conn 합집합)로 고유 Object 를
                self.objects / self.pixels 에 저장한다. 각 object 는 connectivity(4/8-conn) 를 보유.
                (2026-07-19) hodel 8-method(count/max·bg 특권화)를 폐지하고 spelke 로 통일.
        """
        if self.height == 0 or self.width == 0:
            self.objects = []
            self.pixels = []
            return

        self.objects = []
        self.pixels = []
        grid_pixel_seen: set = set()   # 동일 (r,c) grid-level Pixel 중복 방지

        for obj_idx, data in enumerate(spelke_arckg_objects(self.raw)):
            object_id = f"{self.node_id}.O{obj_idx}"
            obj = Object(
                object_id=object_id,
                colorgrid=data["colorgrid"],
                pos=data["pos"],
                method=data["method"],
            )

            # Object-level Pixel: 행-열 순 정렬
            sorted_pixels = sorted(data["obj"], key=lambda x: (x[1][0], x[1][1]))
            for pix_idx, (color, (r, c)) in enumerate(sorted_pixels):
                obj_pixel_id = f"{object_id}.X{pix_idx}"
                obj.pixels.append(
                    Pixel(pixel_id=obj_pixel_id, color=color, row=r, col=c)
                )

                # Grid-level Pixel: 행-우선 인덱스, 중복 없이
                grid_pixel_idx = r * self.width + c
                if grid_pixel_idx not in grid_pixel_seen:
                    grid_pixel_seen.add(grid_pixel_idx)
                    grid_pixel_id = f"{self.node_id}.X{grid_pixel_idx}"
                    self.pixels.append(
                        Pixel(pixel_id=grid_pixel_id, color=color,
                              row=r, col=c)
                    )

            self.objects.append(obj)

    def to_json(self) -> dict:
        """
        GRID property 3개:
          size     : {"height": int, "width": int}
          color    : {0: bool, …, 9: bool}
          contents : 2D int array
        REF: ARC-solver/ARCKG/grid.py GRID.update_property (line 209-222)
        """
        color_dict = {i: False for i in range(10)}
        for row in self.raw:
            for val in row:
                if 0 <= val <= 9:
                    color_dict[val] = True

        return {
            "size": {
                "height": self.height,
                "width": self.width,
            },
            "color": color_dict,
            "contents": self.raw,
        }

    def save(self, semantic_memory_root: str):
        """E_G{g}.json 기록 후 하위 Object / Pixel 모두 재귀 save."""
        folder = node_id_to_folder_path(self.node_id, semantic_memory_root)
        os.makedirs(folder, exist_ok=True)
        path = id_to_json_path(self.node_id, semantic_memory_root)
        with open(path, "w") as f:
            json.dump({"id": self.node_id, "result": self.to_json()}, f, indent=2)

        for obj in self.objects:
            obj.save(semantic_memory_root)

        for pixel in self.pixels:
            pixel.save(semantic_memory_root)

    def __repr__(self) -> str:
        return (f"Grid(id={self.node_id}, "
                f"size={self.height}×{self.width}, "
                f"objects={len(self.objects)})")
