"""
memory -- the three SOAR long-term memories as on-disk folders, mirroring
ARC-solver (semantic_memory / episodic_memory / procedural_memory). PySOAR's
WM is in-RAM (the kernel); these are the persistent stores.

  procedural_memory/  : the agent's rules -- base production rules + learned
                        chunks (procedural knowledge; see wiki/soar.md).
  episodic_memory/     : one execution trace per solved/attempted task -- the
                        temporally-ordered solve trace (descent order, compares,
                        program trajectory). Raw material for anti-unification.
  semantic_memory/     : the learned DSL/skill abstraction library -- decontextualized,
                        cross-task skill cards (grown by anti-unification), NOT the
                        per-task ARCKG. (ARCKG is contextual/perception-derived = a
                        persisted projection of Working Memory; it flushes to episodic.
                        See wiki/arbor-soar-memory-mapping + arbor-memory-contents.)

This module writes episodic traces and the procedural rule manifest; the semantic
skill library is populated by anti-unification depositing distilled skill cards.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Memory:
    def __init__(self, root: str = ROOT):
        self.semantic = os.path.join(root, "semantic_memory")
        self.episodic = os.path.join(root, "episodic_memory")
        self.procedural = os.path.join(root, "procedural_memory")
        for d in (self.semantic, self.episodic, self.procedural):
            os.makedirs(d, exist_ok=True)

    def write_episode(self, task_id: str, episode: dict) -> str:
        """One execution episode: ops, criterion/transform, reward, attempts."""
        path = os.path.join(self.episodic, f"{task_id}.json")
        with open(path, "w") as f:
            json.dump(episode, f, indent=2, default=str)
        return path

    def write_procedural_manifest(self, base_rules: list, chunks: list) -> str:
        """Record the agent's procedural knowledge: base rules + learned chunks."""
        manifest = {
            "base_rules": [_rule_repr(r) for r in base_rules],
            "learned_chunks": [_rule_repr(r) for r in chunks],
        }
        path = os.path.join(self.procedural, "rules.json")
        with open(path, "w") as f:
            json.dump(manifest, f, indent=2)
        return path

    def episode_count(self) -> int:
        return len([f for f in os.listdir(self.episodic) if f.endswith(".json")])


def _rule_repr(prod) -> dict:
    conds = [f"({c.id} ^{c.attr} {c.value}{' -' if c.negated else ''})"
             for c in prod.conditions]
    acts = [f"({a.id} ^{a.attr} {a.value} {a.pref})" for a in prod.actions]
    return {"name": prod.name, "if": conds, "then": acts}
