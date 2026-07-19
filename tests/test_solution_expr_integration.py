import glob, json, unittest
from debugger.solve_cache import run_solve


def _load(tid):
    return json.load(open(glob.glob(f"data/**/move/{tid}.json", recursive=True)[0]))


class TestSolutionExprIntegration(unittest.TestCase):
    def test_move000a_full_render_has_expressions(self):
        from debugger.reports import program_report as pr
        html = pr.task_section("move000a", _load("move000a"))
        self.assertIn("select(object", html)
        self.assertIn("coordinate(obj0)", html)
        self.assertNotIn("cellset=?c.cells", html)      # raw cellset 제거

    def test_bounded_task_uses_color_not_zero(self):
        from debugger.reports import program_report as pr
        html = pr.task_section("move000o", _load("move000o"))
        self.assertIn("color(o) != 0", html)
        self.assertIn("bottom_right(obj0)", html)       # BR 앵커

    def test_compress_stages_present_for_move(self):
        from debugger.reports import program_report as pr
        html = pr.task_section("move000ah", _load("move000ah"))
        self.assertIn("compress", html.lower())          # compress 단계 라벨 등장
        self.assertIn("픽셀", html)                       # 픽셀 단계 라벨
