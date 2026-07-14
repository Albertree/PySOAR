"""
PySOAR -- a faithful Python re-implementation of the SOAR decision core.

Not a 1:1 transpile of the C++ kernel (324k LOC, half of it the unused SVS
spatial system). This is a *fidelity-first* re-implementation of the decision
cycle semantics that ARBOR depends on, with the C++ build at ~/Desktop/Soar
kept as the differential-testing oracle.

Milestone 1 (this module): preference resolution + impasse typing -- the only
deliberation point in SOAR and the source of TIE/CONFLICT/CONSTRAINT-FAILURE
impasses that earlier ARC ports could not produce.
"""

from .preference import Preference, PreferenceType, Slot
from .decide import ImpasseType, run_preference_semantics, decide_context_slot
from .wm import WorkingMemory
from .production import Action, Cond, Production, Support, match
from .elaborate import (
    Elaborator,
    Instantiation,
    calculate_o_support,
    elaborate_to_quiescence,
)
from .agent import Agent, Goal

__all__ = [
    # milestone 1: preference / impasse
    "Preference",
    "PreferenceType",
    "Slot",
    "ImpasseType",
    "run_preference_semantics",
    "decide_context_slot",
    # milestone 2: truth maintenance (i/o-support, retraction)
    "WorkingMemory",
    "Action",
    "Cond",
    "Production",
    "Support",
    "match",
    "Instantiation",
    "Elaborator",
    "calculate_o_support",
    "elaborate_to_quiescence",
    # milestone 3: decision cycle + substates
    "Agent",
    "Goal",
]
