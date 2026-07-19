# -*- coding: utf-8 -*-
"""resolve_slot 이 grid-declarative slot(size/color of G1)에서 크래시하지 않는다.

size/color 는 _execute_grid 에서 실행에 안 쓰임(contents 가 산출 지배) → per-pair 리터럴이 달라
slot 이 되어도 답과 무관. resolve_slot 은 이를 입력관계로 일반화하고 survivor 를 돌려줘야 한다
(옛 버그: kind='size' 핸들러 없음 → dict//int; kind='color' dict 값 → unhashable). 순수 단위테스트."""
from arbor.reasoning.antiunify import resolve_slot

_TRAIN = [
    {"input": [[0, 6], [7, 8]], "output": [[0, 4], [6, 8]]},
    {"input": [[6, 8, 0]], "output": [[4, 6, 0]]},
]


def test_size_slot_does_not_crash():
    # 옛 버그: {'const':{'height','width'}} 값에 v//W → TypeError. 이제 survivor 반환.
    slot = {"kind": "size", "pos": "size",
            "values": [{"const": {"height": 2, "width": 2}}, {"const": {"height": 1, "width": 3}}]}
    survivors, tried = resolve_slot(slot, _TRAIN)
    assert survivors, "size slot 은 survivor 를 하나 이상 내야 함(선언적·크래시 금지)"


def test_grid_color_slot_does_not_crash():
    # 옛 버그: {'const':[...]} 값에 set(vals) → unhashable dict. 이제 survivor 반환.
    slot = {"kind": "color", "pos": "color",
            "values": [{"const": [0, 4, 6, 8]}, {"const": [0, 4, 6]}]}
    survivors, tried = resolve_slot(slot, _TRAIN)
    assert survivors, "grid color slot 은 survivor 를 하나 이상 내야 함(선언적·크래시 금지)"


def test_pixel_color_slot_still_int_path():
    # 회귀: pixel color slot(kind='color', 정수 값)은 기존 상수색 경로 그대로.
    slot = {"kind": "color", "pos": 1, "values": [4, 4]}
    survivors, tried = resolve_slot(slot, _TRAIN)
    assert any("const 4" in n for n, _ in survivors), "정수 color slot 은 상수색 survivor 유지"
