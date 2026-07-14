"""
Effect (양식) — '무엇을 어떻게 변화시키나' 를 한 줄로 기술. **DSL 활성화의 키**.

핵심 결정: DSL 은 *계층* 으로 걸리지 않는다. *효과* 로 걸린다.
  · DSL 은 자기 effect 를 선언적 명세(semantic)로 들고,
  · Need 는 자기를 해소할 effect 를 requires 로 들고,
  · 활성화 = 둘을 *효과로* 맞춤 (matches).

  effect(verb, kind) = {"verb": verb, "kind": kind}
    verb : 변화의 종류  ("create" | "recolor" | "add" | ...)
    kind : 그 변화가 닿는 실체 타입  ("grid" | "roles" | ...)

예) make_grid → effect("create", "grid")   (size·color 로 grid 를 *지어냄*)
    PAIR 의 need(roles.output 채우기) → requires effect("add", "roles")
    → kind 가 "roles" vs "grid" 라 안 맞음 → 탐색 empty → 막힘 (의도된 결과).
"""

ANY = "*"


def effect(verb: str, kind: str) -> dict:
    """변화 한 줄 기술. DSL 명세와 Need.requires 가 같은 양식을 쓴다."""
    return {"verb": verb, "kind": kind}


def matches(required: dict, provided: dict) -> bool:
    """need.requires(required) 를 DSL.effect(provided) 가 해소하나? — *효과* 매칭.

    kind 는 일치해야 하고(무엇을 바꾸나), verb 는 일치 또는 ANY(어떻게).
    """
    if not required or not provided:
        return False
    if required["kind"] != provided["kind"]:
        return False
    return (required["verb"] == provided["verb"]
            or ANY in (required["verb"], provided["verb"]))
