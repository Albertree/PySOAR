# tests/test_compress_select_emit.py
"""P2b Task5 회귀 고정: compress 가 cellset 대신 select(pixel,coord_in) 을 emit 하는지.

_object_change_program(g0, g1, W) 결과 JSON 은
  - "cellset" 을 포함하지 않아야 하고(더 이상 cellset 을 emit 하지 않음)
  - "select" 를 포함해야 하며(coordinate_of(select("input","pixel",coord_in(...))) target)
  - execute(ast, g0) == g1 이어야 한다(실행 결과는 cellset 시절과 동치).

move000a(실제 train pair, 객체 이동)로 고정 — Phase 2a 가 증명한 select≡cellset 동치를
compress 의 실제 emit 경로에서도 검증한다.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.reasoning import program_ast as PA
from arbor.procedural_memory.operators import compress as CG


def _load_move000a_pair0():
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "ARC_human", "move", "move000a.json")) as f:
        d = json.load(f)
    p = d["train"][0]
    return p["input"], p["output"]


class TestObjectChangeProgramEmitsSelect(unittest.TestCase):
    def test_no_cellset_has_select_and_executes_to_g1(self):
        g0, g1 = _load_move000a_pair0()
        W = len(g0[0])
        result = CG._object_change_program(g0, g1, W)
        self.assertIsNotNone(result, "move000a pair0 은 객체 변화가 있어야 program 을 내야 함")
        self.assertNotIn('"cellset"', result, "compress 가 여전히 cellset 을 emit 함(P2b 미완)")
        self.assertIn('"select"', result, "compress 가 select target 을 emit하지 않음")
        ast = json.loads(result)
        out = PA.execute(ast, g0)
        self.assertEqual(out, g1, "select-target 실행 결과가 cellset 시절 산출(g1)과 달라짐")


if __name__ == "__main__":
    unittest.main()
