# rot2 폴더 — Concept 설계

`rot2`는 `rotate`와 **완전히 동일한 concept**의 쌍둥이(twin) 문제집이다. 구조·규칙·생성 로직이 `rotate`와 같고(객체분류 6 × 회전횟수 3 = 18 couple = 36 JSON, **파일 내 parity 통일 포함**), 오직 **난수 seed만 달라** 구체적인 문제가 서로 다르다 — 같은 컨셉에서 나온 서로 다른 인스턴스이며, `rotate`와 동일한 문제는 하나도 없다.

- 설계 전체는 `rotate/CONCEPTS.md` 참조 (parity 통일 규칙 포함).
- 생성기: 루트 `gen_rot2.py` (`gen_rotate`의 생성 함수를 그대로 재사용, seed만 변경).
- 파일 코드 `rot2` → `rot2000a`(2ex)/`rot2000b`(3ex) …, id 규칙은 HARNESS.md §9.
- 검증: 36개 전수 구조·회전 변환 정확성 통과, 파일 내 parity 통일(36/36 uniform). `rotate`와 짝별 대조 시 동일 문제 0개.
