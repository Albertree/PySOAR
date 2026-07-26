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
