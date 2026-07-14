# -*- coding: utf-8 -*-
"""ARBOR operator bodies 레지스트리 (procedural LTM).
operator 이름 → 실행 body. propose/apply 규칙(P3 JSON)이 이 이름으로 결선한다."""
from procedural_memory.operators.observe import _op_observe
from procedural_memory.operators.compare import _op_compare
from procedural_memory.operators.select import _op_select
from procedural_memory.operators.synthesize import _op_synthesize
from procedural_memory.operators.hypothesize import _op_hypothesize
from procedural_memory.operators.coloring import _op_coloring
from procedural_memory.operators.verify import _op_verify
from procedural_memory.operators.grid_slots import _op_set_grid_size, _op_set_grid_color

OPERATOR_BODIES = {"observe": _op_observe, "compare": _op_compare, "select": _op_select,
                   "hypothesize": _op_hypothesize, "coloring": _op_coloring, "verify": _op_verify,
                   "set_grid_size": _op_set_grid_size, "set_grid_color": _op_set_grid_color,
                   "synthesize": _op_synthesize}
