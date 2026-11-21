"""t59 (after t62k09): a changed line evaluated at import whose call shape,
subscripts or attribute chains change may fail the import: importers."""
import ast
import difflib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("selector_t59s", ROOT / "selector.py")
sel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sel)

OLD = '''import re

def _build_to_date(args):
    return args

def rename_func(name):
    return lambda self, e: name

class HiveParser:
    FUNCTIONS = {
        "TO_DATE": _build_to_date,
        "FIRST": rename_func("FIRST"),
        "ALIAS": OTHER["TRY_CAST"],
        "LAMBDA": lambda args: _build_to_date(args),
        "KIND": exp.Day,
    }

    @staticmethod
    def method(self):
        return rename_func("x")(1, 2)
'''


def change(old, new):
    text = OLD.replace(old, new)
    assert text != OLD
    diff = "diff --git a/m.py b/m.py\n" + "".join(difflib.unified_diff(
        [l + "\n" for l in OLD.split("\n")], [l + "\n" for l in text.split("\n")], "a/m.py", "b/m.py"))
    fp = sel.parse_patch(diff)[0]
    return sel.import_shape_change(ast.parse(OLD), ast.parse(text), fp, OLD)


def test_call_added_with_wrong_arity():  # t62k09
    assert "call shape" in change('"TO_DATE": _build_to_date,', '"TO_DATE": _build_to_date([]),')


def test_call_removed_leaves_bare_builder():
    assert "call shape" in change('"FIRST": rename_func("FIRST"),', '"FIRST": rename_func,')


def test_arity_and_keywords():
    assert "call shape" in change('rename_func("FIRST")', 'rename_func("FIRST", "X")')
    assert "call shape" in change('rename_func("FIRST")', 'rename_func(name="FIRST")')


def test_subscript_key_changed():
    assert "subscript" in change('OTHER["TRY_CAST"]', 'OTHER["TRY_CASTS"]')


def test_attribute_never_spelled():
    assert "attribute" in change('exp.Day,', 'exp.Dayy,')


def test_changed_literal_in_same_call_shape_is_left_to_other_rules():
    assert change('rename_func("FIRST")', 'rename_func("FIRSTX")') is None
    assert change('"FIRST": rename_func', '"FIRST2": rename_func') is None


def test_function_and_lambda_bodies_run_later():
    assert change('lambda args: _build_to_date(args)', 'lambda args: _build_to_date(args, 1)') is None
    assert change('return rename_func("x")(1, 2)', 'return rename_func("x")(1)') is None


def test_whole_entry_removed_with_its_call():
    assert change('        "FIRST": rename_func("FIRST"),\n', '') is None
    assert change('        "ALIAS": OTHER["TRY_CAST"],\n', '') is None


def test_any_decorator_change():
    assert "decorator" in change('@staticmethod', '@staticmethod()') or change('@staticmethod', '@staticmethod()')
    assert "decorator" in change('@staticmethod', '@classmethod')
