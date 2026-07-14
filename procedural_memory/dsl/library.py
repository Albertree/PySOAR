"""
DSL 학습 라이브러리 — semantic 의 *자라는* 부분 ([[arbor-memory-contents]]).

**한 추상 = 한 파일.** 파일명 = opaque ID = *구조 해시* (같은 구조 → 같은 ID = 공짜
중복제거). 파일 안: {id, schema(=구조=의미), provenance, reuse_count}.
이름·설명 필드 없음 — 초기 지능체는 함수 이름을 못 만든다. 의미는 *구조(schema)* 에 있고,
사람은 ID 가 아니라 그 구조(명명된 씨앗의 합성)를 읽어 이해한다.

  semantic_memory/dsl_library/abs_<hash>.json

index(빠른 조회 캐시)·과제 간 병합(structure-mapping)은 규모가 커지면 추후 (지금은
"색칠" 메커니즘 하나라 불필요). 검색이 필요하면 파일을 직접 훑는다 (몇 개뿐).
"""

import hashlib
import json
import os

LIB_DIR = "dsl_library"


def _struct_id(schema: dict) -> str:
    """구조의 지문(해시). 같은 구조 → 같은 ID."""
    canon = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(canon.encode()).hexdigest()[:8]


def _lib_dir(root: str) -> str:
    return os.path.join(root, LIB_DIR)


def deposit(schema: dict, provenance: dict, root: str) -> dict:
    """추상 한 개 적재. 같은 구조(해시 동일)면 provenance·reuse_count 만 갱신, 새 구조면 새 파일."""
    lib = _lib_dir(root)
    os.makedirs(lib, exist_ok=True)
    sid = _struct_id(schema)
    fpath = os.path.join(lib, f"abs_{sid}.json")

    if os.path.exists(fpath):
        with open(fpath) as f:
            entry = json.load(f)
        entry["reuse_count"] = entry.get("reuse_count", 0) + 1
        if provenance not in entry["provenance"]:
            entry["provenance"].append(provenance)
    else:
        entry = {"id": sid, "schema": schema, "provenance": [provenance], "reuse_count": 0}

    with open(fpath, "w") as f:
        json.dump(entry, f, indent=2, ensure_ascii=False)
    return entry


def load(root: str) -> list:
    """라이브러리의 모든 추상 (파일 직접 훑기 — index 없음)."""
    lib = _lib_dir(root)
    if not os.path.isdir(lib):
        return []
    out = []
    for name in sorted(os.listdir(lib)):
        if name.startswith("abs_") and name.endswith(".json"):
            with open(os.path.join(lib, name)) as f:
                out.append(json.load(f))
    return out
