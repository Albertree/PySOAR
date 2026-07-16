# keep 제거 + 뷰어 라운드2 (AST 명확화·2D matrix·실행기 수리) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** 사용자 후속 피드백 반영 — grid-property `keep` 인코딩을 명시 식(`expr("<prop>(input_grid)")`)으로 교체해 ②AST트리와 ①body 를 일치시키고, ③시각화의 2D 배열을 줄바꿈 matrix 로, 코드 실행기의 에러처리·편집즉시실행·결과 시각화 품질을 고친다.

**Architecture:** `keep` 은 grid-property leaf 에만 존재(program_ast.py). `keep(prop)→expr("<prop>(input_grid)")` 스왑은 execute(size/color inert·contents-expr는 identity fallback)와 display_source(둘 다 `size(input_grid)` 렌더)를 보존함이 **실측 검증됨** → golden 불변. 나머지는 뷰어 표시/JS UX.

**Tech Stack:** Python 3, unittest/pytest, 정적 HTML + 바닐라 JS.

## Global Constraints

- `program_ast.to_source`/`as_source`/`parse_program` 의 **pixel/blob 경로**는 파싱 계약이라 불변. grid 경로 to_source 는 파싱되지 않으므로 `keep`→`expr` 표기 변경 허용(해당 테스트 재기준화).
- keep→expr 스왑은 **golden 보존**이어야 함(easy a–h 답·step 수 불변): size/color setter 는 Phase-1 실행에서 inert, contents-expr 는 `_execute_grid` 의 identity fallback 이 처리. 구현 후 반드시 golden 재확인.
- 코드 실행기는 이미 **진짜 실행**함(Node 검증: 편집 시 출력 상이). 문제는 UX(에러 시 stale 출력·좁은 문법·저품질 결과격자)만 — 이것만 고친다. JS atom 은 Python DSL 의 충실한 미러 유지(parity 배지 정직성).
- 커밋 말미 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. 브랜치 `seokki-refactor`.

---

### Task 1: grid-property `keep` 제거 → 명시 expr

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (keep 생성/렌더/실행 제거)
- Modify: `tests/test_grid_program.py`, `tests/test_display_source.py` (keep → expr 재기준화)
- Test: 위 + golden 게이트

**Interfaces:**
- Changed: `_size_leaf`/`_color_leaf`/`grid_program_from_decide` 는 이제 KEEP 자리에서 `expr("<prop>(input_grid)")` 를 낸다. `keep()` 생성자 삭제. AST 에 `{"keep":...}` leaf 는 더 이상 존재하지 않음.

- [ ] **Step 1: 회귀 기준선 캡처(golden)**

Run: `PYTHONPATH=. python3 tests/verify_refactor.py 2>&1 | tail -3` (golden 9/9 확인 — 존재 시). 또한 현행 display_source 스냅샷:
```bash
python -c "from arbor.reasoning import program_ast as PA; from debugger.reports.program_viewer import display_source; print(display_source(PA.grid_program(PA.keep('size'),PA.const([0,2]),PA.const([[0,0],[0,2]]))))"
```
출력을 기록(이 텍스트는 Step 이후에도 **동일해야** 한다).

- [ ] **Step 2: 테스트를 expr 기대값으로 갱신(먼저 실패 유도)**

`tests/test_grid_program.py` — `P.keep("size")`→`P.expr("size(input_grid)")`, `P.keep("color")`→`P.expr("color(input_grid)")`, `P.keep("contents")`→`P.expr("contents(input_grid)")` 로 전 호출 치환. 어서션도 갱신:
- `self.assertEqual(ast["body"][0]["args"]["size"], {"keep": "size"})` → `{"expr": "size(input_grid)"}`.
- `test_keep_contents_is_identity`/`test_keep_size_const_contents` 등은 이름 유지하되 leaf 를 expr 로; identity 실행 결과 어서션은 그대로여야 함(값 불변).

`tests/test_display_source.py:9` — `PA.keep("size")` → `PA.expr("size(input_grid)")`. 나머지 어서션(`set_grid_size(g, size(input_grid))`, banned 에 "keep") 그대로.

Run: `python -m pytest tests/test_grid_program.py tests/test_display_source.py -q` → 일부 FAIL(구현 전이므로 keep 생성자 아직 존재하나 어서션 불일치). RED 확인.

- [ ] **Step 3: program_ast.py 에서 keep 제거**

`arbor/reasoning/program_ast.py`:
- `def keep(prop): return {"keep": prop}` (line ~37) **삭제**.
- `_size_leaf`: `if "KEEP" in kinds: return keep("size")` → `return expr("size(input_grid)")`.
- `_color_leaf`: `if ok and k.startswith("KEEP"): return keep("color")` → `return expr("color(input_grid)")`.
- `grid_program_from_decide`: `if cnote == "항등": c_leaf = keep("contents")` → `c_leaf = expr("contents(input_grid)")`.
- `_grid_leaf_src`: `if "keep" in leaf: return "keep"` 줄 **삭제**(expr 는 `_leaf_src` 가 `size(input_grid)` 문자열로 렌더).
- `_execute_grid`: `if "keep" in ct: return [list(r) for r in grid_in]` 줄 **삭제**(contents=expr 는 마지막 identity fallback 이 동일하게 처리). 주석은 "expr(항등 등)은 fallback=identity" 로 갱신.

- [ ] **Step 4: 테스트 GREEN + display_source 불변 확인**

Run: `python -m pytest tests/test_grid_program.py tests/test_display_source.py tests/test_program_ast.py -q` → PASS. (test_program_ast.py 가 grid keep 을 참조하면 동일 규칙으로 갱신.)
Run: Step 1 의 display_source 스냅샷 명령 재실행 → **동일 출력**(스왑이 body 를 안 바꿈).

- [ ] **Step 5: golden 재확인 + 전체 스위트**

Run: `PYTHONPATH=. python3 tests/verify_refactor.py 2>&1 | tail -3` → 9/9(불변). 없으면 `python -m debugger.reports.program_viewer` 재생성 후 RUNNER_DATA parity(16/16) 로 대체 확인.
Run: `python -m pytest tests/ -q` → test_seokki_relations.py 5 pre-existing 외 전부 PASS.

- [ ] **Step 6: Commit**

```bash
git add arbor/reasoning/program_ast.py tests/test_grid_program.py tests/test_display_source.py
git commit -m "refactor(program-ast): grid-property keep 제거 → 명시 expr(<prop>(input_grid))

golden 보존(size/color inert·contents-expr=identity fallback), display_source 불변, ②AST트리=①body 일치.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 뷰어 — ③ contents 2D matrix + ② AST 트리 명확화

**Files:**
- Modify: `debugger/reports/program_viewer.py`

**Interfaces:**
- Consumes: R1 후 grid leaf = expr/const/var (keep 없음).

- [ ] **Step 1: ③ set_grid_contents 를 2D matrix 로**

`_grid_step_rows` 의 contents 행. 현재 `EV.colr(_grid_leaf_repr(ct, "contents"))` 는 flat. const 2D 배열이면 줄바꿈 matrix 로. 헬퍼 추가(파일 상단 헬퍼 근처):

```python
def _contents_cell(leaf):
    """set_grid_contents leaf → 시각화 셀. const 2D 배열이면 줄바꿈 matrix(<pre>), 아니면 콤팩트 라벨."""
    if "const" in leaf and _is_grid_literal(leaf["const"]):
        mat = "\n".join(" ".join(str(x) for x in row) for row in leaf["const"])
        return f'<pre class="cmat">{html.escape(mat)}</pre>'
    return EV.colr(_grid_leaf_repr(leaf, "contents"))
```
`_grid_step_rows` 의 set_grid_contents 행을 다음으로 교체:
```python
        f'<div class="row">{EV.opb("set_grid_contents")}<span class="h"></span>{_contents_cell(ct)}</div><div class="v"></div>',
```
CSS 에 추가(`CSS` 문자열):
```python
.cmat{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:6px 9px;margin:0;
 font:11px/1.35 ui-monospace,monospace;color:#e6c99a;white-space:pre}
```

- [ ] **Step 2: ② AST 트리 — 암묵 grid threading 범례**

grid body 스텝은 AST 에 `size`/`color`/`contents` arg 만 있고 첫 인자 grid(`g`)는 파이프라인 암묵 threading 이다. `_pair_block` 의 ② view 헤더(`② AST 트리`) 아래에 grid body 일 때 한 줄 범례를 넣는다. `_pair_block` 의 ② view 부분을 다음으로 교체(grid 여부로 note 분기):

```python
            f'<div class="view"><div class="vt">② AST 트리</div>'
            + ('<div class="astnote">grid 스텝은 첫 인자 grid(<code>g</code>)를 파이프라인으로 암묵 전달 — '
               'AST 엔 property arg 만. leaf <code>{"expr":"size(input_grid)"}</code>=ARCKG 식, '
               '<code>{"const":…}</code>=고정값.</div>' if PA._is_grid_body(ast.get("body") or []) else '')
            + f'{ast_tree(ast)}</div>'
```
CSS 추가:
```python
.astnote{font-size:10px;color:#8b93a3;background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:6px 8px;margin-bottom:8px;line-height:1.5}
.astnote code{color:#7fb2e0}
```

- [ ] **Step 3: 재생성 + grep 확인**

Run:
```bash
python -m debugger.reports.program_viewer
python - <<'PY'
s=open("debugger/traces/program_report_all.html").read()
assert 'class="cmat"' in s, "2D matrix 미적용"
assert 'class="astnote"' in s, "AST 범례 미적용"
assert '{"keep"' not in s and "'keep'" not in s, "AST 에 keep 잔존(R1 확인)"
print("OK R2 확인")
PY
```
Expected: `OK R2 확인`.

- [ ] **Step 4: Commit**

```bash
git add debugger/reports/program_viewer.py
git commit -m "feat(viewer): ③ contents 2D matrix 렌더 + ② AST 암묵 grid threading 범례

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 코드 실행기 — 편집즉시실행·에러처리·결과 시각화 품질

**Files:**
- Modify: `debugger/reports/program_viewer.py` (`_RUNNER_HTML` 의 JS `run`/`load`/`gridHTML` + CSS)

**Interfaces:**
- Consumes: 기존 `RUNNER_DATA`, `runBody`(불변 — 진짜 실행 로직), `ATOM`.

- [ ] **Step 1: 에러 시 stale 출력 제거 + 편집즉시실행 + select 후 실행**

`_RUNNER_HTML` 의 IIFE 안 `run`/`load`/wiring 을 교체:

```javascript
  function load(){var d=RUNNER_DATA[sel.value]; document.getElementById("rcode").value=d.body;
    document.getElementById("regrid").innerHTML=gridHTML(d.expected); run();}   // load 후 즉시 실행
  function run(){var d=RUNNER_DATA[sel.value]; var err=document.getElementById("rerr");
    var badge=document.getElementById("rbadge"); err.textContent="";
    try{ var out=runBody(document.getElementById("rcode").value, d.input);
      document.getElementById("rgrid").innerHTML=gridHTML(out);
      document.getElementById("regrid").innerHTML=gridHTML(d.expected);
      var ok=eqGrid(out,d.expected); badge.textContent=ok?"✓ parity":"✗ 불일치";
      badge.className="rbadge "+(ok?"rok":"rno");
    }catch(e){ document.getElementById("rgrid").innerHTML='<span class="rerr">실행 불가</span>';  // stale 제거
      err.textContent=String(e.message||e); badge.textContent="✗ 실행오류"; badge.className="rbadge rno"; }}
  var _t; document.getElementById("rcode").oninput=function(){clearTimeout(_t);_t=setTimeout(run,250);}; // 편집즉시(debounce)
  sel.onchange=load; document.getElementById("rrun").onclick=run;
  if(RUNNER_DATA.length){ load(); }
```

- [ ] **Step 2: 결과 격자 시각화 품질 개선**

`gridHTML` 을 셀 크게·격자선으로 교체(썸네일 `thumb` 대신 전용 `rgridbox`):

```javascript
function gridHTML(g){ if(!g||!g.length) return '<span class="rerr">–</span>';
  var w=g[0].length, cells=g.map(function(r){return r.map(function(v){
    return '<i style="background:'+PAL_JS[((v%10)+10)%10]+'"></i>';}).join("");}).join("");
  return '<div class="rgridbox" style="grid-template-columns:repeat('+w+',20px)">'+cells+'</div>';
}
```
CSS 추가:
```python
.rgridbox{display:inline-grid;gap:1px;background:#2a2e38;border:1px solid #3a4150;padding:1px;width:max-content}
.rgridbox i{width:20px;height:20px;display:block}
.rout{align-items:flex-start}.rlab{font-weight:700}
```

- [ ] **Step 3: 재생성 + Node 회귀(실행·편집 반영·parity)**

Run:
```bash
python -m debugger.reports.program_viewer
python - <<'PY'
import re,json
s=open("debugger/traces/program_report_all.html").read()
assert "rgridbox" in s and "oninput" in s and "실행 불가" in s, "R3 미적용"
m=re.search(r'var RUNNER_DATA=(\[.*?\]);</script>', s, re.S); assert m
print("OK R3 임베드 확인:", len(json.loads(m.group(1))), "programs")
PY
```
그리고 편집반영·parity 를 Node 로 재확인(엔진 불변 증명): `runBody(원본)` ≠ `runBody(편집본)`, 원본은 expected 와 일치. (구현자는 이전 라운드 harness 방식으로 grid·pixel 각 1개 확인.)
Expected: `OK R3 임베드 확인: N programs` (N≥8) + 편집반영 true·parity 유지.

- [ ] **Step 4: Commit**

```bash
git add debugger/reports/program_viewer.py
git commit -m "fix(viewer/runner): 편집즉시실행·에러시 stale출력 제거·결과격자 품질 개선

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 전체 회귀 + dashboard 재빌드

- [ ] **Step 1:** `python -m pytest tests/ -q` → 5 pre-existing(test_seokki_relations) 외 PASS.
- [ ] **Step 2:** `python -m debugger.build` → easy a–h **step 수 불변**(a/b 1280, c–h 2760 = golden) + program_report_all.html 정상. keep→expr 가 솔버 회귀를 안 냈음을 확인.
- [ ] **Step 3:** 정직성 자문: AST 에 keep 부재·②트리=①body 일치? 실행기 편집 반영·에러 명확? contents 2D matrix?

## Self-Review (작성자 체크)

- **Spec coverage:** 사용자 5피드백 → #1 2-arg(R2 Step2 범례) · #2 keep 제거(R1) · #3 2D matrix(R2 Step1) · #4 실행기 수리(R3) · #5 결과 시각화(R3 Step2). 전부 태스크 有.
- **Placeholder scan:** 없음.
- **Type consistency:** R1 후 grid leaf=expr/const/var; R2 `_contents_cell`·`astnote` 는 그 표현 소비. R3 `gridHTML`/`run`/`load` 이름 일관. keep→expr 스왑 golden/display 보존은 실측 검증됨(계획 전제).
- **리스크:** R1 이 golden 을 바꾸면(예상 밖) 즉시 STOP — size/color inert·contents identity fallback 전제가 틀린 것. R4 Step2 가 게이트.
