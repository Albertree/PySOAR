"""
production -- LHS conditions, RHS actions, and a simple matcher.

Oracle reference: SoarGroup/Soar `parsing/parser.cpp`, `decision_process/rete.cpp`.
PySOAR does NOT replicate the Rete network (a caching optimization, not a
semantics -- see docs/AUDIT.md). At ARC scale a naive matcher producing the same set
of complete variable bindings is behaviourally identical to quiescence.

Supported in milestone 2:
  - positive conditions  (id ^attr value)
  - negated conditions  -(id ^attr value)   [no match may exist]
  - variables  <x>  bind across conditions; constants match literally
  - attributes are constants (sufficient for the truth-maintenance work)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator

from .wm import Triple, WorkingMemory


class Support(Enum):
    """Declared support of a production (instantiation.cpp:559)."""

    UNDECLARED = 0   # architecture decides per the o-support calculation
    O_SUPPORT = 1    # :o-support  -> always persistent
    I_SUPPORT = 2    # :i-support  -> always truth-maintained


def is_var(x: Any) -> bool:
    return isinstance(x, str) and len(x) >= 2 and x[0] == "<" and x[-1] == ">"


@dataclass(frozen=True)
class Cond:
    """A condition. ``id``/``value`` may be variables (<x>) or constants;
    ``attr`` is a constant. ``negated`` = this pattern must NOT be present."""

    id: Any
    attr: str
    value: Any
    negated: bool = False


@dataclass(frozen=True)
class Action:
    """A RHS make/remove action, or an operator preference.

    For ordinary attributes (attr != "operator"):
      pref "+"  make the WME (elaboration)
      pref "-"  remove the WME (reject) -- used by operator-application rules

    For the operator context slot (attr == "operator"), ``pref`` is the Soar
    preference symbol and routes through M1 (run_preference_semantics):
      "+" acceptable   "!" require   "-" reject   "~" prohibit
      ">" best/better  "<" worst/worse   "=" (binary/unary) indifferent
    ``referent`` (a second operator) makes ">"/"<"/"=" binary (better/worse/
    binary-indifferent); leave it None for the unary forms.
    """

    id: Any
    attr: str
    value: Any
    pref: str = "+"
    referent: Any = None


@dataclass
class Production:
    name: str
    conditions: list[Cond]
    actions: list[Action]
    support: Support = Support.UNDECLARED
    # convenience: positive conditions first is not required; matcher handles order
    _pos: list[Cond] = field(default_factory=list, repr=False)
    _neg: list[Cond] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._pos = [c for c in self.conditions if not c.negated]
        self._neg = [c for c in self.conditions if c.negated]


# --------------------------------------------------------------------------
# Matcher: backtracking over positive conditions, then filter by negations.
# --------------------------------------------------------------------------
def _unify(pattern: Any, value: Any, binding: dict) -> dict | None:
    """Try to bind one pattern element against a concrete value."""
    if is_var(pattern):
        if pattern in binding:
            return binding if binding[pattern] == value else None
        nb = dict(binding)
        nb[pattern] = value
        return nb
    return binding if pattern == value else None


def _match_positive(conds: list[Cond], wm: WorkingMemory, binding: dict,
                    i: int, matched: tuple) -> Iterator[tuple[dict, tuple]]:
    if i == len(conds):
        yield binding, matched
        return
    c = conds[i]
    cid = binding.get(c.id, c.id) if is_var(c.id) else c.id
    cval = binding.get(c.value, c.value) if is_var(c.value) else c.value
    for (wi, wa, wv) in wm.matching(
        identifier=None if is_var(c.id) and c.id not in binding else cid,
        attr=c.attr,
        value=None if is_var(c.value) and c.value not in binding else cval,
    ):
        b1 = _unify(c.id, wi, binding)
        if b1 is None:
            continue
        b2 = _unify(c.value, wv, b1)
        if b2 is None:
            continue
        yield from _match_positive(conds, wm, b2, i + 1, matched + ((wi, wa, wv),))


def _negation_satisfied(neg: list[Cond], wm: WorkingMemory, binding: dict) -> bool:
    """True if NO negated pattern is present under this binding."""
    for c in neg:
        cid = binding.get(c.id, c.id) if is_var(c.id) else c.id
        cval = binding.get(c.value, c.value) if is_var(c.value) else c.value
        found = any(True for _ in wm.matching(
            identifier=None if is_var(c.id) and c.id not in binding else cid,
            attr=c.attr,
            value=None if is_var(c.value) and c.value not in binding else cval,
        ))
        if found:
            return False
    return True


def match(prod: Production, wm: WorkingMemory) -> list[tuple[dict, frozenset]]:
    """Return all complete matches: (variable_binding, matched_positive_WMEs)."""
    results: list[tuple[dict, frozenset]] = []
    for binding, matched in _match_positive(prod._pos, wm, {}, 0, ()):
        if _negation_satisfied(prod._neg, wm, binding):
            results.append((binding, frozenset(matched)))
    return results
