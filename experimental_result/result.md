# ARC_human 12셋 실험 결과

12 데이터셋(4개념 × 원본·트윈2·트윈3)을 **캐시 없이 독립 실행**한 결과. 각 셋은 `run_all.py` 가 solve 캐시를 지운 뒤 솔버 1회 solve → program_report 생성.

- 실행기: `run_all.py`  ·  총 소요 2429s

## 요약

| 개념 | 원본 | 트윈2 | 트윈3 |
|---|---|---|---|
| **이동(translation·anchor 정렬)** | move 60/60 | mov2 60/60 | mov3 60/60 |
| **대칭(반사)** | flip 24/24 | fli2 24/24 | fli3 24/24 |
| **회전** | rota 36/36 | rot2 36/36 | rot3 36/36 |
| **객체 재채색** | objc 8/8 | obj2 8/8 | obj3 8/8 |

**합계: 384 / 384**

## 데이터셋별 상세

| 데이터셋 | 정답/전체 | 소요(s) | 리포트 |
|---|---|---|---|
| move | 60/60 | 224.8 | [move_program_report.html](move_program_report.html) |
| mov2 | 60/60 | 275.3 | [mov2_program_report.html](mov2_program_report.html) |
| mov3 | 60/60 | 284.6 | [mov3_program_report.html](mov3_program_report.html) |
| flip | 24/24 | 208.3 | [flip_program_report.html](flip_program_report.html) |
| fli2 | 24/24 | 189.7 | [fli2_program_report.html](fli2_program_report.html) |
| fli3 | 24/24 | 204.7 | [fli3_program_report.html](fli3_program_report.html) |
| rota | 36/36 | 313.6 | [rota_program_report.html](rota_program_report.html) |
| rot2 | 36/36 | 322.2 | [rot2_program_report.html](rot2_program_report.html) |
| rot3 | 36/36 | 294.4 | [rot3_program_report.html](rot3_program_report.html) |
| objc | 8/8 | 35.7 | [objc_program_report.html](objc_program_report.html) |
| obj2 | 8/8 | 35.0 | [obj2_program_report.html](obj2_program_report.html) |
| obj3 | 8/8 | 40.8 | [obj3_program_report.html](obj3_program_report.html) |

## 비고
- 각 리포트의 Step C(TASK.solution)는 ①code(실행형) ②AST ③시각화 갤러리 3-표현. Step A/A.5/A.6/B(pixelize·objectize·anti-unification)도 함께 렌더.
- SCORE 는 리포트 상단 탭의 solved/unsolved(=정답 attempt 존재) 집계 — `python -m debugger.score <set>` 게이트와 동일 기준.
- 재실행: `python experimental_result/run_all.py` (전체) 또는 `... run_all.py move flip` (선택).
