# -*- coding: utf-8 -*-
"""transform operator 통합검사 — generalize 실패→needs-transform→transform 이 WM 에
TASK.solution 을 물질화하는지(발화 증거). isolated unit 이 아니라 파이프라인 결선을 본다."""
from env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve


def test_transform_writes_solution():
    t = load_task(dict(list_tasks("rotate"))["rota000b"])
    r = run_solve("rota000b", t, use_cache=False)
    sol = next((v for (i, a, v) in r["wm"]
                if i == "Trota000b.property" and a == "solution"), None)
    assert sol is not None
