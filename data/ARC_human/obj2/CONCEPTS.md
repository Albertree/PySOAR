# obj2 폴더 — Concept 설계

`obj2`는 `objc`(object_coloring)와 **완전히 동일한 concept**의 쌍둥이(twin) 문제집이다. 구조·규칙이 `objc`와 같고(OC-단일 1 + OC-다 선택근거 3종(색/크기/모양) = 4 couple = 8 JSON), 구체적인 문제만 서로 다르다 — 같은 컨셉에서 나온 서로 다른 인스턴스이며 `objc`와 동일한 문제는 하나도 없다.

- 설계 전체는 `objc/CONCEPTS.md` 참조 (선택된 객체의 색만 고정색 C로 바꾸고 위치·모양·크기는 불변).
- **objc는 손수 만든(hand-made) 데이터라 생성기가 없었으므로**, obj2용으로 컨셉 생성기 `gen_obj2.py`를 새로 작성해 만들었다(seed=20260727). objc는 그대로 두고 obj2만 생성.
- 파일 코드 `obj2` → `obj2000a`(2ex)/`obj2000b`(3ex) …, id 규칙은 HARNESS.md §9.
- 검증: 8개 전수 — pair 내 크기 고정, 객체 위치·모양·크기 불변, 정확히 1개 객체만 색 변화(→C), 객체 크기 2–9, grid 내 객체 색 전부 상이, no-op 없음. `objc`와 동일 문제 0개.
