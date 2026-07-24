# 최상위 폴더 재구조화 설계 — Fat ARBOR

- **날짜**: 2026-07-24
- **브랜치**: `seokki-refactor2`
- **관련 메모리**: `[[seokki-refactor]]`, `[[seokki-windows-branch]]`
- **상위 규약**: `ARBOR_HARNESS.md`, `CLAUDE.md`

---

## 1. 목표

레포를 대규모 삭제·이동으로 정리해, 최상위가 **"에이전트 ↔ 세계 ↔ 관찰자 ↔ 검증"**
네 경계만 노출하도록 만든다. 리팩터 중간 상태에서 생긴 **중복 트리·죽은 빈 폴더·stale 문서**를 제거한다.

두 개의 제품 요구를 코드 구조로 강제한다:

1. **독립 에이전트 포장** — `arbor/` 폴더 = 에이전트 그 자체. `env`만 주면 이것만으로 문제를 풀고 결과를 낸다.
2. **투명한 후처리 디버깅** — arbor가 풀이 중 기록한 트레이스/아티팩트를, `debugger/`가 **멈춘 뒤** 읽어
   웹으로 시각화한다(후처리, 실행 루프에 개입하지 않음).

**비목표(Non-goals):** arbor **내부** 재편(perception/reasoning/engine 세부 배치)은 이 스펙 밖이다.
이 스펙은 **최상위 경계**와 그에 필요한 최소 이동/삭제만 다룬다.

---

## 2. 결정된 원리

### 2-1. "독립 에이전트"의 단위 = `arbor/` 폴더 (fat arbor)

에이전트가 생각하는 데 필요한 모든 것을 `arbor/` 안에 둔다: SOAR 커널, 3개 LTM(procedural/
semantic/episodic), perception, reasoning, engine, agent glue, LTM 접근 계층.

- **근거**: `arbor/` 폴더 자체가 배포 단위가 되어 "폴더 = 에이전트" 포장 이야기가 가장 깨끗하다.
  SOAR 인지 구조는 사라지지 않고 `arbor/` **안에서** 그대로 보인다 — 이들은 *이 에이전트의* 메모리이므로
  arbor 네임스페이스 아래 두는 것이 정직하다.
- **커널을 밖에 두지 않는 이유**: `procedural_memory`가 `soar`를 import한다(7곳). 커널을 arbor 밖에 두면
  최상위 peer가 arbor 내부를 파고들게 된다. 또한 3개 LTM(에이전트 고유)을 밖에 두면서 범용 커널만 안에
  두는 것은 배치가 거꾸로다. → 커널·메모리 모두 arbor 안.

### 2-2. 의존 방향 (비순환)

```
arbor  ──uses──▶  env  ──reads──▶  data
  │
  └──writes──▶  (episodic trace / artifacts)  ◀──reads──  debugger
```

- `arbor` → `env` → `data` 만 허용. **`env`는 `arbor`를 절대 import하지 않는다**(세계는 에이전트를 모름).
  이 규칙이 "env는 arbor와 독립" 원칙을 코드로 강제한다.
- `debugger`는 arbor의 **기록물만** 읽는다. 실행 경로에 없다(후처리).
- `soar` 커널은 상위(arbor/메모리)를 import하지 않는 **순수 커널**로 유지한다(현재도 그러함).

### 2-3. 세계 vs 에이전트 데이터 구분

- `data/` = 원본 ARC 코퍼스(세계의 문제은행, 읽기전용). **레포 내부에서 문제를 생성하지 않는다.**
- `episodic_memory/` = arbor의 **경험 기록**(`{task_id, task_solved, ...}` + 풀이 트레이스). 세계 데이터가
  아니라 에이전트의 것 → `arbor/` 안.

---

## 3. 최종 최상위 구조

```
<repo>/
├── arbor/          🧠 에이전트 그 자체 (fat)
│   ├── soar/                  ← 커널 흡수 (구 최상위 soar/)
│   ├── procedural_memory/     ← 흡수 (operators + dsl + production_rules)
│   ├── semantic_memory/       ← 흡수 (ontology + learned_skills)
│   ├── episodic_memory/       ← 흡수, 232 정본으로 병합
│   ├── perception/            (기존)
│   ├── reasoning/             (기존)
│   ├── engine/                (기존)
│   ├── agent/                 (기존)
│   ├── memory.py              (LTM 접근 계층 — 구 arbor/env/memory.py)
│   ├── solver.py, expr_solver.py, ...
│   └── __main__.py            ← 신설: 에피소드 루프 entrypoint (python -m arbor)
├── env/            🌍 세계 하네스 (구 arbor/env/ 승격, 하네스 부분만)
│   ├── environment.py         (ARCEnvironment: 제시·픽셀채점·3회 재시도)
│   ├── dataset.py             (list_tasks / load_task / available)
│   └── grid.py                (ARC 격자 I/O 타입/헬퍼)
├── data/           🌍 원본 ARC 코퍼스 (ARC_human/AGI_v1/v2/easy) — 유지
├── debugger/       🔍 후처리 시각화 (트레이스→인터랙티브 웹) — 유지
├── docs/           📄 설계·계획·위키 — 유지
└── tests/          🧪 pytest
    └── oracle/                ← 구 최상위 oracle/ 이동 (C++ Soar 차등 오라클)
```

**최상위 = `arbor` `env` `data` `debugger` `docs` `tests` — 6개.**

---

## 4. 이동/흡수 (migration)

| 대상 | 현재 | 이후 | 비고 |
|---|---|---|---|
| SOAR 커널 | `soar/` | `arbor/soar/` | import 경로 `soar.*` → `arbor.soar.*` 전면 갱신 |
| 절차 메모리 | `procedural_memory/` | `arbor/procedural_memory/` | operators·dsl·production_rules |
| 의미 메모리 | `semantic_memory/` | `arbor/semantic_memory/` | ontology·learned_skills |
| 경험 메모리 | `episodic_memory/`(232) + `arbor/episodic_memory/`(24) | `arbor/episodic_memory/`(232 정본) | 24는 232에 포함되면 삭제, 아니면 병합 |
| 세계 하네스 | `arbor/env/{environment,dataset,grid}.py` | `env/` | arbor→env 의존 방향 유지 |
| LTM 접근 계층 | `arbor/env/memory.py` | `arbor/memory.py` | env가 아니라 에이전트 내장 |
| 오라클 | `oracle/` | `tests/oracle/` | 테스트 지원 하네스 |

**import 경로 전면 갱신 대상(현 사용처 수):** `soar` (arbor 8·procedural_memory 7·tests 11·oracle 1·docs 1),
`procedural_memory`·`semantic_memory`·`oracle` (arbor·debugger·tests), `arbor.env.*` (env 승격분).

---

## 5. 삭제

| 대상 | 사유 |
|---|---|
| `arc/` | 대시보드/리포트 **출력 target**(`.gitignore`: `arc/*.html`, `arc/*.csv`). 추적 파일 0. 출력은 `debugger/` 밑으로 재지정 |
| `pysoar/` | 죽은 빈 잔재(커널은 `soar/`). 추적 파일 0 |
| `arbor/operators/` | 빈 껍데기(`__init__.py`뿐). 진짜 operator는 `procedural_memory/operators/` |
| `arbor/env/make_tasks.py` | 합성 task 생성기. 레포 내부에서 문제를 만들지 않기로 확정 |
| `arbor/env/survey.py` | 다양성 관찰용 task 묶음 선택기(import처 1, 은퇴 인프라 참조). 기능은 entrypoint `--dataset/--tasks` 플래그로 흡수 |

---

## 6. Entrypoint: `python -m arbor`

`arbor/__main__.py` 가 **에피소드 루프**를 구현한다:

```
python -m arbor --dataset ARC_human      # 60문제 풀이 + 트레이스/결과 기록
python -m arbor --tasks easy000a         # 단일 문제
```

루프: `env`가 `data/`에서 문제 제시 → `arbor`가 풀이 + 트레이스 기록 → `env`가 픽셀채점·**3회 재시도**
프로토콜 → `arbor/episodic_memory/`에 경험 기록. 이후 `debugger`가 그 기록을 읽어 시각화(별도 실행).

- survey.py의 "묶음 선택" 역할은 `--dataset` / `--tasks` 인자로 대체한다(`env.dataset.list_tasks` 사용).

---

## 7. 문서 갱신 (같은 브랜치에서)

- **README.md** — 현재 옛 flat `arc/` 레이아웃(`arc/dataset.py`·`arc/environment.py`·`arc/run.py`·
  `arc/expr_solver.py`)을 서술하는 **stale** 상태. 새 구조·`python -m arbor` entrypoint로 갱신.
- **CLAUDE.md** — 경로 참조(`soar/`, `arc/fine_trace.py`, 진입점 `python -m debugger.build`) 갱신.
- **`ARBOR_HARNESS.md` §2-5** — `focus_dashboard.html`/`arc/` 출력 경로 언급을 `debugger/` 출력으로 정정.

---

## 8. 검증 (완료 판정)

이 리팩터는 **행위 보존(behavior-preserving)** 이어야 한다 — 구조만 옮기고 로직은 안 바꾼다.

1. **주 게이트**: `arc_human/move` 60/60 이 이동 전후 **동일**.
2. **결정성**: `PYTHONHASHSEED` 를 바꿔도 solve 결과 동일(ARBOR_HARNESS §2-6).
3. **테스트**: `tests/` 전부 통과 (import 경로 갱신 반영).
4. **entrypoint**: `python -m arbor --tasks easy000a` 가 답과 트레이스를 낸다.
5. **의존 규칙**: `env/`가 `arbor`를 import하지 않음(grep로 확인). `soar`가 상위를 import하지 않음.
6. **죽은 참조 0**: 삭제된 `arc/`·`pysoar/`·`make_tasks`·`survey`에 대한 잔존 import 없음.

---

## 9. 열린 항목 (구현 계획에서 확정)

- 24개 `arbor/episodic_memory/`(easy)가 232 최상위 세트에 스키마상 포함되는지 — 포함이면 삭제, 아니면 병합 규칙.
- `env/grid.py` vs arbor 내부 격자 표현의 최종 경계(세계 I/O 타입은 env, 파생 연산은 arbor) — 이동 시 확정.
- 대시보드 출력 디렉터리 명칭(`debugger/out/` 등)과 `.gitignore` 갱신.
