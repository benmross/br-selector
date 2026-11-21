"""Focused selector safety regressions; run with python -m unittest discover -s tools."""
import ast
import sys
import tempfile
from unittest.mock import patch as mock_patch
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selector import Selector, same_ast, build_test_importers, FilePatch, build_shared_setups, parse_patch


def file_patch(path, before, after):
    """A real parsed FilePatch, so hunk ranges match the hardened apply()."""
    import difflib
    body = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                       "a/" + path, "b/" + path))
    return parse_patch(f"diff --git a/{path} b/{path}\n" + body)[0]


class SelectorSafetyTests(unittest.TestCase):
    def test_removed_decorator_is_a_semantic_change(self):
        for before, after, line in (
            ("@staticmethod\ndef f():\n    pass\n", "def f():\n    pass\n", 1),
            ("@a\n@b\nclass C:\n    pass\n", "@a\nclass C:\n    pass\n", 2),
            ("class C:\n    @classmethod\n    def f(cls):\n        pass\n",
             "class C:\n    def f(cls):\n        pass\n", 2),
        ):
            with self.subTest(before=before):
                self.assertFalse(same_ast(ast.parse(before).body, ast.parse(after).body, line, line))

    def test_comment_in_sql_literal_is_observable(self):
        self.assertFalse(same_ast(ast.parse('sql = "SELECT 1"').body,
                                  ast.parse('sql = "SELECT /* comment */ 1"').body, 1, 1))

    def test_python_comments_and_trailing_space_are_unchanged(self):
        self.assertTrue(same_ast(ast.parse("x = 1\n").body,
                                 ast.parse("# comment\nx = 1  \n").body, 1, 2))

    def test_protocol_attributes_include_collection_only_users(self):
        tests = {0: ("test_class", "tests/test_demo.py", 1),
                 1: ("test_function", "tests/test_demo.py", 1),
                 2: ("collection_only", "tests/test_other.py", 1)}
        mapping = {"sets": [[0], [1]], "files": {"sqlglot/demo.py": {"10": 1}},
                   "classes": {"sqlglot.demo:Thing": 0}, "fixtures": {}}
        sel = Selector(tests, mapping)
        def no_explicit_reader_filter(names):
            raise AssertionError("protocol attributes have implicit readers")
        sel.readers = no_explicit_reader_filter
        node = ast.parse('__slots__ = ("value",)').body[0]
        self.assertEqual(sel.module_level("sqlglot/demo.py", "sqlglot.demo", "Thing", [], 1, node), {0, 1, 2})

    def test_shared_helpers_follow_transitive_and_relative_imports(self):
        sources = {
            "tests/__init__.py": "",
            "tests/support/__init__.py": "",
            "tests/support/shared.py": "VALUE = 1",
            "tests/support/middle.py": "from .shared import VALUE",
            "tests/test_one.py": "from tests.support import middle",
            "tests/test_two.py": "pass",
        }
        tests = {0: ("one", "tests/test_one.py", 1), 1: ("two", "tests/test_two.py", 1)}
        sel = Selector(tests, {"sets": [], "files": {}, "classes": {}, "fixtures": {}})
        sel.index = {"@test_importers": build_test_importers(sources)}
        self.assertEqual(sel.test_importers("tests/support/shared.py"), {0})
        self.assertEqual(sel.test_importers("tests/support/__init__.py"), {0})
        self.assertEqual(sel.test_importers("tests/__init__.py"), {0, 1})
        self.assertEqual(sel.broad("tests/support/shared.py"), {0})
        self.assertEqual(sel.importers("tests/support/shared.py"), {0})

    def test_new_test_configuration_and_collected_modules_are_conservative(self):
        tests = {0: ("one", "tests/test_one.py", 1), 1: ("two", "tests/test_two.py", 1)}
        sel = Selector(tests, {"sets": [], "files": {}, "classes": {}, "fixtures": {}})
        for path in ("tests/conftest.py", "tests/test_new.py"):
            patch = FilePatch()
            patch.new = path
            patch.hunks = [(0, ["+VALUE = 1"])]
            self.assertEqual(sel.for_file(patch, []), {0, 1})

    def test_removed_name_read_at_import_selects_everything(self):
        # Replaces t3's literal-edit import probe: patched code is never run.
        # Deleting an enum member read inside another class body breaks import.
        tests = {0: ("one", "tests/test_one.py", 1), 1: ("two", "tests/test_two.py", 1)}
        mapping = {"sets": [[0]], "files": {"sqlglot/enum.py": {"3": 0}},
                   "classes": {"sqlglot.enum:Kind": 0}, "fixtures": {},
                   "import_lines": {"sqlglot/user.py": [3]}}
        sel = Selector(tests, mapping)
        before = "class Kind:\n    A = 1\n    B = 2\n"
        sel.index = {"B": {"u": False, "c": [["sqlglot/user.py", 3, 3]], "t": [], "tf": []}}
        fp = file_patch("sqlglot/enum.py", before, "class Kind:\n    A = 1\n")
        with tempfile.TemporaryDirectory() as root:
            source = Path(root, "sqlglot/enum.py")
            source.parent.mkdir()
            source.write_text(before)
            with mock_patch("selector.SRC", root):
                self.assertEqual(sel.for_python(fp, fp.new, []), {0, 1})

    def test_shared_setup_phase_expands_class_without_expanding_run_phase(self):
        tests = {0: ("tests/test_a.py::TestA::test_first", "tests/test_a.py", 1),
                 1: ("tests/test_a.py::TestA::test_later", "tests/test_a.py", 1),
                 2: ("tests/test_a.py::TestB::test_other", "tests/test_a.py", 1)}
        mapping = {"sets": [[0]], "files": {"tests/test_a.py": {"10": 0},
                   "sqlglot/helper.py": {"1": 0, "2": 0}},
                   "setup_files": {"sqlglot/helper.py": {"1": 0}, "tests/test_a.py": {"10": 0}},
                   "classes": {}, "fixtures": {}}
        sel = Selector(tests, mapping)
        sel.index = {"@shared_setup": [["tests/test_a.py", 10, 12, "tests/test_a.py::TestA::"]]}
        # The first test's ordinary body does not represent shared state.
        self.assertEqual(sel.expand_shared_setup(sel.cov("sqlglot/helper.py", [2]), []), {0})
        # The same test's setup-phase call affects all members of its class.
        self.assertEqual(sel.expand_shared_setup(sel.cov("sqlglot/helper.py", [1]), []), {0, 1})
        sel.pending_shared.clear()
        self.assertEqual(sel.expand_shared_setup(sel.cov("sqlglot/helper.py", [2]), []), {0})

    def test_shared_setup_specs_come_from_source_scopes(self):
        specs = build_shared_setups({"tests/test_a.py":
            "class TestA:\n    @classmethod\n    def setUpClass(cls):\n        cls.state = 1\n"})
        self.assertEqual(specs, [["tests/test_a.py", 4, 4, "tests/test_a.py::TestA::"]])

    def test_imported_shared_fixture_expands_its_importing_test_files(self):
        tests = {0: ("tests/test_a.py::test_first", "tests/test_a.py", 1),
                 1: ("tests/test_a.py::test_later", "tests/test_a.py", 1)}
        mapping = {"sets": [[0]], "files": {"tests/helpers.py": {"10": 0}},
                   "setup_files": {"tests/helpers.py": {"10": 0}}, "classes": {}, "fixtures": {}}
        sel = Selector(tests, mapping)
        sel.index = {"@shared_setup": [["tests/helpers.py", 10, 10, "@imports:tests/helpers.py"]],
                     "@test_importers": {"tests.helpers": ["tests/test_a.py"]}}
        self.assertEqual(sel.expand_shared_setup(sel.cov("tests/helpers.py", [10]), []), {0, 1})

    def test_new_import_time_call_selects_everything_without_running_it(self):
        # t3 probed the overlay of both files; main's rule never executes the
        # patch and treats a new import-time call as a possible import failure.
        tests = {0: ("one", "tests/test_one.py", 1), 1: ("two", "tests/test_two.py", 1)}
        mapping = {"sets": [[0]], "files": {"sqlglot/helper.py": {"2": 0}},
                   "classes": {}, "fixtures": {}, "import_lines": {"sqlglot/bootstrap.py": [1, 2]}}
        sel = Selector(tests, mapping)
        sel.module_level = lambda *args, **kwargs: {0}
        before = "from .helper import cold\nVALUE = 1\n"
        boot = file_patch("sqlglot/bootstrap.py", before, "from .helper import cold\nVALUE = cold()\n")
        with tempfile.TemporaryDirectory() as root:
            package = Path(root, "sqlglot")
            package.mkdir()
            (package / "bootstrap.py").write_text(before)
            with mock_patch("selector.SRC", root), mock_patch("selector.log"):
                self.assertEqual(sel.for_python(boot, boot.new, []), {0, 1})

    def test_functions_executed_at_import_select_everything(self):
        tests = {0: ("one", "tests/test_one.py", 1), 1: ("two", "tests/test_two.py", 1)}
        mapping = {"sets": [[0]], "files": {"sqlglot/helper.py": {"2": 0}},
                   "classes": {}, "fixtures": {}, "import_lines": {"sqlglot/helper.py": [2]}}
        sel = Selector(tests, mapping)
        before = "def f():\n    return 1\n"
        fp = file_patch("sqlglot/helper.py", before, "def f():\n    return missing_name\n")
        with tempfile.TemporaryDirectory() as root:
            source = Path(root, "sqlglot/helper.py")
            source.parent.mkdir()
            source.write_text(before)
            with mock_patch("selector.SRC", root):
                self.assertEqual(sel.for_python(fp, fp.new, []), {0, 1})

    def test_module_move_is_not_skipped_as_identical_ast(self):
        tests = {0: ("one", "tests/test_one.py", 1)}
        sel = Selector(tests, {"sets": [], "files": {}, "classes": {}, "fixtures": {}})
        fp = FilePatch()
        fp.old, fp.new = "sqlglot/old.py", "sqlglot/new.py"
        self.assertEqual(sel.for_file(fp, []), {0})

    def test_renamed_definition_keeps_importers_without_runtime_coverage(self):
        tests = {0: ("one", "tests/test_one.py", 1)}
        sel = Selector(tests, {"sets": [], "files": {}, "classes": {}, "fixtures": {}})
        fp = file_patch("sqlglot/helper.py", "def exported():\n    return 1\n",
                        "def renamed():\n    return 1\n")
        with tempfile.TemporaryDirectory() as root:
            source = Path(root, "sqlglot/helper.py")
            source.parent.mkdir()
            source.write_text("def exported():\n    return 1\n")
            with mock_patch("selector.SRC", root):
                self.assertEqual(sel.for_python(fp, fp.new, []), {0})

    def test_data_move_retains_old_readers_and_new_directory_watchers(self):
        tests = {0: ("one", "tests/test_one.py", 1), 1: ("two", "tests/test_two.py", 1)}
        sel = Selector(tests, {"sets": [[0], [1]], "files": {}, "classes": {},
                               "fixtures": {"tests/fixtures/a.sql": 0, "tests/other/": 1}})
        fp = FilePatch()
        fp.old, fp.new = "tests/fixtures/a.sql", "tests/other/b.sql"
        self.assertEqual(sel.for_file(fp, []), {0, 1})


if __name__ == "__main__":
    unittest.main()
