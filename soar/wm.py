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
        self._sorted: "list[Triple] | None" = None   # 결정적 반복순서 캐시(§2-6); add/remove 시 무효화
        self._idx_id: "dict[str, list[Triple]] | None" = None    # id -> 정렬 버킷(matching 인덱스)
        self._idx_attr: "dict[str, list[Triple]] | None" = None  # attr -> 정렬 버킷

    def _invalidate(self) -> None:
        self._sorted = self._idx_id = self._idx_attr = None       # 반복순서·인덱스 캐시 무효화(§2-6)

    def _ordered(self) -> "list[Triple]":
        """결정적 정렬 반복순서(캐시). matching() 은 매처가 극빈번 호출하므로 매번 정렬하면 느리다 →
        **mutation 당 1회만** 정렬해 상각(add/remove 가 캐시 무효화). __iter__·all()·matching() 공용."""
        if self._sorted is None:
            self._sorted = sorted(self._wmes, key=_wm_key)
        return self._sorted

    def _build_index(self) -> None:
        """id·attr 별 정렬 버킷을 mutation 당 1회 구성(상각). 각 버킷은 `_ordered()` 의 부분수열이라
        반복 순서·결정성이 전체 반복과 동일 → matching() 결과가 선형 스캔 때와 비트 단위로 같다."""
        idx_id: "dict[str, list[Triple]]" = {}
        idx_attr: "dict[str, list[Triple]]" = {}
        for w in self._ordered():
            idx_id.setdefault(w[0], []).append(w)
            idx_attr.setdefault(w[1], []).append(w)
        self._idx_id, self._idx_attr = idx_id, idx_attr

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
        if w not in self._wmes:
            self._wmes.add(w)
            self._invalidate()                           # 반복순서·인덱스 캐시 무효화(§2-6)
        return w

    def remove(self, identifier: str, attr: str, value: Any) -> bool:
        w = (identifier, attr, value)
        if w in self._wmes:
            self._wmes.discard(w)
            self._invalidate()                           # 반복순서·인덱스 캐시 무효화(§2-6)
            return True
        return False

    def contains(self, identifier: str, attr: str, value: Any) -> bool:
        return (identifier, attr, value) in self._wmes

    def matching(self, identifier=None, attr=None, value=None) -> Iterator[Triple]:
        # 결정성(재현성): __iter__ 와 **같은 정렬**로 반복한다. operator body 들이
        # `next((.. for .. in wm.matching(..)), default)` 로 '첫 매치' 를 고르고, 매처(production.py)도
        # 이걸 쓰므로, 정렬 안 하면 PYTHONHASHSEED 에 따라 첫 매치/바인딩 순서가 달라져 경계 태스크
        # 결과가 실행마다 뒤집힌다(개발 중 2회 발생). '집합은 순서 무관' 은 틀림 — 첫매치는 순서 의존.
        #
        # 성능(2026-07-18): 매처는 이 함수를 태스크당 수십만~수백만 번 부르는데, 픽셀 레벨로 WM 이
        # 수천 WME 인 문제에선 매번 전체 리스트를 선형 스캔하면 병목(프로파일 tottime 1위)이었다.
        # id/attr 인덱스 버킷으로 스캔 범위를 좁힌다 — 버킷은 `_ordered()` 의 부분수열이라 반복 순서·
        # 결정성이 전체 스캔과 동일(결과 비트 단위 일치). 매처 조건은 항상 attr 을 지정하므로 대부분
        # id 또는 attr 버킷으로 떨어진다(둘 다 None 인 전체 반복은 사실상 없음).
        if identifier is not None:
            if self._idx_id is None:
                self._build_index()
            bucket: "Iterable[Triple]" = self._idx_id.get(identifier, ())
        elif attr is not None:
            if self._idx_attr is None:
                self._build_index()
            bucket = self._idx_attr.get(attr, ())
        else:
            bucket = self._ordered()
        for (i, a, v) in bucket:
            if attr is not None and a != attr:
                continue
            if value is not None and v != value:
                continue
            yield (i, a, v)

    def all(self) -> list[Triple]:
        return list(self._ordered())

    def __iter__(self) -> Iterator[Triple]:
        # 결정적 반복(§2-6): WM 은 set 이라 반복순서가 PYTHONHASHSEED 에 따라 달라진다 → 정렬 캐시로
        # 반복. operator body next((v for ... in wm if ..)) 첫매치·매처·all()·matching() 모두 이 순서.
        return iter(self._ordered())

    def __len__(self) -> int:
        return len(self._wmes)

    def load(self, triples: Iterable[Triple]) -> "WorkingMemory":
        for (i, a, v) in triples:
            self.add(i, a, v)
        return self
