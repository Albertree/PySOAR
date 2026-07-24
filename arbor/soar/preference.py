"""
preference -- SOAR preference data model (faithful port of the C++ kernel).

Reference (oracle): SoarGroup/Soar `Core/SoarKernel/src/shared/enums.h:423`
and `soar_representation/preference.h`.

A *preference* is an assertion about an operator (a value) in a slot. Operator
selection is NOT a fixed name-ranking (that was the mistake in the previous ARC
ports) -- it is the cascade defined over these typed preferences. See
``pysoar/decide.py:run_preference_semantics`` for the resolution algorithm.

Values here are plain Python objects compared by ``==`` (operator names are
strings in the ARC repos). The C++ kernel compares ``Symbol*`` by pointer
identity; for distinct interned operator symbols that is equivalent to ``==``
on unique names, which is what we rely on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Optional


class PreferenceType(IntEnum):
    """Preference types, numbered EXACTLY as the C++ kernel (enums.h:423-437).

    The numeric order is load-bearing in places (the kernel indexes arrays by
    it), so we keep the same values even where we don't use all of them yet.
    """

    ACCEPTABLE = 0          # (S ^operator O +)   -- O is a candidate
    REQUIRE = 1             # (S ^operator O !)   -- O must be selected
    REJECT = 2              # (S ^operator O -)   -- O is not a candidate
    PROHIBIT = 3            # (S ^operator O ~)   -- O must not be selected
    RECONSIDER = 4          # (S ^operator O @)   -- (not used in selection)
    UNARY_INDIFFERENT = 5   # (S ^operator O =)   -- O is indifferent (unary)
    UNARY_PARALLEL = 6      # (rarely used)
    BEST = 7                # (S ^operator O >)   -- O is best
    WORST = 8               # (S ^operator O <)   -- O is worst
    BINARY_INDIFFERENT = 9  # (S ^operator O1 = O2) -- O1 indifferent to O2
    BINARY_PARALLEL = 10    # (rarely used)
    BETTER = 11             # (S ^operator O1 > O2) -- O1 better than O2
    WORSE = 12              # (S ^operator O1 < O2) -- O1 worse than O2
    NUMERIC_INDIFFERENT = 13  # (S ^operator O = 3.2) -- numeric (RL) indifferent


# Compact textual aliases (Soar production syntax) -> PreferenceType.
SYMBOL_TO_TYPE = {
    "+": PreferenceType.ACCEPTABLE,
    "!": PreferenceType.REQUIRE,
    "-": PreferenceType.REJECT,
    "~": PreferenceType.PROHIBIT,
    "@": PreferenceType.RECONSIDER,
    "=": PreferenceType.UNARY_INDIFFERENT,   # binary/numeric disambiguated by args
    ">": PreferenceType.BEST,                # binary disambiguated by referent
    "<": PreferenceType.WORST,
}


@dataclass
class Preference:
    """One preference assertion for a slot.

    Attributes:
        ptype:     the PreferenceType.
        value:     the operator this preference is about (the "value" symbol).
        referent:  for binary preferences (better/worse/binary-indifferent),
                   the second operator. None for unary preferences.
        numeric:   for NUMERIC_INDIFFERENT, the numeric value.
    """

    ptype: PreferenceType
    value: Any
    referent: Optional[Any] = None
    numeric: Optional[float] = None

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        sym = {v: k for k, v in SYMBOL_TO_TYPE.items()}.get(self.ptype, self.ptype.name)
        if self.referent is not None:
            return f"({self.value} {sym} {self.referent})"
        if self.numeric is not None:
            return f"({self.value} = {self.numeric})"
        return f"({self.value} {sym})"


class Slot:
    """A slot holding all preferences for one (identifier, attribute).

    In SOAR every preference for the operator slot of a state lands here, and
    ``run_preference_semantics`` reads the per-type lists to decide. Insertion
    order within a type is preserved (it is the deterministic tie-break for
    indifferent selection, mirroring ``indifferent-selection --first``).
    """

    def __init__(self) -> None:
        self.preferences: dict[PreferenceType, list[Preference]] = {
            t: [] for t in PreferenceType
        }

    # -- construction helpers -------------------------------------------------
    def add(self, pref: Preference) -> Preference:
        self.preferences[pref.ptype].append(pref)
        return pref

    def add_pref(
        self,
        ptype: PreferenceType,
        value: Any,
        referent: Optional[Any] = None,
        numeric: Optional[float] = None,
    ) -> Preference:
        return self.add(Preference(ptype, value, referent, numeric))

    def get(self, ptype: PreferenceType) -> list[Preference]:
        return self.preferences[ptype]

    def has_any(self) -> bool:
        return any(self.preferences[t] for t in PreferenceType)

    # -- convenience for tests/agents ----------------------------------------
    def acceptable(self, *values: Any) -> "Slot":
        for v in values:
            self.add_pref(PreferenceType.ACCEPTABLE, v)
        return self

    def reject(self, *values: Any) -> "Slot":
        for v in values:
            self.add_pref(PreferenceType.REJECT, v)
        return self

    def prohibit(self, *values: Any) -> "Slot":
        for v in values:
            self.add_pref(PreferenceType.PROHIBIT, v)
        return self

    def require(self, *values: Any) -> "Slot":
        for v in values:
            self.add_pref(PreferenceType.REQUIRE, v)
        return self

    def best(self, *values: Any) -> "Slot":
        for v in values:
            self.add_pref(PreferenceType.BEST, v)
        return self

    def worst(self, *values: Any) -> "Slot":
        for v in values:
            self.add_pref(PreferenceType.WORST, v)
        return self

    def better(self, value: Any, referent: Any) -> "Slot":
        self.add_pref(PreferenceType.BETTER, value, referent)
        return self

    def worse(self, value: Any, referent: Any) -> "Slot":
        self.add_pref(PreferenceType.WORSE, value, referent)
        return self

    def indifferent(self, value: Any, referent: Any = None) -> "Slot":
        if referent is None:
            self.add_pref(PreferenceType.UNARY_INDIFFERENT, value)
        else:
            self.add_pref(PreferenceType.BINARY_INDIFFERENT, value, referent)
        return self

    def numeric_indifferent(self, value: Any, numeric: float) -> "Slot":
        self.add_pref(PreferenceType.NUMERIC_INDIFFERENT, value, numeric=numeric)
        return self
