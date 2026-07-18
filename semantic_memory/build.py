# -*- coding: utf-8 -*-
"""semantic_memory.build — DSL registry 의 선언적 명세(spec)를 semantic 라이브러리로 방출.

두 얼굴(arbor-memory-contents): DSL 한 항목 = **body(procedural)** + **spec(semantic)**.
여기서는 spec 쪽만 모아 `semantic_memory/ontology.json` 으로 물질화한다 — anti-unification·
비교·합성은 불투명 body 가 아니라 이 spec(name·kind·in/out·effect)에만 작용한다.

Slice 1 은 vendored DSL 의 최소 명세만(26개). 학습된 고차 DSL(learned_skills/)은
anti-unify 로 후생성되어 여기 자란다 (지금 풍부히 짜면 "그럴싸한 추상" — 금지).

    python -m semantic_memory.build     # -> semantic_memory/ontology.json
"""
from __future__ import annotations

import json
import os

# @dsl 등록 트리거 (import 시 SPECS 채워짐)
import procedural_memory.dsl.transformation  # noqa: F401
import procedural_memory.dsl.property        # noqa: F401
import procedural_memory.dsl.relation        # noqa: F401
import procedural_memory.dsl.util            # noqa: F401
import procedural_memory.dsl.selection       # noqa: F401
from procedural_memory.dsl.registry import SPECS, spec


def build_ontology() -> str:
    """SPECS(body 제외) → kind 별로 묶어 ontology.json 으로 쓴다."""
    by_kind: dict = {}
    for name in sorted(SPECS):
        s = spec(name)                       # body 를 뺀 선언적 명세
        by_kind.setdefault(s["kind"], {})[name] = s
    onto = {
        "note": "DSL 선언적 명세(semantic 라이브러리). body=procedural 은 procedural_memory/dsl/ 에 있다. "
                "transformation 은 동결 하나(coloring), 나머지는 조합 재료.",
        "counts": {k: len(v) for k, v in sorted(by_kind.items())},
        "dsl_specs": by_kind,
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ontology.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(onto, f, ensure_ascii=False, indent=2)
    return out


if __name__ == "__main__":
    print("wrote", build_ontology())
