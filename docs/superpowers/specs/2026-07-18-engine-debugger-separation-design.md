# 실행 엔진 ↔ 디버거 분리 설계 (Engine / Journal / Renderer)

- 날짜: 2026-07-18
- 상태: 승인됨 (brainstorming §1–§4)
- 선행 컨텍스트: [ARBOR_HARNESS.md](../../../ARBOR_HARNESS.md), memory `[[seokki-refactor]]`
- 성공 불변조건: **arc_human/move 60/60 유지**, seed 0/1/42 결정성 유지, 전체 pytest 신규 회귀 0

## 0. 배경 — 왜 지금 이 작업인가

현재 ARBOR 는 **디버거가 곧 솔버**인 구조다.

- `soar/agent.py`의 네이티브 `Agent.step()`/`Agent.run()`은 generic SOAR 커널이라 **ARCKG 계층 하강을 모른다**. 실측: `setup_focus_agent` 로 만든 agent 를 `ag.run(500)` 만 돌리면 move 를 못 푼다(답 없음, 500 사이클을 헛돌며 focus/level 마커 0개 = 하강 자체가 안 일어남).
- ARBOR 의 실제 solve 제어 로직 — **P1 계층 하강(`_do_descend`), arg-선택 substate(`_open_arg_substate`), 2-사이클 ONC 감지** — 이 전부 `arbor/engine/trace.py`의 `_Tracer` 안에 있다. `_Tracer.run()`은 결정 사이클을 **통째로 재구현**하며, 동시에 매 micro-step 마다 full WM 스냅샷을 뜨고 HTML 이벤트를 방출한다.
- 결과: (1) 실행·제어·시각화가 한 덩어리라 "디버거 없이 빠르게" 자체가 불가능하다. (2) 두 개의 결정 사이클(`Agent.step()` vs `_Tracer.run()`)이 갈라져 유지보수 위험. (3) 채점·회귀조차 `run_solve`가 `_Tracer` 로만 실행돼 시각화 비용을 전부 낸다(원래 60초 중 ~15–20초가 WM 스냅샷).

목표는 **구조체의 실행과정과 디버거의 출력/시각화를 떼어내는 것**이다. 실행은 메모리에서 빠르게 진행되고(WM 상주), 디버거는 그 출력물(journal)을 받아 시간순으로 풀어서 보여주기만 한다. 이게 되어야 속도 제약 없이 확장(op-body 가시성 등 Part-2)해 나갈 수 있다.

이 문서는 그 분리의 **1차 하위 프로젝트**만 다룬다. op-body 해체(arg 탈절차화, 원자단위 분해)는 이 seam 이 깔린 뒤의 후속 작업이다.

## 1. 컴포넌트 경계와 계약

사이클 로직은 **물리적으로 옮기지 않는다**(제자리 재구성 = 리스크 최소). 방출 지점에 이음새(seam)를 넣어 의존성을 역전한다.

```
┌─ EngineRun (지금의 _Tracer.run 사이클 — 하강·ONC·arg-substate 그대로) ─┐
│   결정 사이클을 돌리며, 방출 지점마다 self.sink.event(...) 만 호출        │
│   sink 가 무엇인지 모른다 (의존성 역전)                                   │
└──────────────────────────────────────────────────────────────────────┘
        │ sink 주입
   ┌────┴─────────────────────────┐
   ▼                              ▼
NullSink (headless)          JournalSink (debug)
 event() = pass               event() + WM mutation 을 append-only 로 기록
 → 채점·대량 = 방출비용 0       → journal(이벤트 + WM 델타) 축적
                                        │
                                        ▼
                              Renderer (순수 함수: journal → events/wm_states)
                                        │
                                        ▼
                              dashboard.py (기존 그대로 — 손 안 댐)
```

**계약:**

- **Engine**: 방출 지점마다 `sink.event(phase, kind, label, highlight=None, detail=None, rule=None, goal_stack=None)` 만 호출한다. 현재 `emit()` 내부의 WM 스냅샷·이벤트 dict 조립·dedup 로직은 전부 sink 로 이동한다. Engine 은 순수 실행이 된다.
- **Sink 인터페이스**: `event(...)` + WM 변경 훅 수신. `NullSink` 은 전부 no-op → headless 는 방출 비용 0. `JournalSink` 은 이벤트와 WM mutation 을 append-only journal 로 기록.
- **Renderer**: journal 을 입력받아 **현재와 동일한 `events` + `wm_states` 자료구조**를 재생산하는 순수 함수. 따라서 `debugger/dashboard.py`·`_HTML`·`make_dashboard` 는 한 줄도 바뀌지 않고, 결과 HTML 을 baseline 과 byte 비교로 검증할 수 있다.
- **run_solve**: `mode="score"` → NullSink(빠름, `attempts` 만 반환) / `mode="debug"` → JournalSink → Renderer.

의도: **실행은 sink 를 모르고, 디버거는 실행을 모른다(journal 만 본다).** 나중에 `_Tracer` 를 `engine.py` + `renderer.py` 로 rename 하는 것은 이 seam 이 검증된 뒤의 순수 파일 이동으로 미룬다(§4-e).

## 2. WM 델타를 event-sourcing 으로 (스냅샷 제거)

**현재 병목:** `emit()`이 매 이벤트마다 `_wm()`로 전체 WM 을 O(n) materialize + `_wm_states` dedup. 31k 이벤트 × 수천 WME = 원래 ~15–20초. 근본 원인은 "매 이벤트마다 전체 WM 을 훑는다".

**해법:** WM 변경은 오직 `wm.add`/`wm.remove` 두 곳에서만 일어난다. 여기에 **선택적 저널 훅**을 단다.

```python
# soar/wm.py — add/remove 안 (Task 1 의 _invalidate() 옆)
if self.journal is not None:            # headless = None → None 체크 한 번(무시할 비용)
    self.journal.append(("+", w))       # 또는 ("-", w)
```

- **headless(NullSink)**: `wm.journal = None` → 매 mutation 에 `is not None` 한 번. 사실상 0. 채점은 그대로 빠르다.
- **debug(JournalSink)**: `wm.journal = 로그`. 각 mutation = O(1) append. 이벤트가 방출될 때 sink 는 **그 순간의 로그 길이(cursor)만** 이벤트에 기록한다. 전체 WM 을 만들지 않는다.

**Renderer 가 시간순으로 "풀어서" 재구성:**

```
running_wm = set()                        # 빈 WM 에서 시작
for ev in events(순서대로):
    running_wm 에 [직전 cursor .. ev.cursor] 사이 mutation 을 적용   # 델타만
    if 바뀌었으면: wm_states.append(snapshot); ev.wm_state = 새 인덱스
    else:          ev.wm_state = 직전 인덱스     # 기존 dedup 재현
```

전체 materialize 는 오프라인(단일 태스크 렌더링) 때 한 번, 그것도 델타 증분 적용이라 싸다. 실행 중에는 O(1) append 뿐이다.

**부수 효과(의도된 것):** op-body 가 `ag.wm.add/remove` 하는 변경도 자동으로 저널에 잡힌다 → Part-2 "op-body 사고과정 가시성"의 기반이 공짜로 깔린다. 단, WM 이 아닌 순수 중간값(resolve 의 4.5만 좌표식 후보 등)은 나중에 별도 `sink.thought(...)` 이벤트로 다룬다 — 이 문서 범위 밖.

## 3. 데이터 흐름 & 결선

```
run_solve(tid, task, max_cycles, mode)
 ├─ mode="score"  (채점·대량·회귀 기본값):
 │     Engine + NullSink. WM 메모리 상주, journal 없음.
 │     반환 = {attempts, error}.   ← 빠른 경로 (방출·스냅샷 0)
 │
 └─ mode="debug"  (대시보드 볼 때):
       Engine + JournalSink → journal(이벤트 + WM 델타)
       → Renderer(journal) → {events, wm_states, attempts, wm, error}
```

- **채점/회귀**(`score_move.py`, 향후 eval): `mode="score"`.
- **`debugger/build.py` `_dash_data`**: `mode="debug"` → Renderer 가 `events`/`wm_states` 재생산 → `make_dashboard`·`_HTML`·`dashboard.py` 불변.
- **`debugger/solve_cache.py`**: 캐시 대상을 무거운 events+snapshots 대신 **가벼운 journal**(debug) 또는 attempts(score)로. Renderer 는 필요 시 on-demand 실행.
- move_dashboard 전체 빌드(60개 렌더)는 여전히 debug 비용을 내지만, 그건 "전부 보겠다"는 명시적 행동이라 허용. 회귀·측정은 빠른 경로로.

`_safe_dash_data` 의 태스크당 timeout/예외 격리 래퍼는 그대로 둔다.

## 4. 60/60 보존 & 검증 (단계별, 각 green 후 다음)

동작 보존 리팩터다(사이클 코드 불변, emit→sink·render 분리만). `attempts` 는 환경 submit/채점 경로에서 나오며 방출과 독립이므로 두 모드 모두에서 동일하게 산출된다.

| 단계 | 작업 | 검증 게이트 |
|---|---|---|
| a | `soar/wm.py`에 `journal` 훅(기본 None) 추가 | 60/60 + 전체 pytest 불변 (None 체크뿐, 동작 0변경) |
| b | Sink 추상화 도입, `_Tracer.emit`을 JournalSink 로 라우팅 (아직 full 스냅샷 그대로) | 대시보드 데이터(events/wm_states) **byte 동일** |
| c | JournalSink → 델타/event-sourcing + Renderer 가 재구성 | `wm_states` + 이벤트 `wm_state` 인덱스 **자료구조 diff = 0** (old vs new) |
| d | NullSink + `mode="score"` 빠른 경로, `score_move.py`·`_dash_data` 결선 | 60/60 유지 + 시간 추가 단축 |
| e | (보류) 모듈 rename → `arbor/engine/engine.py` + `arbor/engine/renderer.py` | 순수 파일 이동, import 갱신 |

**불변 조건 체크:**
- move 60/60 (score 모드, seed 0/1/42)
- 전체 pytest: 기존 10개 실패(easy_a 미해결·낡은 트레이스 스키마)와 동일, 신규 회귀 0
- `move_dashboard.html` 임베드 JSON byte 비교(old vs new)

**핵심 안전장치:** (b)에서 Renderer 가 *기존과 동일한* events/wm_states 를 내는지부터 못박고 → (c)에서 내부만 델타로 바꿔도 출력이 불변임을 diff 로 증명한다. "출력 계약 고정 → 내부 최적화" 순서라 60/60 이 흔들릴 구조적 여지가 없다.

## 5. 범위 밖 (명시적 비목표)

- op-body 의 arg 선택 탈절차화 / 원자단위 분해 (Part-2 — 이 seam 위에서 진행)
- `_build_agenda`(비교쌍 선정), generalize anti-unify 본체, `_resolve_cellset` 고정 cycle 의 규칙화 (Part-2)
- xform ↔ ARCKG relation 통합 (Part-2)
- 네이티브 `Agent.step()`으로의 하강 로직 일반화 (단계 e 이후 별도 판단)
- 낡은 트레이스 스키마(`event["wm"]`)를 참조하는 2개 테스트 수정 — 별건으로 처리 가능

## 6. 관련 파일

- 실행/제어(현재 tracer 내부): `arbor/engine/trace.py` (`_Tracer.run`, `emit`, `_wm`, `_do_descend`, `_open_arg_substate`, `_match_preview`, `elaborate`)
- WM: `soar/wm.py`
- 진입/결선: `debugger/solve_cache.py` (`run_solve`), `debugger/build.py` (`_dash_data`, `make_dashboard`)
- 소비자(불변): `debugger/dashboard.py` (`_HTML`, `wm_deltas`)
