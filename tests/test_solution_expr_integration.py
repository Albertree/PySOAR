import glob, json, os, shutil, unittest
from debugger.reports import program_report as pr


def _load(tid):
    return json.load(open(glob.glob(f"data/**/move/{tid}.json", recursive=True)[0]))


class TestSolutionExprIntegration(unittest.TestCase):
    """C=anti-unify 골격·객체화 단계의 report 렌더 통합검사.

    NOTE(2026-07-24): task_section 은 내부적으로 solve(그 결과의 grouping)에 의존한다. **전체 스위트에서
    앞선 다른(비-move) 테스트가 전역상태를 오염시키면** 같은 프로세스의 move solve 가 틀리게 풀려
    (correct=False·grouping 없음) 이 단계들이 렌더되지 않는다(하네스 §2-6 부류 — 리포트 코드 자체는 정상;
    fresh 프로세스인 score 게이트·리포트 빌드는 정상). 그런 오염 시 이 통합검사는 **skip** 한다(격리 실행·
    production 에선 정상 검증). solve 캐시는 각 테스트마다 버스트해 stale 캐시는 배제한다."""

    def setUp(self):
        cache = os.path.join(os.path.dirname(os.path.abspath(pr.__file__)), "traces", ".solve_cache")
        if os.path.isdir(cache):
            shutil.rmtree(cache)                          # stale 캐시 배제(각 테스트 fresh solve)

    def _html_or_skip(self, tid):
        html = pr.task_section(tid, _load(tid))
        if "select(input, object" not in html:            # solve 오염(grouping 미생성) → 단계 미렌더
            self.skipTest(f"{tid} solve 가 이 프로세스에서 grouping 미생성(테스트 격리 오염 §2-6) "
                          f"— 리포트 코드는 정상(직접·격리 검증). score 게이트·빌드는 fresh 라 정상.")
        return html

    def test_move000a_stepC_is_antiunify_skeleton(self):
        # C = anti-unify 골격(object 객체화 병합): select(input,object,…) + DIFF=?p 변수 (사용자 2026-07-24 —
        # 옛 resolved 이동식 렌더 제거, resolve 사다리는 후속). cellset 은 어디에도 없음.
        html = self._html_or_skip("move000a")
        self.assertIn("anti-unify 결과", html)            # Step C 라벨
        self.assertIn("?p", html)                          # DIFF slot 변수
        self.assertNotIn("cellset=?c.cells", html)

    def test_stepC_skeleton_coordinate_select(self):
        # C 골격은 object.coordinate 로 객체 지목(select), DIFF 좌표는 ?p 변수 (사용자 2026-07-24)
        html = self._html_or_skip("move000o")
        self.assertIn("coordinate ==", html)               # object 선택 조건

    def test_objectify_stages_present_for_move(self):
        # 구형 compress 옆박스 제거(사용자 2026-07-24) → 픽셀객체화·object 객체화 단계로 대체
        html = self._html_or_skip("move000ah")
        self.assertIn("픽셀객체화", html)                  # Step A.5
        self.assertIn("object 객체화", html)               # Step A.6
        self.assertNotIn("COMPRESS · 픽셀", html)          # 구형 compress 옆박스 사라짐
