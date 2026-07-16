# 통일 흐름 (라운드4) — grid size/color 결론 하강 후 유지 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.
> 근거·전체 설계는 스펙: `docs/superpowers/specs/2026-07-16-unified-grid-flow-carrydown-design.md`.

**Goal:** 모든 PAIR.program·TASK.solution 을 grid body 3슬롯으로 통일하고, grid-level 에서 결정된 size/color 를
하강 후에도 유지한다. c–h program = `g.size`(grid)·`g.color`(grid)·`g.contents`(하강 coloring 합성). 정답은
이 통일 program 실행에서 나온다.

**Architecture:** `contents_leaf ∈ {const | program(coloring body)}`. execute 가 nested coloring contents 를
실행(= 현행 pixel body 실행과 동일 산출 → 정답 불변). antiunify 는 contents=program 이면 inner coloring body 를
재귀 anti-unify(기존 pixel 로직 재사용). hypothesize 가 부분결정 skeleton 을 유지하고 verify 가 하강 coloring 을
contents 로 감싼다.

**Tech Stack:** Python 3, unittest/pytest, 정적 HTML+JS.

## Global Constraints

- **정답 정오 전 태스크 불변**(easy a–h): nested coloring contents 산출 == 현행 pixel body 산출(같은 body).
  c–h **step 수는 변함(carry-down)** = 의도(§2-4). golden_steps.json 재생성(손편집 금지) 후 delta 검토.
- `to_source`/`as_source`/`parse_program`(pixel/blob 파싱 계약) 불변. grid 경로만 확장(파싱 안 됨).
- program 텍스트에 `raise Impasse`/에러 리터럴 금지 — impasse 는 SOAR substate. placeholder `{"pending":…}` 는
  렌더 안 함(하강완료 후 채워진 것만 표시). 코드는 단정.
- 새 atom 발명 금지 — contents=program 은 grid body + coloring body 의 합성.
- 커밋 말미 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. 브랜치 `seokki-refactor`.
- **최대 리스크: execute 는 유일한 정답-실행 지점.** 태스크마다 `PYTHONPATH=. python3 tests/verify_refactor.py`
  로 정답 정오(및 golden) 확인. T1–T3 은 golden 불변이어야, T4 에서 step 변화+재기준화.

---

### Task 1: program_ast — `program` contents leaf + execute (pixel loop 추출 + nested 분기)

**Files:** Modify `arbor/reasoning/program_ast.py`; Test `tests/test_nested_contents.py`

**Interfaces:**
- Produces: `contents_program(body) -> {"program":{"body":body}}`; `_execute_pixel_body(body, grid_in, choice) -> grid`
  (execute·_execute_grid 공용); `_execute_grid` 가 contents `program` 을 실행.

- [ ] **Step 1: 실패 테스트**
```python
# tests/test_nested_contents.py
import unittest
from arbor.reasoning import program_ast as PA

class TestNestedContents(unittest.TestCase):
    def test_program_contents_executes_like_pixel_body(self):
        # pixel body: recolor cell idx1 → 5
        pbody = [PA.step("coloring", target=PA.ref("pixel", PA.const(1)), color=PA.const(5))]
        pixel_prog = PA.program(pbody)
        inp = [[0, 0], [0, 0]]
        pixel_out = PA.execute(pixel_prog, inp)                 # 현행 pixel 실행
        # hybrid grid program: size/color leaves + contents = program(pbody)
        hybrid = PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, 5]),
                                 PA.contents_program(pbody))
        hybrid_out = PA.execute(hybrid, inp)
        self.assertEqual(hybrid_out, pixel_out)                # nested == pixel (정답 불변)
        self.assertEqual(hybrid_out, [[0, 5], [0, 0]])

    def test_const_contents_unchanged(self):
        g = PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, 2]), PA.const([[0, 0], [0, 2]]))
        self.assertEqual(PA.execute(g, [[9, 9], [9, 9]]), [[0, 0], [0, 2]])
```
Run: `python -m pytest tests/test_nested_contents.py -q` → FAIL(`contents_program` 없음).

- [ ] **Step 2: 구현**
`arbor/reasoning/program_ast.py`:
1. 생성자 추가(다른 leaf 생성자 근처, ~line 25): `def contents_program(body): return {"program": {"body": list(body)}}`.
2. `execute`([:199-226](../../../arbor/reasoning/program_ast.py#L199))의 pixel/object 루프(`H,W=...` 이후 for 문 ~202-223)를 헬퍼로 추출:
   `def _execute_pixel_body(body, grid_in, choice): ...` (기존 루프 그대로 이동, 반환 grid). `execute` 의 비-grid 분기는 이 헬퍼 호출.
3. `_execute_grid`([:229-239](../../../arbor/reasoning/program_ast.py#L229)): contents 분기 확장:
```python
    ct = parts["set_grid_contents"]["contents"]
    if "const" in ct:
        return [list(r) for r in ct["const"]]
    if "program" in ct:                                   # nested coloring 합성 = 하강 산출
        return _execute_pixel_body(ct["program"]["body"], grid_in, choice)
    return [list(r) for r in grid_in]                     # expr 항등 등 identity fallback
```
Run: `python -m pytest tests/test_nested_contents.py -q` → PASS.

- [ ] **Step 3: 회귀(정답·golden 불변 — 아직 hybrid 미생성이라 순수 additive)**
Run: `python -m pytest tests/ -q`(5 pre-existing 외 PASS) + `PYTHONPATH=. python3 tests/verify_refactor.py`(9/9 불변).

- [ ] **Step 4: Commit**
```bash
git add arbor/reasoning/program_ast.py tests/test_nested_contents.py
git commit -m "feat(program-ast): contents_program leaf + execute nested coloring 실행(pixel loop 추출)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: program_ast — antiunify nested contents 재귀

**Files:** Modify `arbor/reasoning/program_ast.py`; Test `tests/test_nested_antiunify.py`

**Interfaces:** `_antiunify_ast_grid` 가 contents_leaf=program 이면 inner body 를 `_antiunify_ast_pixel` 로 재귀, inner slot 을 top-level 로 승격(prefix `?c.`).

- [ ] **Step 1: 실패 테스트**
```python
# tests/test_nested_antiunify.py
import unittest
from arbor.reasoning import program_ast as PA

class TestNestedAntiunify(unittest.TestCase):
    def test_grid_with_program_contents_recurses(self):
        def hyb(idx, col):
            b = [PA.step("coloring", target=PA.ref("pixel", PA.const(idx)), color=PA.const(col))]
            return PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, col]), PA.contents_program(b))
        a, b = hyb(7, 0), hyb(35, 2)                      # 같은 size, color DIFF, contents(coloring) DIFF
        sk, slots = PA.antiunify_ast([a, b])
        self.assertIsNotNone(sk)
        parts = {s["call"]: s["args"] for s in sk["body"]}
        ct = parts["set_grid_contents"]["contents"]
        self.assertIn("program", ct)                       # contents 는 여전히 program(합성)
        # inner coloring 의 src/color 가 slot 으로 승격됨
        self.assertTrue(any(k.startswith("?c.") for k in slots))
```
Run: `python -m pytest tests/test_nested_antiunify.py -q` → FAIL.

- [ ] **Step 2: 구현**
`_antiunify_ast_grid`([:322-339](../../../arbor/reasoning/program_ast.py#L322)) 의 contents property 처리에 분기 추가: 전 pair contents_leaf 가 `program` 이면
```python
        if call == "set_grid_contents" and all("program" in pn[call][key] for pn in partsN):
            inner_asts = [PA.program(pn[call][key]["program"]["body"]) for pn in partsN]
            sk_inner, inner_slots = _antiunify_ast_pixel(inner_asts)   # 기존 pixel 재귀
            leaf = {"program": {"body": (sk_inner or {}).get("body", [])}}
            for nm, meta in (inner_slots or {}).items():               # top-level 로 승격(prefix)
                slots[f"?c.{nm[1:]}"] = meta
            # inner body 의 var 이름도 ?c. 로 재바인딩(승격 일관)
            leaf = _reprefix_inner_vars(leaf, "?c.")
            body.append({"call": call, "args": {key: leaf}}); continue
```
(`_reprefix_inner_vars` = inner body 의 `{"var":"?srcN"}`/`{"var":"?colorN"}` 를 `?c.srcN` 등으로 바꾸는 작은 헬퍼. slots 키와 일치시킴.) const/expr 는 현행 로직.
Run: `python -m pytest tests/test_nested_antiunify.py tests/test_grid_program.py -q` → PASS(기존 grid antiunify 불변).

- [ ] **Step 3: 회귀** `python -m pytest tests/ -q` + `verify_refactor.py` 9/9(additive — 아직 hybrid 미생성).

- [ ] **Step 4: Commit** `git commit -m "feat(program-ast): antiunify nested contents 재귀(pixel 로직 재사용·slot 승격) ..."`

---

### Task 3: hypothesize — 부분결정 skeleton carry-down (golden 불변)

**Files:** Modify `arbor/reasoning/program_ast.py`(`grid_program_from_decide`), `procedural_memory/operators/hypothesize.py`

**Interfaces:** `grid_program_from_decide` 는 부분결정도 skeleton(결정 size/color leaf + contents `{"pending":"contents"}`) 반환. hypothesize 는 full/partial 을 구분해 partial 이면 `grid-skeleton` stash 후 하강.

- [ ] **Step 1: 진단 스냅샷** `_grid_decide`(easy000c) 로 size/color=DECIDE 재확인. 현행 hypothesize:47 분기 로직 정독.
- [ ] **Step 2: `grid_program_from_decide` — 부분 skeleton**
[program_ast.py:79-92](../../../arbor/reasoning/program_ast.py#L79): 셋 다 DECIDE 아니어도 결정된 것은 leaf, contents 미결이면 `{"pending":"contents"}` placeholder 로 채워 `grid_program(size_leaf, color_leaf, pending)` 반환. **full 여부 플래그**를 함께 노출(예 반환 dict 에 `"_partial": bool` 또는 별도 판정 함수 `is_full_grid_program(gp)`).
- [ ] **Step 3: hypothesize 분기**
[hypothesize.py:46-72](../../../procedural_memory/operators/hypothesize.py#L46): `gp` 가 **full**(모든 슬롯 결정) → 현행(물질화+programs-ready). **partial** → skeleton 을 parent GRID substate 에 `ag.wm.add(sid, "grid-skeleton", json.dumps(gp))` 로 stash + 기존처럼 size/color 가설 노출 + `create_hspace` 하강. (placeholder pending 은 렌더/실행 대상 아님 — verify 가 채우기 전엔 PAIR.program 미기록.)
- [ ] **Step 4: 회귀(golden 불변!)** verify.py 가 아직 pixel body 를 쓰므로(T4 전) c–h PAIR.program·정답·step **불변**이어야 함. `verify_refactor.py` → **9/9 그대로**. 아니면 STOP(분기 로직이 흐름을 바꿈). `python -m pytest tests/ -q`.
- [ ] **Step 5: Commit** `git commit -m "feat(hypothesize): 부분결정 grid-skeleton stash+유지(버리지 않고 carry-down 준비) ..."`

---

### Task 4: verify — 하강 coloring 을 contents 로 감싸 hybrid PAIR.program (golden 재기준화)

**Files:** Modify `procedural_memory/operators/verify.py`; re-baseline `tests/golden_steps.json`

**Interfaces:** verify 가 PAIR.program 을 쓸 때 `grid-skeleton` 있으면 그 contents 슬롯을 `contents_program(coloring_ast["body"])` 로 채워 grid body(3슬롯) 로 기록.

- [ ] **Step 1: verify 조립**
[verify.py:25-31](../../../procedural_memory/operators/verify.py#L25): `code`(coloring AST-json) 를 PAIR.program 으로 쓰기 직전, parent chain 에서 `grid-skeleton` 조회. 있으면 skeleton 을 parse → contents 슬롯(`pending`)을 `PA.contents_program(json.loads(code)["body"])` 로 치환 → 그 grid body 를 PAIR.program 으로. 없으면 현행(pixel body).
- [ ] **Step 2: 정답 동등성 실측(핵심 게이트)**
재생성 없이 스크립트로: 각 c–h 태스크의 새 PAIR.program(hybrid) 을 `PA.execute(hybrid, pair.input)` → 그 pair 의 output 과 일치(전 train pair). 즉 hybrid 산출 == 정답. 어긋나면 STOP.
- [ ] **Step 3: golden 재기준화**
`PYTHONPATH=. python3 tests/verify_refactor.py` → **정답 정오는 불변, step 수는 c–h 에서 변함**(carry-down). golden 를 **재생성**(그 생성 경로로; 손편집 금지) 후, delta 가 c–h(및 a/b skeleton 통일) carry-down 에서만 왔는지 검토. 정답이 하나라도 오답으로 바뀌면 STOP.
- [ ] **Step 4: 회귀 + Commit** `python -m pytest tests/ -q`. `git commit -m "feat(verify): 하강 coloring 을 grid-skeleton contents 로 감싸 hybrid PAIR.program + golden 재기준화 ..."`

---

### Task 5: display / runner / viz — hybrid 렌더 (라운드3 연장)

**Files:** Modify `debugger/reports/program_viewer.py`

- [ ] **Step 1: `_display_grid` — contents=program 렌더**
contents_leaf 가 `program` 이면 `g.contents` 를 coloring 합성으로: `g.contents = coloring(pixels_of(input_grid)[i].coord, c) ∘ …`(inner body 를 `_display_pixel` 스타일로). const 면 현행(2D 배열). c–h 가 `g.size`/`g.color`/`g.contents` 3슬롯으로 보이게.
- [ ] **Step 2: 러너 — coloring-합성 contents 실행**
`set_grid_contents(<coloring 합성>)` 를 러너 JS 가 실행해 contents 산출(라운드3 `_arr`/valid 규칙 유지: size/color 는 완성 contents 와 일관해야 valid). `_runner_payload` 의 expected=execute(hybrid) 와 parity.
- [ ] **Step 3: ③ viz — nested coloring box-flow**(기존 pixel viz 재사용, contents 슬롯 안에 중첩).
- [ ] **Step 4: 재생성 + 확인** `python -m debugger.reports.program_viewer` → c–h 탭이 `g.size`/`g.color`/`g.contents(coloring)` 3슬롯. Node parity(hybrid 포함) 16/16 + 색모순 검출 유지. Commit.

---

### Task 6: 전체 회귀 + dashboard 재빌드 + 최종 검증

- [ ] **Step 1:** `python -m pytest tests/ -q`(5 pre-existing 외 PASS).
- [ ] **Step 2:** `PYTHONPATH=. python3 tests/verify_refactor.py` → 정답 정오 전 태스크 불변(step 은 재기준화된 값).
- [ ] **Step 3:** `python -m debugger.build` → 전 태스크 정상, program_report_all.html 에서 c–h 통일 3슬롯 확인.
- [ ] **Step 4:** 정직성 자문: 모든 program 이 grid body 3슬롯 통일? c–h 가 grid size/color 유지+contents=하강 coloring? 코드 단정(raise 없음)? 정답=program 실행? golden 재기준화가 carry-down 만 반영?

## Self-Review (작성자 체크)

- **Spec coverage:** §3-1/3-2(T1) · §3-3(T2) · §4-1(T3) · §4-2+§6(T4) · §5(T5) · §6/§7(T4·T6). 전부 태스크 有.
- **Staging/golden:** T1·T2·T3 golden 불변(additive/미생성) → T4 에서 hybrid 생성+step 변화+재기준화. 각 태스크 verify_refactor 게이트.
- **정답 안전:** nested==pixel 산출 동등성을 T1(단위)·T4(실측) 이중 게이트. execute/antiunify/resolve 무-오답 원칙.
- **리스크:** T3 분기가 golden 을 바꾸면(예상=불변) 즉시 STOP(흐름 오변경 신호). T4 가 정답을 바꾸면 STOP.
