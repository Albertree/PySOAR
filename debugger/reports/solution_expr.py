# -*- coding: utf-8 -*-
"""TASK.solution 표현식 렌더 — 솔버 선택자/resolved 를 함수·symbol 조합 표현식으로 재표기.
설계: docs/superpowers/specs/2026-07-20-solution-expression-viz-design.md. 시각화-먼저(솔버 불변).
금지: count·output_grid symbol (P5, input_grid 만)."""
from __future__ import annotations
import html
import re


def selector_to_condition(sel):
    """솔버 선택자 이름 → (select 조건식, shape_ref|None). 채택된 선택자 충실 렌더.
    bounded → color(o) != 0 (표현계층 색0≠배경 완화, 설계 §3-2)."""
    if not sel:
        return "true", None
    if sel.startswith("color="):
        return f"color(o) == {sel[len('color='):]}", None
    if sel.startswith("size="):
        return f"area(o) == {sel[len('size='):]}", None
    if sel == "bounded":
        return "color(o) != 0", None
    if sel.startswith("shape#"):
        ref = f"shape{sel[len('shape#'):]}"
        return f"shape(o) == {ref}", ref
    return sel, None                       # 정직 fallback (row=/col= 등 move 미사용)


def _parse_axis(tok):
    """이동 축 토큰 → (kind, target, anchor_comp_kind). kind: rel|abs|edge|corner|br|raw.
    anchor_comp_kind: 'tl'(top_left)|'br'(bottom_right)|'0'(없음=상대). target: int|'corner'|str."""
    m = re.match(r"^[rc]0([+-]\d+)$", tok)
    if m:
        return ("rel", int(m.group(1)), "0")
    if tok.startswith("BR="):
        return ("br", int(tok[len("BR="):]), "br")
    if tok.startswith("="):
        return ("abs", int(tok[len("="):]), "tl")
    if tok == "0":
        return ("edge", 0, "tl")
    if tok in ("H-h", "W-w"):
        return ("corner", "corner", "br")
    return ("raw", tok, "0")


def move_to_vector(row_tok, col_tok, objvar):
    """resolved move[ROW,COL] → 벡터-산술 표현식(설계 §3-4). 같은-모델은 깔끔형, 혼합은 성분별."""
    r = _parse_axis(row_tok)
    c = _parse_axis(col_tok)
    coord = f"coordinate({objvar})"
    # 제자리(둘 다 rel Δ0)
    if r[0] == "rel" and c[0] == "rel":
        if r[1] == 0 and c[1] == 0:
            return coord
        return f"{coord} + ({r[1]}, {c[1]})"
    # 둘 다 격자코너: GRID 는 size/color/contents 만 가짐(코너 property 없음). 격자 우하코너 = (H-1, W-1)
    # = (height(input_grid)-1, width(input_grid)-1). bottom_right(input_grid) 는 무효(사용자 2026-07-20).
    if r[0] == "corner" and c[0] == "corner":
        return f"{coord} - bottom_right({objvar}) + (height(input_grid) - 1, width(input_grid) - 1)"
    # 앵커 성분(각 축)과 target 성분
    def _anchor(comp, axis):                       # axis: 'row'|'col'
        if comp == "tl":
            return f"top_left({objvar}).{axis}"
        if comp == "br":
            return f"bottom_right({objvar}).{axis}"
        return "0"                                 # 상대축은 anchor 0
    def _target(kind, tgt, axis):
        if kind == "corner":                       # row→height, col→width (H-1 / W-1)
            return f"{'height' if axis == 'row' else 'width'}(input_grid) - 1"
        return str(tgt)                            # rel Δ / abs v / br v / edge 0
    ar, ac = _anchor(r[2], "row"), _anchor(c[2], "col")
    tr, tc = _target(r[0], r[1], "row"), _target(c[0], c[1], "col")
    # 두 축 anchor 종류 같으면 whole-point 형태(top_left(obj)/bottom_right(obj))
    if r[2] == c[2] and r[2] in ("tl", "br"):
        whole = "top_left" if r[2] == "tl" else "bottom_right"
        return f"{coord} - {whole}({objvar}) + ({tr}, {tc})"
    # 혼합: 성분별 anchor
    return f"{coord} - ({ar}, {ac}) + ({tr}, {tc})"


def _split_move(resolved_val):
    """'move[ROW,COL]@sel' → (row_tok, col_tok, sel). 파싱 실패 시 (None,None,None)."""
    m = re.match(r"^move\[(.+?),(.+?)\](?:@(.+))?$", resolved_val)
    if not m:
        return None, None, None
    return m.group(1), m.group(2), (m.group(3) or None)


def _strip_vspace(sel):
    """선택자 뒤에 붙는 version-space 가설 인덱스 suffix('...#k', k=정수) 제거 — 모호(K>1)할 때만
    resolve 가 전체 이름 끝에 최종 '#k' 를 덧붙인다(arbor/reasoning/antiunify.py `_push`/`resolve_slot`,
    §2026-07-20 조사). `shape#N` 은 그 자체가 base 선택자 이름(N=shape class index)이라 보존 —
    'shape#0#1' 처럼 뒤에 또 버전 suffix 가 붙은 경우만 그 마지막 '#k' 를 벗긴다."""
    m = re.match(r"^shape#\d+#\d+$", sel)
    if m:
        return sel.rsplit("#", 1)[0]
    if not sel.startswith("shape#") and re.match(r"^.+#\d+$", sel):
        return sel.rsplit("#", 1)[0]
    return sel


def _sel_of(resolved_val):
    """resolved 값의 @선택자 ('move[..]@color=2'→'color=2', 'color@bounded'→'bounded').
    version-space suffix('@bounded#0'→'bounded')는 _strip_vspace 로 제거."""
    sel = resolved_val.rsplit("@", 1)[1] if "@" in resolved_val else None
    return _strip_vspace(sel) if sel else sel


def object_binding_lines(resolved, shapes):
    """객체 선정 preamble 라인들 — `shape0 = [[..]]`(shape 선택자 시) + `obj0 = select(object, <조건>)`.
    ①②③ 공통(사용자 2026-07-20: ②③ 시각화만 봐도 obj0 가 무엇이고 어떻게 선정됐는지 알게).
    선택자-일관: 모든 슬롯이 같은 @sel 이라 obj0 하나로 묶인다."""
    sel = next((_sel_of(v) for v in resolved.values() if _sel_of(v)), None)
    cond, shape_ref = selector_to_condition(sel)
    lines = []
    if shape_ref is not None:
        lines.append(f"{shape_ref} = {shapes.get(shape_ref, '[]')}")
    lines.append(f"obj0 = select(object, {cond})")
    return lines


def object_select_expr(resolved):
    """obj 을 인라인한 select 표현식 문자열 'select(object, <조건>)'. ②③ 그래프트 서브트리가
    obj0 심볼에 의존하지 않고 '어떤 객체인지'(선정 조건)까지 자립적으로 보이게(사용자 2026-07-20)."""
    sel = next((_sel_of(v) for v in resolved.values() if _sel_of(v)), None)
    cond, _ref = selector_to_condition(sel)
    return f"select(object, {cond})"


def graft_expr(resolved_val, resolved_all):
    """한 DIFF 슬롯의 resolved 값 → 그 자리에 이식할 함수-조합 표현식 문자열(select 인라인).
    move[..] → 벡터식(coordinate(select(...))±…), color@.. → color(select(...))."""
    obj = object_select_expr(resolved_all)
    if resolved_val.startswith("move["):
        rt, ct, _sel = _split_move(resolved_val)
        return move_to_vector(rt, ct, obj) if rt else f"coordinate({obj})"
    if resolved_val.startswith("color@"):
        return f"color({obj})"
    return resolved_val


def render_solution_lines(solution_ast, resolved, comm, shapes):
    """설계 §5 형태의 표시줄 리스트. 시각화-먼저(솔버 데이터 재표기). 결정적."""
    body = solution_ast.get("body") or []
    parts = {s["call"]: s["args"] for s in body}
    # 1) 공통 선택자 → 객체 바인딩 obj0 (선택자-일관: 모든 슬롯 동일 @sel)
    lines = list(object_binding_lines(resolved, shapes))
    objvar = "obj0"
    var_i = [0]

    def _new_var():
        var_i[0] += 1
        return f"?var{var_i[0]}"

    # 2) set_grid_size (COMM→리터럴, DIFF→변수화)
    sz = parts["set_grid_size"]["size"]
    if comm.get("size", True):
        v = sz.get("const")
        if isinstance(v, dict):
            lit = f"({v.get('height')}, {v.get('width')})"
        elif v is not None:
            lit = str(v)
        else:
            lit = str(sz.get("expr"))                 # const 없음(예: size(input_grid)) → expr fallback
        lines.append(f"set_grid_size = {lit}")
    else:
        vn = _new_var(); lines.append(f"{vn} = size(input_grid)")
        lines.append(f"set_grid_size = {vn}")
    # 3) set_grid_color
    co = parts["set_grid_color"]["color"]
    if comm.get("color", True):
        lines.append(f"set_grid_color = {co.get('const', co.get('expr'))}")
    else:
        vn = _new_var(); lines.append(f"{vn} = color(input_grid)")
        lines.append(f"set_grid_color = {vn}")
    # 4) coloring 스텝 (cellset=DIFF 슬롯 → 변수화; color=const→리터럴/var→color(obj))
    prog = parts["set_grid_contents"]["contents"].get("program", {}).get("body", [])
    for s in prog:
        tgt = s["args"]["target"]; colr = s["args"]["color"]
        cell_var = tgt.get("cells", {}).get("var") if tgt.get("ref") == "cellset" else None
        # 좌표 변수
        if cell_var and cell_var in resolved:
            rt, ct, _ = _split_move(resolved[cell_var])
            expr = move_to_vector(rt, ct, objvar) if rt else f"coordinate({objvar})"
        else:
            expr = f"coordinate({objvar})"
        vcoord = _new_var(); lines.append(f"{vcoord} = {expr}")
        # 색
        if "const" in colr:
            cterm = str(colr["const"])
        else:
            vcol = _new_var(); lines.append(f"{vcol} = color({objvar})")
            cterm = vcol
        lines.append(f"coloring({vcoord}, {cterm})")
    return lines


# ══ 표현식 코드 → AST 파서 (②AST 트리·③시각화 트리가 '하나의 코드'를 구조로 그리게) ══════════════
# 사용자 2026-07-20: obj0=select(…)·?var 도 코드다. preamble 로 첨가하지 말고, render_solution_lines 가
# 낸 표시줄(코드) 전체를 여기서 파싱해 구조(AST)로 렌더한다. HTML 렌더는 program_report(html import 有)에서.

def _tok(s):
    """표현식 문자열 → 토큰. op문자열 | ('num',int) | ('id',str) | 'and'|'not'."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif s[i:i + 2] in ("==", "!="):
            out.append(s[i:i + 2]); i += 2
        elif c in "()[],.+-*":
            out.append(c); i += 1
        elif c.isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            out.append(("num", int(s[i:j]))); i = j
        elif c.isalpha() or c in "?_":
            j = i
            while j < n and (s[j].isalnum() or s[j] in "?_"):
                j += 1
            w = s[i:j]; i = j
            out.append(w if w in ("and", "not") else ("id", w))
        else:
            i += 1
    return out


class _Parser:
    """재귀하강. 우선순위(낮→높): and < ==/!= < +/- < unary(not) < postfix(.,call) < primary."""
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def _peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def _pop(self):
        tk = self.t[self.i]; self.i += 1; return tk

    def _eat(self, x):
        if self._peek() == x:
            self.i += 1; return True
        return False

    def expr(self):
        left = self._cmp()
        if self._peek() == "and":
            items = [left]
            while self._eat("and"):
                items.append(self._cmp())
            return {"k": "and", "items": items}
        return left

    def _cmp(self):
        left = self._add()
        if self._peek() in ("==", "!="):
            return {"k": "cmp", "op": self._pop(), "lhs": left, "rhs": self._add()}
        return left

    def _add(self):
        left = self._unary()
        while self._peek() in ("+", "-"):
            op = self._pop()
            left = {"k": "binop", "op": op, "lhs": left, "rhs": self._unary()}
        return left

    def _unary(self):
        if self._peek() == "not":
            self._pop(); return {"k": "not", "e": self._unary()}
        return self._post()

    def _post(self):
        base = self._prim()
        while self._peek() == ".":
            self._pop(); fld = self._pop()
            base = {"k": "member", "base": base, "field": fld[1] if isinstance(fld, tuple) else str(fld)}
        return base

    def _prim(self):
        tk = self._peek()
        if tk == "(":
            self._pop()
            items = [self.expr()]
            while self._eat(","):
                items.append(self.expr())
            self._eat(")")
            return items[0] if len(items) == 1 else {"k": "tuple", "items": items}
        if tk == "[":
            return {"k": "lit", "v": self._list()}
        if tk == "-":
            self._pop(); num = self._pop()
            return {"k": "lit", "v": -num[1] if isinstance(num, tuple) else 0}
        if isinstance(tk, tuple) and tk[0] == "num":
            self._pop(); return {"k": "lit", "v": tk[1]}
        if isinstance(tk, tuple) and tk[0] == "id":
            self._pop()
            if self._peek() == "(":
                self._pop(); args = []
                if self._peek() != ")":
                    args.append(self.expr())
                    while self._eat(","):
                        args.append(self.expr())
                self._eat(")")
                return {"k": "call", "fn": tk[1], "args": args}
            return {"k": "id", "name": tk[1]}
        if tk is not None:
            self._pop()
        return {"k": "id", "name": str(tk)}

    def _list(self):
        self._eat("[")
        items = []
        while self._peek() not in ("]", None):
            if self._peek() == "[":
                items.append(self._list())
            elif self._peek() == "-":
                self._pop(); items.append(-self._pop()[1])
            else:
                tk = self._pop(); items.append(tk[1] if isinstance(tk, tuple) else tk)
            self._eat(",")
        self._eat("]")
        return items


def parse_expr(s):
    return _Parser(_tok(s)).expr()


def parse_program(lines):
    """표시줄(코드) → 문장 AST. 'lhs = rhs'(첫 = 가 == 아님)→assign, 그 외→stmt(call)."""
    stmts = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r"^([\w?]+)\s*=(?!=)\s*(.+)$", ln)
        if m:
            stmts.append({"k": "assign", "lhs": m.group(1), "rhs": parse_expr(m.group(2))})
        else:
            stmts.append({"k": "stmt", "e": parse_expr(ln)})
    return stmts


def _lit_str(v):
    return "[" + ", ".join(_lit_str(x) for x in v) + "]" if isinstance(v, list) else str(v)


def node_label_children(node):
    """expr AST 노드 → (label, [자식노드]) — HTML 트리 렌더가 소비(program_report)."""
    k = node["k"]
    if k == "call":
        return node["fn"], node["args"]
    if k in ("binop", "cmp"):
        return node["op"], [node["lhs"], node["rhs"]]
    if k == "and":
        return "and", node["items"]
    if k == "not":
        return "not", [node["e"]]
    if k == "tuple":
        return "( , )", node["items"]
    if k == "member":
        return f".{node['field']}", [node["base"]]
    if k == "id":
        return node["name"], []
    if k == "lit":
        return _lit_str(node["v"]), []
    return "?", []


def expr_str(node):
    """expr AST → 문자열(라운드트립 검증용)."""
    k = node["k"]
    if k == "call":
        return f"{node['fn']}({', '.join(expr_str(a) for a in node['args'])})"
    if k in ("binop", "cmp"):
        return f"{expr_str(node['lhs'])} {node['op']} {expr_str(node['rhs'])}"
    if k == "and":
        return " and ".join(expr_str(x) for x in node["items"])
    if k == "not":
        return f"not {expr_str(node['e'])}"
    if k == "tuple":
        return "(" + ", ".join(expr_str(x) for x in node["items"]) + ")"
    if k == "member":
        return f"{expr_str(node['base'])}.{node['field']}"
    if k == "id":
        return node["name"]
    if k == "lit":
        return _lit_str(node["v"])
    return "?"


# ══ 완전 실행형 TASK.solution 코드 (pair.program 과 같은 골격) ═══════════════════════════════════
# 사용자 2026-07-20: task.solution ① 코드는 pair.program 처럼 변수선언 생략 없이 g/g0..gN/result/
# output_grid 스레딩 + set_grid_contents(result) 마무리를 갖춰야 한다. g0/g1/g2 는 시각화(solution_grid)
# 에서만 인위 누락하고, 코드에는 유지한다. ?var 는 anti-unification DIFF 자리에만 발생한다.
def render_solution_source(solution_ast, resolved, comm, shapes):
    """TASK.solution → 완전 실행형 코드 라인(pair.program 골격). render_solution_lines(단순 표시줄)
    와 같은 재료(obj0 선정·move 벡터식·COMM 리터럴/DIFF ?var)를 g/g0..gN/result/output_grid 스레딩
    스켈레톤에 실어 낸다. 결정적."""
    body = solution_ast.get("body") or []
    parts = {s["call"]: s["args"] for s in body}
    var_i = [0]

    def nv():
        var_i[0] += 1
        return f"?var{var_i[0]}"

    defs_head = []
    sz = parts["set_grid_size"]["size"]
    if comm.get("size", True):
        v = sz.get("const")
        if isinstance(v, dict):
            szt = f"({v.get('height')}, {v.get('width')})"
        elif v is not None:
            szt = str(v)
        else:
            szt = str(sz.get("expr"))
    else:
        vn = nv(); defs_head.append(f"{vn} = size(input_grid)"); szt = vn
    co = parts["set_grid_color"]["color"]
    if comm.get("color", True):
        cot = str(co.get("const", co.get("expr")))
    else:
        vn = nv(); defs_head.append(f"{vn} = color(input_grid)"); cot = vn
    obj_lines = list(object_binding_lines(resolved, shapes))
    prog = parts["set_grid_contents"]["contents"].get("program", {}).get("body", [])
    objvar = "obj0"
    thread = ["g0 = g.contents"]
    gi = 0
    for s in prog:
        tgt = s["args"]["target"]; colr = s["args"]["color"]
        cell_var = tgt.get("cells", {}).get("var") if tgt.get("ref") == "cellset" else None
        if cell_var and cell_var in resolved:
            rt, ct, _ = _split_move(resolved[cell_var])
            expr = move_to_vector(rt, ct, objvar) if rt else f"coordinate({objvar})"
        else:
            expr = f"coordinate({objvar})"
        vc = nv(); thread.append(f"{vc} = {expr}")
        if "const" in colr:
            cterm = str(colr["const"])
        else:
            vcol = nv(); thread.append(f"{vcol} = color({objvar})"); cterm = vcol
        gi += 1
        thread.append(f"g{gi} = coloring(g{gi - 1}, {vc}, {cterm})")
    thread.append(f"result = g{gi}")
    return (["g = input_grid"] + defs_head
            + [f"g.size = set_grid_size({szt})", f"g.color = set_grid_color({cot})", ""]
            + obj_lines + thread
            + ["g.contents = set_grid_contents(result)", "output_grid = g"])


# ══ 그리드 데이터플로우 시각화 (완전 실행형 코드 → 정돈 SVG) ══════════════════════════════════════
# 사용자 2026-07-20 규칙: 척추=왼쪽 세로(input_grid→set_grid_size→set_grid_color→coloring…→
# set_grid_contents→output_grid). g0/g1/g2 스레딩·result·wrapper 는 척추로 흡수(시각화 누락). coloring
# 은 set_grid_color 아래 한 칸 들여쓴 열에서 threading, 종착 result 를 set_grid_contents 가 받는다.
# 같은 가로줄=함수+arg 체인. ?var/연산자·논리식은 placeholder 로 한 단 위로 올림(+/==/… 는 인픽스).
# 중복 노드(obj0)는 우측 상단에 정의를 따로. ?var 발생은 DIFF 자리에만(render_solution_* 가 이미 보장).
_GRID_BIN = {"+", "-", "*", "==", "!="}


def _grid_classify(lines):
    """완전 실행형 코드 라인 → (defs, setg, colorings). g.size/g.color=set_grid_*(arg)→setg,
    gN=coloring(gM,T,C)→colorings(그리드-스레드 인자 gM 제외), 그 외 name=expr→defs(?var/obj/shape).
    g=input_grid / gN=g.contents / result=gN / g.contents=… / output_grid=g 스켈레톤은 무시(척추 흡수)."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    defs, setg, colorings = {}, [], []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r"^g\.(size|color)\s*=\s*set_grid_\w+\((.+)\)$", ln)
        if m:
            setg.append((f"set_grid_{m.group(1)}", parse_expr(m.group(2))))
            continue
        if (re.match(r"^g\.contents\s*=", ln) or re.match(r"^g\w*\s*=\s*g\.contents$", ln)
                or re.match(r"^result\s*=", ln) or re.match(r"^g\s*=\s*input_grid$", ln)
                or re.match(r"^output_grid\s*=", ln)):
            continue
        m = re.match(r"^g\d+\s*=\s*coloring\((.+)\)$", ln)
        if m:
            colorings.append(parse_expr("coloring(" + m.group(1) + ")")["args"][1:])
            continue
        m = re.match(r"^([\w?]+)\s*=(?!=)\s*(.+)$", ln)
        if m:
            defs[m.group(1)] = parse_expr(m.group(2))
            continue
    return defs, setg, colorings


def _grid_layout(defs, setg, colorings, compare=None):
    """(defs, setg, colorings) → (nodes, edges, outlines). 노드=[id,label,row,col,kind].
    좌표평면 격자 배치. compare(선택, _compare_asts 결과) 있으면 set_grid_size/color·coloring
    target/color 값노드에 COMM('comm')/DIFF('diff') 아웃라인을 outlines[id] 로 매긴다."""
    nodes, edges, nid, pc = [], [], [0], [0]
    outlines = {}

    def N(label, row, col, kind):
        nid[0] += 1
        i = f"g{nid[0]}"
        nodes.append([i, label, row, col, kind])
        return i

    ch = node_label_children

    def simple_tuple(node):
        """좌표류 튜플(항목이 전부 leaf) → 단일 박스로. `(2, 3)`·`(1, 1)` 을 `( , )`–2–3 으로 쪼개지
        않게(사용자 2026-07-20). 복합 항목(H-1 등 연산)이 있으면 False(구조 유지)."""
        return node.get("k") == "tuple" and all(not ch(it)[1] for it in node.get("items", []))

    def named(name, defexpr, row, col, kind="var"):
        f, fk = ch(defexpr); fs = str(f)
        if fs in _GRID_BIN and len(fk) == 2:              # 인픽스: op1 op op2, 값은 op 아래
            w1, r1 = operand(fk[0], row - 1, col); opc = col + w1
            opid = N(fs, row - 1, opc, "fn"); w2, r2 = operand(fk[1], row - 1, opc + 1)
            vid = N(name, row, opc, kind)
            edges.extend([(r1, opid, "h"), (opid, r2, "h"), (opid, vid, "v")])
            return opc + 1 + w2 - col, vid
        vid = N(name, row, col, kind)
        fid = N(fs, row - 1, col, "fn" if fk else "lit"); edges.append((fid, vid, "v"))
        c = col + 1; prev = fid
        for k in fk:
            w, rid = child(k, row - 1, c); edges.append((prev, rid, "h")); prev = rid; c += w
        return max(1, c - col), vid

    def operand(node, row, col):                          # 인픽스 피연산자: call 이면 placeholder
        if simple_tuple(node):
            return 1, N(expr_str(node), row, col, "lit")
        if ch(node)[1]:
            pc[0] += 1; return named(f"?p{pc[0]}", node, row, col)
        return leafish(node, row, col)

    def child(node, row, col):                            # prefix arg: binary 면 placeholder, else inline
        if simple_tuple(node):
            return 1, N(expr_str(node), row, col, "lit")
        label, kids = ch(node); s = str(label)
        if kids and s in _GRID_BIN and len(kids) == 2:
            pc[0] += 1; return named(f"?p{pc[0]}", node, row, col)
        return inline(node, row, col)

    def leafish(node, row, col):
        label, kids = ch(node); s = str(label)
        if node.get("k") == "id" and s in defs and s.startswith("?"):
            return named(s, defs[s], row, col)
        if node.get("k") == "id" and s == "obj0":
            return 1, N("obj0", row, col, "var")
        if node.get("k") == "id" and s in defs and s.startswith("shape"):
            vid = N(s, row, col, "var")
            edges.append((N(str(ch(defs[s])[0]), row - 1, col, "lit"), vid, "v"))
            return 1, vid
        return 1, N(s, row, col, "var" if s.startswith("?") else "lit")

    def inline(node, row, col):                           # non-binary call → fn + args 같은 줄
        if simple_tuple(node):
            return 1, N(expr_str(node), row, col, "lit")
        label, kids = ch(node); s = str(label)
        if not (kids and s not in _GRID_BIN):
            return leafish(node, row, col)
        fid = N(s, row, col, "fn"); c = col + 1; prev = fid
        for k in kids:
            w, rid = child(k, row, c); edges.append((prev, rid, "h")); prev = rid; c += w
        return max(1, c - col), fid

    def hn(defexpr):
        f, fk = ch(defexpr); fs = str(f)
        if fs in _GRID_BIN and len(fk) == 2:
            return 1 + max(ho(fk[0]), ho(fk[1]))
        return 1 + max([hc(k) for k in fk], default=0)

    def ho(node):
        if simple_tuple(node):
            return 0
        label, kids = ch(node); s = str(label)
        if node.get("k") == "id" and s in defs and s.startswith("?"):
            return hn(defs[s])
        if node.get("k") == "id" and s == "obj0":
            return 0
        if node.get("k") == "id" and s in defs and s.startswith("shape"):
            return 1
        return hn(node) if kids else 0

    def hc(node):
        if simple_tuple(node):
            return 0
        label, kids = ch(node); s = str(label)
        if kids and s in _GRID_BIN and len(kids) == 2:
            return hn(node)
        return hi(node)

    def hi(node):
        if simple_tuple(node):
            return 0
        label, kids = ch(node); s = str(label)
        if node.get("k") == "id" and s in defs and s.startswith("?"):
            return hn(defs[s])
        if node.get("k") == "id" and s == "obj0":
            return 0
        if node.get("k") == "id" and s in defs and s.startswith("shape"):
            return 1
        return max([hc(k) for k in kids], default=0) if kids else 0

    steps = (compare or {}).get("contents", {}).get("steps", []) if compare else []
    row = 0; prev = N("input_grid", 0, 0, "end")
    for label, arg in setg:
        h = hi(arg); row += h + 1
        opid = N(label, row, 0, "op"); edges.append((prev, opid, "spine")); prev = opid
        _w, rid = child(arg, row, 1); edges.append((opid, rid, "h"))
        if compare:                                       # set_grid_size/color 값 → COMM/DIFF 아웃라인
            key = "size" if label.endswith("size") else ("color" if label.endswith("color") else None)
            if key and compare.get(key):
                outlines[rid] = compare[key]
    for i, args in enumerate(colorings):
        h = max([hc(a) for a in args], default=0); row += h + 1
        opid = N("coloring", row, 1, "op"); edges.append((prev, opid, "spine")); prev = opid
        c = 2; p2 = opid
        for j, a in enumerate(args):
            w, rid = child(a, row, c); edges.append((p2, rid, "h")); p2 = rid; c += w
            if compare and i < len(steps):                # coloring target(j=0)/color(j=1) → COMM/DIFF
                cls = steps[i].get("idx" if j == 0 else "col")
                if cls:
                    outlines[rid] = cls
    row += 1
    scont = N("set_grid_contents", row, 0, "op")
    result = N("result", row, 1, "end")
    edges.append((prev, result, "spine")); edges.append((scont, result, "h"))
    row += 1
    outg = N("output_grid", row, 0, "end"); edges.append((scont, outg, "spine"))
    if "obj0" in defs:                                    # 중복노드 obj0 의 정의를 우측 상단에 따로
        ocol = max(n[3] for n in nodes) + 2
        named("obj0", defs["obj0"], hn(defs["obj0"]), ocol)
    return nodes, edges, outlines


def _grid_render(nodes, edges, outlines=None, cw=176, rh=58, bw=146, bh=30):
    """(nodes, edges) → self-contained SVG(밝은 카드 배경). 척추 세로선·들여쓰기는 박스에 수직
    진입(2번 꺾임). h=가로 arg 체인, v=세로 정의-값, spine=굵은 척추.
    outlines(선택) = {id: 'comm'|'diff'} — 그 값노드 테두리를 녹색(COMM)/빨강(DIFF)으로."""
    outlines = outlines or {}
    pos = {n[0]: (n[3] * cw + 92, n[2] * rh + 42) for n in nodes}
    W = max(p[0] for p in pos.values()) + bw + 20
    Hgt = max(p[1] for p in pos.values()) + bh + 20
    fl = {"var": "#e7dcef", "fn": "#f2f6fb", "lit": "#fbfaf6", "op": "#ffffff", "end": "#eeeeee"}
    sk = {"var": "#8a6ea6", "fn": "#3d6ea5", "lit": "#8a8574", "op": "#2b2b2b", "end": "#555555"}
    ocol = {"comm": "#3fae6a", "diff": "#e23b3b"}
    o = [f'<svg viewBox="0 0 {W} {Hgt}" width="{W}" height="{Hgt}" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="ui-monospace,Menlo,monospace">',
         f'<rect x="0" y="0" width="{W}" height="{Hgt}" rx="12" fill="#f7f6f3"/>']
    for a, b, t in edges:
        x1, y1 = pos[a]; x2, y2 = pos[b]
        c = "#222" if t == "spine" else "#555"; wd = 2.2 if t == "spine" else 1.4
        if t == "h":
            d = f'M{x1 + bw / 2} {y1} L{x2 - bw / 2} {y2}'
        elif t == "spine" and x1 != x2:                   # 들여/내어쓰기: 박스에 수직 진입(2번 꺾임)
            my = (y1 + bh / 2 + y2 - bh / 2) / 2
            d = f'M{x1} {y1 + bh / 2} L{x1} {my} L{x2} {my} L{x2} {y2 - bh / 2}'
        else:
            d = f'M{x1} {y1 + bh / 2} L{x2} {y2 - bh / 2}'
        o.append(f'<path d="{d}" stroke="{c}" stroke-width="{wd}" fill="none"/>')
    for i, label, _r, _c, kind in nodes:
        x, y = pos[i]
        oc = outlines.get(i)                              # COMM/DIFF 테두리(있으면 우선)
        stroke = ocol[oc] if oc else sk[kind]
        sw = 3 if oc else (1.9 if kind == "var" else 1.5)
        o.append(f'<rect x="{x - bw / 2}" y="{y - bh / 2}" width="{bw}" height="{bh}" rx="7" '
                 f'fill="{fl[kind]}" stroke="{stroke}" stroke-width="{sw}"/>')
        o.append(f'<text x="{x}" y="{y + 1}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="12.5" fill="#1a1a1a">{html.escape(str(label))}</text>')
    o.append("</svg>")
    return "".join(o)


def solution_grid(lines, compare=None):
    """완전 실행형 코드(라인 리스트 또는 문자열) → 정돈 데이터플로우 SVG. task.solution·pair.program
    (display_source) 둘 다 같은 골격이라 공통 입력. 파싱 실패/빈 코드면 빈 문자열.
    compare(선택) = _compare_asts 결과 — set_grid_size/color·coloring target/color 값노드에
    COMM(녹색)/DIFF(빨강) 테두리(anti-unification 겹침의 solid 레이어용, 사용자 2026-07-20)."""
    try:
        defs, setg, colorings = _grid_classify(lines)
        if not (setg or colorings):
            return ""
        nodes, edges, outlines = _grid_layout(defs, setg, colorings, compare)
        return _grid_render(nodes, edges, outlines)
    except Exception:                                     # noqa: BLE001 — 표시용, 렌더 실패가 리포트를 죽이지 않게
        return ""
