import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPanel(unittest.TestCase):
    def test_render_transform_panel(self):
        from debugger.build import render_transform_panel
        wm = [("s1", "required-effect", "reflect/rotate/translate"),
              ("s1", "candidates", "rot90,hmirror,move"),
              ("s1", "hypothesis", "s1.T1"),
              ("s1.T1", "rule", "rot90"), ("s1.T1", "src", "param-free"),
              ("s1.T1", "verdict", "survive"),
              ("root", "transform-survivor", "rot90 []")]
        html = render_transform_panel(wm)
        self.assertIn("rot90", html)
        self.assertIn("survive", html)
        self.assertIn("reflect/rotate/translate", html)
