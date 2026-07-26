import pytest
from env.dataset import list_tasks, load_task
from arbor.reasoning.transform import transform_solution_ast, solution_ast_from_answer
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

    # VERIFIED FACT(§brief 2026-07-26): 이 AST 를 test 입력에 그대로 실행하면 정답을 재현해야
    # 한다 — 옛 버전은 vacated(입력엔 있고 답엔 없는) 셀을 배경으로 안 지워 잔상이 남았다.
    assert PA.execute(ast, tin) == tout

    # coloring 의 select target 은 손코딩 dict 가 아니라 program_ast 의 실행가능 shape 라야 한다
    # (accessor 존재·level 소문자 "pixel") — _resolve_select_coords/_sel_src 로 실제 해소해 확인.
    # 이 assert 는 구 malformed shape({"level":"PIXEL", pred without accessor})에서는
    # _compile_pred 가 e["accessor"] 를 찾다 KeyError 로 죽어 반드시 실패한다.
    contents = ast["body"][2]["args"]["contents"]["program"]["body"]
    assert contents, "coloring body must be non-empty"
    H, W = len(tout), len(tout[0])
    vac = {(r, c) for r in range(H) for c in range(W) if tin[r][c] and not tout[r][c]}
    resolved_all = set()
    for coloring_step in contents:
        assert coloring_step["call"] == "coloring"
        target = coloring_step["args"]["target"]
        color = coloring_step["args"]["color"]["const"]

        coords = PA._resolve_select_coords(target, tin)
        assert coords is not None, f"select target not resolvable: {target}"

        # color==0 그룹은 목적지 재칠(=tout 의 그 색 전체)이 아니라 vacated-clear 스텝일 수 있다
        # (§solution_ast_from_answer — 입력 비배경∧답 배경 셀만 지운다, tout 전체 배경이 아님).
        expected = (sorted(vac) if color == 0 and vac
                    else sorted((r, c) for r in range(H) for c in range(W) if tout[r][c] == color))
        assert coords == expected, (tid, color, coords, expected)

        # 렌더 경로(_sel_src)도 raise 없이 소스 조각을 낸다(보고서 표시 경로).
        src = PA._sel_src(target)
        assert src is not None
        assert "coordinate_of(select(" in src

        resolved_all.update(coords)

    # 색별 target 들 + vacated-clear 가 합쳐서 답 격자의 비배경 셀 + vacated 셀 전체를 정확히 덮는다.
    expected_all = {(r, c) for r in range(H) for c in range(W) if tout[r][c]} | vac
    assert resolved_all == expected_all


@pytest.mark.parametrize("ds,tid", [("rotate", "rota000b"), ("rotate", "rota000z"), ("flip", "flip000c")])
def test_solution_ast_from_answer_executes_to_given_answer(ds, tid):
    """solution_ast_from_answer(정답, test_input) 는 solve_any 로 재계산하지 않고 **주어진 정답**
    으로만 AST 를 지으므로, solve_any 가 틀린 첫 답을 내는 태스크(flip000c — Cat-2: 실제 정답은
    우선편입된 transform 후보였음, transform_solution_ast/solve_any 는 이 답과 불일치)에서도
    PA.execute(ast, test_input) == 정답 이 성립해야 한다(§task-6-brief 핵심 검증)."""
    t = load_task(dict(list_tasks(ds))[tid])
    tin, tout = t["test"][0]["input"], t["test"][0]["output"]
    ast = solution_ast_from_answer(tout, tin)
    assert PA._is_grid_body(ast.get("body") or [])
    assert PA.execute(ast, tin) == tout
