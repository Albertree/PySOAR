import debugger.reports.program_report as pv
from arbor.reasoning import program_ast as PA


def test_to_source_toplevel_coord_no_keyerror():
    # 최상위(비-grid) coord body → apply_DSL(.., coloring, (r,c), col) 렌더, KeyError 없음
    ast = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([2, 8])), color=PA.const(0))])
    src = PA.to_source(ast)
    assert "(2, 8)" in src and "coloring" in src


def test_to_source_mixed_coord_pixel_body():
    # coord const + pixel var(slot) 혼합(=_antiunify_ast_pixel 산물 형태) 도 렌더
    body = [PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])), color=PA.const(3)),
            PA.step("coloring", target=PA.ref("pixel", PA.var("?src1")), color=PA.const(4))]
    src = PA.to_source(PA.program(body))
    assert "(0, 1)" in src                              # coord 는 리터럴, pixel var 는 기존 표기


def test_display_source_renders_literal_coord():
    ast = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([2, 8])), color=PA.const(0))])
    src = pv.display_source(ast)
    assert "(2, 8)" in src or "(2,8)" in src           # 리터럴 좌표 표기
    assert "cellset" not in src and "pixels_of" not in src
