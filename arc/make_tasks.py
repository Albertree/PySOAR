"""
make_tasks -- generate three multi-object ARC tasks that each require `select`
with a different basis. The transformation is pure selection: the output keeps
ONLY the selected object (at its place); everything else (incl. any marker) is
removed. So solving = correctly identifying the selection criterion.

  select_color    : fixed attribute   -- keep the object with color == 2
  select_largest  : generalized attr  -- keep the object of maximum area
                    (the size VALUE differs across pairs -> not "size == k")
  select_relation : relation          -- keep the object sharing a row with the
                    color-1 marker (selected object's own attributes vary)

Saved to arc/data/multi/*.json (real ARC format).
"""

import json
import os

H = W = 6


def grid(cells):
    """cells: list of (r, c, color). Returns a 6x6 grid."""
    g = [[0] * W for _ in range(H)]
    for (r, c, v) in cells:
        g[r][c] = v
    return g


def block(r0, c0, h, w, color):
    return [(r0 + dr, c0 + dc, color) for dr in range(h) for dc in range(w)]


def task_select_color():
    """keep the color-2 object; others (distinct colors) removed."""
    train = [
        {"input": grid([(1, 1, 2), (2, 4, 3), (4, 2, 5)]), "output": grid([(1, 1, 2)])},
        {"input": grid([(0, 3, 2), (3, 1, 7), (5, 5, 8)]), "output": grid([(0, 3, 2)])},
    ]
    test = [{"input": grid([(2, 2, 4), (4, 4, 2), (1, 5, 6)]), "output": grid([(4, 4, 2)])}]
    return {"train": train, "test": test}


def task_select_largest():
    """keep the largest-area object; largest's size differs across pairs."""
    train = [
        {"input": grid(block(0, 0, 1, 1, 3) + block(2, 2, 1, 2, 5) + block(4, 3, 2, 2, 8)),
         "output": grid(block(4, 3, 2, 2, 8))},                  # largest area = 4
        {"input": grid(block(0, 4, 1, 1, 6) + block(3, 0, 2, 3, 7) + block(0, 1, 1, 2, 2)),
         "output": grid(block(3, 0, 2, 3, 7))},                  # largest area = 6
    ]
    test = [
        {"input": grid(block(0, 0, 1, 1, 4) + block(1, 3, 2, 2, 9) + block(4, 1, 1, 1, 5)),
         "output": grid(block(1, 3, 2, 2, 9))},                  # largest area = 4
    ]
    return {"train": train, "test": test}


def task_select_relation():
    """keep the object sharing a row with the color-1 marker (marker removed)."""
    train = [
        {"input": grid([(2, 0, 1), (2, 4, 3), (0, 3, 5)]), "output": grid([(2, 4, 3)])},
        {"input": grid([(5, 5, 1), (5, 1, 8), (1, 2, 6)]), "output": grid([(5, 1, 8)])},
    ]
    test = [{"input": grid([(4, 1, 1), (4, 5, 7), (1, 2, 9)]), "output": grid([(4, 5, 7)])}]
    return {"train": train, "test": test}


def task_select_move():
    """select the color-2 object AND move it to the corner (needs BOTH select
    and transform) -- neither solver alone can do this."""
    train = [
        {"input": grid([(1, 1, 2), (2, 4, 3), (4, 2, 5)]), "output": grid([(5, 5, 2)])},
        {"input": grid([(0, 3, 2), (3, 1, 7), (5, 5, 8)]), "output": grid([(5, 5, 2)])},
    ]
    test = [{"input": grid([(2, 2, 4), (4, 4, 2), (1, 5, 6)]), "output": grid([(5, 5, 2)])}]
    return {"train": train, "test": test}


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "multi")
    os.makedirs(out, exist_ok=True)
    tasks = {
        "select_color": task_select_color(),
        "select_largest": task_select_largest(),
        "select_relation": task_select_relation(),
        "select_move": task_select_move(),
    }
    for name, t in tasks.items():
        with open(os.path.join(out, f"{name}.json"), "w") as f:
            json.dump(t, f, indent=2)
        print(f"wrote {name}.json  (train={len(t['train'])}, test={len(t['test'])})")


if __name__ == "__main__":
    main()
