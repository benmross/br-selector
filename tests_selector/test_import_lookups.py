"""t15: import-time lookups by key, and definition header edits."""
import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("selector_t15", ROOT / "selector.py")
sel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sel)

BASE = '''class Tokenizer:
    HINT_START = "/*+"
    KEYWORDS = {
        HINT_START: 1,
        "SORT BY": 2,
        "QUALIFY": 3,
    }
'''
SUB = '''class Duck(Tokenizer):
    KEYWORDS = {**Tokenizer.KEYWORDS}
    KEYWORDS.pop("/*+")
    KEYWORDS.pop("QUALIFY", None)

def later(k):
    return KEYWORDS.pop("SORT BY")
'''


def scopes_for(rel, text):
    return sel.Scopes(ast.parse(text))


def dropped(after):
    return sel.removed_dict_keys(ast.parse(BASE), ast.parse(after))


def test_removed_key_resolved_through_class_constant_is_popped_at_import():
    gone = dropped(BASE.replace("        HINT_START: 1,\n", ""))
    assert gone == {"KEYWORDS": {"'/*+'"}}
    assert sel.popped_at_import({"sub.py": SUB}, gone, scopes_for) == ("KEYWORDS", "sub.py")


def test_pop_with_default_or_at_runtime_does_not_count():
    assert sel.popped_at_import({"sub.py": SUB}, dropped(BASE.replace('"QUALIFY"', '"QUALIFY2"')), scopes_for) is None
    assert sel.popped_at_import({"sub.py": SUB}, dropped(BASE.replace('"SORT BY"', '"SORT_BY"')), scopes_for) is None


def test_value_edit_drops_no_key():
    assert dropped(BASE.replace("3,", "4,")) == {}


def test_lookup_at_import_sees_changed_pop_literal_only():
    tree = ast.parse(SUB)
    stmts = {s[3].lineno: s[3] for s in sel.Scopes(tree).stmts}
    assert sel.lookup_at_import(stmts[3], 3, [3])
    assert not sel.lookup_at_import(stmts[2], 2, [2])
    annotated = ast.parse("class A:\n    X: t.ClassVar[dict] = {\n        'a': 1,\n    }\n")
    node = annotated.body[0].body[0]
    assert not sel.lookup_at_import(node, 2, [2])


class _FP:
    def __init__(self, before, after):
        import difflib
        text = "diff --git a/m.py b/m.py\n" + "".join(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True), "a/m.py", "b/m.py"))
        fp = sel.parse_patch(text)[0]
        self.hunks, self.ranges = fp.hunks, fp.ranges


def test_import_time_regex_that_no_longer_compiles():
    before = 'import re\nP = re.compile(r"a(b)?")\n'
    bad = before.replace('(b)?', '(b?')
    good = before.replace('(b)?', '(c)?')
    tree = ast.parse(before)
    node = tree.body[1]
    assert sel.bad_regex_at_import(node, 2, [2], ast.parse(bad), _FP(before, bad))
    assert not sel.bad_regex_at_import(node, 2, [2], ast.parse(good), _FP(before, good))
