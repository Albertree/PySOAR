import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# rot90 을 요구하는 train: input 을 시계방향 90도 회전하면 output.
_ROT_TRAIN = [
    {"input": [[1, 2], [3, 4]], "output": [[3, 1], [4, 2]]},
    {"input": [[5, 6], [7, 8]], "output": [[7, 5], [8, 6]]},
]


class TestTransformSearchOp(unittest.TestCase):
    def test_body_writes_hypotheses_and_survivor(self):
        from procedural_memory.operators.transform_search import _op_transform_search

        class WM:
            def __init__(self): self.t = []
            def add(self, i, a, v): self.t.append((i, a, v))
        class AG:
            def __init__(self):
                self.wm = WM()
                self.stack = [type("S", (), {"id": "s1"})()]
                self.task = {"train": _ROT_TRAIN}
        ag = AG()
        # superstate 를 다른 식별자("root")로 둬서 s ≠ superstate(s) 를 구분 가능하게 한다.
        ag.wm.t.append(("s1", "superstate", "root"))
        _op_transform_search(ag)

        hyps = [v for (i, a, v) in ag.wm.t if a == "hypothesis"]
        self.assertTrue(hyps)                                   # 후보 물질화(§1-5)
        # 모든 hypothesis WME 는 operator 가 도는 상태 s(=s1)에 붙어야 한다.
        self.assertTrue(all(i == "s1" for (i, a, v) in ag.wm.t if a == "hypothesis"))

        # survivor placement: transform-survivor 는 s(=s1)에 붙고 superstate("root")로 새면 안 된다.
        surv = [(i, v) for (i, a, v) in ag.wm.t if a == "transform-survivor"]
        self.assertTrue(surv)
        self.assertTrue(any("rot90" in v for (i, v) in surv))
        self.assertTrue(all(i == "s1" for (i, v) in surv),
                        "transform-survivor 는 조부모(superstate)가 아니라 s 에 붙어야 한다")

        # answer-ready 도 s(=s1)에 — 조부모("root")로 escape 하면 게이트가 무력화된다(리뷰 Critical).
        ar_ids = [i for (i, a, v) in ag.wm.t if a == "answer-ready"]
        self.assertIn("s1", ar_ids)
        self.assertNotIn("root", ar_ids)

    def test_json_loads_in_productions(self):
        from procedural_memory.loader import PRODUCTIONS
        names = [p.name for p in PRODUCTIONS]
        self.assertIn("propose*transform_search", names)
        self.assertIn("apply*transform_search", names)

    def test_real_agent_places_results_on_running_state_not_superstate(self):
        """실제 soar.Agent 커널로 propose/apply 를 돌려, 결과가 operator 가 실행된 상태(S2)에
        붙고 superstate(S1)로 새지 않음을 검증한다. transform_search 는 substate 를 push 하지
        않으므로 s 자신이 synthesize 가 ^transform-search-open 을 쓴 부모다."""
        from soar import Agent
        from soar.decide import ImpasseType
        from procedural_memory.loader import PRODUCTIONS
        from procedural_memory.operators import OPERATOR_BODIES

        ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES)
        ag.task = {"train": _ROT_TRAIN, "test": [{"input": [[1, 2], [3, 4]]}]}
        ag.kg = {}
        # S1(top) 아래 S2 substate 를 만들어 진짜 2-레벨 goal stack 을 구성한다.
        # synthesize 는 GRID goal 을 보유한 상태(=여기 S2)에 ^transform-search-open 을 쓴다.
        s1 = ag.stack[0]
        s2 = ag.create_substate(s1, ImpasseType.SNC, "state", [])
        self.assertEqual(s1.id, "S1")
        # superstate(S2) 는 S1 이어야 한다(구분 가능).
        self.assertIn(("S2", "superstate", "S1"), set(ag.wm))
        ag.wm.add(s2.id, "transform-search-open", "yes")

        # 한 decision cycle: S1 은 SNC 로 S2 로 하강, S2 에서 transform_search 선택+적용.
        ag.step()

        wm = set(ag.wm)
        # survivor/answer-ready 는 S2(실행 상태)에 붙어야 한다.
        surv = [(i, v) for (i, a, v) in wm if a == "transform-survivor"]
        self.assertTrue(surv, "transform-survivor 가 생성되지 않음 (rot90 생존 실패?)")
        self.assertTrue(all(i == "S2" for (i, v) in surv))
        self.assertTrue(any("rot90" in v for (i, v) in surv))
        # answer-ready 는 S2 에만, S1(superstate)로 escape 하면 안 된다.
        self.assertIn("S2", [i for (i, a, v) in wm if a == "answer-ready"])
        self.assertNotIn("S1", [i for (i, a, v) in wm if a == "answer-ready"])
        # hypothesis 물질화도 S2 에.
        self.assertTrue(any(a == "hypothesis" and i == "S2" for (i, a, v) in wm))


if __name__ == "__main__":
    unittest.main()
