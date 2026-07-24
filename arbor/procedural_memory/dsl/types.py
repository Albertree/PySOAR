# -*- coding: utf-8 -*-
"""
DSL 타입 어휘 — 이 시스템의 DSL(property/relation/..)이 반환하는 값의 타입을 **한 곳에** 정의.

원칙:
  · Scalar(atomic)    = 더 못 쪼개는 단일값.
  · Compound          = number 묶음. accessor 로 atomic 을 투영한다(일관 규칙).
                        coordinate{row,col}→row_of/col_of · size{height,width}→height_of/width_of
  · Collection        = 원소의 모음.
  · class             = 불투명 구조값(2D 배열·다필드 번들). 내부는 전용 accessor 로만 꺼낸다.

`python -m arbor.procedural_memory.dsl.types` 로 어휘 + 실제 사용 현황을 한눈에 본다.
"""
from __future__ import annotations

# ── Scalar (atomic) ─────────────────────────────────────────
NUMBER = "number"    # 정수: area·height·width·row·col·count
COLOR = "color"      # 색 값 (0..9). number 와 구별한다.
BOOLEAN = "boolean"  # 참/거짓: 대칭축
SYMBOL = "symbol"    # 열거 라벨: type_of(task/pair/..) · subtype_of(example/test/input/output)

# ── Compound (number 묶음 — accessor 로 투영) ───────────────
COORDINATE = "coordinate"  # {row, col}       → row_of / col_of
SIZE = "size"              # {height, width}  → height_of / width_of

# ── Collection ──────────────────────────────────────────────
COLOR_SET = "color_set"            # {0..9: bool} 색 presence  (= set of color)
COORDINATE_SET = "coordinate_set"  # [[r,c], ..]                (= set of coordinate)

# ── Opaque structured ───────────────────────────────────────
CLASS = "class"  # 불투명 구조값: contents·shape(2D 배열) · position·symmetry·role(다필드 번들)

# 카테고리별 어휘 (표시/검증용)
SCALARS = [NUMBER, COLOR, BOOLEAN, SYMBOL]
COMPOUNDS = [COORDINATE, SIZE]
COLLECTIONS = [COLOR_SET, COORDINATE_SET]
OPAQUE = [CLASS]
ALL = SCALARS + COMPOUNDS + COLLECTIONS + OPAQUE


def types_in_use() -> dict:
    """SPECS 를 훑어 실제 DSL 이 선언한 반환타입(out) → 그 타입을 쓰는 DSL 이름 목록."""
    from arbor.procedural_memory.dsl.registry import SPECS
    used: dict = {}
    for name, s in SPECS.items():
        for t in str(s.get("out", "")).split("|"):
            used.setdefault(t.strip(), []).append(name)
    return used


def _report() -> str:
    used = types_in_use()
    lines = ["=== DSL 타입 어휘 (정의) ==="]
    for cat, members in [("Scalar", SCALARS), ("Compound", COMPOUNDS),
                         ("Collection", COLLECTIONS), ("Opaque", OPAQUE)]:
        lines.append(f"  [{cat}] " + " · ".join(members))
    lines.append("\n=== 실제 사용 현황 (SPECS.out) ===")
    for t in sorted(used):
        mark = "" if t in ALL else "  (!) 어휘밖"
        lines.append(f"  {t:16} ({len(used[t]):2}) {', '.join(sorted(used[t])[:6])}"
                     f"{' ..' if len(used[t]) > 6 else ''}{mark}")
    unused = [t for t in ALL if t not in used]
    if unused:
        lines.append(f"\n  (정의됐지만 미사용: {', '.join(unused)})")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_report())
