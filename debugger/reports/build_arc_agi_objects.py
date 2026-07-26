"""Rebuild the embedded datasets in arc_agi_objects.html from PySOAR/data.

The report embeds several datasets as <script type="application/json" id="ds_*">
blocks, each a list of {id, p:[{i,o,io,oo,s}]} where io/oo are spelke object
decompositions ({c,b,x}). This script regenerates those blocks from the CURRENT
data on disk (so renamed/regenerated tasks + new folders like mov2 show up) and
updates the dataset dropdown, then writes the HTML back in place.

Object decomposition uses the exact same function the report was built with:
arbor.perception.spelke.spelke_arckg_objects (spelke 4-conn ∪ same-color 8-conn,
background included). Verified byte-identical against the old embedded ds_easy.

Run from anywhere: `python3 debugger/reports/build_arc_agi_objects.py`
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]        # PySOAR/
sys.path.insert(0, str(ROOT))
from arbor.perception.spelke import spelke_arckg_objects  # noqa: E402

DATA = ROOT / "data"
HTML = ROOT / "debugger" / "reports" / "arc_agi_objects.html"

# dataset key -> (source folder rel to data/, dropdown label, file code or None).
# order here = order of <script> blocks and dropdown options.
# `code`: the 4-char filename prefix. When given, tasks are ordered by the base26
# value of the id (code stripped, leading '0' padding ignored) so they sort
# naturally regardless of the padding scheme (handles both `move00aa` and the old
# `move000aa`). None -> plain string sort (ARC-AGI hex ids).
DATASETS = [
    ("agitrain", "ARC_AGI/training",           "arc-agi · train",   None),
    ("agieval",  "ARC_AGI/evaluation",         "arc-agi · eval",    None),
    ("easy",     "ARC_easy",                   "arc-easy",          "easy"),
    ("object",   "ARC_human/object_coloring",  "arc-human · object", "objc"),
    ("move",     "ARC_human/move",             "arc-human · move",  "move"),
    ("mov2",     "ARC_human/mov2",             "arc-human · mov2",  "mov2"),
    ("flip",     "ARC_human/flip",             "arc-human · flip",  "flip"),
    ("rotate",   "ARC_human/rotate",           "arc-human · rotate", "rota"),
]


def _base26(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 96)
    return n


def _sort_key(stem, code):
    """Natural order for `<code><0-padding><letters>` ids; string otherwise."""
    if code and stem.startswith(code):
        ident = stem[len(code):].lstrip("0")
        if ident and ident.isalpha():
            return (0, _base26(ident))
    return (1, stem)


def objs(grid):
    """Grid -> list of {c,b,x} spelke objects (background included)."""
    w = len(grid[0])
    out = []
    for o in spelke_arckg_objects(grid):
        pixels = o["obj"]                                  # frozenset((color,(r,c)))
        c = next(iter(pixels))[0]
        cells = sorted((r, cc) for (_col, (r, cc)) in pixels)
        rmin, cmin = o["pos"]
        cg = o["colorgrid"]
        b = [rmin, cmin, rmin + len(cg) - 1, cmin + len(cg[0]) - 1]
        x = [r * w + cc for (r, cc) in cells]
        out.append({"c": c, "b": b, "x": x})
    return out


def build_task(task_json, task_id):
    pairs = []
    for grp, tag in (("train", "train"), ("test", "test")):
        for pr in task_json.get(grp, []):
            gi, go = pr["input"], pr["output"]
            pairs.append({"i": gi, "o": go, "io": objs(gi), "oo": objs(go), "s": tag})
    return {"id": task_id, "p": pairs}


def build_dataset(folder, code):
    src = DATA / folder
    files = [p for p in src.glob("*.json") if p.stem != "MANIFEST"]
    files.sort(key=lambda p: _sort_key(p.stem, code))
    return [build_task(json.load(open(f)), f.stem) for f in files]


def main():
    html = HTML.read_text()

    built = {}
    for key, folder, _label, code in DATASETS:
        data = build_dataset(folder, code)
        built[key] = data
        print(f"  {key}: {len(data)} tasks  (first={data[0]['id']} last={data[-1]['id']})")

    # --- replace / insert each ds_* json block ---
    def block(key):
        payload = json.dumps(built[key], separators=(",", ":"))
        return f'<script type="application/json" id="ds_{key}">{payload}</script>'

    for key, _f, _l, _c in DATASETS:
        pat = re.compile(rf'<script type="application/json" id="ds_{key}">.*?</script>', re.S)
        if pat.search(html):
            html = pat.sub(lambda m: block(key), html, count=1)
        else:
            # new dataset (e.g. mov2): insert right after ds_move block
            anchor = re.compile(r'(<script type="application/json" id="ds_move">.*?</script>)', re.S)
            html = anchor.sub(lambda m: m.group(1) + block(key), html, count=1)

    # --- rebuild the dropdown options ---
    opts = "".join(
        f'<option value="{key}">{label} ({len(built[key])})</option>'
        for key, _f, label, _c in DATASETS
    )
    html = re.sub(r'(<select id="dssel">).*?(</select>)',
                  lambda m: m.group(1) + opts + m.group(2), html, count=1, flags=re.S)

    HTML.write_text(html)
    print(f"wrote {HTML} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
