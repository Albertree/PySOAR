import subprocess
import sys
import unittest


class TestEntrypoint(unittest.TestCase):
    def test_arbor_main_runs_single_task(self):
        """python -m arbor wires env + run_solve end-to-end (fast single-task path)."""
        out = subprocess.run([sys.executable, "-m", "arbor", "--tasks", "easy000a", "--dataset", "easy"],
                             capture_output=True, text=True)
        combined = out.stdout + out.stderr
        self.assertNotIn("Traceback", combined, combined)        # no import/runtime error
        self.assertIn("easy000a: SOLVED", out.stdout, combined)  # entrypoint ran the solve to completion
        self.assertEqual(out.returncode, 0, combined)            # SOLVED → exit 0


if __name__ == "__main__":
    unittest.main()
