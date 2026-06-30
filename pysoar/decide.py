"""
decide -- faithful port of SOAR's preference resolution and impasse typing.

Oracle reference: SoarGroup/Soar
  - ``Core/SoarKernel/src/decision_process/decide.cpp:1104`` run_preference_semantics
  - ``Core/SoarKernel/src/shared/constants.h:26``           impasse type constants

This is the single most important piece of fidelity in the ARC port: it is the
*only* deliberation point in SOAR ("decide is the only choice point"), and it is
what produces TIE / CONFLICT / CONSTRAINT-FAILURE impasses -- the structural
transitions that previous ARC ports could not generate because they had no real
preference engine.

The cascade (exact order from decide.cpp), each stage narrowing the candidate
set and exiting early when 0 or 1 candidate remains:

    1. Require            -> winner, or CONSTRAINT_FAILURE
    2. Acceptable / Reject / Prohibit  (build candidate set)
    3. Better / Worse     -> prune, or CONFLICT
    4. Best               -> keep bests (if any candidate is best)
    5. Worst              -> drop worsts (if any non-worst remains)
    6. Indifferent        -> single winner, or TIE

Determinism note: where the C++ kernel calls the exploration policy to break a
fully-indifferent set, we pick the first candidate in acceptable-insertion
order, i.e. ``indifferent-selection --first``. This keeps oracle differential
tests reproducible.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from .preference import PreferenceType as PT
from .preference import Slot


class ImpasseType(IntEnum):
    """Impasse types, numbered EXACTLY as the C++ kernel (constants.h:26-32)."""

    NONE = 0                 # resolved -- a winner (or empty) was produced
    CONSTRAINT_FAILURE = 1   # >1 required, or required item also prohibited
    CONFLICT = 2             # better/worse cycle: no unconflicted candidate
    TIE = 3                  # multiple candidates, not all mutually indifferent
    NO_CHANGE = 4            # (generic) -- see ONC / SNC below
    ONC = 5                  # operator no-change (selected op makes no progress)
    SNC = 6                  # state no-change (no operator could be selected)


def _unique(values: list[Any]) -> list[Any]:
    """De-duplicate preserving first-seen order (candidates are by value)."""
    seen: list[Any] = []
    for v in values:
        if v not in seen:
            seen.append(v)
    return seen


def run_preference_semantics(slot: Slot) -> tuple[ImpasseType, list[Any]]:
    """Resolve a slot's preferences into (impasse_type, candidate_values).

    Faithful to ``run_preference_semantics`` (decide.cpp:1104). Returns the
    impasse type and the surviving candidate list. On NONE the list holds the
    selected operator (length 0 or 1); on TIE/CONFLICT/CONSTRAINT_FAILURE it
    holds the items that caused the impasse.
    """
    P = slot.preferences

    # --- trivial: no preferences at all (decide.cpp:1132) ---
    if not slot.has_any():
        return ImpasseType.NONE, []

    # === Requires (decide.cpp:1193) ===
    if P[PT.REQUIRE]:
        required = _unique([p.value for p in P[PT.REQUIRE]])
        # >1 required -> constraint failure (decide.cpp:1217)
        if len(required) > 1:
            return ImpasseType.CONSTRAINT_FAILURE, required
        value = required[0]
        # required item also prohibited -> constraint failure (decide.cpp:1227)
        # (this is the ONE difference between prohibit and reject)
        if any(p.value == value for p in P[PT.PROHIBIT]):
            return ImpasseType.CONSTRAINT_FAILURE, [value]
        return ImpasseType.NONE, [value]

    # === Acceptables, minus Prohibits and Rejects (decide.cpp:1251) ===
    acceptable = _unique([p.value for p in P[PT.ACCEPTABLE]])
    blocked = {p.value for p in P[PT.PROHIBIT]} | {p.value for p in P[PT.REJECT]}
    candidates = [v for v in acceptable if v not in blocked]

    # Exit point 1 (decide.cpp:1306)
    if len(candidates) <= 1:
        return ImpasseType.NONE, candidates

    # === Better / Worse (decide.cpp:1326) ===
    if P[PT.BETTER] or P[PT.WORSE]:
        cand_set = set(candidates)
        conflicted: set[Any] = set()
        # better: value j is better than referent k -> k loses (decide.cpp:1355)
        for p in P[PT.BETTER]:
            j, k = p.value, p.referent
            if j == k:
                continue
            if j in cand_set and k in cand_set:
                conflicted.add(k)
        # worse: value j is worse than referent k -> j loses (decide.cpp:1372)
        for p in P[PT.WORSE]:
            j, k = p.value, p.referent
            if j == k:
                continue
            if j in cand_set and k in cand_set:
                conflicted.add(j)

        remaining = [c for c in candidates if c not in conflicted]
        # no unconflicted candidate -> conflict, return conflicted set
        # (decide.cpp:1402)
        if not remaining:
            return ImpasseType.CONFLICT, [c for c in candidates if c in conflicted]
        candidates = remaining

    # Exit point 2 (decide.cpp:1485)
    if len(candidates) <= 1:
        return ImpasseType.NONE, candidates

    # === Bests (decide.cpp:1506) ===
    # Reduce to best candidates ONLY if at least one candidate is best;
    # best prefs that reference no candidate are no-ops (decide.cpp:1546 subtlety).
    if P[PT.BEST]:
        best_vals = {p.value for p in P[PT.BEST]}
        best_cands = [c for c in candidates if c in best_vals]
        if best_cands:
            candidates = best_cands

    # Exit point 3 (decide.cpp:1554)
    if len(candidates) <= 1:
        return ImpasseType.NONE, candidates

    # === Worsts (decide.cpp:1575) ===
    # Drop worst candidates ONLY if at least one non-worst remains; if every
    # candidate is worst, worst has no effect (decide.cpp:1635 subtlety).
    if P[PT.WORST]:
        worst_vals = {p.value for p in P[PT.WORST]}
        non_worst = [c for c in candidates if c not in worst_vals]
        if non_worst:
            candidates = non_worst

    # Exit point 4 (decide.cpp:1643)
    if len(candidates) <= 1:
        return ImpasseType.NONE, candidates

    # === Indifferents (decide.cpp:1662) ===
    unary = {p.value for p in P[PT.UNARY_INDIFFERENT]}
    numeric = {p.value for p in P[PT.NUMERIC_INDIFFERENT]}
    binary = P[PT.BINARY_INDIFFERENT]

    def binary_indiff(a: Any, b: Any) -> bool:
        for p in binary:
            if (p.value == a and p.referent == b) or (p.value == b and p.referent == a):
                return True
        return False

    not_all_indifferent = False
    for cand in candidates:
        # unary or numeric indifferent -> fine on its own (decide.cpp:1698)
        if cand in unary or cand in numeric:
            continue
        # otherwise must be binary-indifferent to EVERY other candidate
        for other in candidates:
            if other == cand:
                continue
            if not binary_indiff(cand, other):
                not_all_indifferent = True
                break
        if not_all_indifferent:
            break

    if not not_all_indifferent:
        # fully indifferent -> pick one (deterministic: first). decide.cpp:1738
        return ImpasseType.NONE, [candidates[0]]

    # not all indifferent -> tie (decide.cpp:1828)
    return ImpasseType.TIE, candidates


def decide_context_slot(slot: Slot) -> tuple[ImpasseType, list[Any]]:
    """Decide an operator (context) slot, mapping the preference result to the
    goal-level impasse the decider would install.

    - NONE + 1 candidate  -> operator selected            (NONE, [op])
    - NONE + 0 candidates  -> no operator selectable        (SNC, [])
    - TIE / CONFLICT / CONSTRAINT_FAILURE -> passed through

    NOTE: *operator* no-change (ONC) is a cross-cycle condition (a selected
    operator persists without producing progress); it is detected by the run
    loop, not by preference semantics. See ``pysoar/cycle.py`` (next milestone).
    """
    imp, cands = run_preference_semantics(slot)
    if imp is not ImpasseType.NONE:
        return imp, cands
    if len(cands) == 1:
        return ImpasseType.NONE, cands
    # 0 candidates: no operator could be selected for this state
    return ImpasseType.SNC, []
