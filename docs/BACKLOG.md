# 백로그 — seokki-refactor2 후속 작업

이번 브랜치 구조 정리 중 "나중에" 로 미룬 항목들. 각 항목은 게이트(move 60/60)·이벤트
패리티(골든)·테스트(unittest) 를 지키며 진행한다.

## 1. expr_solver 해체 / 정리
- `arbor/expr_solver.py` 는 이름과 달리 solver 가 아니라 **ARCKG 빌더**(`build_arckg`) + to_json→WME
  로더(`_load_value`/`_tup`). importer 12곳.
- 할 일: **`arckg_build.py`(가칭) 로 rename** 해 정체를 드러내고, 필요하면 빌더/로더를 분리(해체).
  importer 전부 갱신 + 게이트/패리티 검증.

## 2. lazy ARCKG (build 경량화)
- 지금 `build_arckg`(expr_solver:62-67) 가 grid 마다 **`extract_objects()` eager 호출** → 안 쓸
  object/pixel 까지 다 만듦. `objects_of` 는 lazy hook(`if not grid.objects: extract`) 이 있고
  `pixels_of` 는 raw 에서 즉석 생성(이미 stored 의존 제거됨).
- 할 일: build 에서 eager extract 제거 + **`index_arckg`(nav.py:25,33 가 grid.objects/pixels 를
  index-time 에 훑음) 와 하강 로직을 lazy 화** — focus 가 object/pixel 레벨에 내려갈 때 비로소
  추출. "막혀야 내려간다"(P1) 를 연산에서도 실현. 위험: index/descent 가 빈 컬렉션을 잡지 않게.

## (참고) 그 밖에 표면화된 미배선/정리거리
- effect-매칭(`effect.matches`/`requires`) 미배선 — DSL 활성화가 effect 로 되게 하려면 배선 필요.
- select DSL / `scope` 타입 미호출 — 실제 선택은 select operator 가 WM 인라인 추론. DSL 은 표면
  언어(dashboard 렌더)로만 쓰임.
- `set_grid_size`/`set_grid_color` DSL 은 선언 stub("contents 가 산출 지배" 모델). program_ast 의
  `set_grid_*` AST 빌더와 이름 겹침(별칭으로 회피 중) — 필요 시 이름 구분.
