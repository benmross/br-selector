import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class WidenMapTests(unittest.TestCase):
    def run_widen(self, base, tests, children, status):
        d = tempfile.mkdtemp()
        bp, tp, op, rp = (os.path.join(d, n) for n in ("base.json.gz", "tests.json", "out.json.gz", "r.json"))
        fork = os.path.join(d, "fork")
        os.makedirs(fork)
        with gzip.open(bp, "wt") as f:
            json.dump(base, f)
        json.dump({"tests": tests}, open(tp, "w"))
        for i, c in enumerate(children):
            with gzip.open(os.path.join(fork, f"{i}.json.gz"), "wt") as f:
                json.dump(c, f)
        json.dump(status, open(os.path.join(fork, "status.0of1.json"), "w"))
        subprocess.run([sys.executable, os.path.join(HERE, "widen_map.py"), bp, tp, op, "--fork", fork,
                        "--report", rp], check=True, capture_output=True)
        return json.load(gzip.open(op, "rt")), json.load(open(rp))

    def test_cached_builder_credited_to_every_test_that_runs_it_alone(self):
        tests = [{"id": f"tests/test_g.py::T::test_{i}", "number": i, "seconds": 1} for i in range(3)]
        base = {"sets": [[0], [0, 1, 2]], "files": {"sqlglot/g.py": {"10": 0, "20": 1}},
                "setup_files": {}, "import_lines": {"sqlglot/g.py": [1]},
                "classes": {"sqlglot.g:G": 0}, "fixtures": {}, "tests": {}}
        children = [{"nodeid": t["id"], "outcome": "passed",
                     "lines": {"sqlglot/g.py": [10, 20]},
                     "classes": {t["id"]: ["sqlglot.g:G"]}, "fixtures": {}} for t in tests]
        status = {t["id"]: 0 for t in tests}
        out, rep = self.run_widen(base, tests, children, status)
        sets = out["sets"]
        self.assertEqual(sorted(sets[out["files"]["sqlglot/g.py"]["10"]]), [0, 1, 2])
        self.assertEqual(sorted(sets[out["files"]["sqlglot/g.py"]["20"]]), [0, 1, 2])
        self.assertEqual(sorted(sets[out["classes"]["sqlglot.g:G"]]), [0, 1, 2])
        self.assertEqual(out["import_lines"], {"sqlglot/g.py": [1]})
        self.assertEqual(rep["summary"]["fork"]["missing_output"], [])

    def test_missing_or_crashed_child_is_reported(self):
        tests = [{"id": "tests/test_g.py::T::test_0", "number": 0, "seconds": 1},
                 {"id": "tests/test_g.py::T::test_1", "number": 1, "seconds": 1}]
        base = {"sets": [[0]], "files": {"sqlglot/g.py": {"10": 0}}, "setup_files": {},
                "import_lines": {}, "classes": {}, "fixtures": {}, "tests": {}}
        children = [{"nodeid": tests[0]["id"], "outcome": "passed", "lines": {}, "classes": {}, "fixtures": {}}]
        out, rep = self.run_widen(base, tests, children, {tests[0]["id"]: 0, tests[1]["id"]: 3})
        self.assertEqual(rep["summary"]["fork"]["missing_output"], [tests[1]["id"]])
        self.assertEqual(rep["summary"]["fork"]["nonzero_exit"], {tests[1]["id"]: 3})
        # never narrower than the base map
        self.assertEqual(out["sets"][out["files"]["sqlglot/g.py"]["10"]], [0])


if __name__ == "__main__":
    unittest.main()
