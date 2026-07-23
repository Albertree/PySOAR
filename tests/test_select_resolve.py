# -*- coding: utf-8 -*-
"""P2 Phase 2a Task3: resolve + execute 의 select-var 지원 (cellset 동치, additive).

move000a 의 두 train pair 로부터 **cellset 스켈레톤**과 **select 스켈레톤**을 (같은 좌표 데이터로)
각각 anti-unify → resolve_slot → execute 한다. select-var 경로의 산출 grid 가 cellset-var 경로와
**완전히 동일**함을 pin 한다(index-vs-coord 표현만 다르고 의미는 같음). 둘 다 실제 train 출력과도 일치.
"""
import json
import unittest

from arbor.reasoning import program_ast as PA
from arbor.reasoning import antiunify as AU

_TRAIN = json.load(open("data/ARC_human/move/move000a.json"))["train"]


def _cellset_ops(p):
    """train pair 를 재현하는 (sorted_pixel_indices, out_color) op 목록 (출력색 순 결정적)."""
    gi, go = p["input"], p["output"]
    W = len(gi[0])
    by = {}
    for r in range(len(gi)):
        for c in range(len(gi[0])):
            if gi[r][c] != go[r][c]:
                by.setdefault(go[r][c], []).append(r * W + c)
    return [(sorted(cells), col) for col, cells in sorted(by.items())]


def _cellset_ast(p):
    body = [PA.step("coloring", target=PA.cellset(PA.const(cells)), color=PA.const(col))
            for cells, col in _cellset_ops(p)]
    return PA.program(body)


def _select_ast(p):
    W = len(p["input"][0])
    body = []
    for cells, col in _cellset_ops(p):
        coords = [[ix // W, ix % W] for ix in cells]
        body.append(PA.step("coloring",
                            target=PA.coordinate_of(PA.select("input", "pixel",
                                     PA.coord_in("pixel_coordinate", coords))),
                            color=PA.const(col)))
    return PA.program(body)


def _resolve_choice(slots):
    """모든 slot 을 resolve → 각 slot survivor[0] 을 고른 choice dict (없으면 KeyError 로 실패)."""
    choice = {}
    for name, slot in slots.items():
        surv, _tried = AU.resolve_slot(slot, _TRAIN, _TRAIN[0]["input"])
        assert surv, f"no survivor for {name}: {slot}"
        choice[name] = surv[0][1]
    return choice


class TestSelectResolve(unittest.TestCase):
    def test_resolve_cellset_accepts_coord_pairs(self):
        # select-body slot: values 원소가 (r,c) 좌표쌍이어도 resolve 가 처리(예전엔 idx//W 로 TypeError).
        slot = {"kind": "cellset", "pos": 0, "values": [[[3, 2]], [[6, 0]]]}
        surv, _ = AU.resolve_slot(slot, _TRAIN, _TRAIN[0]["input"])
        self.assertTrue(surv)

    def test_select_var_equivalent_to_cellset_var(self):
        cellset_asts = [_cellset_ast(p) for p in _TRAIN]
        select_asts = [_select_ast(p) for p in _TRAIN]
        sk_c, slots_c = PA.antiunify_ast(cellset_asts, force_slots=True)
        sk_s, slots_s = PA.antiunify_ast(select_asts, force_slots=True)
        self.assertIsNotNone(sk_c)
        self.assertIsNotNone(sk_s)
        # select 스켈레톤엔 cellset ref 가 없어야(순수 select 표현)
        self.assertNotIn('"cellset"', json.dumps(sk_s))

        choice_c = _resolve_choice(slots_c)
        choice_s = _resolve_choice(slots_s)
        for p in _TRAIN:
            g0 = p["input"]
            out_c = PA.execute(sk_c, g0, choice_c)
            out_s = PA.execute(sk_s, g0, choice_s)
            self.assertEqual(out_s, out_c)          # 동치 pin
            self.assertEqual(out_s, p["output"])    # 실제 train 출력과도 일치


if __name__ == "__main__":
    unittest.main()
