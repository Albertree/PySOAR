# ARBOR

**ARBOR** = SOAR 인지 아키텍처 위에서 **ARCKG**(TASK→PAIR→GRID→OBJECT→PIXEL 5계층
지식그래프)로 ARC 문제를 푸는 symbolic 추론 에이전트. 이 레포는 **self-contained** —
SOAR 결정 커널(`arbor/soar/`, 옛 이름 *PySOAR*), 지각/추론(`arbor/perception/`·
`arbor/reasoning/`), 절차·의미·일화 LTM(`arbor/procedural_memory/`·`arbor/semantic_memory/`·
`arbor/episodic_memory/`), 문제 제시·채점용 환경(`env/`), 후처리 시각화(`debugger/`),
원본 데이터(`data/`)를 한데 둔다.

**진입점:** `python -m arbor [--dataset D] [--tasks ID]` — `env` 가 `data/` 에서 문제를
제시하고 `arbor` 가 풀이, `env` 가 채점(3회 재시도)한다.
**게이트:** `python -m debugger.score move` → `SCORE: 60/60`.
**대시보드:** `python -m debugger.reports.dashboard` → `debugger/reports/dashboard.html`
(풀이 과정 시각화).
**행동보존 검증:** `PYTHONPATH=. python3 tests/verify_refactor.py`.

## SOAR 커널 (`arbor/soar/`)

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
arbor/soar/
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
tests/oracle/
  soar_oracle.py  Slot/agent → .soar → ./out/soar 실행 → 결정/WM/트레이스/청크 파싱
```

## 사용
```python
from arbor.soar import Slot, decide_context_slot, ImpasseType        # M1
decide_context_slot(Slot().acceptable("a", "b").better("a", "b"))  # (NONE, ["a"])
decide_context_slot(Slot().acceptable("a", "b"))                   # (TIE, ["a","b"])

from arbor.soar import WorkingMemory, Production, Cond, Action, Elaborator  # M2
elab = Production("elab", [Cond("S1","a","<v>")], [Action("S1","b","<v>")])
wm = WorkingMemory(); wm.mark_goal("S1"); wm.add("S1","a","1")
el = Elaborator([elab]); el.settle(wm)     # (S1 ^b 1) 생김 (i-support)
wm.remove("S1","a","1"); el.settle(wm)     # 지원 사라짐 → (S1 ^b 1) retract

from arbor.soar import Agent                                      # M3
ag = Agent([                                                      # tie → 해소 → 선택
    Production("pa", [Cond("S1","superstate","nil")], [Action("S1","operator","a","+")]),
    Production("pb", [Cond("S1","superstate","nil")], [Action("S1","operator","b","+")]),
    Production("resolve", [Cond("<s>","impasse","tie"), Cond("<s>","superstate","<ss>")],
               [Action("<ss>","operator","a",">")]),
])
ag.step()  # tie -> substate S2;  ag.step() -> select a, S2 해소
```

## 현재 구조 (top-level, 정확히 6개 디렉터리)

```
arbor/                 지능체 본체 — soar/ 커널 위에 지각/추론/기억/솔버를 얹는다.
  soar/                 결정 커널 (M1–M4, 위 표)
  perception/           ARCKG 지각(arckg/) + nav.py(lazy 하강) + spelke.py
  reasoning/             compare_engine.py(COMM/DIFF, 2차/n차) · antiunify.py ·
                         program.py / program_ast.py (PAIR.program)
  procedural_memory/    operator body + production rule (기초 DSL)
  semantic_memory/      학습된 스킬 추상화 (디스크)
  episodic_memory/      태스크별 실행 트레이스 (디스크)
  agent/focus.py         조립 + REFLEX LOOP: inject_focus + setup_focus_agent.
                         solve 를 미지 operator 로 두고 impasse(operator no-change)로
                         substate 를 열어 focus 를 ARCKG 한 레벨씩 하강시키며 observe/compare 로 채운다
                         (PRODUCTIONS/OPERATOR_BODIES 는 procedural_memory 에서 배선)
  engine/                트레이서(trace.py) · 렌더러(renderer.py) · sink.py
  expr_solver.py         ARCKG 빌더(build_arckg, to_json→WME 로더). observe/compare/
                         generalize/compose 파이프라인은 은퇴, 지금은 agent/focus 와
                         procedural_memory operator 가 공용으로 쓰는 ARCKG 구성 로직만 남음
  memory.py              procedural/semantic/episodic LTM 의 디스크 접근 계층
  __main__.py             python -m arbor 진입점
env/                    world harness — data/ 에서 문제를 제시하고 arbor 의 제출을 채점
  dataset.py             list_tasks / load_task
  environment.py         ARCEnvironment (3회 재시도, pixel-exact 채점)
data/                   원본 ARC 코퍼스 (easy / move / human 등 데이터셋)
debugger/               풀이 과정 후처리 시각화 — arbor/env 를 import 만 하고 상위참조 안 됨
  score.py               score_dataset — 게이트 (python -m debugger.score move)
  solve_cache.py         run_solve — 태스크 1개 풀이 + 캐시
  reports/dashboard.py   python -m debugger.reports.dashboard → dashboard.html
docs/                   설계 문서
tests/                  python -m unittest discover -s tests -p "test_*.py"
  oracle/                soar_oracle.py — C++ Soar 차등 오라클 파서
```

의존 방향: `env/` 는 `arbor` 를 import 하지 않고, `arbor/soar/` 는 `arbor` 상위 패키지나
`env` 를 import 하지 않는다 — 커널은 순수 SOAR 결정 사이클 의미론만 담는다.

## 테스트
```bash
python -m unittest discover -s tests -p "test_*.py"   # 전체 178 (skipped=27)
python -m unittest tests.test_oracle_chunk -v          # M4 오라클 차등 (out/soar 필요)
python -m tests.oracle.soar_oracle                     # M1 차등 데모 표
```
오라클은 `~/Desktop/Soar/out/soar`를 자동 사용하며, 없으면 차등 테스트는 skip.

## 왜 이렇게
"디테일을 다 챙길 수 있나"를 추측이 아니라 **측정**으로 답하기 위해.
오라클 차등이 있으면 미스매칭이 추상적 불안이 아니라 실패하는 테스트로 드러난다.
preference/impasse는 17/17 일치로 확인됨.

다음 마일스톤: **anti-unification 통합** — `chunk.py`의 1:1 정확 변수화를 여러 result
인스턴스의 *최소 일반 일반화*로 교체 (ARBOR 방향, 오라클 없는 설계 영역).
[`docs/AUDIT.md`](docs/AUDIT.md) 참고.
