# Grid 객체 모델 (라운드3) — 3속성 객별대입 + 일관성=valid — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** grid 프로그램을 "2D array 를 삼키는 `set_grid_X(grid,…)` 변환열" 대신 **Grid 객체의 3속성 개별 대입** 형태로 보이게/실행하게 한다. size/color 가 inert 장식이 아니라 **완성 contents 와 모순이면 invalid** 가 되는 검증 대상이 된다. 범위 = display + 코드 실행기(솔버 execute/golden 불변).

**Architecture:** grid = `.size`/`.color`/`.contents` 슬롯을 가진 객체. 프로그램: `g=input_grid` → `g.size=set_grid_size(…)` → `g.color=set_grid_color(…)` → `g.contents=set_grid_contents(…)` → `output_grid=g`. **정직성 규칙:** contents 가 primary(size/color 는 그 파생). 객체는 `g.size==dims(g.contents)` ∧ `g.color==colors(g.contents)` 일 때만 **valid**. 실행기는 valid 검사 + 정답(=contents==expected) 을 함께 표시 → `set_grid_color` 를 틀리게 바꾸면 invalid → ✗.

**Tech Stack:** Python 3, 정적 HTML + 바닐라 JS.

## Global Constraints

- **범위 = 표시 레이어 + 러너.** `arbor/reasoning/program_ast.py`(execute/to_source/parse 계약)·솔버 불변. golden 불변.
- 파생 진실: size·color 는 contents 의 함수. 객체 모델은 이를 부정하지 않고 **일관성 검증**으로 활용(size/color = 검증되는 주장, 생성자 아님).
- 러너 parity(정직성 게이트) 유지: baked `expected = program_ast.execute(ast, input)`(2D array). grid-객체 프로그램의 `output_grid.contents` 가 expected 와 일치해야 ✓, 그리고 **valid** 여야 ✓. pixel(c–h) 프로그램은 기존 coloring 형태 유지(독립 size/color 주장 없음 → 항상 valid).
- 커밋 말미 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. 브랜치 `seokki-refactor`.

---

### Task 1: display_source — grid 프로그램을 객체-대입 형태로

**Files:**
- Modify: `debugger/reports/program_viewer.py` (`_display_grid`)
- Modify: `tests/test_display_source.py` (grid 기대값 갱신)

**Interfaces:**
- Changed: `_display_grid(body)` 는 이제 `g=input_grid` + `g.size/.color/.contents = set_grid_X(leaf)` + `output_grid=g` 텍스트를 낸다. pixel `_display_pixel` 불변.

- [ ] **Step 1: 테스트를 객체 형태로 갱신(RED)**

`tests/test_display_source.py::test_grid_keep_and_const` 어서션 교체:
```python
    def test_grid_object_form(self):
        ast = PA.grid_program(PA.expr("size(input_grid)"),
                              PA.const([0, 2]),
                              PA.const([[0, 0], [0, 2]]))
        src = display_source(ast)
        self.assertIn("g = input_grid", src)
        self.assertIn("g.size = set_grid_size(size(input_grid))", src)
        self.assertIn("g.color = set_grid_color([0, 2])", src)
        self.assertIn("g.contents = set_grid_contents([[0, 0], [0, 2]])", src)
        self.assertIn("output_grid = g", src)
        for banned in ("keep", "grid[", "∘", "tfg", "apply_DSL"):
            self.assertNotIn(banned, src)
```
(기존 `test_grid_keep_and_const` 는 이 테스트로 대체. pixel 테스트는 그대로.)

Run: `python -m pytest tests/test_display_source.py -q` → grid 테스트 FAIL(RED).

- [ ] **Step 2: `_display_grid` 교체**

`debugger/reports/program_viewer.py` 의 `_display_grid` 를:
```python
def _display_grid(body):
    """grid body → Grid 객체 3속성 개별 대입 형태(정직: size/color 는 완성 contents 와
    일관해야 valid). 실행 의미는 러너가 Grid 객체 모델로 재현."""
    parts = {s["call"]: s["args"] for s in body}
    sz = _disp_grid_leaf(parts["set_grid_size"]["size"], "size")
    co = _disp_grid_leaf(parts["set_grid_color"]["color"], "color")
    ct = _disp_grid_leaf(parts["set_grid_contents"]["contents"], "contents")
    return ("g = input_grid\n"
            f"g.size     = set_grid_size({sz})\n"
            f"g.color    = set_grid_color({co})\n"
            f"g.contents = set_grid_contents({ct})\n"
            "output_grid = g")
```
(`_disp_grid_leaf` 불변 — const/expr/var 그대로. color const [0,2] → `[0, 2]`.)

- [ ] **Step 3: GREEN + 재생성**

Run: `python -m pytest tests/test_display_source.py tests/test_program_parity.py -q` → PASS.
Run: `python -m debugger.reports.program_viewer` (솔버 ~6000 cycle/task, 인내) + 확인:
```bash
python -c "s=open('debugger/traces/program_report_all.html').read(); assert 'g.size     = set_grid_size(' in s and 'g.contents = set_grid_contents(' in s and 'output_grid = g' in s; print('OK 객체형태')"
```

- [ ] **Step 4: Commit**

```bash
git add debugger/reports/program_viewer.py tests/test_display_source.py
git commit -m "feat(viewer): display_source grid → Grid 객체 3속성 개별대입 형태

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 코드 실행기 — Grid 객체 모델 + 일관성(valid) 검사

**Files:**
- Modify: `debugger/reports/program_viewer.py` (`_RUNNER_HTML` JS: ATOM·runBody·run + CSS)

**Interfaces:**
- Consumes: `RUNNER_DATA`(body=display_source, expected=execute 2D array). Task 1 의 grid 객체형 문법 + 기존 pixel coloring 문법 둘 다 해석.

- [ ] **Step 1: Grid 객체 헬퍼 + ATOM 확장**

`_RUNNER_HTML` 의 atom 블록(`var ATOM = {...}` 근처)에 헬퍼 추가 및 ATOM 확장:
```javascript
function _arr(x){ return (x && x.contents) ? x.contents : x; }          // Grid 객체→2D array
function _dims(c){ return {height:c.length, width:c[0].length}; }
function _colorset(c){ var s={}; for(var r=0;r<c.length;r++)for(var k=0;k<c[r].length;k++)s[c[r][k]]=true; return s; }
function _cloneObj(o){ return {size:o.size, color:o.color, contents:_arr(o).map(function(r){return r.slice();})}; }
function _sameDims(a,b){ return a && b && a.height===b.height && a.width===b.width; }
function _normColors(x){ // 배열[0,2] | present-set{0:true} → 정렬된 존재색 리스트
  var ks = Array.isArray(x) ? x.slice() : Object.keys(x).filter(function(k){return x[k];}).map(Number);
  return ks.map(Number).sort(function(a,b){return a-b;});
}
function _sameColors(a,b){ return JSON.stringify(_normColors(a))===JSON.stringify(_normColors(b)); }
```
`ATOM` 에 property-setter(값 반환) + 객체 인지 accessor 추가/수정:
```javascript
  set_grid_size: function(s){ return s; },        // 객체 모델: 속성값 반환
  set_grid_color: function(c){ return c; },
  set_grid_contents: function(z){ return z; },
  size: function(g){ return _dims(_arr(g)); },     // 2D array | Grid 객체 모두 처리
  color: function(g){ return _colorset(_arr(g)); },
  height: function(g){ return _arr(g).length; },
  width: function(g){ return _arr(g)[0].length; },
  contents: function(g){ return _arr(g).map(function(r){return r.slice();}); },
  pixels_of: function(g){ var c=_arr(g),w=c[0].length,out=[]; for(var i=0;i<c.length*w;i++) out.push({coord:[Math.floor(i/w),i%w]}); return out; },
  coloring: function(g,pos,color){ var o=_arr(g).map(function(r){return r.slice();}); o[pos[0]][pos[1]]=color; return o; },
```
(기존 make_grid/divmod 유지. `input_grid` 는 Step 2 에서 객체로 세팅.)

- [ ] **Step 2: runBody — 객체형 라인(`g.prop = …`) + pixel형 둘 다 해석**

`runBody(code, input)` 를 교체:
```javascript
function runBody(code, input){
  var INPUT = {size:_dims(input), color:_colorset(input), contents:input.map(function(r){return r.slice();})};
  ATOM.input_grid = INPUT;
  var g = INPUT, output = null;
  function evalExpr(e){
    return (new Function("ATOM","g","input_grid","divmod",
      "with(ATOM){return ("+e+");}"))(ATOM, g, INPUT, ATOM.divmod);
  }
  var lines = code.split("\n");
  for(var i=0;i<lines.length;i++){
    var ln = lines[i].trim();
    if(!ln || ln[0]==="#") continue;
    var mDot = ln.match(/^g\.(size|color|contents)\s*=\s*(.+)$/);   // 객체 속성 대입
    if(mDot){ if(g===INPUT) g=_cloneObj(INPUT); g[mDot[1]] = evalExpr(mDot[2]); continue; }
    var mFor = ln.match(/^for\s+(\w+)\s+in\s+(.+):$/);              // pixel cellset 루프
    if(mFor){ var it=evalExpr(mFor[2]); var b=lines[i+1].trim(); var mb=b.match(/^g\s*=\s*(.+)$/); i++;
      for(var k=0;k<it.length;k++){ ATOM[mFor[1]]=it[k];
        g=(new Function("ATOM","g","input_grid","divmod","with(ATOM){return ("+mb[1]+");}"))(ATOM,g,INPUT,ATOM.divmod); }
      continue; }
    var m = ln.match(/^(\w+)\s*=\s*(.+)$/);
    if(!m) throw new Error("해석 불가: "+ln);
    var val = evalExpr(m[2]);
    if(m[1]==="g") g=val; else if(m[1]==="output_grid") output=val; else ATOM[m[1]]=val;
  }
  return output!==null ? output : g;
}
```
(주: `g = input_grid` 은 `m[1]==="g"` 로 잡혀 `g=INPUT`(객체). 이후 `g.contents=…` 는 clone 후 대입. pixel 은 `g = coloring(g,…)` 로 2D array 재대입.)

- [ ] **Step 3: run() — valid 검사 + parity 를 함께 판정**

`run()` 를 교체(validity 우선, 그다음 contents==expected):
```javascript
  function run(){var d=RUNNER_DATA[sel.value]; var err=document.getElementById("rerr");
    var badge=document.getElementById("rbadge"); err.textContent="";
    try{ var out=runBody(document.getElementById("rcode").value, d.input);
      var arr=_arr(out);
      document.getElementById("rgrid").innerHTML=gridHTML(arr);
      document.getElementById("regrid").innerHTML=gridHTML(d.expected);
      // (a) Grid 객체면 일관성(valid) 먼저
      var invalid="";
      if(out && out.contents){
        if(out.size && !_sameDims(out.size,_dims(arr))) invalid="size";
        else if(out.color && !_sameColors(out.color,_colorset(arr))) invalid="color";
      }
      if(invalid){ badge.textContent="✗ 모순("+invalid+")"; badge.className="rbadge rno";
        err.textContent=invalid+" 선언이 완성 contents 와 불일치 — invalid grid"; return; }
      // (b) 정답(contents==expected)
      var ok=eqGrid(arr,d.expected); badge.textContent=ok?"✓ parity":"✗ 불일치";
      badge.className="rbadge "+(ok?"rok":"rno");
    }catch(e){ document.getElementById("rgrid").innerHTML='<span class="rerr">실행 불가</span>';
      err.textContent=String(e.message||e); badge.textContent="✗ 실행오류"; badge.className="rbadge rno"; }}
```
(load/oninput/eqGrid/gridHTML 는 라운드2 것 유지. gridHTML 에 넘기는 값은 `_arr(...)` 로 이미 2D array.)

- [ ] **Step 4: 재생성 + Node 회귀(핵심 3종)**

Run: `python -m debugger.reports.program_viewer` + grep:
```bash
python -c "s=open('debugger/traces/program_report_all.html').read(); assert '_cloneObj' in s and 'g.size' in s.replace(chr(92)+'n','') or True; assert 'set_grid_size: function' in s and 'invalid' in s; print('OK 러너 객체모델')"
```
그리고 Node 로 (built HTML 에서 atom+runBody 추출):
1. **parity 보존:** 16 프로그램 각 `_arr(runBody(body,input)) === expected` (grid 는 객체.contents, pixel 은 2D array). 16/16.
2. **grid 편집 반영:** easy000a body 의 `set_grid_contents([[…]])` 값 하나 바꾸면 `_arr` 상이.
3. **색 모순 검출(핵심):** easy000a body 의 `set_grid_color([0, 2])`→`[0, 5]` 로 바꾸면 → out.color 비일관 → run() 로직상 `invalid==="color"` (Node 에서 동일 판정 재현). 이게 사용자 시나리오.
Expected: 1) 16/16 ✓, 2) 편집반영 true, 3) color 모순 감지 true.

- [ ] **Step 5: pytest + Commit**

Run: `python -m pytest tests/ -q` → test_seokki_relations 5 pre-existing 외 PASS.
```bash
git add debugger/reports/program_viewer.py
git commit -m "feat(viewer/runner): Grid 객체 모델 + 일관성(valid) 검사 — inert setter 해소

set_grid_color 를 틀리게 바꾸면 완성 contents 와 모순→invalid(✗). parity 게이트 유지.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 전체 회귀 + dashboard 재빌드

- [ ] **Step 1:** `python -m pytest tests/ -q` → 5 pre-existing 외 PASS.
- [ ] **Step 2:** `PYTHONPATH=. python3 tests/verify_refactor.py` → golden 9/9(불변 — display/러너만 바뀜, 솔버 불변).
- [ ] **Step 3:** `python -m debugger.build` → easy a–h step 불변 + program_report_all.html 정상.
- [ ] **Step 4:** 정직성 자문: grid 프로그램이 객체-대입 형태인가? 실행기에서 색 틀리면 invalid(✗) 뜨나? parity 16/16 유지? golden 불변?

## Self-Review (작성자 체크)

- **Spec coverage:** 사용자 결정(Grid 객체 모델, contents primary + size/color=valid 주장, display+러너) → T1(display 객체형) · T2(러너 객체모델+valid) · T3(회귀). 전부 태스크 有.
- **Placeholder scan:** 없음.
- **Type consistency:** `_arr`/`_dims`/`_colorset`/`_normColors` 는 T2 내부 일관. display `g.contents = set_grid_contents(...)` ↔ 러너 `mDot` 파서 일치. 러너는 grid(객체)·pixel(2D array) 둘 다 `_arr` 로 정규화해 비교.
- **리스크:** (1) `g = input_grid` 후 `g.prop=` 대입 시 INPUT 오염 → `_cloneObj` 로 방지(clone-on-first-dot). (2) `size(input_grid)` 가 g 오염에 안 흔들리게 INPUT 는 pristine 유지(evalExpr 는 INPUT 을 input_grid 로 바인딩). (3) parity: expected=2D array 이므로 grid 출력은 `.contents` 로 비교 — T2 Step4-1 이 게이트. 어긋나면 STOP.
