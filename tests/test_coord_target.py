import json
from arbor.reasoning import program_ast as PA


def test_coord_execute_paints_literal_cell():
    # 2x3 grid, coord (1,2) 를 색 7 로
    ast = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([1, 2])), color=PA.const(7))])
    out = PA.execute(json.loads(json.dumps(ast)), [[0, 0, 0], [0, 0, 0]])
    assert out == [[0, 0, 0], [0, 0, 7]]


def test_coord_ops_and_pixel_body():
    body = [PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])), color=PA.const(3))]
    ast = PA.program(body)
    assert PA._is_pixel_body(body) is True                 # coord 도 픽셀 body
    assert PA.ops_of_ast(ast) == [((0, 1), 3)]             # 좌표 튜플 키


def test_coord_antiunify_positional_comm_diff():
    # 두 pair: 같은 좌표(0,1) COMM, 색 DIFF → 색 slot
    a0 = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])), color=PA.const(3))])
    a1 = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])), color=PA.const(5))])
    sk, slots = PA.antiunify_ast([a0, a1])
    assert sk is not None and any(s["kind"] == "color" for s in slots.values())
