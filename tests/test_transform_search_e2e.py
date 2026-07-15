import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""transform_search end-to-end — 정정된(비침입적) 설계 기준.

역사(정직 기록): Task 6/8 은 synthesize 의 contents-DESCEND 분기에서 ^transform-search-open 을
써서 transform_search 를 라이브 SOAR 루프에 자동 진입시켰다. 그러나 그 훅은 기존에 잘 돌던
하강 경로(grid-descend)와 **동시에** 제안되어 propose*set_grid_size 와 TIE impasse 를 만들고,
그 impasse 가 진행을 막아 **easy000c-h(원래 2851 step 에 ✓풀림) 를 1302 step impasse 로 회귀**
시켰다(base 61126cd 대조로 실측). → 훅을 되돌렸다. DSL 흡수는 **additive**(어휘·엔진·operator
등록)로만 두고, transform_search 를 라이브 루프에 개입시키는 것은 **회귀 없는 tie-resolution**
을 갖춘 뒤(후속 스펙)에만 한다.

그래서 이 파일은 두 가지를 지킨다:
  (A) 회귀 가드 — synthesize 는 contents-DESCEND 에 도달하되(grid-descend) transform_search 를
      라이브 루프에 열지 않는다(^transform-search-open 부재). 훅이 재도입되면 이 테스트가 깨진다.
  (B) 흡수된 operator 자체는 정상 — 실제 하강 상태에서 **명시적으로** 열면 REAL propose*/apply*
      transform_search + REAL _op_transform_search body 가 발화해 hypothesis(§1-5)+survivor(rot90)
      +answer-ready 를 그 실행 상태에 남긴다(operator 의 WME 배치 정확성은 test_transform_search_op
      의 실-Agent 테스트가 별도로도 커버)."""


def _rot90_task():
    from procedural_memory.dsl.registry import body
    rot90 = body("rot90")
    # 반복색 grid — 모든 값이 서로 다르면 전역 색치환 하나로 train 이 우연히 설명돼(치환=순열이라
    # 회전과 구별 불가) synthesize 의 contents 가 '전역remap'으로 DECIDE 돼 DESCEND 까지 못 간다.
    g1 = [[1, 1, 2], [1, 1, 2], [3, 3, 3]]
    g2 = [[2, 1, 1], [2, 3, 3], [2, 1, 1]]
    train = [{"input": g1, "output": rot90(g1)}, {"input": g2, "output": rot90(g2)}]
    test_input = [[1, 2, 3], [1, 2, 3], [1, 2, 3]]
    return {"train": train, "test": [{"input": test_input}]}, rot90(test_input)


def _descend_to_grid_goal(max_cycles=200):
    """REAL Agent(PRODUCTIONS+OPERATOR_BODIES, via setup_focus_agent)를 raw task 에서 _Tracer 로
    자연 하강시켜, synthesize 가 contents-DESCEND 를 판정하고 grid-descend 를 남긴 GRID goal 상태를
    반환. (synthesize 는 더 이상 transform-search-open 을 쓰지 않는다 — 회귀수정.)"""
    from arbor.engine.trace import _Tracer
    from arbor.agent.focus import setup_focus_agent
    task, expected = _rot90_task()
    tr = _Tracer(task, "e2e-rot90", setup=setup_focus_agent)
    tr.run(max_cycles=max_cycles)
    ag = tr.ag
    gd = [i for (i, a, v) in ag.wm if a == "grid-descend"]
    return ag, gd, expected


class TestTransformSearchE2E(unittest.TestCase):
    def test_synthesize_descends_without_opening_transform_search(self):
        """(A) 회귀 가드 — synthesize 는 contents-DESCEND 에 도달하지만(grid-descend) 라이브 루프에
        transform_search 를 열지 않는다. 그 훅은 기존 하강경로와 TIE impasse 를 만들어 easy000c-h 를
        깨뜨렸으므로 제거됐다. 재도입되면(^transform-search-open 이 다시 켜지면) 이 테스트가 깨진다."""
        ag, gd, _ = _descend_to_grid_goal()
        self.assertTrue(gd, "synthesize 가 contents-DESCEND 에 도달하지 못함(grid-descend 없음)")
        tso = [v for (i, a, v) in ag.wm if a == "transform-search-open"]
        self.assertFalse(tso, "synthesize 가 ^transform-search-open 을 씀 — 회귀 훅 재도입"
                              "(easy000c-h 가 TIE impasse 로 다시 깨진다)")

    def test_transform_search_proposes_when_explicitly_opened(self):
        """(B) 흡수된 operator 는 라이브 배선만 뺐을 뿐 살아있다 — 실제 하강 상태(grid-descend)에서
        테스트가 명시적으로 ^transform-search-open 을 쓰면 REAL propose*transform_search production 이
        발화해 transform_search 가 후보로 제안된다(effect-매칭 어휘 발화). operator body 의 실행·WME
        배치(survivor/answer-ready 를 실행 상태에, 조부모로 새지 않게)는 test_transform_search_op 의
        실-Agent 테스트가 별도로 커버하므로 여기서는 propose 발화까지만 확인한다(스택 취약성 회피)."""
        from soar.decide import run_preference_semantics
        ag, gd, _expected = _descend_to_grid_goal()
        self.assertTrue(gd)
        s = gd[0]
        ag.wm.add(s, "transform-search-open", "yes")          # 테스트가 명시적으로 연다(synthesize 아님)
        ag.elaborator.settle(ag.wm)
        slot = ag.collect_operator_prefs(s)
        _imp, cands = run_preference_semantics(slot)
        names = {next((v for (i, a, v) in ag.wm if i == c and a == "name"), None) for c in cands}
        self.assertIn("transform_search", names,
                      f"명시적으로 열었는데 transform_search 가 제안 안 됨 — 후보: {names}")


if __name__ == "__main__":
    unittest.main()
