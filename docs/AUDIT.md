# Fidelity Audit — Preference / Impasse (Milestone 1)

날짜: 2026-06-15. 오라클: `~/Desktop/Soar` (SoarGroup/Soar 9.6.5, C++).
대조 대상: `~/Desktop/SOAR-ARC-test`, `~/Desktop/ARC-solver`.

## 정본 (oracle)
`Core/SoarKernel/src/decision_process/decide.cpp:1104` `run_preference_semantics`.
SOAR의 **유일한 숙고 지점**. preference를 8단계 캐스케이드로 해소하고
impasse 종류(NONE/CONSTRAINT_FAILURE/CONFLICT/TIE)를 반환한다.
impasse 상수: `shared/constants.h:26`.

```
1. Require           -> 승자 1개, 아니면 CONSTRAINT_FAILURE(>1개 / require+prohibit)
2. Accept/Reject/Prohibit  -> 후보집합 = acceptable − (reject ∪ prohibit)
3. Better/Worse      -> 진 쪽 제거, 순환이면 CONFLICT
4. Best              -> best 후보만 남김 (후보 중 best가 있을 때만)
5. Worst             -> worst 후보 제거 (non-worst가 남을 때만)
6. Indifferent       -> 전부 상호 indifferent면 승자 1개, 아니면 TIE
```

## 발견 — 두 파이썬 구현 모두 preference 의미론 **미구현**

| | C++ 오라클 | SOAR-ARC-test | ARC-solver |
|---|---|---|---|
| preference 단위 | operator 값 + 14 type | operator **이름** 고정순위(`PREFERENCE_ORDER`) | **property 이름** 순위 (operator 선호 아님) |
| 선택 | 8단계 캐스케이드 | `min(rank)` | `cands[0]` |
| TIE impasse | indifferent 아니면 발생 | **구조상 불가** | **불가** |
| CONFLICT | better/worse 순환 | 없음 | 없음 |
| CONSTRAINT_FAILURE | require 충돌 | 없음 | 없음 |
| impasse→substate | 종류가 substate 할 일 결정 | no-change/예외 2종 | 고정 `next_level` 하강 |

### 핵심 결론
- **tie 평가(look-ahead) substate가 빠진 건 우연이 아니다.** tie impasse를 만들
  preference 엔진 자체가 없었기 때문. → `wiki/arbor.md` "정정 2" 와 정확히 일치.
- ARC-solver의 고정 `next_level` 하강은 `wiki/impasse.md`가 이미 "architecture 아님"
  으로 정정한 바로 그 안티패턴. impasse 종류 기반 emergent descent로 가야 함.
- `preferences.py`/`preference.py`의 "preference"는 SOAR 용어를 빌렸을 뿐 다른 개념
  (operator 이름 순위 / property 순위)이라, 이름이 혼선을 키웠다.

## 처방 — `pysoar/decide.py`
`run_preference_semantics`를 decide.cpp 라인 주석과 함께 1:1 충실 포팅.
미묘한 지점까지 보존:
- require + **prohibit** = 실패지만 require + **reject** = require 승 (둘의 유일한 차이, decide.cpp:1227).
- best가 후보 아닌 값을 가리키면 **무효**(no-op), 후보 안 줄임 (decide.cpp:1546).
- 모든 후보가 worst면 worst **무효** (decide.cpp:1635).
- better/worse 순환 → CONFLICT, 비순환 체인 → 최상위 승자.

## 검증 — 오라클 차등 테스트 (`tests/test_oracle_diff.py`)
같은 preference 집합을 **PySOAR**와 **실제 `out/soar`** 양쪽에 먹여 결정 비교.
17개 시나리오 전부 impasse 종류 일치 (승자도 일치, 아래 1건 제외).

```
tie / conflict / constraint-failure / best / worst / better / worse /
chain / reject / prohibit / all-rejected / best-over-worst / ...  → 17/17 OK
```

## 알려진 미세 발산 (DESIGN FREE)
**완전 indifferent 집합의 승자 선택.** Soar 기본은 확률적(softmax). `-f`(first)로
고정해도 커널이 acceptable을 **prepend**해 내부 순서가 역순이라 first=마지막삽입.
PySOAR는 삽입순 first. → impasse 종류(NONE)는 동일, 구체적 승자만 다름.
사용자 위키가 선택 기준을 `DESIGN FREE`로 명시한 지점이라 PySOAR는 결정적
"삽입순 first"로 커밋. 필요 시 `decide.py`의 indifferent 분기 한 줄로 조정 가능.

## 다음 마일스톤
1. ✅ **i-support / o-support 진리유지(retraction)** — 마일스톤 2 완료 (아래).
2. substate 생성 + impasse WME 자동 기입(`^superstate ^impasse ^item …`) +
   operator no-change(ONC) 의 cross-cycle 감지.
3. chunking / backtracing (또는 ARBOR의 anti-unification 대체).

---

# Fidelity Audit — i/o-support & Retraction (Milestone 2)

## 정본 (oracle)
- o-support 판정: `instantiation.cpp:545 calculate_support_for_instantiation_preferences`
- retraction: `instantiation.cpp:1412 retract_instantiation` —
  "retract any preferences that are in TM and aren't o-supported" (line 1431).

### o-support 규칙 (선언 없을 때 아키텍처가 결정)
1. operator를 **제안**(`(state ^operator <o> +)`, id가 state) → **i-support**.
2. 선택된 operator를 **LHS에서 테스트**(`(lowest-goal ^operator <x>)`, non-acceptable) →
   - RHS가 operator만 elaborate → **i-support** (operator elaboration).
   - RHS가 그 외를 만듦 → **o-support** (operator application).
   - 섞이면 → i-support (경고).
3. 그 외 모든 elaboration → **i-support**.

### retraction 규칙
인스턴스화가 더 이상 매칭 안 되면(조건 WME 소멸) 철회 → 그 인스턴스화가 만든
preference 중 **i-support만 제거, o-support는 잔존**. 이게 진리유지.

## 발견 — 두 파이썬 레포 모두 support 개념 **부재**
- support 타입(i/o) 자체가 없음 → retraction도 persistence도 둘 다 없음.
- SOAR-ARC-test `cycle.py`의 "no-change"는 *WME 개수 변화*로만 판정 — apply가
  덮어쓰면 변화로 보지만, **조건이 사라져 결과가 철회돼야 하는 경우를 못 잡음**.
- 증상: substate에서 만든 가설/중간 WME가 조건이 바뀌어도 **안 죽고 남는 유령 WME**.
  (네가 처음에 말한 "내 생각대로 안 도는" 그 버그의 직접 원인.)

## 처방 — `pysoar/{wm,production,elaborate}.py`
- `WorkingMemory`: WME 삼중쌍 + goal/level (o-support의 lowest-goal 탐색용).
- `Production`/`match`: positive/negated 조건 매칭 (Rete는 캐시 최적화라 생략, ARC
  스케일에선 naive 매칭이 quiescence와 동치).
- `Elaborator.settle()`: assert/retract를 quiescence까지. **상태 지속이 핵심** —
  fresh 엔진은 자기가 뭘 derive했는지 몰라 retract 못 함(첫 구현 버그였음).
  i-support WME = 현재 매칭되는 인스턴스화의 합집합; o-support WME = 한 번 fire되면
  지속(reject로만 제거). `calculate_o_support`는 cpp:545 라인주석과 함께 1:1 포팅.

## 검증 — 오라클 차등 (`tests/test_oracle_retraction.py`)
판별 시나리오(apply-go=o-support, elab=i-support, apply-clear=reject)를 **실제
`out/soar`** 와 PySOAR 양쪽에서 구동 → 최종 WM의 판별 속성 비교:
- `^trophy won` PRESENT (o-support는 operator go 사라져도 잔존)
- `^marker` ABSENT (reject), `^derived` ABSENT (i-support는 marker 소멸시 retract)
양쪽 완전 일치. 단위 11 + 차등 2 = **13/13**, 전체 누적 **60/60**.

## 다음 마일스톤
- ✅ 결정 사이클 결합 (substate + ONC/SNC) — 마일스톤 3 완료 (아래).
- chunking / backtracing (또는 anti-unification 대체).

---

# Fidelity Audit — 결정 사이클 결합 (Milestone 3)

## 정본 (oracle)
- `decide.cpp:2708 decide_context_slot` — preference 해소 → winner 설치 또는 impasse.
- `decide.cpp:1869 create_new_impasse` / `2536 create_new_context` — substate +
  impasse WME 자동 기입.
- `decide.cpp:2805 attribute_of_impasse` — NO_CHANGE인데 operator 선택돼 있으면
  attr=operator→**ONC**, 없으면 attr=state→**SNC**.

### substate 에 아키텍처가 설치하는 WME (cpp:1877-1962, 2549)
`^type state ^superstate <g> ^impasse <tie|conflict|constraint-failure|no-change>
^choices <multiple|none> ^attribute <operator|state> ^quiescence t` +
tie/conflict이면 `^item <cand>… ^item-count N`.

### 핵심 규칙 — 슬롯 "decidable" (재진동 방지)
operator가 선택되면 그 선택은 *유지*되고 슬롯은 재결정 안 됨(re-tie 안 함). 선택된
operator가 더 이상 candidate가 아닐 때(지원 상실/reject)만 재고려. 선택이 유지된 채
더 결정할 게 없으면 → operator no-change(ONC).

## 발견 — 오라클로 직접 동작 확인 (추측 금지)
tie-resolve 에이전트를 `out/soar`에 돌려 **실제 동작을 관찰**:
```
D1 ==>S: S2 (operator tie)        # tie → substate
D2 O: O2 (a)                       # substate가 best 부여 → 해소 → 선택
D3 ==>S: S3 (operator no-change)   # 선택됐지만 deselect 없음 → ONC
D4 ==>S: S4 (state no-change)      # ONC substate 안엔 op 없음 → SNC 캐스케이드
D5… S5,S6,… (무한 SNC)
```
첫 구현은 매 사이클 재결정해 **진동**(tie↔select 반복)했음 — 오라클이 "선택 유지 후
ONC"가 정답임을 알려줌. 신호추적 없이 제어흐름으로 잡힘(선택 유지된 채 fall-through =
no progress = ONC).

## 처방 — `pysoar/agent.py`
`Agent`가 M1 `run_preference_semantics` + M2 `Elaborator.settle`를 PSA로 결합:
1. PROPOSE: settle (i-support elaboration + operator 제안, apply도 여기서).
2. DECIDE: goal stack top-down. 선택 유효하면 skip(non-decidable). winner→설치+하위
   substate 해소. impasse→substate 생성(또는 같은 종류 있으면 ^item 갱신 후 더 깊이).
3. operator preference는 active 인스턴스화에서 수집(진리유지된 집합) → M1 Slot.
substate 해소는 M2 진리유지가 처리: 상위 impasse 풀리면 substate WME 제거→의존 룰 retract.

## 검증 — 오라클 차등 (`tests/test_oracle_cycle.py`)
같은 에이전트를 `out/soar`와 PySOAR 양쪽 실행 → **결정 이벤트 시퀀스**(select/tie/
conflict/onc/snc) 사이클 단위 비교. 2 시나리오(tie-해소 / operator-시퀀스→SNC) 일치.
단위 8 + 차등 2 = 10/10. 누적 **70/70**.

## 다음 마일스톤
- ✅ chunking / backtracing — 마일스톤 4 완료 (아래).
- anti-unification 통합 — chunking의 *정확 변수화*를 일반화 합성으로 대체(ARBOR 방향).

---

# Fidelity Audit — Chunking / Backtracing (Milestone 4)

## 정본 (oracle)
- `ebc_build.cpp:218 get_results_for_instantiation` — preference 중 id의 level이
  인스턴스화의 match goal level보다 *낮으면*(상위 state) **result**.
- `ebc_backtrace.cpp:104 backtrace_through_instantiation` — result 인스턴스화의
  조건을 훑어: WME id level ≤ goal level이면 **ground**(청크 LHS), 아니면 **local**
  → 그 WME를 만든 인스턴스화로 재귀. 아키텍처 substate WME(^impasse/^superstate…)는
  생성 인스턴스화 없어 기여 안 함.

청크 = 변수화된 grounds → LHS, 변수화된 result → RHS. **변수화**는 원본 인스턴스화를
따름: 원본 production에서 *변수*로 매칭된 심볼은 변수화(같은 WM 심볼 → 같은 청크 변수),
*상수*는 상수 유지.

## 오라클로 실제 학습 결과 관찰 (`chunk always`)
compute 에이전트(substate가 상위 ^a/^b를 직접 테스트 → result ^result):
```
sp {chunk*compute*t3-1 :chunk
    (state <s1> ^b <b1> ^a <a1>)  -->  (<s1> ^result computed) }
```
정확히 예측대로 — grounds = 상위 ^a/^b, 값은 변수로 테스트돼 변수화, ^result는 상수.

## 처방 — `pysoar/chunk.py`
`backtrace` (result 인스턴스화 → grounds, local은 provenance 맵으로 재귀, 아키텍처
attr는 drop) + `_Variablizer`(원본 var/const 보존) + `build_chunk`. Agent에 `learn`
플래그 → 매 propose settle 후 `_learn_chunks`가 result 탐지·청크 합성·production에 추가.

## 검증 — 오라클 차등 (`tests/test_oracle_chunk.py`)
같은 compute 에이전트를 `out/soar`(chunk always)와 PySOAR 양쪽 학습 → 청크 **구조
시그니처**(조건 (attr, var?/const) 집합 + result, 변수명 무관) 비교 일치. 상수 테스트
케이스도 검증(상수 유지). 단위 6 + 차등 2 = 8/8. 누적 **78/78**.

## 알려진 한계 (anti-unification이 들어갈 자리)
- **tie-resolve 청크 미지원**: substate 룰이 아키텍처 WME(`^impasse tie`)만 테스트하면
  backtrace ground가 비어 청크 안 만듦. Soar는 *architectural impasse-item 인스턴스화*
  를 통해 tie items(상위 operator preference)로 역추적함 — 그 특수 기계는 미구현.
- 정확 변수화만 — anti-unification(부분 일반화/구조 매핑)은 다음 마일스톤. 이 `chunk.py`
  의 `build_chunk`가 그 대체 지점.
- negated 조건은 청크에 안 실림.

## 다음 마일스톤
- anti-unification 통합 — `build_chunk`의 1:1 변수화를 여러 result 인스턴스의
  *최소 일반 일반화*로 교체. 여기서부터 오라클 없는 ARBOR 설계 영역.
