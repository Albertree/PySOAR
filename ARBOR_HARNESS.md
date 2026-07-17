# ARBOR 개발 하네스 — 매 행동 전 반드시 읽는다

> 이 파일은 **PySOAR/arc 의 ARBOR 솔버를 건드리는 모든 행동(코드 작성·수정·설계·리팩터·트레이스 해석) 직전에
> Claude 가 반드시 다시 읽어야 하는 계약서**다. 압축·요약 금지. 여기 적힌 MUST / MUST NOT 은 편의나
> 효율보다 우선한다. 이 계약과 충돌하는 "더 빠른 해법"은 채택하지 않는다.
>
> 읽는 순서: **이 파일 → (해당 작업의) 위키 규약 → 코드**. 한 줄이라도 어기려는 낌새가 들면 멈추고
> 사용자에게 제안·의논한다(§7).

---

## 0. 한 줄 요지

**우리는 "이 ARC 문제를 푸는 최적 코드"를 만드는 게 아니라, "symbolic 정보를 rule-based operator 로 다루는
초기 지능체(ARBOR)의 *생각 단위 모듈*"을 만든다.** 문제 해결은 그 시스템이 돌아간 *결과*여야지, 목표가 아니다.

---

## 0.5 핵심 정의 — 이 다섯 단어를 섞지 마라 (2026-07-07 신설, §5 승인)

혼선의 뿌리는 **relation 과 program 을 같은 말처럼 쓴 것**이다. 아래 정의를 고정한다.

- **relation (서술적 · edge).** `compare()` 의 결과 `{type: COMM/DIFF, score, category}`. 두 컴포넌트의
  *차이/대응을 기술*할 뿐 **아무것도 변환하지 않는다.** ARCKG **edge**(E_*.json)로 물질화. 재귀적(2차·n차).
- **program (절차적 · PAIR 아티팩트).** transformation DSL 을 property/util/relation 표현식으로 조합한
  *실행가능* 함수 G→G. 한 pair 의 G0→G1 을 재현한다. search+verify 로 도출. `PAIR.program` 으로 물질화.
- **solution (절차적 · TASK 아티팩트).** pair.program 들을 anti-unify 한 task-general 스키마(변수 포함).
  `TASK.solution` 으로 물질화. 실체 = `compare(prog, prog)` + DIFF slot 변수화 + `resolve`.

세 기법(과정):

- **program synthesis** — *pair 안에서* program 을 찾는 search+verify. **세로축(입력→출력).** §1-3 의
  가설탐색이 여기. → `PAIR.program`.
- **structure mapping** — *pair 들 사이에서* **대응(roles)** 을 세운다. 표면 속성이 아니라 관계프로파일
  일치로(§4-2). "무엇이 pair 간에 *같은가*". **가로축.** anti-unification 의 *선행조건*이다.
- **anti-unification** — *pair 들 사이에서* 정렬된 per-pair program 들을 공통 골격+변수 스키마로 일반화.
  **가로축.** 실체 = `compare(prog,prog)` + 변수화 + `resolve`. → `TASK.solution`.

네 칸 (섞이던 것이 분리된다):

| | 서술적 (relation) | 절차적 (program) |
|---|---|---|
| **pair-특정** | `compare(G0,G1)` = 변화 스펙 (edge) | `PAIR.program` = G0→G1 구현 |
| **task-일반** | 2차 `compare` = 공통관계·대응 (edge) | `TASK.solution` = 변수 스키마 |

칸을 잇는 화살표 = operator: 서술pair→절차pair = **search**(program synthesis) · 서술pair→서술task =
**compare 2차**(structure mapping) · 절차pair→절차task = **generalize**(anti-unification) · 서술task→절차task
= **resolve**. relation(스펙)이 program 탐색을 제약하고, program 이 anti-unify 의 실체가 된다.

---

## 1. 절대 하지 말 것 (MUST NOT)

### 1-1. 막힌다고 새 operator / DSL 을 임의로 만들지 마라
- 풀이 과정에서 막히는 부분이 있어도, **새로운 operator 나 DSL 을 그 자리에서 지어내서 문제를 뚫지 마라.**
- 예: "여기서 `select_largest_object` 라는 함수 하나 만들면 풀리는데" → **금지.** 그건 손코딩 finder 를
  다시 들여오는 것이고, 시스템이 아니라 정답을 구현하는 것이다.
- 새 operator/DSL 이 정말 필요하다고 판단되면 → **§7 절차**(제안 → 의논 → 승인)를 밟는다. 승인 전엔 안 만든다.

### 1-2. 정답을 안다고 최적 풀이를 곧장 구현하지 마라
- 나(Claude)는 종종 이 ARC 문제의 답·변환을 이미 안다. 그렇다고 **그 최적 변환을 바로 코드로 박으면 안 된다.**
- 구현 대상은 "답" 이 아니라 **"이 지능체가 그 답에 *도달하는 생각의 단위 모듈*"** 이다.
- 초기 지능체는 **우리가 당연하게 여기는 것을 모른다.** "가장 큰 것", "우하단", "(H-h, W-w)" 같은 개념은
  이 지능체에겐 *공짜가 아니다*. 그것들이 비교·탐색·검증을 통해 *도출되는 과정*을 구현해야 한다.

### 1-3. 탐색을 함수 하나로 건너뛰지 마라 (수식은 바로 나오지 않는다)
- 구체 예시 (사용자 원문): 이동해야 하는 지점이 **(H-h, W-w)** 여야 한다는 것을 *내가 알고 있더라도*,
  `H` 와 `-` 그리고 `h` 를 조합해서 "좌표의 첫 번째 위치"를 결정하는 일은 **어느 정도의 탐색이 필요하다.**
- 이런 수식은 **바로 튀어나오는 것이 아니다.** 현재 지능체가 가진 수준의 정보들로 이루어진 **조합공간을
  탐색**해야 한다.
- 즉 `H-1`, `H+3`, `h-H`, `H*2`, `H-w`, `W-w`, `H-h` … 같은 **가설을 인위적으로 만들어 시도해 보고,
  train 으로 검증해서 틀린 건 버리고 맞는 걸 남기는 과정**이 반드시 있어야 한다.
- **금지 패턴**: `dest = (H - h, W - w)` 를 그냥 계산해서 넣는 것. 이건 탐색·검증 과정을 삭제하고
  정답 수식을 손으로 박은 것이다.
- **요구 패턴**: 표현식 후보를 생성(generate) → train 입력에 적용(predict) → train 출력과 대조(evaluate,
  틀리면 다음 후보) → 살아남은 것 검증(verify). 탐색이 아키텍처에 *보여야* 한다.

### 1-4. 문제를 이미 안다고 가정하고 지름길을 내지 마라
- "grid 가 두 개 있으니 비교한다" 처럼 **문제 구조를 미리 아는 척** 코드를 짜지 마라.
- 지능체의 유일한 눈은 **ARCKG** 다. 계층을 **lazy 하게, 소속(membership)된 대로 차례로** 확인해 나가는
  것 외에 세상을 보는 방법이 없다. (막혀야 내려간다 = P1.)

### 1-5. 물질화된 아티팩트를 손코딩 finder 로 채우지 마라 (2026-07-07 추가)
- program/relation/solution 을 ARCKG 아티팩트로 *저장하는 것*과, 그 값을 *진짜 탐색으로 계산하는 것*은
  **독립(직교)**이다. 좋은 저장소로 옮긴다고 계산이 정직해지지 않는다.
- **금지:** `PAIR.program` 을 "정답을 이미 아는" 함수(예: `_CORNERS = [("bottom-right", H-h, W-w), …]` 를
  열거·검증하는 `_synth_*`)의 반환값으로 채워 `program.json` 에 기록. finder 를 property 칸으로 이전한
  것이고 §1-1 위반이다.
- **요구:** program 은 `search` 가 후보식을 *생성*(그게 "코너"인 줄 모른 채)→G0 적용→G1 대조→기각→생존
  으로 채운다. 시도·기각한 후보가 아티팩트/트레이스에 남아야 한다. `(H-h, W-w)` 는 *발견*이지 전제가 아니다.
- **위험:** 물질화는 파이프라인을 *원리적으로 보이게* 만들어, 정작 탐색이 없었다는 사실을 가린다. 성공판정
  (다른 step 수·근거 잔존)조차 그럴싸한 아티팩트로 위조될 수 있다.
- **자가검증:** "이 program 에 도달하며 어떤 후보식을 시도·기각했는가?" 를 트레이스에서 답할 수 없으면 finder.

---

## 2. 반드시 할 것 (MUST)

### 2-1. ARCKG 와 각 계층의 property 를 반드시 사용하라
- 본 ARC 문제를 symbolic 계층 구조로 표현한 것이 **ARCKG** (TASK → PAIR → GRID → OBJECT → PIXEL) 이고,
  각 계층에 **정의해 놓은 property** (예: GRID = size/color/contents, OBJECT = area/color/coordinate/
  method/position/shape/size/symmetry, PIXEL = color/coordinate) 가 있다.
- 풀이에 쓰는 모든 정보는 **이 ARCKG 노드와 그 property 에서** 나와야 한다. 임의의 새 property 를
  즉석에서 만들지 않는다(필요하면 §7).

### 2-2. compare 로직으로 "항목 간 비교"와 "관계 간 비교"를 하라
- 근거(P3·P4)는 항상 **compare 의 결과(COMM/DIFF)** 에서 나온다.
- 반드시 **항목 간 비교**(노드 ↔ 노드) 뿐 아니라 **관계 간 비교**(관계 ↔ 관계 = 2차, 그 이상 = n차)를
  사용한다. 사용자가 설계한 `compare()` 는 2차·3차·그 이상도 재귀적으로 비교할 수 있다 —
  (ARC-solver `ARCKG/comparison.py`, `compare(a,b)` 에서 a,b 가 비교결과 dict 여도 그 `result` 를 재귀 비교).
- "가장 긴 / 가장 큰" 같은 파생 관계는 **요소끼리 비교해 `longer_than` 류 관계를 만들고, 그 관계들을 다시
  비교(2차)해 relational profile("outgoing 관계 3개")로 매칭**해 도출한다. 하드코딩 rank 열거로 대체 금지.

### 2-3. ARC 를 analogical reasoning 문제로 다뤄라 (이게 핵심 프레임)
- ARC 는 **유추(analogical reasoning)** 문제다. **Pair 들 사이의 GRID 변화를 비교해 그 *공통 구조*를 찾는
  것**이 중요하다.
- **혼동 주의 (2026-07-07 정정, §0.5):** "각 object 를 순위대로 재채색" 같은 *sequence of transformation* 은
  **relation 이 아니라 그 변화를 실현하는 program 이다.** relation(=compare 의 COMM/DIFF)은 변화의 *스펙*
  (무엇이 보존/변경되나)이고, program 은 그 스펙을 만족시키는 *구현*이다. 이 둘을 같은 말로 부르지 마라.
- 세 과정으로 나뉜다 (정의는 §0.5):
  - **한 pair 의 G0→G1 변환식을 찾는 과정 = program synthesis** (세로축; 변환/표현식 조합공간 탐색;
    §1-3 의 가설 탐색이 여기). → `PAIR.program`.
  - **pair 들 사이에서 대응(roles)을 세우는 과정 = structure mapping** (가로축; 속성이 아닌 관계프로파일
    일치, §4-2). anti-unification 의 선행조건.
  - **정렬된 per-pair program 들을 공통 스키마로 일반화하는 과정 = anti-unification** (가로축; 실체 =
    compare(prog,prog)+변수화+resolve). → `TASK.solution`.

### 2-4. 시스템 구현에 초점을 맞춰라 (문제 풀이가 아니라)
- 매 커밋/변경의 자문: **"이게 이 지능체의 생각 단위 모듈을 구현한 것인가, 아니면 이 문제의 정답을 구현한
  것인가?"** 후자면 되돌린다.
- 검수 기준의 예: 서로 다른 문제는 서로 다른 탐색·서로 다른 step 수를 낳아야 한다. **모든 문제가 같은
  step 수로 풀리면**(예: 4문제 전부 186 step) 그건 탐색이 함수 안에 숨은 것 — 시스템이 아니라 정답을
  구현했다는 신호다.

### 2-5. 구조체를 바꿨으면 dashboard 에 반영하라 (2026-07-07 추가)
- 사용자는 **`focus_dashboard.html`** 로 구현을 *시각적으로* 검증한다. WM/ARCKG/program/relation/solution
  등 **구조체(데이터 모델)를 추가·변경하면 그 변화가 dashboard 렌더링에 반드시 드러나야** 한다.
- 새 아티팩트(`PAIR.program`·`TASK.solution`·relation edge)나 스키마 변경은 그 생성 코드(focus_solver /
  dashboard 생성부)에서 **패널·필드로 노출**한다. 화면에 안 보이면 검증 불가 = 미완.
- 특히 §1-5 의 탐색 트레이스(시도·기각 후보)와 하강 단계는 dashboard 에서 읽혀야 한다 (근거가 WM 에
  남는다 = 화면에도 남는다).

### 2-6. 결정성 — 결과에 영향 주는 반복은 반드시 정렬하라 (2026-07-17 추가, 개발 중 2회 발생)
- **문제:** WM·객체집합·후보목록 등을 **평범한 `set`/`dict` 로 반복**하면 순서가 **`PYTHONHASHSEED`
  (프로세스마다 랜덤)**에 따라 달라진다. operator body 의 `next((.. for .. in ..), default)` **첫-매치 픽**,
  매처 바인딩 순서, resolve 후보/version-space 순서 등 **순서가 결과를 바꾸는 지점**에서 이는 **실행마다
  경계 태스크 결과가 뒤집히는 비결정성**을 낳는다 (측정·검증 불가). 실제로 `wm.py __iter__` 는 정렬됐으나
  `wm.matching()` 이 raw set 을 돌아 같은 버그가 재발했다(2026-07-17). "집합은 순서 무관" 은 **첫-매치·
  탐색 순서에는 틀린 말**이다.
- **MUST:** 결과(첫-매치·후보순위·트레이스·제출)에 영향을 주는 모든 반복은 **결정적 키로 정렬**해서 돈다.
  WM 반복(`__iter__`·`matching()`·`all()`)은 **같은 정렬 키**를 쓴다. `set.pop()`·`next(iter(set))`(len>1)·
  set 리터럴 반복 금지. `dict` 는 삽입순서가 결정적일 때만 안전(삽입이 정렬된 소스에서 왔는지 확인).
- **자가검증:** "같은 코드·같은 데이터·같은 max_cycles 인데 `PYTHONHASHSEED` 를 바꾸면 solve 결과가
  같은가?" 를 물어라. 다르면 비결정 반복이 남은 것 — 찾아서 정렬한다. (검증: 여러 seed 로 경계 태스크를
  돌려 동일 결과 확인.)

- ARBOR 는 **symbolic 하게 표현된 정보**를 **rule-based operator** 로 동작시키는 **초기 지능체**다.
- 초기 지능체인 만큼, **우리가 당연하게 생각하는 것을 모를 수 있다.** ("가장 큰", "코너", "순위",
  "H-1", "대응되는 object" 등은 전부 *도출 대상*이지 전제가 아니다.)
- 그러므로 개발의 초점은 **효율적인 문제 풀이 방식을 찾아 그 문제를 해결하는 것**이 아니라, **이 구조체의
  system(생각의 단위 모듈)을 구현하는 것**이다.
- 지능체가 "당연한 것"을 스스로 비교·탐색·검증으로 **획득해 가는 과정**을 만드는 것이 목적이다.

---

## 4. 구체 예시 모음 (원문 보존 — 지우지 말 것)

### 4-1. 좌표 수식 (H-h, W-w) — "바로 나오지 않는다"
> 예를 들어 이동해야 하는 지점이 (H-h, W-w) 이여야 하는 것을 알고 있더라도, H 와 - 그리고 h 를 조합해서
> 좌표의 첫 번째 위치에 결정하는 것은 어느 정도의 탐색이 필요하다. 이러한 수식은 바로 나오지 않는 것이기
> 때문에 현재 가지고 있는 수준의 정보들의 조합공간을 탐색하는 것이 필요하다. **H-1, H+3, h-H, H*2, H-w
> 등의 가설을 인위적으로 만들어 시도해보고 검증하는 과정은 필요하다.**

→ 구현 시사점: position 의 각 성분(row, col)을 결정할 때, `{H, W, h, w, 상수, +, -, *}` 로 만들 수 있는
후보 표현식을 **생성→train 적용→대조→다음 후보** 로 걸러라. 정답 `(H-h, W-w)` 를 손으로 계산해 박지 마라.

### 4-2. "가장 긴 회색 막대" — relational profile 로 도출
- 두 pair 의 회색 막대는 길이가 달라 "같은 객체"로 이을 근거가 없다. "가장 긴"은 fixed property 가 아니라
  *어떤 범위에서 비교해야* 정해지는 derived 속성이다.
- 도출법: 각 grid 안에서 object 끼리 비교 → `A → longer_than → {B,C,D}` (outgoing 3개). 다른 pair 에서
  `E → longer_than → {F,G,H}` (outgoing 3개). → **A 와 E 를 잇는 근거 = "각자 outgoing longer_than edge
  가 3개"** 라는 relational profile(구조적 역할 동등성 = structure mapping). 이걸 2차 compare 로 매칭한다.

### 4-3. relation = sequence of transformation 일 수 있다
- 어떤 pair 의 G0→G1 relation 은 "size COMM, color COMM, contents DIFF" 같은 property 관계로 끝나지 않고,
  "**각 object 를 제자리에서 순위대로 재채색**" 이라는 *변환열*로 표현될 수 있다. 그 변환열 자체가 pair 의
  relation 이고, 이것을 pair 들끼리 anti-unify 해 공통 구조를 찾는다.
- **정정 (2026-07-07, §0.5):** 위 "변환열 자체가 pair 의 relation" 은 용어가 섞인 표현이다. 정확히는 그
  *변환열 = program*(그 pair 의 G0→G1 구현)이고, relation 은 그 변화의 *스펙*(compare COMM/DIFF)이다.
  pair 들끼리 anti-unify 되는 대상도 relation 이 아니라 **program 들**(→ `TASK.solution`)이다. 취지(변환열이
  pair 의 핵심이며 그것을 pair 간 일반화한다)는 유효하되, 여기의 "relation" 은 "program" 으로 읽어라.

---

## 5. 위반이 의심될 때의 절차 (§1 을 어기게 될 것 같으면)

1. **멈춘다.** 코드를 짜지 않는다.
2. 무엇이 막혔는지, 왜 기존 operator/DSL/property 로 안 되는지 **구체적으로 진단**한다.
3. **제안한다**: "새 operator/DSL/property X 가 필요해 보인다. 이유는 …, 대안은 …" 를 사용자에게 제시.
4. **의논을 통해 받아들일지 결정**한다. 사용자의 승인 전에는 만들지 않는다.
5. 승인되면 그때 구현하고, 규약(이 파일)·위키에 근거를 남긴다.

> 원칙: "막혀서 못 푸는 것"은 실패가 아니다. **막힘을 정직하게 드러내는 것**이 이 프로젝트의 검증 방식이다
> (impasse 는 정보 부족의 *검증*). 막힘을 몰래 함수로 메우는 것이 진짜 실패다.

---

## 6. 관련 규약·계획 (이 하네스의 상위 근거 — 함께 참조)

- **7 원리 (P1–P7)** — `~/Desktop/wiki/wiki/arbor-execution-trace.md`:
  P1 계층 깊이는 필요(막힘)로 · P2 비교는 동일 레벨끼리 · P3 정답엔 근거(값보다 이유) ·
  P4 근거는 비교의 결과에서 · P5 변수 출처는 G0(test 엔 G1 없음) · P6 2개씩 짝지어 비교 ·
  P7 모든 정보 symbolic dict + json.
- **compare 엔진 (2차·n차)** — ARC-solver `~/Desktop/ARC-solver/ARCKG/comparison.py` `compare(a,b)`.
- **within-pair 비교 / lazy 하강** — ARC-solver `agent/descent.py` (G0↔G1 비교), `objects_of()` lazy.
- **스키마 결정 (2026-07-07 — §5 절차로 사용자 승인).** program/relation/solution 을 ARCKG 에 물질화한다:
  `relation` = **edge**(compare 결과 E_*.json; 이미 존재) · `PAIR.program` = PAIR 폴더 아래 **파생 아티팩트**
  (program.json; to_json 0th-order property 아님 — pair.py 계약 "관측만") · `TASK.solution` = TASK 폴더 아래
  **파생 아티팩트**(solution.json; task.py 계약 "비교·파생 결과 금지"라 to_json 아님). 이들은 문제특이
  property 가 아니라 *구조적 슬롯*이므로 §1-1 위반이 아니다. 근거: wiki {arckg-node-edge, arbor-operators}.
- **재건 계획(현행, 2026-07-07 갱신).** driver = **property 공백 기반 하강**: `solve` 가 `TASK.solution` 제출
  시도 → 공백 → impasse → PAIR 하강 → `PAIR.program` 공백 → impasse → GRID/OBJECT 하강 → relation(compare)
  획득 → 그걸 *이용해* program(search+verify) → program 들 anti-unify → solution. 4칸(서술/절차 × pair/task,
  §0.5)이 이 순서로 채워진다. 테스트 사다리 easy000a → made000b → 08ed6ac7 → made000a. 성공 판정 = 4문제
  하강 깊이·step 수가 서로 달라지고, 각 아티팩트(relation/program/solution)가 디스크에 남으며 근거
  (COMM/DIFF)가 WM 에 남는다.
- **위키 허브** — `~/Desktop/wiki/wiki/pysoar.md`, `arbor-operators.md`, `arckg-node-edge.md`,
  `coarse-to-fine-abductive-reasoning.md`, `structure-mapping-theory.md`, `anti-unification.md`.

---

## 7. 매 행동 전 체크리스트 (스스로 묻는다)

- [ ] 지금 새 operator/DSL/property 를 임의로 만들고 있지 않은가? (만들면 §5 절차)
- [ ] 정답을 알아서 최적 변환을 바로 박고 있지 않은가? 생각 단위 모듈을 구현하는가?
- [ ] 수식/좌표/선택을 **탐색+검증** 없이 손으로 계산해 넣지 않았는가? (§1-3, §4-1)
- [ ] 정보는 전부 **ARCKG 노드 property** 에서 나오는가? (§2-1)
- [ ] 근거는 **compare(COMM/DIFF)** 에서 나오는가? 항목 비교뿐 아니라 **관계 비교(2차/n차)** 를 쓰는가?
- [ ] program synthesis(pair 안·세로)와 structure mapping(대응)·anti-unification(program 일반화·가로)을
      구분해 쓰는가? relation(스펙·edge)과 program(구현·PAIR 아티팩트)을 혼동하지 않는가? (§0.5)
- [ ] 물질화된 아티팩트(program/solution)가 **진짜 탐색**에서 나왔는가 — 시도·기각한 후보가 트레이스에
      남는가? (없으면 finder — §1-5)
- [ ] 서로 다른 문제가 서로 다른 탐색/step/**하강 깊이**를 낳는가? (같으면 함수에 숨은 것)
- [ ] 막혔다면, 몰래 메우지 않고 **정직하게 impasse 로 드러내고** 사용자에게 제안했는가?
- [ ] 구조체(program/solution/relation·스키마)를 바꿨으면 **`focus_dashboard.html`** 에 패널·필드로
      반영했는가? (§2-5)
- [ ] 결과에 영향 주는 반복을 **정렬**했는가? `PYTHONHASHSEED` 를 바꿔도 solve 결과가 같은가? (§2-6)
