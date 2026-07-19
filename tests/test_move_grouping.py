# tests/test_move_grouping.py
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning import program_ast as PA
from arbor.reasoning import antiunify as AU
from procedural_memory.operators import compress as CG


class TestGridBlobAntiunify(unittest.TestCase):
    def _grid_blob(self, cells, col):
        b = [PA.step("coloring", target=PA.cellset(PA.const(cells)), color=PA.const(col))]
        return PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                               PA.contents_program(b))

    def test_grid_with_blob_contents_recurses(self):
        a = self._grid_blob([7, 8], 3)
        b = self._grid_blob([20, 21], 3)          # 같은 색, cellset DIFF
        sk, slots = PA.antiunify_ast([a, b])
        self.assertIsNotNone(sk)
        parts = {s["call"]: s["args"] for s in sk["body"]}
        inner = parts["set_grid_contents"]["contents"]["program"]["body"]
        self.assertEqual(inner[0]["args"]["target"]["ref"], "cellset")
        self.assertTrue(any(k.startswith("?c.cells") for k in slots))


class TestGridInnerCounts(unittest.TestCase):
    def _grid_pixel(self, idxs):
        b = [PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(0)) for i in idxs]
        return PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                               PA.contents_program(b))

    def test_grid_inner_op_counts_reads_contents_length(self):
        self.assertEqual(PA.grid_inner_op_counts(self._grid_pixel([1, 2, 3])), [3])

    def test_grid_inner_op_counts_none_for_nongrid(self):
        flat = PA.program([PA.step("coloring", target=PA.ref("pixel", PA.const(1)), color=PA.const(0))])
        self.assertIsNone(PA.grid_inner_op_counts(flat))


class TestCompressGridWrapped(unittest.TestCase):
    def test_grid_pixel_program_compresses_inner_keeps_wrapper(self):
        # 잔여 4셀(=2셀 객체 이동): W=5. 나간자리 idx 0,1(색0); 들어온자리 idx 12,13(색3)
        inner = [PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(c))
                 for i, c in [(0, 0), (1, 0), (12, 3), (13, 3)]]
        gp = PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                             PA.contents_program(inner))
        out = json.loads(CG._blob_program(json.dumps(gp), 5))
        parts = {s["call"]: s["args"] for s in out["body"]}
        self.assertIn("set_grid_size", parts)                 # 래퍼 유지
        blob_body = parts["set_grid_contents"]["contents"]["program"]["body"]
        self.assertTrue(all(s["args"]["target"]["ref"] == "cellset" for s in blob_body))
        self.assertEqual(len(blob_body), 2)                   # 2 덩어리(나간/들어온)

    def test_op_compress_reaches_grid_branch_live(self):
        """_op_compress 호출 경로(라이브)가 grid 분기에 도달함을 회귀-고정: WM 의 grid>pixel
        PAIR.program 을 넣고 operator body 를 돌리면 grid>blob 이 새 `grouping` slot 에 기록돼야
        한다(PAIR.program 은 픽셀 그대로 유지 — Task 3). (call-site 가 raw 대신 as_source(raw)=납작한
        텍스트를 넘기던 버그면 grid 미탐지→스킵→grouping 미생성으로 FAIL.)"""
        import types
        from soar.wm import WorkingMemory
        inner = [PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(c))
                 for i, c in [(0, 0), (1, 0), (12, 3), (13, 3)]]
        gp = PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                             PA.contents_program(inner))
        ppid = "Tx.P0.property"
        wm = WorkingMemory()
        wm.add(ppid, "program", json.dumps(gp))
        pair = types.SimpleNamespace(node_id="Tx.P0")
        root = types.SimpleNamespace(example_pairs=[pair])
        ag = types.SimpleNamespace(
            wm=wm, kg={"arckg_root": root},
            task={"train": [{"input": [[0] * 5]}]},           # W=5 (grid 폭만 사용)
            stack=[types.SimpleNamespace(id="S1")])
        CG._op_compress(ag)
        still_pixel = json.loads(next(v for (i, a, v) in wm if i == ppid and a == "program"))
        self.assertEqual(still_pixel, gp)                     # PAIR.program 은 그대로(픽셀) 유지
        out = json.loads(next(v for (i, a, v) in wm if i == ppid and a == "grouping"))
        parts = {s["call"]: s["args"] for s in out["body"]}
        blob_body = parts["set_grid_contents"]["contents"]["program"]["body"]
        self.assertTrue(all(s["args"]["target"]["ref"] == "cellset" for s in blob_body))
        self.assertEqual(len(blob_body), 2)                   # grid>blob 로 압축됨 = 분기 도달
        self.assertEqual(ag.kg["compress"]["n_pairs"], 1)     # 이 pair 가 실제로 재작성됨

    def test_blob_program_flat_pixel_path_unwrapped(self):
        """flat pixel program(그리드 래퍼 없음)은 여전히 래퍼 없는 flat blob 으로(경로 보존)."""
        flat = PA.program([PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(c))
                           for i, c in [(0, 0), (1, 0), (12, 3), (13, 3)]])
        out = json.loads(CG._blob_program(json.dumps(flat), 5))
        calls = [s["call"] for s in out["body"]]
        self.assertNotIn("set_grid_size", calls)              # 래퍼 없음(flat 유지)
        self.assertTrue(all(s["args"]["target"]["ref"] == "cellset" for s in out["body"]))
        self.assertEqual(len(out["body"]), 2)                 # 2 덩어리


class TestResolveCellsetRigidDelta(unittest.TestCase):
    def _pair(self, grid_in, dest_cells):
        return {"input": grid_in, "output": grid_in}       # output 미사용(dest 는 vals 로 전달)

    def test_relative_offset_resolves_rigidly(self):
        # 3x5 grid, 소스객체=색3 두 셀 (0,0),(0,1)=idx0,1. dest= +2행 이동 → (2,0),(2,1)=idx10,11
        g0 = [[3,3,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]
        g1 = [[3,3,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]           # 두번째 pair: 같은 오프셋, 다른 위치는 아래서
        train = [{"input": g0, "output": g1}, {"input": g0, "output": g1}]
        comps = [AU._components(e["input"]) for e in train]
        sels = AU._selectors(comps)
        vals = [[10, 11], [10, 11]]                          # +2행 dest (relative)
        slot = {"kind": "cellset", "pos": 0, "values": vals}
        survivors, tried = AU.resolve_slot(slot, train)
        self.assertTrue(survivors, f"no survivor; tried={tried}")
        cells = survivors[0][1](g0)
        self.assertEqual(sorted(cells), [10, 11])            # G0 에 적용 시 dest 재현

    def test_relative_offset_survives_only_new_impl(self):
        """판별 케이스(브리프 원 예제는 3행 격자라 dest row(2)==H-1 과 우연히 겹쳐 구 canonical
        placement(bottom anchor)로도 통과 — 회귀만으론 구현 교체를 증명 못 함. 여기서는 6행 격자로
        dest row(3) 를 top(0)·bottom(H-1=5)·keep(r0=0) 어디와도 안 겹치게 해 진짜 relative-Δ(r0+3 류)
        만 재현 가능하게 만든다: 구현 전엔 survivor 없음(probe 로 확인), 구현 후엔 존재해야 함."""
        g0 = [[3, 3, 0, 0, 0],
              [0, 0, 0, 0, 0],
              [0, 0, 0, 0, 0],
              [0, 0, 0, 0, 0],
              [0, 0, 0, 0, 0],
              [0, 0, 0, 0, 0]]
        train = [{"input": g0, "output": g0}, {"input": g0, "output": g0}]
        vals = [[15, 16], [15, 16]]                          # dest row3,col0-1 (H=6,W=5)
        slot = {"kind": "cellset", "pos": 0, "values": vals}
        survivors, tried = AU.resolve_slot(slot, train)
        self.assertTrue(survivors, f"no survivor; tried={tried}")
        cells = survivors[0][1](g0)
        self.assertEqual(sorted(cells), [15, 16])


class TestCornerPrior(unittest.TestCase):
    """canonical 코너 prior: 두 pair 의 dest 앵커가 우연히 같아 상수가 fit 해도(few-shot),
    구조식 H-h/W-w 를 우선 채택해 test 격자로 일반화한다 (move000q/r 회귀 근거)."""
    def _grid(self, obj_r, obj_c):
        g = [[0] * 6 for _ in range(6)]
        for dr in range(2):
            for dc in range(2):
                g[obj_r + dr][obj_c + dc] = 3
        return g

    def test_br_corner_prefers_H_minus_h_over_coincidental_constant(self):
        g0a, g0b = self._grid(0, 0), self._grid(1, 2)         # 2x2 객체, 서로 다른 출발
        # dest = 우하단 코너 (4,4)~(5,5) = idx 28,29,34,35 (양 pair 동일 → 상수 (4,4) 도 fit)
        vals = [[28, 29, 34, 35], [28, 29, 34, 35]]
        train = [{"input": g0a, "output": g0a}, {"input": g0b, "output": g0b}]
        slot = {"kind": "cellset", "pos": 0, "values": vals}
        survivors, tried = AU.resolve_slot(slot, train)
        self.assertTrue(survivors, f"no survivor; tried={tried}")
        self.assertIn("H-h", survivors[0][0])                 # 코너 구조식 우선(상수 아님)
        self.assertIn("W-w", survivors[0][0])


class TestObjectMoveProgram(unittest.TestCase):
    """대응 기반 전체-객체 복원: 객체가 원위치와 겹쳐 이동해도 잔여(부분)가 아니라 전체 객체를 잡는다."""
    def test_full_object_recovered_on_overlap(self):
        # 3x4, 2셀 객체 (0,0),(0,1) → +1col (0,1),(0,2). 겹침 (0,1). 잔여는 [0],[2] 뿐이나 전체는 [0,1],[1,2].
        g0 = [[3, 3, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        g1 = [[0, 3, 3, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        prog = CG._object_move_program(g0, g1, 4)
        self.assertIsNotNone(prog)
        inner = json.loads(prog)["body"][2]["args"]["contents"]["program"]["body"]
        cellsets = [sorted(s["args"]["target"]["cells"]["const"]) for s in inner]
        self.assertIn([0, 1], cellsets)                       # 전체 source 객체 (부분 [0] 아님)
        self.assertIn([1, 2], cellsets)                       # 전체 dest 객체 (부분 [2] 아님)


class TestPropertySelectors(unittest.TestCase):
    """변화객체 비교 기반 선택자: 색/모양/크기가 각 grid 에서 유일하면 그 속성으로 mover 선택."""
    def test_color_selector_picks_unique_color_object(self):
        # 2 grid, 각기 색5(1셀)·색3(1셀). color=5 선택자는 색5 셀만.
        g0 = [[5, 0, 3], [0, 0, 0]]
        comps = AU._components(g0)
        sels = dict(AU._selectors([comps]))
        self.assertIn("color=5", sels)
        # 선택자는 이제 **매치 리스트**(모호 지원). 색5 유일 성분 하나 → [[(0,0)]].
        self.assertEqual(sels["color=5"](comps), [[(0, 0)]])   # 색5 유일 성분(리스트)
        self.assertEqual(sels["color=3"](comps), [[(0, 2)]])
