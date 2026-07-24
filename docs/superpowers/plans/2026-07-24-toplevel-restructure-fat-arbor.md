# 최상위 폴더 재구조화 (Fat ARBOR) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 레포 최상위를 `arbor env data debugger docs tests` 6개로 축소하고, SOAR 커널·3 LTM을 `arbor/` 안으로 흡수(fat arbor)하며 죽은 폴더·스크립트·stale 참조를 제거한다.

**Architecture:** 순수 **행위 보존(behavior-preserving)** 리팩터 — 파일을 `git mv`로 옮기고 import 경로/깊이-민감 경로연산만 갱신한다. 로직은 바꾸지 않는다. 각 태스크는 기준선 게이트·테스트가 **동일**함을 확인하고 커밋한다.

**Tech Stack:** Python 3.10, unittest, Git Bash(sed/grep). 패키지 해석은 conftest/pyproject 없이 **repo 루트를 cwd/sys.path 에 두고** 절대 import (`import arbor.…`, `import env.…`).

## Global Constraints

이 세 명령의 출력은 **모든 태스크 전후로 동일**해야 한다. 태스크마다 마지막에 실행한다.

- **GATE**: `python -m debugger.score move` → 반드시 `SCORE: 60/60` (스펙 §8 주 게이트)
- **TESTS**: `python -m unittest discover -s tests -p "test_*.py"` → 반드시 `Ran 177 tests` + `OK (skipped=27)`
- **DETERMINISM**: `PYTHONHASHSEED=1 python -m debugger.score move` 와 `PYTHONHASHSEED=2 python -m debugger.score move` 결과 동일 (ARBOR_HARNESS §2-6)
- import 재작성은 **`*.py` 코드에만** 적용. `docs/superpowers/plans/*.md`(과거 계획 스냅샷)의 예시 import 는 건드리지 않는다.
- 문자열 폴더명(예: `memory.py` 의 `"procedural_memory"`)은 import 토큰이 아니므로 재작성 대상이 아니다.
- 모든 명령은 **repo 루트**(`c:\Users\Sir_K\Downloads\PySOAR`)에서 실행. 브랜치 `seokki-refactor2`.

---

## File Structure (이동/삭제 총괄)

```
삭제:   arc/  pysoar/  arbor/operators/  arbor/env/make_tasks.py  arbor/env/survey.py
이동:   soar/                → arbor/soar/
        procedural_memory/   → arbor/procedural_memory/
        semantic_memory/     → arbor/semantic_memory/
        episodic_memory/(232)→ arbor/episodic_memory/  (기존 arbor/episodic_memory 24개는 232의 부분집합 → 대체)
        arbor/env/{environment,dataset,grid}.py → env/
        arbor/env/memory.py  → arbor/memory.py
        oracle/              → tests/oracle/
신설:   arbor/__main__.py    (python -m arbor 진입점)
        env/__init__.py
```

import 재작성 규모(사전 측정): `soar` 27 파일 · `procedural_memory`/`semantic_memory` 10 파일 · `arbor.env.*` 소수.

---

### Task 0: 기준선 고정 (baseline oracle)

**Files:** 없음(측정만).

- [ ] **Step 1: 게이트 측정**

Run: `python -m debugger.score move`
Expected: `SCORE: 60/60`

- [ ] **Step 2: 테스트 측정**

Run: `python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3`
Expected: `Ran 177 tests` … `OK (skipped=27)`

- [ ] **Step 3: 결정성 측정**

Run: `PYTHONHASHSEED=1 python -m debugger.score move && PYTHONHASHSEED=2 python -m debugger.score move`
Expected: 두 줄 모두 `SCORE: 60/60`

숫자가 다르면 **중단**하고 사용자에게 보고(기준선이 스펙과 불일치). 이 세 결과가 이후 모든 태스크의 합격 기준이다.

---

### Task 1: 죽은 아티팩트 삭제 (arc/, pysoar/, arbor/operators/, make_tasks.py)

**근거:** 로컬 `arc/`·`pysoar/` 디렉터리는 코드 의존 0 (grep 상의 "pysoar"는 출력 라벨/변수명, "arc/"는 docstring·외부 `~/Desktop` 경로). `arbor/operators/__init__.py`는 2줄 빈 스캐폴드(진짜는 `procedural_memory/operators/`). `make_tasks.py`는 레포 내부 문제생성기(사용 안 하기로 확정).

**Files:**
- Delete: `arc/`, `pysoar/`, `arbor/operators/`, `arbor/env/make_tasks.py`

**Interfaces:** 없음(순수 삭제, live import 대상 아님).

- [ ] **Step 1: 삭제 전 참조 0 확인**

Run: `git grep -nE "import arbor\.operators|from arbor\.operators|arbor\.env\.make_tasks|import make_tasks" -- '*.py'`
Expected: 출력 없음 (참조 0)

- [ ] **Step 2: 삭제**

```bash
git rm -r arc pysoar arbor/operators arbor/env/make_tasks.py
rm -rf arc pysoar   # untracked __pycache__ 잔재 제거
```

- [ ] **Step 3: GATE + TESTS 확인**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: 죽은 폴더/스크립트 삭제 (arc pysoar arbor/operators make_tasks)"
```

---

### Task 2: survey.py 제거 + 소비자 재배선

**근거:** `_load_survey`는 실제로 `debugger/reports/dashboard.py:190` 한 곳에서만 호출(`_load_survey(agi_ids=SURVEY_AGI)` → easy 8 + agi 1 = 9 태스크 묶음). `arbor/solver.py:52`는 import만 하고 미사용. 이 묶음-선택 기능은 `env.dataset.list_tasks` 로 대체.

**Files:**
- Modify: `debugger/reports/dashboard.py:11,190`
- Modify: `arbor/solver.py:52` (미사용 import 삭제)
- Delete: `arbor/env/survey.py`

**Interfaces:**
- Consumes: `arbor.env.dataset.list_tasks(dataset, limit) -> list[tuple[str,str]]`, `load_task(path) -> dict`
- Produces: 없음(내부 재배선).

- [ ] **Step 1: SURVEY_AGI 실제 id 목록 확보**

Run: `git grep -nE "SURVEY_AGI\s*=" -- arbor/env/survey.py`
Expected: `SURVEY_AGI = [...]` 형태의 리스트. 이 리스트 값(agi task id 들)을 다음 스텝에 그대로 박는다.

- [ ] **Step 2: dashboard.py 재배선**

`debugger/reports/dashboard.py:11` 의 `from arbor.env.survey import _load_survey, SURVEY_AGI` 를 삭제하고,
파일 상단 import 부에 `from arbor.env.dataset import list_tasks, load_task` 가 없으면 추가(이미 153·163 라인에서 지역 import 중이므로 모듈 상단으로 승격).
`:190` 의 `tasks = _load_survey(agi_ids=SURVEY_AGI)` 를 아래로 교체 (easy 8 + Step1의 agi id들):

```python
        _SURVEY = ["easy000a", "easy000b", "easy000c", "easy000d",
                   "easy000e", "easy000f", "easy000g", "easy000h"] + SURVEY_AGI_IDS  # Step1 값
        tasks = []
        for _tid in _SURVEY:
            for _ds in ("easy", "agi"):
                _hits = [(t, p) for t, p in list_tasks(_ds) if t == _tid]
                if _hits:
                    tasks.append((_hits[0][0], load_task(_hits[0][1])))
                    break
```

주의: `_load_survey` 의 원래 반환 형태(`list[(task_id, task_dict)]` 인지 `list[(id, path)]` 인지)를 survey.py 원문에서 확인해 정확히 맞춘다. 다르면 위 append 형태를 원형에 맞게 조정.

- [ ] **Step 3: solver.py 미사용 import 삭제**

`arbor/solver.py:52` 의 `from arbor.env.survey import _load_survey, SURVEY_AGI` 줄 삭제.

Run: `git grep -nE "_load_survey|SURVEY_AGI" -- arbor/solver.py`
Expected: 출력 없음.

- [ ] **Step 4: survey.py 삭제**

```bash
git rm arbor/env/survey.py
```

- [ ] **Step 5: GATE + TESTS + 대시보드 스모크**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`
Run(대시보드 경로 사용 시): `python -m debugger.build 2>&1 | tail -3` — 에러 없이 완료(9-태스크 묶음이 dashboard.py:190 경로).
Expected: 예외 없음.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: survey.py 제거, dashboard 묶음선택을 env.dataset 로 재배선"
```

---

### Task 3: oracle/ → tests/oracle/ 이동

**근거:** oracle 은 soar 커널을 진짜 C++ Soar 에 차등대조하는 **테스트 지원 하네스**(tests 11곳이 사용). `soar_oracle.py:26` 은 `sys.path.insert(0, dirname²(__file__))` 로 repo 루트를 넣는데, `tests/oracle/` 로 가면 dirname² = `tests/` 가 되어 **깨진다** → dirname³ 로 고친다.

**Files:**
- Move: `oracle/soar_oracle.py` → `tests/oracle/soar_oracle.py`
- Create: `tests/oracle/__init__.py`
- Modify: `tests/oracle/soar_oracle.py:26` (dirname² → dirname³)
- Modify: oracle 를 import 하는 테스트들 (`from oracle.soar_oracle` → `from tests.oracle.soar_oracle`)

**Interfaces:**
- Consumes: `soar.preference.PreferenceType/Slot`, `soar.decide.ImpasseType` (Task 7 전까지 top-level `soar` 그대로).
- Produces: `tests.oracle.soar_oracle` 모듈 경로.

- [ ] **Step 1: oracle import 사이트 파악**

Run: `git grep -nE "from oracle|import oracle" -- '*.py'`
Expected: 사이트 목록(대부분 `tests/test_oracle_*.py`). 이 목록을 Step 4 재작성 대상으로.

- [ ] **Step 2: 이동 + __init__**

```bash
mkdir -p tests/oracle
git mv oracle/soar_oracle.py tests/oracle/soar_oracle.py
rmdir oracle 2>/dev/null
: > tests/oracle/__init__.py && git add tests/oracle/__init__.py
```

- [ ] **Step 3: soar_oracle.py 의 repo-루트 경로 깊이 +1**

`tests/oracle/soar_oracle.py:26` 을 교체:

```python
# before: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

(tests/oracle/soar_oracle.py → dirname³ = repo 루트.)

- [ ] **Step 4: import 재작성**

Step 1 목록의 각 파일에서 `oracle.soar_oracle` → `tests.oracle.soar_oracle`:

```bash
git grep -lE "from oracle\.soar_oracle|import oracle\.soar_oracle|from oracle import|import oracle\b" -- '*.py' \
  | grep -v "tests/oracle/soar_oracle.py" \
  | xargs sed -i 's/\boracle\.soar_oracle\b/tests.oracle.soar_oracle/g; s/from oracle import/from tests.oracle import/g'
```

- [ ] **Step 5: 오라클 테스트가 skip 이 아닌지(스킵이면 게이트로만 검증)**

Run: `python -m unittest tests.test_oracle_chunk 2>&1 | tail -3`
Expected: `OK` 또는 `OK (skipped=…)` — 외부 `out/soar` 바이너리 없으면 skip(정상). import 에러(ModuleNotFoundError)면 실패로 간주하고 경로 수정.

- [ ] **Step 6: GATE + TESTS**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)` (스킵 수 27 유지)

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: oracle/ → tests/oracle/ (repo-루트 경로 깊이 +1, import 갱신)"
```

---

### Task 4: procedural_memory/ → arbor/procedural_memory/ 흡수

**근거:** fat arbor. `procedural_memory` 내부는 `from soar import …` 을 쓰지만 Task 7 전까지 soar 는 top-level 이라 그대로 해석됨. 외부/내부의 `procedural_memory.` 모듈 참조만 `arbor.procedural_memory.` 로 바꾼다. `memory.py`의 문자열 `"procedural_memory"`(폴더명)은 건드리지 않음.

**Files:**
- Move: `procedural_memory/` → `arbor/procedural_memory/`
- Modify: `procedural_memory` 를 import 하는 모든 `*.py` (arbor/agent/focus.py, arbor/reasoning/program_ast.py, arbor/solver.py, debugger/reports/dashboard.py, tests/*, 그리고 procedural_memory 내부 self-import)

**Interfaces:**
- Consumes: (Task 7 전) top-level `soar`.
- Produces: `arbor.procedural_memory.loader.PRODUCTIONS/OP_DOCS`, `arbor.procedural_memory.operators.OPERATOR_BODIES`, `arbor.procedural_memory.dsl.registry.SPECS` 등 기존 심볼 그대로.

- [ ] **Step 1: 이동**

```bash
git mv procedural_memory arbor/procedural_memory
```

- [ ] **Step 2: 모듈 import 재작성 (from/import 문만)**

```bash
git grep -lE "(from|import) procedural_memory\b" -- '*.py' \
  | xargs sed -i -E 's/\b(from|import) procedural_memory\b/\1 arbor.procedural_memory/g'
```

- [ ] **Step 3: 잔존 top-level 참조 0 확인**

Run: `git grep -nE "(from|import) procedural_memory\b" -- '*.py'`
Expected: 출력 없음 (전부 `arbor.procedural_memory`).

- [ ] **Step 4: GATE + TESTS**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: procedural_memory → arbor/procedural_memory (import 갱신)"
```

---

### Task 5: semantic_memory/ → arbor/semantic_memory/ 흡수

**근거:** fat arbor. import 사이트는 Task 4 grep 에 포함(10 중 semantic 분). `build.py` 의 self-import(`semantic_memory.…`)도 함께.

**Files:**
- Move: `semantic_memory/` → `arbor/semantic_memory/`
- Modify: `semantic_memory` 를 import 하는 모든 `*.py`

**Interfaces:**
- Produces: `arbor.semantic_memory.build.*` 등 기존 심볼 그대로. `arbor/semantic_memory/ontology.json` 디스크 위치.

- [ ] **Step 1: 이동**

```bash
git mv semantic_memory arbor/semantic_memory
```

- [ ] **Step 2: 모듈 import 재작성**

```bash
git grep -lE "(from|import) semantic_memory\b" -- '*.py' \
  | xargs sed -i -E 's/\b(from|import) semantic_memory\b/\1 arbor.semantic_memory/g'
```

- [ ] **Step 3: 잔존 참조 0 확인**

Run: `git grep -nE "(from|import) semantic_memory\b" -- '*.py'`
Expected: 출력 없음.

- [ ] **Step 4: GATE + TESTS**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: semantic_memory → arbor/semantic_memory (import 갱신)"
```

---

### Task 6: episodic_memory(232) → arbor/episodic_memory/ 흡수 (중복 24 대체)

**근거:** top-level `episodic_memory/`(232) 는 기존 `arbor/episodic_memory/`(24 easy) 를 **완전 포함**(교집합 24). 즉 24는 232의 부분집합 → 232로 대체한다. episodic 은 모듈 import 대상이 아니라 **파일시스템 폴더**(memory.py·ARCKG 가 경로로 읽음)이므로 import 재작성은 없고 **경로 정합성**만 확인.

**Files:**
- Delete: `arbor/episodic_memory/` (24, 232의 부분집합)
- Move: `episodic_memory/`(232) → `arbor/episodic_memory/`

**Interfaces:** 없음(디스크 폴더 위치만 변경). Task 9 에서 `memory.py` 의 `ROOT`(=`arbor/`)가 이 폴더를 가리키게 정합.

- [ ] **Step 1: 24 ⊂ 232 재확인(안전)**

Run: `comm -23 <(git ls-files arbor/episodic_memory/*.json | sed 's#.*/##' | sort) <(git ls-files episodic_memory/*.json | sed 's#.*/##' | sort)`
Expected: 출력 없음 (24 중 232에 없는 것이 0 = 완전 부분집합). 출력이 있으면 그 파일들은 **삭제 말고 병합**(232 쪽으로 복사).

- [ ] **Step 2: 24 삭제 후 232 이동**

```bash
git rm -r arbor/episodic_memory
git mv episodic_memory arbor/episodic_memory
```

- [ ] **Step 3: 폴더를 파일경로로 읽는 코드가 새 위치와 정합인지 확인**

Run: `git grep -nE "episodic_memory" -- '*.py'`
Expected: `arbor/env/memory.py`(ROOT+"episodic_memory", ROOT=arbor 이므로 정합) 외 다른 하드코딩 경로 없음. ARCKG(`memory_paths.py`)는 root 를 인자로 받으므로 무관. 하드코딩된 `"episodic_memory"` 절대/상대경로가 있으면 새 위치로 수정.

- [ ] **Step 4: GATE + TESTS**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: episodic_memory(232) → arbor/episodic_memory, 중복 24 제거"
```

---

### Task 7: soar/ → arbor/soar/ 흡수 (27 파일 import 재작성)

**근거:** fat arbor 의 마지막 흡수. 커널은 순수(상위를 import 안 함)이므로 이동 자체는 안전하고, 모든 소비자의 `soar` → `arbor.soar` 재작성이 핵심. `from soar …` / `from soar.X …` / 바레 `import soar` 세 형태를 모두 처리.

**Files:**
- Move: `soar/` → `arbor/soar/`
- Modify: `soar` 를 import 하는 모든 `*.py` (arbor 8 + arbor.procedural_memory 7 + tests 11 + tests/oracle 1)

**Interfaces:**
- Produces: `arbor.soar.Agent/Cond/Action/Production`(패키지 `__init__` 재수출), `arbor.soar.preference.*`, `arbor.soar.decide.*`, `arbor.soar.wm.WorkingMemory` 등 기존 심볼 그대로.

- [ ] **Step 1: 바레 `import soar` 존재 여부(별칭 처리 필요)**

Run: `git grep -nE "^\s*import soar\s*$|^\s*import soar\s+as" -- '*.py'`
Expected: 목록. 있으면 Step 3에서 `import arbor.soar as soar` 로(사용부 `soar.X` 보존).

- [ ] **Step 2: 이동**

```bash
git mv soar arbor/soar
```

- [ ] **Step 3: import 재작성 (세 형태)**

```bash
# (a) from soar / from soar.X
git grep -lE "from soar(\.| import)" -- '*.py' | xargs sed -i -E 's/\bfrom soar\b/from arbor.soar/g'
# (b) 바레 import soar  → 별칭 유지
git grep -lE "^\s*import soar\s*$" -- '*.py' | xargs sed -i -E 's/^(\s*)import soar\s*$/\1import arbor.soar as soar/'
```

- [ ] **Step 4: 잔존 top-level soar 참조 0 확인**

Run: `git grep -nE "(from|import) soar(\.|[[:space:]]|$)" -- '*.py' | grep -v "arbor.soar"`
Expected: 출력 없음.

- [ ] **Step 5: GATE + TESTS + 결정성**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`
Run: `PYTHONHASHSEED=1 python -m debugger.score move && PYTHONHASHSEED=2 python -m debugger.score move`
Expected: 둘 다 `SCORE: 60/60`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: soar → arbor/soar (27 파일 import 갱신, fat arbor 흡수 완료)"
```

---

### Task 8: arbor/env/{environment,dataset,grid}.py → env/ 승격

**근거:** 세계 하네스는 최상위 peer. `dataset.py` 의 `_ROOT = dirname³(__file__)+/data` 는 `arbor/env/`(depth2) 기준 — `env/`(depth1)로 가면 `dirname²` 로 **깊이 −1** 해야 `data/` 를 찾는다. `environment.py`·`grid.py` 도 깊이-민감 경로연산 유무 확인.

**Files:**
- Create: `env/__init__.py`
- Move: `arbor/env/environment.py`, `arbor/env/dataset.py`, `arbor/env/grid.py` → `env/`
- Modify: `env/dataset.py` `_ROOT`(깊이 −1)
- Modify: `arbor.env.{environment,dataset,grid}` 소비자 전부 → `env.{…}`

**Interfaces:**
- Consumes: `data/` 코퍼스(경로).
- Produces: `env.dataset.list_tasks/load_task/available`, `env.environment.ARCEnvironment/grids_equal`, `env.grid.*` — 기존 심볼 그대로.
- **의존 규칙**: `env/` 는 `arbor` 를 import 하지 않는다(Step 5에서 grep 검증).

- [ ] **Step 1: 이동 + __init__**

```bash
: > env/__init__.py
mkdir -p env && git add env/__init__.py
git mv arbor/env/environment.py env/environment.py
git mv arbor/env/dataset.py     env/dataset.py
git mv arbor/env/grid.py        env/grid.py
```

- [ ] **Step 2: dataset.py `_ROOT` 깊이 −1**

`env/dataset.py:15` 교체:

```python
# before: _ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
```

Run(검증): `python -c "import sys; sys.path.insert(0,'.'); from env.dataset import available; print(list(available())[:3])"`
Expected: 데이터셋 키 목록(빈 리스트/에러 아님) — `_ROOT` 가 `data/` 를 올바로 가리킴.

- [ ] **Step 3: environment.py·grid.py 깊이-민감 경로 확인**

Run: `git grep -nE "dirname\(os\.path\.dirname|sys\.path|_ROOT|ROOT" -- env/environment.py env/grid.py`
Expected: 깊이 기반 repo/data 경로 연산이 있으면 depth −1 로 동일 수정. 없으면 무변경.

- [ ] **Step 4: `arbor.env.*` 소비자 재작성**

```bash
git grep -lE "arbor\.env\.(environment|dataset|grid)" -- '*.py' \
  | xargs sed -i -E 's/\barbor\.env\.(environment|dataset|grid)\b/env.\1/g'
```

또한 `arbor/engine/trace.py:71` 의 지역 import `from arbor.env.environment import ARCEnvironment` → `from env.environment import ARCEnvironment` 포함되는지 확인.

Run: `git grep -nE "arbor\.env\.(environment|dataset|grid)" -- '*.py'`
Expected: 출력 없음.

- [ ] **Step 5: 의존 방향 검증 (env → arbor 금지)**

Run: `git grep -nE "(from|import) arbor\b" -- env/`
Expected: 출력 없음 (세계는 에이전트를 모른다).

- [ ] **Step 6: GATE + TESTS**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: env 하네스 최상위 승격(env/), dataset _ROOT 깊이 보정, 의존방향 env↛arbor"
```

---

### Task 9: arbor/env/memory.py → arbor/memory.py 이동

**근거:** `memory.py` 는 3 LTM 을 디스크 폴더로 여는 **에이전트 내장 LTM 접근계층**(env 아님). 현재 `ROOT = dirname²(arbor/env/memory.py) = arbor/`. `arbor/memory.py`(depth1)로 가면 `dirname¹ = arbor/` — **동일 결과**지만 dirname 횟수를 1로 줄여 의도를 명확히. 이제 `arbor/{semantic,episodic,procedural}_memory` 가 모두 존재하므로 `self.semantic/.procedural/.episodic` 가 실재 폴더와 정합(Task 4·5·6 이후).

**Files:**
- Move: `arbor/env/memory.py` → `arbor/memory.py`
- Modify: `arbor/memory.py` `ROOT`(dirname² → dirname¹)
- Modify: `arbor.env.memory` 소비자(있으면) → `arbor.memory`
- Delete: `arbor/env/` (비면 `__init__.py` 만 남으므로 제거)

**Interfaces:**
- Produces: `arbor.memory.Memory`(변경 없음). `ROOT` = `arbor/`.

- [ ] **Step 1: memory 소비자 파악**

Run: `git grep -nE "arbor\.env\.memory|from \.memory import|from \.\.env\.memory" -- '*.py'`
Expected: 목록(없을 수 있음 — Memory 클래스 미사용 가능성). 있으면 Step 3에서 재작성.

- [ ] **Step 2: 이동 + ROOT 보정**

```bash
git mv arbor/env/memory.py arbor/memory.py
```

`arbor/memory.py:26` 교체:

```python
# before: ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.abspath(__file__))   # = arbor/
```

- [ ] **Step 3: import 재작성 + 빈 env 패키지 제거**

```bash
git grep -lE "arbor\.env\.memory" -- '*.py' | xargs -r sed -i -E 's/\barbor\.env\.memory\b/arbor.memory/g'
git rm arbor/env/__init__.py 2>/dev/null; rmdir arbor/env 2>/dev/null || true
```

- [ ] **Step 4: 경로 정합 스모크**

Run: `python -c "import sys; sys.path.insert(0,'.'); from arbor.memory import Memory; m=Memory(); import os; print(os.path.isdir(m.episodic), os.path.isdir(m.procedural), os.path.isdir(m.semantic))"`
Expected: `True True True` (세 LTM 폴더가 arbor/ 아래 실재).

- [ ] **Step 5: GATE + TESTS**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: memory.py → arbor/memory.py (LTM 접근계층 arbor 내장, ROOT 정합)"
```

---

### Task 10: arbor/__main__.py 진입점 (python -m arbor)

**근거:** 스펙 §6. 실제 solve 루프(`run_solve`)와 채점 러너(`score_dataset`)는 현재 `debugger/` 에 있고, 그 재배치는 본 스펙의 비목표(arbor-내부/debugger 재편). 따라서 진입점은 기존 러너를 감싸는 **얇은 래퍼**로 만들어 `python -m arbor` 를 동작시킨다. (러너를 arbor 로 이관하는 disentangle 은 후속 계획.)

**Files:**
- Create: `arbor/__main__.py`

**Interfaces:**
- Consumes: `debugger.score.score_dataset(dataset, limit, max_cycles, use_cache) -> {ok,total,fail,seconds}`, `debugger.solve_cache.run_solve`, `env.dataset.list_tasks/load_task`.
- Produces: CLI `python -m arbor [--dataset D] [--tasks ID]`.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_entrypoint.py` 생성:

```python
import subprocess, sys
def test_arbor_main_scores_move():
    out = subprocess.run([sys.executable, "-m", "arbor", "--dataset", "move"],
                         capture_output=True, text=True, cwd=".")
    assert "SCORE: 60/60" in (out.stdout + out.stderr), out.stdout + out.stderr
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_entrypoint -v`
Expected: FAIL — `No module named arbor.__main__`.

- [ ] **Step 3: __main__.py 구현**

`arbor/__main__.py` 생성:

```python
"""python -m arbor — ARBOR 에이전트 진입점.
env 가 data/ 에서 문제를 제시 → arbor 가 풀이 → env 채점(3회 재시도). 기록은 debugger 가 후처리.
러너(run_solve)는 현재 debugger 에 있어 이를 재사용한다(후속 계획에서 arbor 로 이관)."""
from __future__ import annotations
import argparse
import sys
from debugger.score import score_dataset
from debugger.solve_cache import run_solve
from env.dataset import list_tasks, load_task


def main(argv=None):
    ap = argparse.ArgumentParser(prog="arbor")
    ap.add_argument("--dataset", default="move", help="풀 데이터셋 (기본 move)")
    ap.add_argument("--tasks", default=None, help="단일 task id (지정 시 그 문제만)")
    ap.add_argument("--max-cycles", type=int, default=500)
    args = ap.parse_args(argv)

    if args.tasks:
        hit = [(t, p) for t, p in list_tasks(args.dataset) if t == args.tasks]
        if not hit:
            print(f"NOT FOUND: {args.tasks} in {args.dataset}"); return 1
        tid, path = hit[0]
        r = run_solve(tid, load_task(path), max_cycles=args.max_cycles, mode="score")
        ok = any(a["correct"] for a in r["attempts"])
        print(f"{tid}: {'SOLVED' if ok else 'FAIL'}")
        return 0 if ok else 1

    r = score_dataset(args.dataset, max_cycles=args.max_cycles)
    print(f"SCORE: {r['ok']}/{r['total']}  ({r['seconds']:.1f}s)")
    if r["fail"]:
        print("FAIL:", r["fail"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 통과 확인**

Run: `python -m unittest tests.test_entrypoint -v`
Expected: PASS.
Run: `python -m arbor --tasks easy000a --dataset easy`
Expected: `easy000a: SOLVED` 또는 `FAIL`(예외 없이 한 줄 출력).

- [ ] **Step 5: GATE + TESTS (테스트 수 +1 = 178)**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)` (Ran 178 — 신규 테스트 1 추가).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(arbor): python -m arbor 진입점(얇은 래퍼) + 스모크 테스트"
```

---

### Task 11: 문서·gitignore 갱신

**근거:** 스펙 §7. README 는 옛 flat `arc/` 레이아웃을 서술(stale). `.gitignore` 는 삭제된 `arc/*.html` 출력 target 을 참조.

**Files:**
- Modify: `README.md`(구조도·명령·테스트수 177), `CLAUDE.md`(경로 참조), `ARBOR_HARNESS.md`(§2-5 `arc/` 출력 언급)
- Modify: `.gitignore`(`arc/*` → `debugger/out/*` 또는 실제 출력경로)

**Interfaces:** 없음(문서).

- [ ] **Step 1: .gitignore 갱신**

`.gitignore` 의 `arc/*.html`·`arc/compare_viz/*.html`·`arc/*.csv` 3줄을 실제 대시보드 출력 경로로 교체. 출력 경로 확인:

Run: `git grep -nE "\.html'|\.html\"|write.*html|open\(.*html" -- debugger/*.py debugger/reports/*.py | head`
Expected: 실제 출력 파일 경로. 그 디렉터리를 `.gitignore` 에 반영(예: `debugger/*.html`, `debugger/reports/*.html` 은 이미 존재 — `arc/` 줄만 삭제).

- [ ] **Step 2: README.md 구조/명령 갱신**

- 5행 구조 설명: `soar/`→`arbor/soar/`, 진입점 `python -m debugger.build`→`python -m arbor` 병기.
- 8행 진입점 `arc/focus_dashboard.html` 언급 → 새 출력 경로.
- 79·86·94–108행: 옛 `arc/dataset.py`·`arc/environment.py`·`arc/run.py`·`arc/expr_solver.py`·`arc/memory.py` 표 → 새 위치(`env/dataset.py`, `env/environment.py`, `python -m arbor`, `arbor/expr_solver.py`, `arbor/memory.py`).
- 180행 `전체 80` → `전체 177`.

- [ ] **Step 3: CLAUDE.md 갱신**

5행 `커널 soar/` → `커널 arbor/soar/`, `arc/fine_trace.py` 참조 확인·정정, 진입점 `python -m debugger.build` → `python -m arbor`(게이트는 `python -m debugger.score move` 유지 명시).

- [ ] **Step 4: ARBOR_HARNESS.md §2-5 정정**

`focus_dashboard.html`/`arc/` 출력 경로 언급을 `debugger/` 출력으로 정정(내용 원칙은 보존, 경로만).

- [ ] **Step 5: 문서 링크·경로 잔존 오류 스캔**

Run: `git grep -nE "\bsoar/|\barc/|procedural_memory/|semantic_memory/|episodic_memory/|oracle/" -- README.md CLAUDE.md ARBOR_HARNESS.md | grep -vE "arbor/(soar|procedural_memory|semantic_memory|episodic_memory)|tests/oracle|debugger"`
Expected: 남은 옛 경로가 없거나, 있으면 의도된 역사 서술만.

- [ ] **Step 6: GATE + TESTS (무변경 확인) + Commit**

Run: `python -m debugger.score move && python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2`
Expected: `SCORE: 60/60` · `OK (skipped=27)`
```bash
git add -A && git commit -m "docs: 새 구조(fat arbor·env 승격·python -m arbor)로 README/CLAUDE/HARNESS/gitignore 갱신"
```

---

### Task 12: 최종 검증 (스펙 §8 전체)

**Files:** 없음(검증만).

**Interfaces:** 없음.

- [ ] **Step 1: 최상위 구조 확인**

Run: `ls -d */ | sort`
Expected: `arbor/ data/ debugger/ docs/ env/ tests/` — 정확히 6개(+ `.git` 등 숨김 제외).

- [ ] **Step 2: 죽은 참조 0 (삭제/이동된 것)**

Run: `git grep -nE "(from|import) (soar|procedural_memory|semantic_memory|oracle)\b|arbor\.env\.|import make_tasks|arbor\.operators|_load_survey" -- '*.py' | grep -vE "arbor\.soar|arbor\.procedural_memory|arbor\.semantic_memory|tests\.oracle"`
Expected: 출력 없음.

- [ ] **Step 3: 의존 방향 규칙**

Run: `git grep -lE "(from|import) arbor\b" -- env/ ; echo "---soar 상위참조---"; git grep -nE "(from|import) (arbor|env)\b" -- arbor/soar/`
Expected: 둘 다 출력 없음 (env↛arbor, soar↛상위).

- [ ] **Step 4: 게이트·테스트·결정성·진입점 (스펙 §8 1–4)**

Run:
```bash
python -m debugger.score move
python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -2
PYTHONHASHSEED=1 python -m debugger.score move && PYTHONHASHSEED=2 python -m debugger.score move
python -m arbor --dataset move
```
Expected: `SCORE: 60/60`(×3, `python -m arbor` 포함) · `OK (skipped=27)`.

- [ ] **Step 5: 최종 커밋(있으면) + 브랜치 상태 보고**

Run: `git log --oneline seokki-refactor2 ^main | head -20 && git status`
Expected: 12개 태스크 커밋, 워킹트리 clean. 사용자에게 요약 보고(게이트 60/60 유지, 최상위 6개, 삭제/이동 완료).

---

## Self-Review

**Spec coverage:**
- §3 최상위 6개 → Task 1–9, 검증 Task 12.
- §4 이동표 전 항목 → soar(T7)·procedural(T4)·semantic(T5)·episodic(T6)·env(T8)·memory.py(T9)·oracle(T3).
- §5 삭제 전 항목 → arc/pysoar/operators/make_tasks(T1)·survey(T2)·oracle 이동(T3).
- §6 entrypoint → T10.
- §7 문서 → T11.
- §8 검증 → 각 태스크 GATE/TESTS + T12 종합.
- §9 열린 항목 → 24⊂232(T6 Step1 확정)·grid.py 경계(T8 Step3)·대시보드 출력 디렉터리(T11 Step1).

**Placeholder scan:** 각 코드 스텝에 실제 코드/명령 수록. survey 재배선(T2)만 원문 반환형 확인 후 맞추라는 조건부 — survey.py 원문 값 의존이라 불가피(Step1에서 실측하도록 명시).

**Type consistency:** 심볼명 보존(behavior-preserving) — `PRODUCTIONS/OP_DOCS/OPERATOR_BODIES/SPECS/ARCEnvironment/grids_equal/list_tasks/load_task/available/Memory/run_solve/score_dataset` 를 이동 전후 동일 사용. `ROOT`/`_ROOT` 깊이 보정은 T8·T9 에서 명시적 계산.
