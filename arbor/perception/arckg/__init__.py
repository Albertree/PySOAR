"""
ARCKG — Knowledge Graph 패키지.

Public interface:
    compare  — 두 KG 노드를 비교해 relation edge를 생성한다
"""

from .comparison import compare

__all__ = ["compare"]
