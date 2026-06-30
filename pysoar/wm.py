"""
wm -- working memory: a set of WMEs (identifier, attribute, value) triplets.

Oracle reference: SoarGroup/Soar `soar_representation/wmem.*`. WM is the in-memory
scratchpad (no disk); see wiki/soar.md. For PySOAR we model it as a set of
triples plus a record of which identifiers are goals/states (needed by the
o-support calculation, which looks for the lowest goal among an instantiation's
condition WMEs -- instantiation.cpp:636).

A WME here carries no timetag object identity beyond its (id, attr, value); two
WMEs with the same triple are the same WME (Soar interns symbols, so distinct
acceptable preferences for one value collapse to one WME -- same as M1).
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

Triple = tuple[str, str, Any]


class WorkingMemory:
    def __init__(self) -> None:
        self._wmes: set[Triple] = set()
        self._goals: set[str] = set()
        self._level: dict[str, int] = {}

    # -- goals / states -------------------------------------------------------
    def mark_goal(self, identifier: str, level: int = 1) -> None:
        """Register an identifier as a goal/state. ``level`` is the goal depth
        (top state = 1, substates deeper); used to find the *lowest* goal in the
        o-support calculation (instantiation.cpp:640)."""
        self._goals.add(identifier)
        self._level[identifier] = level

    def is_goal(self, identifier: Any) -> bool:
        return identifier in self._goals

    def goal_level(self, identifier: str) -> int:
        return self._level.get(identifier, 0)

    # -- WMEs -----------------------------------------------------------------
    def add(self, identifier: str, attr: str, value: Any) -> Triple:
        w = (identifier, attr, value)
        self._wmes.add(w)
        return w

    def remove(self, identifier: str, attr: str, value: Any) -> bool:
        w = (identifier, attr, value)
        if w in self._wmes:
            self._wmes.discard(w)
            return True
        return False

    def contains(self, identifier: str, attr: str, value: Any) -> bool:
        return (identifier, attr, value) in self._wmes

    def matching(self, identifier=None, attr=None, value=None) -> Iterator[Triple]:
        for (i, a, v) in self._wmes:
            if identifier is not None and i != identifier:
                continue
            if attr is not None and a != attr:
                continue
            if value is not None and v != value:
                continue
            yield (i, a, v)

    def all(self) -> list[Triple]:
        return sorted(self._wmes, key=lambda w: (str(w[0]), str(w[1]), str(w[2])))

    def __iter__(self) -> Iterator[Triple]:
        return iter(self._wmes)

    def __len__(self) -> int:
        return len(self._wmes)

    def load(self, triples: Iterable[Triple]) -> "WorkingMemory":
        for (i, a, v) in triples:
            self.add(i, a, v)
        return self
