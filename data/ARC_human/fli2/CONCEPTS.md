# fli2 폴더 — Concept 설계

`fli2`는 `flip`과 **완전히 동일한 concept**의 쌍둥이(twin) 문제집이다. 구조·규칙·생성 로직이 `flip`과 같고(객체분류 6 × 반전방향 2 = 12 couple = 24 JSON, **파일 내 parity 통일 포함**), 오직 **난수 seed만 달라** 구체적인 문제가 서로 다르다 — 같은 컨셉에서 나온 서로 다른 인스턴스이며, `flip`과 동일한 문제는 하나도 없다.

- 설계 전체는 `flip/CONCEPTS.md` 참조 (parity 통일 규칙 포함).
- 생성기: 루트 `gen_fli2.py` (`gen_flip`의 생성 함수를 그대로 재사용, seed만 변경).
- 파일 코드 `fli2` → `fli2000a`(2ex)/`fli2000b`(3ex) …, id 규칙은 HARNESS.md §9.
- 검증: 24개 전수 구조·반전 변환 정확성 통과, 파일 내 parity 통일(24/24 uniform). `flip`과 짝별 대조 시 동일 문제 0개.
