# -*- coding: utf-8 -*-
"""TASK.solution 표현식 렌더 — 솔버 선택자/resolved 를 함수·symbol 조합 표현식으로 재표기.
설계: docs/superpowers/specs/2026-07-20-solution-expression-viz-design.md. 시각화-먼저(솔버 불변).
금지: count·output_grid symbol (P5, input_grid 만)."""
from __future__ import annotations
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
