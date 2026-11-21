import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import label_trace
from label_reports import failure_numbers, report_failures, summary_failures


class LabelReportTests(unittest.TestCase):
    def test_space_and_multiline_subtests_count_when_parent_passes(self):
        tests = {"tests/test_x.py::TestX::test_sql": 7}
        text = '''PASSED tests/test_x.py::TestX::test_sql
================ short test summary info ================
SUBFAILED[SELECT x[0] FROM t WHERE x = 1] tests/test_x.py::TestX::test_sql
SUBFAILED[SELECT x
FROM t] tests/test_x.py::TestX::test_sql
SUBFAILED(sql='SELECT x FROM t') tests/test_x.py::TestX::test_sql
'''
        self.assertEqual(summary_failures(text, tests), {7})

    def test_collection_error_marks_whole_class(self):
        tests = {"tests/test_x.py::TestX::test_one": 0,
                 "tests/test_x.py::TestX::test_two": 1,
                 "tests/test_x.py::TestOther::test_one": 2}
        self.assertEqual(failure_numbers(["tests/test_x.py::TestX"], tests), {0, 1})
        self.assertEqual(failure_numbers(["tests/test_x.py"], tests), {0, 1, 2})

    def test_structured_report_keeps_subtest_failure_despite_passed_parent(self):
        tid = "tests/test_x.py::TestX::test_sql"
        with tempfile.TemporaryDirectory() as directory:
            prefix = str(Path(directory, "run"))
            with patch.dict(os.environ, {"LABEL_REPORT_PREFIX": prefix}, clear=True):
                label_trace._failed.clear()
                label_trace.pytest_configure(SimpleNamespace())
                label_trace.pytest_runtest_logreport(SimpleNamespace(nodeid=tid, failed=True))
                label_trace.pytest_runtest_logreport(SimpleNamespace(nodeid=tid, failed=False))
                label_trace.pytest_sessionfinish(None, 1)
                self.assertEqual(report_failures(prefix, {tid: 7}), {7})
        label_trace._failed.clear()


if __name__ == "__main__":
    unittest.main()
