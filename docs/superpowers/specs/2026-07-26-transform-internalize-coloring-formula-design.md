# 변환 내재화 — 좌표식 coloring 으로 fallback 을 메인 흐름에 합치기

> 설계 확정: 2026-07-26 (대화 수렴). 초기 지능체는 **coloring 밖에 모르며 "center/axis/rotate/flip/move"
> 개념이 없다.** 모든 표현은 좌표 산술 + coloring 으로 닫히고, 불변은 **compare 로 관찰**해 쓴다(가정 금지).

## 0. 목표

현재 rotate/flip 을 푸는 로직은 `arbor/reasoning/transform.py` 의 **fallback**(SOAR anti-unify 루프 밖,
`agent.py::_try_transform_fallback`)에 있다. 이를 **메인 흐름(anti-unify 의 impasse-resolution)** 으로 내재화하고
(§10d 숙제), 그 결과를 **좌표식 coloring** 으로 표현한다. move 도 같은 골격의 특수경우로 통일한다.

## 1. 불변식 (반드시 지킨다)

- **개념 이름 금지:** 프로그램·아티팩트·필드 어디에도 `center/axis/pivot/rotate/flip/move` 를 symbol 로 넣지 않는다.
  (`(r0+r1)//2` 같은 **산술식**은 허용 — 새 symbol 아님. 두 좌표의 평균일 뿐.)
- **불변은 compare 로 관찰:** mover in/out 을 compare 해 어떤 bbox 산술값이 COMM 인지 **발견**한다. 관찰 안 되면
  그 배치를 가정하지 않는다(막힘으로 남긴다).
- **표현은 좌표식 coloring:** `∀ 픽셀 (r,c)∈객체 O: coloring((F행(r,c), F열(r,c)), 색)`. F = 원자
  `{r,c,r0,c0,r1,c1,h,w,H,W,상수}` + `{+,−,×,//}`.
- **게이트 불변:** move 60/60 · rotate 36/36 · flip 24/24. HASHSEED 무관 결정적. 새 operator/DSL/property 는 §5 절차.

## 2. 표현 (Q1 — 개념 없는 task.solution)

변환 = **객체 O 의 각 픽셀에 공통 좌표식 F 적용**:
```
select O  (역할/불변 property 로; 다객체면 compare-대응)
∀ p=(r,c) ∈ O:  coloring( ( a·r+b·c+e ,  d·r+f·c+g ),  색(p) )
```
- 선형부 `(a,b,d,f)` 와 오프셋 `(e,g)` 는 **좌표식**이다 (D4·중심은 표현에 안 나옴; 탐색 전략일 뿐).
- move = `(1,0,0,1)` + 평행이동 오프셋. flip = 반사 선형부 + `(c0+c1)−c` 류. rotate = 회전 선형부 + 오프셋.
- **펼침(픽셀별 N개 coloring) = anti-unify 가 F 를 찾는 근거. 합침(O→F) = TASK.solution.**

## 3. 불변식 발견 (compare 로 center-산술 정당화)

비정사각 제자리 회전의 오프셋은 `(r0+r1)//2` 를 거친다(검증됨: 순수 2연산 탐색은 12/18 에서 막힘, 비정사각
회전이 벽). 이 `//2` 는 **compare 로 관찰된 불변**에서만 정당화한다:
- mover in/out 의 bbox 산술값(`r0+r1`, `c0+c1`, 코너 등)을 compare → **COMM 집합** 발견.
- `r0+r1` 과 `c0+c1` 이 COMM(=제자리) 이면 그 오프셋을 쓴다. 아니면 다른 불변을 찾거나 impasse.
- 코드·아티팩트에 "center" 라 쓰지 않는다. `bbox합 COMM` 이라는 compare 결과로만 표기.

## 4. 단계 (게이트 검증하며)

- **Stage 1 — 좌표식 + compare-불변 (solver, 저위험).** `transform.py` 에 (a) mover in/out compare 로 불변 발견,
  (b) 해 를 `(a,b,d,f,e,g)` 좌표식으로 노출하는 함수. 현행 18/18·60/60 유지 확인. 파이프라인 미변경.
- **Stage 2 — coloring 물질화 (report).** 해를 `∀픽셀 coloring(F(p),색)` 로 물질화해 `PAIR.program`/보고서에
  노출. A.5 pixelize 가 자동으로 픽셀별 전개(예 15+1). "왜 N개인가 = 규칙 F 의 정의역=객체" 를 화면에 표기.
- **Stage 3 — anti-unify 내재화 (core loop, 고위험).** diff program 이 안 맞는 impasse 에서 §2·§3 로직을
  anti-unify 의 impasse-resolution 으로 호출. fallback 훅 제거. move 도 이 경로로 통일. **게이트 재검증 필수.**

## 5. 위험 · 열린 결정

- Stage 3 은 메인 solve 루프 변경 → move 60/60 회귀 위험. 단계별 게이트 없이 진행 금지.
- 다객체 선택 규칙(area/색 불변)도 compare-도출로 정당화 필요(현행은 코드가 판단). Stage 3 에서 정리.
- 비정사각을 (a) 방침(center-산술 허용)으로 푸므로, `//2` 산술이 좌표식에 등장한다. 이름만 안 붙이면 규약 OK.
