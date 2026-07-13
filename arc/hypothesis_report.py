# -*- coding: utf-8 -*-
"""
hypothesis_report — hypothesize 의 **가설 생성·검증(generate-and-test)** 을 표로 보여준다.

GRID hypothesize 는 grid.size/grid.color 가설을 관계에서 고르되, brute-force 로 만든 수식 후보
(H1=H0*2, H1=H0-1, …)를 **생성 즉시 각 train PAIR 로 테스트**한다. 그 전 과정 —
어떤 후보가 나왔는지 / 각 pair 에서 뭐가 기대됐고 뭐가 나왔는지 / 통과했는지 — 를 모은다.

용량 안전: 전체 시도표는 WM 이 아니라 `ag.kg["hyp_trials"]`(순수 리스트)에 쌓인다(WM 엔 요약만).
여기서 그걸 읽어 **CSV(arc/hypothesis_trials.csv) + 동기화 HTML(arc/hypothesis_trials.html)** 로 낸다.

    python3 -m arc.hypothesis_report     # -> arc/hypothesis_trials.{csv,html}
"""
from __future__ import annotations

import csv
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_HTML = os.path.join(HERE, "hypothesis_trials.html")
OUT_CSV = os.path.join(HERE, "hypothesis_trials.csv")


def _collect():
    """17-세트를 돌려 각 task 의 hyp_trials(가설 시도 로그)를 모은다."""
    from arc.make_made_tasks import write_all
    write_all()
    from arc.focus_solver import _load_survey, SURVEY_AGI, setup_focus_agent
    from arc.fine_trace import _Tracer
    rows = []
    for tid, task in _load_survey(agi_ids=SURVEY_AGI):
        try:
            tr = _Tracer(task, tid, setup=setup_focus_agent)
            tr.run(max_cycles=6000)
            rows += tr.ag.kg.get("hyp_trials", [])
        except Exception as e:                              # noqa: BLE001
            rows.append({"task": tid, "level": "-", "target": "-", "kind": "ERROR",
                         "candidate": f"{type(e).__name__}: {e}", "verdict": "fail", "per_pair": None})
    return rows


def _pp_str(per_pair):
    """per_pair(list) → 사람용 축약. 각 pair: 입력크기 → 기대/실제 (✓/✗)."""
    if not per_pair:
        return ""
    out = []
    for p in per_pair:
        h, w = p["in"]
        mark = "✓" if p["ok"] else "✗"
        out.append(f"{h}×{w}→기대{p['expected']}/실제{p['got']}{mark}")
    return "  ·  ".join(out)


def build():
    rows = _collect()
    # ── CSV (평면 원자료) ─────────────────────────────────────────────
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["task", "level", "target", "kind", "candidate", "verdict", "per_pair"])
        for r in rows:
            w.writerow([r["task"], r["level"], r["target"], r["kind"], r["candidate"],
                        r["verdict"], json.dumps(r.get("per_pair"), ensure_ascii=False)])
    # ── HTML (task→target 그룹 표) ───────────────────────────────────
    by_task = {}
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)
    sections = []
    for tid in sorted(by_task):
        trs = by_task[tid]
        blocks = []
        for target in ("size", "color"):
            tr_rows = [r for r in trs if r["target"] == target]
            if not tr_rows:
                continue
            npass = sum(1 for r in tr_rows if r["verdict"] == "pass")
            body = []
            for r in tr_rows:
                cls = "pass" if r["verdict"] == "pass" else "fail"
                body.append(
                    f"<tr class={cls}><td>{html.escape(str(r['kind']))}</td>"
                    f"<td class=cand>{html.escape(str(r['candidate']))}</td>"
                    f"<td class=pp>{html.escape(_pp_str(r.get('per_pair')))}</td>"
                    f"<td class=v>{'PASS' if r['verdict'] == 'pass' else 'fail'}</td></tr>")
            blocks.append(
                f"<div class=block><h3>{target} <span class=dim>후보 {len(tr_rows)} · 통과 {npass}</span></h3>"
                f"<table><tr><th>kind</th><th>candidate</th><th>각 PAIR 테스트 (생성→즉시 검증)</th>"
                f"<th>판정</th></tr>{''.join(body)}</table></div>")
        if blocks:
            sections.append(f"<section><h2>{tid}</h2>{''.join(blocks)}</section>")
    doc = f"""<!doctype html><meta charset='utf-8'><title>ARBOR hypothesis trials</title>
<style>{CSS}</style>
<h1>ARBOR — hypothesize 가설 생성·검증 표 (generate-and-test)</h1>
<p class=lead>GRID hypothesize 가 grid.size/grid.color 를 맞히려 만든 <b>후보</b>와, 각 후보를 <b>train PAIR
로 즉시 테스트</b>한 결과. 초록=통과, 회색=기각. 전체 원자료는 <code>hypothesis_trials.csv</code>.
(수식 brute-force: H1=H0*2 같은 후보가 생성 즉시 각 pair 에서 기대치와 대조돼 살아남거나 버려진다.)</p>
{''.join(sections)}"""
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(doc)
    return OUT_HTML, OUT_CSV


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin-bottom:18px;max-width:960px}
section{border:1px solid #30363d;border-radius:9px;padding:12px 16px;margin:0 0 15px;background:#161b22}
h2{font-size:15px;margin:0 0 8px;color:#e6edf3} h3{font-size:13px;margin:10px 0 5px}
.dim{color:#8b949e;font-weight:normal;margin-left:6px}
.block{margin-bottom:8px}
table{border-collapse:collapse;width:100%;margin-bottom:6px}
th,td{border:1px solid #30363d;padding:3px 8px;text-align:left;vertical-align:top}
th{background:#1c2128;color:#adbac7;font-weight:normal}
tr.pass td{background:#132a17;color:#aff5b4} tr.pass .v{color:#3fb950;font-weight:bold}
tr.fail td{color:#6e7681} tr.fail .v{color:#6e7681}
.cand{color:#d2a8ff} .pp{font-size:12px} code{color:#79c0ff}
"""


if __name__ == "__main__":
    h, c = build()
    print("wrote", h, "and", c)
