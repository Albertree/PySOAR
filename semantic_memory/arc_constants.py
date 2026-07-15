# -*- coding: utf-8 -*-
"""arc-dsl 방향벡터/스칼라 상수 — arg 탐색(§3-3 ③)이 가설 생성에 쓰는 상수 어휘.
constants.py(원본 arc-dsl) 의 방향벡터·정수 상수를 dict 로 노출. 계산으로 도출하지
않는(=탐색으로 도출해야 하는) "이름 붙은 후보" 목록일 뿐 — 여기 자체가 답을 내지 않는다."""

DIRECTIONS = {
    "DOWN": (1, 0), "RIGHT": (0, 1), "UP": (-1, 0), "LEFT": (0, -1),
    "ORIGIN": (0, 0), "UNITY": (1, 1), "NEG_UNITY": (-1, -1),
    "UP_RIGHT": (-1, 1), "DOWN_LEFT": (1, -1),
}

SCALARS = {f"N{i}": i for i in range(11)}
