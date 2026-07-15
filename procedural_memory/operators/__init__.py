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
from procedural_memory.operators.generalize import _op_generalize
from procedural_memory.operators.compress import _op_compress
from procedural_memory.operators.resolve import _op_resolve
from procedural_memory.operators.apply_solution import _op_apply_solution

# (골조 정정 2026-07-16) dead operator set_grid_size/set_grid_color 제거 — WM 슬롯(slot-grid_*)을
# 아무도 안 읽던 죽은 scaffold. grid property 설정은 hypothesize 가 all-3 판정 시 set_grid_* **DSL**
# (procedural_memory/dsl/transformation)을 program 에 emit 하는 것으로 일원화(operator/DSL 이름 충돌 해소).
OPERATOR_BODIES = {"observe": _op_observe, "compare": _op_compare, "select": _op_select,
                   "hypothesize": _op_hypothesize, "coloring": _op_coloring, "verify": _op_verify,
                   "synthesize": _op_synthesize, "generalize": _op_generalize,
                   "compress": _op_compress, "resolve": _op_resolve, "apply_solution": _op_apply_solution}
