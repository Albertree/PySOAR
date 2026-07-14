"""
soar_oracle -- run a preference set through the REAL C++ Soar kernel and read
back its decision, so PySOAR can be differentially tested against ground truth.

This is the whole point of having built SoarGroup/Soar at ~/Desktop/Soar: instead
of trusting that our port matches the kernel, we ask the kernel.

Pipeline:
  Slot  --(translate)-->  .soar productions  --(./out/soar -n)-->  trace
        --(parse)-->  (ImpasseType, winner-name | impasse-items)

Soar preference syntax emitted on the RHS:
    +  acceptable     !  require      -  reject      ~  prohibit
    >  best           <  worst        =  unary-indifferent
    > <ref> better    < <ref> worse   = <ref> binary-indifferent   = NUM numeric
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soar.preference import PreferenceType as PT  # noqa: E402
from soar.preference import Slot  # noqa: E402
from soar.decide import ImpasseType  # noqa: E402

DEFAULT_SOAR = os.path.expanduser("~/Desktop/Soar/out/soar")

# operator value (any hashable) -> a legal, unambiguous Soar operator name
_NAMES = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
]

# How each preference type renders on a Soar RHS.
_UNARY = {
    PT.ACCEPTABLE: "+",
    PT.REQUIRE: "!",
    PT.REJECT: "-",
    PT.PROHIBIT: "~",
    PT.BEST: ">",
    PT.WORST: "<",
    PT.UNARY_INDIFFERENT: "=",
}
_BINARY = {
    PT.BETTER: ">",
    PT.WORSE: "<",
    PT.BINARY_INDIFFERENT: "=",
}

_IMPASSE_WORD = {
    "tie": ImpasseType.TIE,
    "conflict": ImpasseType.CONFLICT,
    "constraint-failure": ImpasseType.CONSTRAINT_FAILURE,
    "state no-change": ImpasseType.SNC,
}


def soar_available(path: str = DEFAULT_SOAR) -> bool:
    return os.path.exists(path) and os.access(path, os.X_OK)


def _name_map(slot: Slot) -> dict:
    values: list = []
    for plist in slot.preferences.values():
        for p in plist:
            for v in (p.value, p.referent):
                if v is not None and v not in values:
                    values.append(v)
    if len(values) > len(_NAMES):
        raise ValueError("too many operators for the oracle harness")
    return {v: _NAMES[i] for i, v in enumerate(values)}


def slot_to_soar(slot: Slot) -> str:
    """Translate a Slot into a single Soar proposal production (+ run/print)."""
    nm = _name_map(slot)
    var = {v: f"<{nm[v]}>" for v in nm}

    lines = ["sp {setup", "   (state <s> ^superstate nil)", "-->"]
    # declare each operator's name once
    for v, name in nm.items():
        lines.append(f"   ({var[v]} ^name {name})")
    # emit every preference
    for ptype, plist in slot.preferences.items():
        for p in plist:
            if ptype in _UNARY:
                lines.append(f"   (<s> ^operator {var[p.value]} {_UNARY[ptype]})")
            elif ptype in _BINARY:
                lines.append(
                    f"   (<s> ^operator {var[p.value]} {_BINARY[ptype]} {var[p.referent]})"
                )
            elif ptype == PT.NUMERIC_INDIFFERENT:
                lines.append(f"   (<s> ^operator {var[p.value]} = {p.numeric})")
    lines.append("}")
    # deterministic indifferent selection so the *winner* (not just the impasse
    # type) is reproducible and comparable to PySOAR's first-in-order choice.
    lines.append("indifferent-selection -f")
    lines.append("run 1")
    lines.append("print <s>")
    return "\n".join(lines) + "\n"


def parse_outcome(output: str, nm_inv: dict) -> tuple[ImpasseType, list]:
    """Parse Soar trace -> (impasse_type, items).

    - operator impasse:  ``==>S: S2 (operator tie)``  etc.
    - clean winner:      ``O: A1 (alpha)``
    - nothing selected:  state no-change / no operator
    """
    # operator-level impasse off the top state
    m = re.search(r"==>S:\s*S\d+\s*\(operator (tie|conflict|constraint-failure)\)", output)
    if m:
        return _IMPASSE_WORD[m.group(1)], []  # items omitted (compared loosely)

    # clean winner: O: <id> (<name>)
    m = re.search(r"\bO:\s*\w+\s*\((\w+)\)", output)
    if m:
        name = m.group(1)
        return ImpasseType.NONE, [nm_inv.get(name, name)]

    # state no-change off the top state -> no operator selectable
    if re.search(r"==>S:\s*S\d+\s*\(state no-change\)", output):
        return ImpasseType.SNC, []

    return ImpasseType.NONE, []  # no operator proposed at all


def ask_oracle(slot: Slot, soar_path: str = DEFAULT_SOAR) -> tuple[ImpasseType, list]:
    """Run the slot through the C++ kernel and return its decision."""
    nm = _name_map(slot)
    nm_inv = {name: v for v, name in nm.items()}
    src = slot_to_soar(slot)
    with tempfile.NamedTemporaryFile("w", suffix=".soar", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run(
            [soar_path, "-n", "-s", path],
            stdin=subprocess.DEVNULL,           # EOF -> clean exit (no hang)
            capture_output=True, text=True, timeout=30,
        )
        return parse_outcome(proc.stdout + proc.stderr, nm_inv)
    finally:
        os.unlink(path)


def run_agent_state(src: str, soar_path: str = DEFAULT_SOAR) -> dict:
    """Run an arbitrary Soar agent and return the top state's augmentations as
    {attr: set(values)} parsed from ``print s1``. Used for milestone-2 (truth
    maintenance) differential tests: compare which WMEs survived."""
    with tempfile.NamedTemporaryFile("w", suffix=".soar", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run(
            [soar_path, "-n", "-s", path],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
        )
        out = proc.stdout + proc.stderr
    finally:
        os.unlink(path)

    # grab the (S1 ... ) block (may wrap across lines)
    m = re.search(r"\(S1\b(.*?)\)", out, re.DOTALL)
    if not m:
        return {}
    body = re.sub(r"\s+", " ", m.group(1))
    augs: dict = {}
    for attr, value in re.findall(r"\^(\S+)\s+(\S+)", body):
        augs.setdefault(attr, set()).add(value)
    return augs


def run_agent_trace(src: str, soar_path: str = DEFAULT_SOAR) -> list:
    """Run an agent under ``watch 1`` and return the normalized decision-event
    sequence parsed from the goal-stack trace. Each decision cycle emits exactly
    one of:
      ("select", <op-name>)         from   O: <id> (<name>)
      ("tie",) ("conflict",) ("constraint-failure",)
      ("onc",) ("snc",)             from   ==>S: S<n> (<kind>)

    Used for milestone-3 (decision cycle) differential tests.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".soar", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run(
            [soar_path, "-n", "-s", path],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
        )
        out = proc.stdout + proc.stderr
    finally:
        os.unlink(path)

    events: list = []
    for line in out.splitlines():
        m = re.search(r"\bO:\s*\w+\s*\((\w+)\)", line)
        if m:
            events.append(("select", m.group(1)))
            continue
        m = re.search(r"==>S:\s*S\d+\s*\((operator|state)\s+([\w-]+)\)", line)
        if m:
            kind, word = m.group(1), m.group(2)
            if word == "no-change":
                events.append(("onc",) if kind == "operator" else ("snc",))
            else:
                events.append((word,))   # tie / conflict / constraint-failure
    return events


def _is_var(s: str) -> bool:
    return isinstance(s, str) and s.startswith("<") and s.endswith(">")


def chunk_signature(conds: list, action: tuple) -> tuple:
    """Structural signature of a chunk, robust to variable NAMES.

    conds  : list of (id, attr, value)
    action : (id, attr, value)
    Returns (frozenset{(attr, 'VAR'|const)}, (attr, 'VAR'|const)). Suitable for
    single-identifier chunks (the case Soar and PySOAR both produce here)."""
    cset = frozenset((a, "VAR" if _is_var(v) else v) for (_i, a, v) in conds)
    _ai, aa, av = action
    return (cset, (aa, "VAR" if _is_var(av) else av))


def learn_chunk_signature(src: str, soar_path: str = DEFAULT_SOAR):
    """Run an agent with chunking on and return the signature of the single
    learned chunk parsed from ``print --chunks --full`` (None if none learned)."""
    with tempfile.NamedTemporaryFile("w", suffix=".soar", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run(
            [soar_path, "-n", "-s", path],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
        )
        out = proc.stdout + proc.stderr
    finally:
        os.unlink(path)

    m = re.search(r"sp \{chunk[^\n]*\n(.*?)\n\}", out, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    if "-->" not in body:
        return None
    lhs, rhs = body.split("-->", 1)

    conds: list = []
    for grp in re.findall(r"\(([^()]*)\)", lhs):
        toks = grp.replace("^", " ").split()
        if not toks:
            continue
        if toks[0] == "state":
            toks = toks[1:]
        if not toks:
            continue
        ident, rest = toks[0], toks[1:]
        for k in range(0, len(rest) - 1, 2):
            conds.append((ident, rest[k], rest[k + 1]))

    action = None
    for grp in re.findall(r"\(([^()]*)\)", rhs):
        toks = grp.replace("^", " ").split()
        if len(toks) >= 3:
            action = (toks[0], toks[1], toks[2])
            break
    if action is None:
        return None
    return chunk_signature(conds, action)


if __name__ == "__main__":
    # quick manual demo
    examples = {
        "tie": Slot().acceptable("O1", "O2"),
        "best-winner": Slot().acceptable("O1", "O2").best("O1"),
        "reject": Slot().acceptable("O1", "O2").reject("O2"),
        "conflict": Slot().acceptable("O1", "O2").better("O1", "O2").better("O2", "O1"),
        "indifferent": Slot().acceptable("O1", "O2").indifferent("O1", "O2"),
    }
    from soar.decide import decide_context_slot
    print(f"{'case':14} {'pysoar':>22} {'oracle':>22}  match")
    for name, slot in examples.items():
        pim, pca = decide_context_slot(slot)
        oim, oca = ask_oracle(slot)
        ok = "OK" if pim == oim else "MISMATCH"
        print(f"{name:14} {pim.name+' '+str(pca):>22} {oim.name+' '+str(oca):>22}  {ok}")
