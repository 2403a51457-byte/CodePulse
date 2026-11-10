import tempfile
import unittest
from pathlib import Path
from modules.code_analyzer import analyze_repository
from modules.health_score import calculate_health_score

class AnalyzerTests(unittest.TestCase):
    def test_detects_security_patterns_and_defected_file_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sample.py").write_text("import subprocess\npassword = 'super-secret-value'\neval(user_input)\nsubprocess.run('echo hi', shell=True)\n", encoding="utf-8")
            result = analyze_repository(root)
            categories = {item["category"] for item in result["findings"]}
            self.assertIn("Possible hardcoded secret", categories)
            self.assertIn("Dynamic code execution", categories)
            self.assertIn("Shell injection risk", categories)
            self.assertEqual(result["files_scanned"], 1)
            self.assertEqual(result["defected_files"], 1)

    def test_skips_generated_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "good.py").write_text("print('ok')", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("eval('x')", encoding="utf-8")
            result = analyze_repository(root)
            self.assertEqual(result["files_scanned"], 1)
            self.assertEqual(result["findings"], [])

    def test_no_python_files_do_not_receive_perfect_score(self):
        self.assertEqual(calculate_health_score([], 0), 0)

if __name__ == "__main__":
    unittest.main()
