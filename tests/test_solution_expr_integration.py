import glob, json, unittest
from debugger.solve_cache import run_solve


def _load(tid):
    return json.load(open(glob.glob(f"data/**/move/{tid}.json", recursive=True)[0]))


class TestSolutionExprIntegration(unittest.TestCase):
    def test_move000a_stepC_is_antiunify_skeleton(self):
        # C = anti-unify 골격(object 객체화 병합): select(input,object,…) + DIFF=?p 변수 (사용자 2026-07-24 —
        # 옛 resolved 이동식 렌더 제거, resolve 사다리는 후속). cellset 은 어디에도 없음.
        from debugger.reports import program_report as pr
        html = pr.task_section("move000a", _load("move000a"))
        self.assertIn("select(input, object", html)
        self.assertIn("anti-unify 결과", html)          # Step C 라벨
        self.assertIn("?p", html)                        # DIFF slot 변수
        self.assertNotIn("cellset=?c.cells", html)

    def test_stepC_skeleton_coordinate_select(self):
        # C 골격은 object.coordinate 로 객체 지목(select), DIFF 좌표는 ?p 변수 (사용자 2026-07-24)
        from debugger.reports import program_report as pr
        html = pr.task_section("move000o", _load("move000o"))
        self.assertIn("coordinate ==", html)             # object 선택 조건
        self.assertIn("select(input, object", html)

    def test_objectify_stages_present_for_move(self):
        # 구형 compress 옆박스 제거(사용자 2026-07-24) → 픽셀객체화·object 객체화 단계로 대체
        from debugger.reports import program_report as pr
        html = pr.task_section("move000ah", _load("move000ah"))
        self.assertIn("픽셀객체화", html)                 # Step A.5
        self.assertIn("object 객체화", html)              # Step A.6
        self.assertNotIn("COMPRESS · 픽셀", html)         # 구형 compress 옆박스 사라짐
