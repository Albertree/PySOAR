# ARBOR

**ARBOR** = SOAR 인지 아키텍처 위에서 **ARCKG**(TASK→PAIR→GRID→OBJECT→PIXEL 5계층
지식그래프)로 ARC 문제를 푸는 symbolic 추론 에이전트. 이 레포는 **self-contained** —
SOAR 결정 커널(`soar/`, 옛 이름 *PySOAR*), 지각/추론(`arbor/`), 절차·의미 LTM
(`procedural_memory/`·`semantic_memory/`), 디버거(`debugger/`), 데이터(`data/`)를 한데 둔다.

진입점: `python -m debugger.build` → `arc/focus_dashboard.html` (풀이 과정 시각화).
행동보존 검증: `PYTHONPATH=. python3 tests/verify_refactor.py`.

## SOAR 커널 (`soar/`)

SOAR 결정 코어의 **충실도 우선(fidelity-first) 파이썬 재구현** (옛 이름 PySOAR).
C++ 커널(324k LOC, 절반은 안 쓰는 SVS) 1:1 트랜스파일이 아니라, ARBOR가 의존하는
**결정 사이클 의미론**만 정확히 옮기고, `~/Desktop/Soar`의 C++ 빌드를
**차등 검증 오라클**로 둔다.

## 완료된 마일스톤

**M1 — preference / impasse.** SOAR의 **유일한 숙고 지점**(operator 선택)과 거기서
나오는 TIE / CONFLICT / CONSTRAINT-FAILURE impasse.

**M2 — i/o-support 진리유지(retraction).** propose 산출물(i-support)은 조건이 사라지면
자동 철회, apply 산출물(o-support)은 지속. 이전 ARC 포팅엔 support 개념 자체가 없어
**유령 WME**(조건 바뀌어도 안 죽는 중간 결과)가 생겼던 그 버그의 근원.

**M3 — 결정 사이클 결합.** M1+M2를 PSA(Propose-Select-Apply)로 묶어 **impasse 시
substate 자동 생성**(`^impasse ^choices ^attribute ^item ^quiescence`) + ONC/SNC.
위키의 "tie → 평가 substate → 해소 → 선택" 흐름이 처음으로 실제로 돌아감.

**M4 — chunking (backtracing).** substate가 result를 만들면 그 result를 만든 상위
state 조건을 역추적(backtrace)해 변수화 → 새 규칙(청크) 합성. 다음 번 같은 상황은
impasse 없이 청크가 직접 해결. anti-unification이 들어갈 자리.

→ 감사 결과와 근거는 [`docs/AUDIT.md`](docs/AUDIT.md).

```
pysoar/
  preference.py   [M1] PreferenceType(14종, enums.h 그대로) · Slot
  decide.py       [M1] run_preference_semantics (decide.cpp:1104) · ImpasseType
  wm.py           [M2] WorkingMemory — WME 삼중쌍 + goal/level
  production.py   [M2] Cond · Action · Production · match (positive/negated)
  elaborate.py    [M2] Elaborator.settle — assert/retract 진리유지 (cpp:545,1431)
  agent.py        [M3] Agent — PSA 사이클 + substate/ONC/SNC (decide.cpp:2708,1869)
  chunk.py        [M4] backtrace · build_chunk — EBC 역추적 (ebc_build/backtrace.cpp)
tests/
  test_decide.py      [M1] 단위 30   test_oracle_diff.py       [M1] 차등 17
  test_retraction.py  [M2] 단위 11   test_oracle_retraction.py [M2] 차등 2
  test_agent.py       [M3] 단위 8    test_oracle_cycle.py      [M3] 차등 2
  test_chunk.py       [M4] 단위 6    test_oracle_chunk.py      [M4] 차등 2
oracle/
  soar_oracle.py  Slot/agent → .soar → ./out/soar 실행 → 결정/WM/트레이스/청크 파싱
```

## 사용
```python
from pysoar import Slot, decide_context_slot, ImpasseType        # M1
decide_context_slot(Slot().acceptable("a", "b").better("a", "b"))  # (NONE, ["a"])
decide_context_slot(Slot().acceptable("a", "b"))                   # (TIE, ["a","b"])

from pysoar import WorkingMemory, Production, Cond, Action, Elaborator  # M2
elab = Production("elab", [Cond("S1","a","<v>")], [Action("S1","b","<v>")])
wm = WorkingMemory(); wm.mark_goal("S1"); wm.add("S1","a","1")
el = Elaborator([elab]); el.settle(wm)     # (S1 ^b 1) 생김 (i-support)
wm.remove("S1","a","1"); el.settle(wm)     # 지원 사라짐 → (S1 ^b 1) retract

from pysoar import Agent                                          # M3
ag = Agent([                                                      # tie → 해소 → 선택
    Production("pa", [Cond("S1","superstate","nil")], [Action("S1","operator","a","+")]),
    Production("pb", [Cond("S1","superstate","nil")], [Action("S1","operator","b","+")]),
    Production("resolve", [Cond("<s>","impasse","tie"), Cond("<s>","superstate","<ss>")],
               [Action("<ss>","operator","a",">")]),
])
ag.step()  # tie -> substate S2;  ag.step() -> select a, S2 해소
```

## DSL 표현식 resolver (솔버 일반화의 핵심)

`arc/dsl.py` + `arc/expr_solver.py`. wiki arbor-dsl-taxonomy 그대로: **모든 출력 =
`make_grid`(캔버스) + `coloring`(셀 칠) — frozen 2개.** 의미는 transformation 조합이
아니라 **각 arg가 어떤 표현식이냐**. arg가 specific 값이면 property로 *일반 표현식*을
찾는다 — 예: 출력 좌표 (5,5)를 literal이 아니라 `corner-br = (H-1,W-1)`로 resolve.
SOAR 사이클(observe→compare→**generalize**(=resolve_arguments)→**compose**(=make_grid+
coloring)). 못 풀면 정직하게 decline(arg 미해결 시 None).
```bash
python3 arc/expr_solver.py   # easy_a 9/9, easy 6/16 + 해결된 표현식 출력
# easy000a:  position=corner-br  color=literal(2)  size=size_of(input)  fill=background(input)
```
**retry diversification (3-submit).** under-determined 태스크(train 2 pair가 한 인자에서
모순)는 단일 답이 안 나온다. `dsl.ranked_hypotheses`가 후보를 train 일관수로 랭킹하고,
`run.py`가 3-submit 환경에서 **틀리면 다음 후보를 제출**(wiki "틀림→reject→다음 후보").
가설은 모든 test pair에 적용(env는 전 test pair all-or-nothing 채점).
```bash
python3 arc/expr_solver.py   # easy_a 9/9 · easy 1-submit 6/16, 3-submit 13/16
python3 arc/run.py easy      # 진짜 환경 retry로 13/16
```
정직: 남은 3개는 진짜 모순(입력 동일·출력 다름). retry가 6→13(+7). 진짜 병목=표현식 폭
(특히 relation 표현식 부재). 손코딩 finder를 **일반 표현식 탐색 + 후보 랭킹**으로 교체한
게 핵심.

## 전체 시스템 (진짜 데이터 · 3-submit 환경 · 메모리)

ARC-solver를 mirror한 인프라. **진짜 ARC 데이터**로 돌고, 결과는 **과장 없이 정직**하다.
```
arc/dataset.py      실제 데이터셋 로드 (~/Desktop/ARC-solver/data: easy_a/easy/human/agi/agi2)
arc/environment.py  3-submit retry 환경 (reset/step/can_retry, pixel-exact 채점) — ARC-AGI-2 식
arc/memory.py       semantic/episodic/procedural 메모리 (디스크) — episodic 트레이스 기록
arc/run.py          에피소드 루프: 진짜 데이터 → 환경 → 통합 에이전트 → 메모리
```
```bash
python3 arc/run.py easy_a      # 9/9  (가설공간을 맞춘 단일픽셀)
python3 arc/run.py easy        # 5/16 (안 본 데이터 — 정직히 부분적)
python3 arc/run.py agi 100     # 0/100 (진짜 ARC-AGI-1 — 솔직한 현실)
```
**정직한 베이스라인:** 검증된 건 *커널*이고, *ARC 풀이 능력*은 단일객체류에 한정. 진짜
ARC-AGI엔 0/100. 인프라는 진짜로 돌지만 솔버 일반화가 약하다 — 여기서부터 개선.

## ARC 풀이 — 통합 에이전트 (솔버 코어)

**`arc/solver.py` — 단일 에이전트, 단일 기본 규칙 집합.** operator 전부(observe/select/
compare/generalize/compose/submit)를 한 풀에 두고, **기본 production 규칙이 *문제 상태*로
어떤 operator를 제안할지 결정**한다 (단계 플래그 하드코딩 ❌, 사람이 스크립트 고르기 ❌).
같은 규칙으로 시퀀스가 task마다 emergent:
```
단일+변환    : observe → compare → generalize → compose → submit   (select 안 뜸)
다객체+선택  : observe → select → compare → compose → submit       (generalize 안 뜸)
다객체+변환  : observe → select → compare → generalize → compose → submit  (둘 다)
```
```bash
python3 arc/make_tasks.py && python3 arc/solver.py    # easy_a 9 + 다객체 4 = 13/13, ONE agent
```
분기(`select`가 뜨나? `generalize`가 뜨나?)는 결정 사이클이 WM 보고 정함 — `propose-select`는
`^multi yes`일 때만, `propose-generalize`는 `^needs-transform yes`일 때만 발화. 디버거로 확인 가능.

> `arc/soar_solver.py`(단일 변환)·`arc/select_solver.py`(다객체 선택)는 통합 전 분리 버전 —
> 이제 `solver.py`가 둘을 하나로 합침(헬퍼는 재사용). 아래는 그 분리 버전들의 설명.

## ARC 풀이 (easy_a 9/9)

**`arc/soar_solver.py` — WM-주도 일반 operator 솔버 (권장, 위키 arbor-operators 설계).**
일반 operator(observe → compare → generalize → compose → submit)가 **실제 ARCKG**
노드를 WM에서 다루고, **PySOAR 결정 사이클**이 매 단계 구동한다. 규칙은 손코딩이 아니라
compare+generalize(anti-unify)로 *도출*된다 — 같은 operator가 task마다 다른 규칙을 냄
(pos=const/delta/diag, col=const/copy).
```bash
python3 arc/soar_solver.py    # 9/9, ARCKG + WM-driven
```
단계마다 WM이 변하는 흐름: `observed → compared(color/coord COMM/DIFF) →
schema-ready(rule-color/rule-position) → answer-ready → done`. operator는 일반적이고
(task-specific 아님), task 지식은 ARCKG 속성 + 도출된 schema에 있다. 새 property 추가로
커버리지 확장(새 operator 불필요).

**`arc/solve.py` — 얇은 첫 버전 (참고용).** task-specific 가설(const_constC 등)을 PySOAR
preference로 선택. 격자는 Python, 선택만 SOAR. soar_solver.py가 이걸 일반화한 것.

**`arc/select_solver.py` — 다객체 + `select` operator.** observe→select→compose→submit.
`select`가 어느 객체가 살아남는지 보고 선택 *근거*를 도출: 고정속성(`color==2`),
일반화속성(`argmax(area)`), 관계(`same_row(marker)`). 같은 operator가 세 근거를 모두
처리 — 커버리지는 속성/관계 추가로 늘지 operator로 늘지 않음.
```bash
python3 arc/make_tasks.py && python3 arc/select_solver.py   # 다객체 3/3
```

**`arc/dashboard.py` — 웹 GUI 디버거 (영역 분할, ARC-solver dashboard.html mirror).**
한 화면을 영역으로 나눠 **모든 SOAR 요소**를 매 결정 사이클마다 표시: goal stack · WM
(추가=초록/철회=빨강취소선) · elaboration(발화/철회 규칙) · decision(제안 operator+
preference, impasse/후보/선택) · operator detail(ARCKG 객체·resolve된 표현식·make_grid+
coloring) · grids(train/test/후보들). 하단 타임라인으로 스텝 이동. 트레이스는 실제 PySOAR
사이클(`agent.py:_record`) + ARC kg에서 나옴.
```bash
python3 arc/dashboard.py easy 1 && open arc/dashboard.html   # easy 1 = retry 케이스
```

한계(정직): 여전히 좁은 태스크류(단일 객체 변환 + 단일 객체 선택). 다객체 *변환*,
구조 일반화는 다음 단계.

## 테스트
```bash
cd ~/Desktop/PySOAR
python3 -m unittest discover -s tests -v        # 전체 80
python3 -m unittest tests.test_oracle_chunk -v  # M4 오라클 차등 (out/soar 필요)
python3 oracle/soar_oracle.py                   # M1 차등 데모 표
```
오라클은 `~/Desktop/Soar/out/soar`를 자동 사용하며, 없으면 차등 테스트는 skip.

## 왜 이렇게
"디테일을 다 챙길 수 있나"를 추측이 아니라 **측정**으로 답하기 위해.
오라클 차등이 있으면 미스매칭이 추상적 불안이 아니라 실패하는 테스트로 드러난다.
preference/impasse는 17/17 일치로 확인됨.

다음 마일스톤: **anti-unification 통합** — `chunk.py`의 1:1 정확 변수화를 여러 result
인스턴스의 *최소 일반 일반화*로 교체 (ARBOR 방향, 오라클 없는 설계 영역).
[`docs/AUDIT.md`](docs/AUDIT.md) 참고.
