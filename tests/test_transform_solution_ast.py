import pytest
from env.dataset import list_tasks, load_task
from arbor.reasoning.transform import transform_solution_ast
import arbor.reasoning.program_ast as PA


@pytest.mark.parametrize("ds,tid", [("rotate", "rota000b"), ("rotate", "rota000z"), ("flip", "flip000m")])
def test_ast_and_answer(ds, tid):
    t = load_task(dict(list_tasks(ds))[tid])
    train = [(p["input"], p["output"]) for p in t["train"]]
    tin, tout = t["test"][0]["input"], t["test"][0]["output"]
    res = transform_solution_ast(train, tin)
    assert res is not None
    ast, answer = res
    assert answer == tout
    assert PA._is_grid_body(ast.get("body") or [])

    # coloring 의 select target 은 손코딩 dict 가 아니라 program_ast 의 실행가능 shape 라야 한다
    # (accessor 존재·level 소문자 "pixel") — _resolve_select_coords/_sel_src 로 실제 해소해 확인.
    # 이 assert 는 구 malformed shape({"level":"PIXEL", pred without accessor})에서는
    # _compile_pred 가 e["accessor"] 를 찾다 KeyError 로 죽어 반드시 실패한다.
    contents = ast["body"][2]["args"]["contents"]["program"]["body"]
    assert contents, "coloring body must be non-empty"
    H, W = len(tout), len(tout[0])
    resolved_all = set()
    for coloring_step in contents:
        assert coloring_step["call"] == "coloring"
        target = coloring_step["args"]["target"]
        color = coloring_step["args"]["color"]["const"]

        coords = PA._resolve_select_coords(target, tin)
        assert coords is not None, f"select target not resolvable: {target}"

        expected = sorted((r, c) for r in range(H) for c in range(W) if tout[r][c] == color)
        assert coords == expected, (tid, color, coords, expected)

        # 렌더 경로(_sel_src)도 raise 없이 소스 조각을 낸다(보고서 표시 경로).
        src = PA._sel_src(target)
        assert src is not None
        assert "coordinate_of(select(" in src

        resolved_all.update(coords)

    # 색별 target 들이 합쳐서 답 격자의 비배경 셀 전체를 정확히 덮는다(누락/중복 없음).
    expected_all = {(r, c) for r in range(H) for c in range(W) if tout[r][c]}
    assert resolved_all == expected_all
