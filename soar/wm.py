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


def _wm_key(w):
    """결정적 반복용 정렬 키 (id, attr, value 를 문자열로)."""
    return (str(w[0]), str(w[1]), str(w[2]))


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
        # 매처(production.py)가 극빈번 호출 → 정렬 없이 빠르게. 매치 '집합'은 순서와 무관하므로
        # 정렬해도 결정에 영향 없음(비용만↑). '첫 매치' 픽의 결정성은 __iter__(정렬)에서 보장.
        for (i, a, v) in self._wmes:
            if identifier is not None and i != identifier:
                continue
            if attr is not None and a != attr:
                continue
            if value is not None and v != value:
                continue
            yield (i, a, v)

    def all(self) -> list[Triple]:
        return sorted(self._wmes, key=_wm_key)

    def __iter__(self) -> Iterator[Triple]:
        # 결정적 반복: WM 은 set 이라 반복순서가 PYTHONHASHSEED 에 따라 달라진다. operator body 들이
        # next((v for ... in wm if ...)) 로 '첫 매치' 를 고르므로(=이 __iter__) 순서가 결과를 바꾼다
        # → 항상 정렬 반복해 재현성 확보 (all() 과 같은 키).
        return iter(sorted(self._wmes, key=_wm_key))

    def __len__(self) -> int:
        return len(self._wmes)

    def load(self, triples: Iterable[Triple]) -> "WorkingMemory":
        for (i, a, v) in triples:
            self.add(i, a, v)
        return self
