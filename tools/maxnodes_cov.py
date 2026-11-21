"""Cold coverage of tests/test_parser.py::TestParser::test_max_nodes: every
sqlglot line it runs after import, in a fresh process. Prints JSON {file: [lines]}."""
import json
import os
import sys
import unittest

src = os.path.abspath(sys.argv[1])
os.chdir(src)
sys.path.insert(0, src)
import coverage  # noqa: E402

cov = coverage.Coverage(data_file=None, source=[os.path.join(src, "sqlglot")])
cov.start()
cov.switch_context("import")
import tests.test_parser as tp  # noqa: E402

cov.switch_context("E")
r = unittest.TestResult()
tp.TestParser("test_max_nodes").run(r)
cov.stop()
data = cov.get_data()
data.set_query_contexts(["E"])
out = {os.path.relpath(os.path.realpath(f), os.path.realpath(src)): sorted(data.lines(f) or [])
       for f in data.measured_files() if data.lines(f)}
json.dump({"ok": r.wasSuccessful(), "lines": out}, sys.stdout)
