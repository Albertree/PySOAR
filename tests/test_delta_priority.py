from arbor.reasoning.program import _resolve_decision, _grid_decide
from env.dataset import list_tasks, load_task


def test_delta_beats_output_const():
    # KEEP(delta,(5,5)) vs CONST(output,(8,8)) → delta 우선 DECIDE(5,5)
    dec, val, cat = _resolve_decision([("KEEP", (5, 5), True), ("CONST", (8, 8), True)])
    assert dec == "DECIDE" and val == (5, 5) and cat == "delta-const"


def test_output_const_when_no_delta():
    dec, val, cat = _resolve_decision([("CONST", (3, 3), True)])
    assert dec == "DECIDE" and val == (3, 3) and cat == "output-const"


def test_deltas_disagree_ambiguous():
    dec, val, cat = _resolve_decision([("KEEP", (5, 5), True), ("MAP[x]", (6, 6), True)])
    assert dec == "AMBIGUOUS" and val is None


def test_empty_descend():
    assert _resolve_decision([("KEEP", (5, 5), False)]) == ("DESCEND", None, None)


def test_move_size_decides_keep_not_pending():
    tid, p = list_tasks("move")[0]
    t = load_task(p)
    dec = _grid_decide(t["train"], t["test"][0]["input"])
    assert dec["size"]["decision"] == "DECIDE"                      # AMBIGUOUS 아님
    assert dec["size"]["value"] == (len(t["test"][0]["input"]), len(t["test"][0]["input"][0]))  # keep=test 입력크기
    assert dec["size"]["category"] == "delta-const"
