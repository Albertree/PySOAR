import json
from arbor.reasoning import program_ast as PA
from arbor.procedural_memory.operators.verify import _literal_grid_props


def test_literal_grid_props_from_output():
    out = [[0, 3, 3], [0, 0, 0]]                        # 2x3, 색 {0,3}
    size_leaf, color_leaf = _literal_grid_props(out)
    assert size_leaf == PA.const({"height": 2, "width": 3})
    assert color_leaf == PA.const([0, 3])              # sorted 색집합


def test_assembled_program_has_literal_size_not_pending():
    # skeleton(size=pending·color=pending·contents=pending) + 하강 coloring body → 조립 결과가
    # 그 pair 출력의 리터럴 size/color 를 갖고, pending 이 없어야 한다.
    import arbor.procedural_memory.operators.verify as V
    sk = PA.grid_program(PA.pending("size"), PA.pending("color"),
                         PA.set_grid_contents(PA.pending("contents"))["args"]["contents"])
    code = json.dumps(PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])),
                                          color=PA.const(3))]))

    class _Ag:
        task = {"train": [{"input": [[0, 0, 0], [0, 0, 0]], "output": [[0, 3, 0], [0, 0, 0]]}]}
        stack = []
        wm = []
    ag = _Ag()
    # grid-skeleton 을 조상 substate 대신 직접 주입하도록 monkeypatch (_find_grid_skeleton)
    V._find_grid_skeleton = lambda a: json.dumps(sk)
    V.pair_cursor = lambda a: 0
    out = json.loads(V._assemble_pair_program(ag, code))
    parts = {s["call"]: s["args"] for s in out["body"]}
    assert parts["set_grid_size"]["size"] == PA.const({"height": 2, "width": 3})   # 출력 [[0,3,0],[0,0,0]] = 2x3
    assert parts["set_grid_color"]["color"] == PA.const([0, 3])                    # 색집합 {0,3}
    assert "pending" not in json.dumps(out)
