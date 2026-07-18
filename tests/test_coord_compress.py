# tests/test_coord_compress.py
"""회귀: flat(non-grid) compress 브릿지 coord-aware — §2b(비-이동 재채색 답은 안 바뀜) 차단.

Task4 이후 pixel coloring 은 ref("coord",[r,c]) 리터럴로도 emit 된다(program_ast.py). 그런데
`arbor.reasoning.antiunify._STEP` 정규식은 `VAR.coord`(pixel provenance) 형만 인식하고 coord
리터럴 `coloring(..., (r, c), color)`는 못 읽어 `parse_program`이 None을 낸다. 그 결과:
  - `compress._blob_program`의 flat(non-grid) 분기가 coord 프로그램을 blobify 못 함
  - `generalize._op_generalize`의 compress 판정(`compressible(progs)`)이 coord op-수-불일치를
    못 잡아 needs-compress 신호 없이 곧장 `generalized: failed`로 떨어짐(§2b 위반 — 스켈레톤 없는
    flat 재채색 태스크가 pair 마다 다른 셀 수를 바꾸면 실패해선 안 됨).

여기서는 AST 기반(coord-aware) 수정이 두 지점 모두를 고친다는 것을 고정한다.
"""
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.reasoning import program_ast as PA
from procedural_memory.operators import compress as CG
from procedural_memory.operators.generalize import _op_generalize
from soar.wm import WorkingMemory


def _flat_coord(cells_colors):
    """[(   (r,c), color), ...] → flat(non-grid) coord AST-json (Task4 emit 형)."""
    body = [PA.step("coloring", target=PA.ref("coord", PA.const(list(rc))), color=PA.const(col))
            for rc, col in cells_colors]
    return PA.program(body)


class TestBlobProgramFlatCoord(unittest.TestCase):
    """`_blob_program`의 flat 분기가 coord 리터럴 program 도 cellset blob 으로 묶는지."""

    def test_flat_coord_program_produces_cellset_blob(self):
        # 3칸 재채색, 전부 4-인접(같은 행) → 한 덩어리
        ast = _flat_coord([((0, 0), 5), ((0, 1), 5), ((0, 2), 5)])
        out_json = CG._blob_program(json.dumps(ast), W=3)
        self.assertIsNotNone(out_json, "flat coord program 이 blobify 되지 않음(coord-blind 회귀)")
        out = json.loads(out_json)
        self.assertTrue(all(s["args"]["target"]["ref"] == "cellset" for s in out["body"]))
        self.assertEqual(len(out["body"]), 1)                       # 3셀이 4-인접 한 덩어리로
        blob_cells = sorted(out["body"][0]["args"]["target"]["cells"]["const"])
        self.assertEqual(blob_cells, [0, 1, 2])                     # (0,0),(0,1),(0,2) → idx 0,1,2 (W=3)

    def test_flat_coord_two_disjoint_blobs(self):
        # 인접하지 않은 두 좌표 → 별개 덩어리 2개(연결성=1차 술어 확인)
        ast = _flat_coord([((0, 0), 5), ((2, 2), 7)])
        out = json.loads(CG._blob_program(json.dumps(ast), W=3))
        self.assertEqual(len(out["body"]), 2)
        self.assertTrue(all(s["args"]["target"]["ref"] == "cellset" for s in out["body"]))


class TestGeneralizeCoordCompressDecision(unittest.TestCase):
    """`_op_generalize`의 compress 판정이 flat coord op-수-불일치를 잡아 needs-compress 를 신호하는지."""

    def _ag(self, asts, train):
        wm = WorkingMemory()
        pairs = []
        for k, ast in enumerate(asts):
            pid = f"Tc.P{k}"
            wm.add(f"{pid}.property", "program", json.dumps(ast))
            pairs.append(types.SimpleNamespace(node_id=pid))
        root = types.SimpleNamespace(node_id="Tc", example_pairs=pairs)
        return types.SimpleNamespace(
            wm=wm, kg={"arckg_root": root}, task={"train": train},
            stack=[types.SimpleNamespace(id="S1")])

    def test_flat_coord_op_count_mismatch_triggers_needs_compress(self):
        # pair A: 2 셀 재채색, pair B: 3 셀 재채색 — 스켈레톤 없는(non-grid-wrapped) flat coord program
        ast_a = _flat_coord([((0, 0), 5), ((0, 1), 5)])
        ast_b = _flat_coord([((0, 0), 5), ((0, 1), 5), ((0, 2), 5)])
        train = [
            {"input": [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "output": [[5, 5, 0], [0, 0, 0], [0, 0, 0]]},
            {"input": [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "output": [[5, 5, 5], [0, 0, 0], [0, 0, 0]]},
        ]
        ag = self._ag([ast_a, ast_b], train)
        _op_generalize(ag)
        self.assertTrue(ag.wm.contains("S1", "needs-compress", "yes"),
                         "op 수 불일치 flat coord program 이 needs-compress 를 신호하지 않음(§2b 회귀)")
        self.assertFalse(ag.wm.contains("S1", "generalized", "failed"),
                          "compress 시도도 없이 곧장 generalized:failed 로 떨어짐(§2b 위반)")

    def test_flat_coord_same_op_count_does_not_force_compress(self):
        # 대조군: op 수가 같으면(2==2) antiunify_ast 가 바로 성공해야 하고, compress 신호는 없어야 함
        ast_a = _flat_coord([((0, 0), 5), ((0, 1), 5)])
        ast_b = _flat_coord([((1, 0), 5), ((1, 1), 5)])
        train = [
            {"input": [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "output": [[5, 5, 0], [0, 0, 0], [0, 0, 0]]},
            {"input": [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "output": [[0, 0, 0], [5, 5, 0], [0, 0, 0]]},
        ]
        ag = self._ag([ast_a, ast_b], train)
        _op_generalize(ag)
        self.assertTrue(ag.wm.contains("S1", "generalized", "yes"))
        self.assertFalse(ag.wm.contains("S1", "needs-compress", "yes"))


if __name__ == "__main__":
    unittest.main()
