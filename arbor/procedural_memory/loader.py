# -*- coding: utf-8 -*-
"""procedural_memory.loader — JSON 실물 규칙 → 커널 Production 리스트 로더.

propose/apply 규칙은 `production_rules/<operator>.json` 에 operator 단위로 산다
(RETE 대신 물리적 JSON — arbor-soar-memory-mapping 의 procedural memory). 이 로더가
그 JSON 을 커널 `Production`(선언적 조건-액션)으로 복원한다. operator 실행 body 는
`procedural_memory/operators/` 에 있고 규칙의 operator 이름으로 결선된다.

focus_solver 의 옛 인라인 `PRODUCTIONS`/`OP_DOCS` 를 대체 (진실의 출처 = JSON 파일).
`order` 필드로 원본 리스트 순서를 정확히 보존 → 대시보드 rules 패널 동일.
"""
from __future__ import annotations

import glob
import json
import os

from arbor.soar import Cond, Action, Production

_RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "production_rules")


def _cond(d):
    return Cond(d["id"], d["attr"], d["value"], d.get("negated", False))


def _action(d):
    return Action(d["id"], d["attr"], d["value"], d.get("pref", "+"), d.get("referent"))


def _rule(entry):
    return (entry["order"],
            Production(entry["name"],
                       [_cond(c) for c in entry["conditions"]],
                       [_action(a) for a in entry["actions"]]))


def load_rules(rules_dir: str = _RULES_DIR):
    """production_rules/*.json → (PRODUCTIONS 리스트, OP_DOCS 딕셔너리).

    PRODUCTIONS 는 각 규칙의 `order` 로 정렬해 원본 순서를 재현한다."""
    ordered, op_docs = [], {}
    for path in sorted(glob.glob(os.path.join(rules_dir, "*.json"))):
        spec = json.load(open(path, encoding="utf-8"))
        if spec.get("doc"):
            op_docs[spec["operator"]] = spec["doc"]
        for entry in spec.get("propose", []) + spec.get("apply", []):
            ordered.append(_rule(entry))
    ordered.sort(key=lambda t: t[0])
    return [p for _, p in ordered], op_docs


PRODUCTIONS, OP_DOCS = load_rules()
