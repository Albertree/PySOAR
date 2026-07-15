import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""Task 8 §9 — end-to-end: 진짜 soar.Agent(procedural_memory.loader.PRODUCTIONS +
procedural_memory.operators.OPERATOR_BODIES)로 SYNTHETIC pure-rot90 task 를 처음부터 구동해
synthesize 의 contents-DESCEND → ^transform-search-open → transform_search propose+apply →
transform-survivor(rot90)+answer-ready 전체 경로가 커널을 통해 실제로 발화하는지 검증한다.

두 가지를 이 파일에서 확인한다:

  (1) task 원본(raw dict)에서 시작해 **진짜 SOAR 하강**(observe/compare/select 의 impasse 로
      ARCKG 계층을 실제로 내려가는 것 — S1 하나만 있는 상태에서 substate 를 손으로 만들지 않음)
      으로 GRID 레벨 hypothesis-space 까지 도달시키고, 거기서 synthesize 가 정말로
      ^transform-search-open 을 쓰는지(§2 훅) — REAL Agent, REAL productions, REAL
      operator body(`_op_synthesize`)로.

  (2) 그 지점에서 REAL propose*transform_search / apply*transform_search production 과 REAL
      operator body(`_op_transform_search`)가 발화해 transform-survivor(rot90 포함)·
      answer-ready 를 그 실행 상태(=superstate 아님)에 남기는지.

정직하게 기록해야 할 known gap(§2-4, 하네스): (1)의 자연 하강 오케스트레이션(레벨 하강·
arg-선택 substate·hspace pop) 은 이 레포에서 soar.Agent 커널의 production 이 아니라
arbor/engine/trace.py::_Tracer 의 Python 제어흐름에 있다(`select-for`/`level`/`focus`
WME 를 실제로 *쓰는* production 이 production_rules/*.json 어디에도 없다 — grep 로 확인;
`_Tracer._open_arg_substate`/`_do_descend` 가 그 자리를 대신한다). 이건 Task 8 훨씬 이전부터
있던 구조라 여기서 새 production/operator 를 만들어 고치지 않는다(하네스: 막힌다고 임의로
만들지 않는다) — 대신 이미 debugger.build 가 실제로 쓰는 그 경로(_Tracer, 그러나 내부적으로
REAL soar.Agent 인스턴스 + REAL PRODUCTIONS + REAL OPERATOR_BODIES 를 그대로 실행)로 자연
하강시킨다. 이 경로로 도달해 보면 **또 다른, 더 근본적인 pre-existing gap** 이 드러난다:
size 가 DECIDE 되면서(회전류 변환은 거의 항상 크기 공식으로 설명되어 DECIDE 됨)
`propose*set_grid_size` 와 `propose*transform_search` 가 **동시에 acceptable** 이 되는데
이 둘을 가를 preference(better/worse) production 이 하나도 없어 진짜 TIE impasse 가 난다
(test_natural_descent_hits_known_tie_gap 이 이걸 실측·고정한다). 그 TIE 를 깨는 것도
Task 8 범위 밖(신규 preference production 도입은 설계 결정 — 하네스: 막히면 사용자와 상의)
이라, (2)에서는 그 TIE 후보 중 transform_search 를 **테스트 코드가** 골라주고(=SOAR 커널이
"단일 승자" 때 하는 것과 정확히 같은 절차 `_install_operator`+`body(ag)`+`settle` 를 그대로
수행) 그 뒤로는 100% REAL production-matched body 실행 결과를 검증한다."""


def _rot90_task():
    from procedural_memory.dsl.registry import body
    rot90 = body("rot90")
    # 반복색이 있는 grid 를 쓴다 — 모든 값이 서로 다르면(예: 2x2 [[1,2],[3,4]]) "전역 색 치환
    # 하나로도 train 을 우연히 설명"할 수 있어(치환=순열이라 회전과 구별 불가) synthesize 의
    # contents 가 '전역remap'으로 DECIDE 돼 버려 DESCEND(=transform-search-open)까지 못 간다.
    # 반복색을 넣으면 그 우연이 깨져 진짜 DESCEND 로 떨어진다(직접 확인함, report 참조).
    g1 = [[1, 1, 2], [1, 1, 2], [3, 3, 3]]
    g2 = [[2, 1, 1], [2, 3, 3], [2, 1, 1]]
    train = [{"input": g1, "output": rot90(g1)}, {"input": g2, "output": rot90(g2)}]
    test_input = [[1, 2, 3], [1, 2, 3], [1, 2, 3]]
    return {"train": train, "test": [{"input": test_input}]}, rot90(test_input)


def _descend_to_transform_search_open(max_cycles=200):
    """REAL Agent(PRODUCTIONS+OPERATOR_BODIES, via setup_focus_agent)를 task 원본에서부터
    _Tracer 로 자연 하강시켜 ^transform-search-open 이 켜진 (agent, state_id, expected_answer)
    를 반환. 못 찾으면 assertion 이 실패하도록 빈 리스트를 그대로 둔다(호출부가 검사)."""
    from arbor.engine.trace import _Tracer
    from arbor.agent.focus import setup_focus_agent
    task, expected = _rot90_task()
    tr = _Tracer(task, "e2e-rot90", setup=setup_focus_agent)
    tr.run(max_cycles=max_cycles)
    ag = tr.ag
    tso = [(i, v) for (i, a, v) in ag.wm if a == "transform-search-open" and v == "yes"]
    return ag, tso, expected


class TestTransformSearchE2E(unittest.TestCase):
    def test_synthesize_reaches_contents_descend_and_opens_transform_search(self):
        """(1) — REAL 커널로 처음부터 하강시켜 synthesize 가 실제로 contents-DESCEND 를
        판정하고 ^transform-search-open 을 쓰는지(§2 훅)."""
        ag, tso, _expected = _descend_to_transform_search_open()
        self.assertTrue(tso, "synthesize 가 진짜 SOAR 하강 경로로 도달한 뒤에도 "
                              "^transform-search-open 을 쓰지 않음 — §2 contents-DESCEND 훅 실패")

    def test_natural_descend_hits_known_tie_gap(self):
        """known gap(정직 기록, §2-4) — transform-search-open 이 켜진 바로 그 상태에서
        propose*set_grid_size 와 propose*transform_search 가 동시에 acceptable 이 되어
        진짜 TIE impasse 가 난다(둘을 가를 preference production 이 없음 — Task 8 범위 밖).
        이 테스트는 그 사실을 고정한다: 만약 미래에 이 gap 이 메워지면(누군가 preference
        production 을 추가하면) 이 테스트가 깨져 알려준다."""
        from soar.decide import run_preference_semantics
        ag, tso, _expected = _descend_to_transform_search_open()
        self.assertTrue(tso)
        s = tso[0][0]
        slot = ag.collect_operator_prefs(s)
        imp, cands = run_preference_semantics(slot)
        names = {c: next((v for (i, a, v) in ag.wm if i == c and a == "name"), None) for c in cands}
        self.assertEqual(imp.name, "TIE", f"TIE 가 아니면 gap 이 메워진 것 — 재확인 필요: {names}")
        self.assertIn("transform_search", names.values())
        self.assertIn("set_grid_size", names.values())

    def test_transform_search_fires_through_real_kernel_after_descend(self):
        """(2) — TIE 후보 중 transform_search 를 골라(known gap 우회, docstring 참조) REAL
        propose*/apply*transform_search production + REAL _op_transform_search body 를 그
        상태(=synthesize 가 연 바로 그 실행 상태)에서 돌리고, transform-survivor 가 rot90 을
        언급하고 answer-ready 가 (superstate 아니라) 그 실행 상태에 붙는지 검증한다."""
        from soar.decide import run_preference_semantics
        ag, tso, expected = _descend_to_transform_search_open()
        self.assertTrue(tso)
        s = tso[0][0]
        goal = next(g for g in ag.stack if g.id == s)
        slot = ag.collect_operator_prefs(s)
        imp, cands = run_preference_semantics(slot)
        names = {c: next((v for (i, a, v) in ag.wm if i == c and a == "name"), None) for c in cands}
        ts_op = next(c for c, n in names.items() if n == "transform_search")

        # SOAR 커널이 "단일 승자"일 때 하는 절차(soar/agent.py Agent.step 의 apply 분기)와
        # 정확히 같은 순서로 real body 를 돈다 — 여기서 대신하는 건 "누가 이겼나"(tie-break)
        # 뿐이고, propose 매칭·apply 매칭·operator body 실행은 전부 REAL 커널 경로다.
        ag._install_operator(goal, ts_op)
        body = ag.body_for(ts_op)
        self.assertIsNotNone(body, "transform_search 의 operator body 가 OPERATOR_BODIES 에 없음")
        body(ag)
        ag.elaborator.settle(ag.wm)

        wm = set(ag.wm)
        # §1-5 visibility: 시도(hypothesis)도 이 상태에 물질화돼야 한다.
        self.assertTrue(any(a == "hypothesis" and i == s for (i, a, v) in wm),
                         "hypothesis WME 물질화 안 됨 — 후보 잔존(§1-5) 실패")
        surv = [(i, v) for (i, a, v) in wm if a == "transform-survivor"]
        self.assertTrue(surv, "transform-survivor 가 안 생김 — rot90 생존 실패?")
        self.assertTrue(all(i == s for (i, v) in surv),
                         "transform-survivor 는 실행 상태에 붙어야(조부모로 새면 안 됨)")
        self.assertTrue(any("rot90" in v for (i, v) in surv), f"survivor 가 rot90 이 아님: {surv}")

        ar_ids = [i for (i, a, v) in wm if a == "answer-ready"]
        self.assertIn(s, ar_ids)
        # 조부모(superstate)로 answer-ready 가 새면 안 된다(리뷰 Critical, Task 6 에서 지적된 것과 동일 위험).
        superstate = next((v for (i, a, v) in wm if i == s and a == "superstate"), None)
        if superstate is not None:
            self.assertNotIn(superstate, ar_ids)


if __name__ == "__main__":
    unittest.main()
