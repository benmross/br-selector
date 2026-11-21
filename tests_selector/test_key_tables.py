"""t59: class-table entry edits narrowed by per-test key probes (keys.json.gz).

The end-to-end cases need the pinned sqlglot (SQLGLOT_SRC), its index and the
committed map and keys; they skip elsewhere."""
import ast
import gzip
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("selector_t59", ROOT / "selector.py")
sel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sel)
SRC = Path(os.environ.get("SQLGLOT_SRC", ROOT / "work/sqlglot"))
INDEX = ROOT / "index.json.gz"
TESTS = Path(os.environ.get("BLAST_TESTS", ROOT / "sample/tests.json"))


def pinned():
    try:
        return json.load(gzip.open(INDEX)).get("@pinned_string_audit") and TESTS.exists()
    except OSError:
        return False


def run(tmp_path, rel, old, new):
    text = (SRC / rel).read_text()
    assert old in text and text.count(old) == 1
    lines = text.split("\n")
    i = next(n for n, l in enumerate(lines) if old in l)
    patch = (f"diff --git a/{rel} b/{rel}\n--- a/{rel}\n+++ b/{rel}\n@@ -{i + 1} +{i + 1} @@\n"
             f"-{lines[i]}\n+{lines[i].replace(old, new)}\n")
    d = tmp_path / "data"
    (d / "commits").mkdir(parents=True)
    (d / "commits" / "x.patch").write_text(patch)
    (d / "tests.json").write_text(TESTS.read_text())
    env = {**os.environ, "DATA_DIR": str(d), "SQLGLOT_SRC": str(SRC), "MAP_PATH": str(ROOT / "map.json.gz"),
           "INDEX_PATH": str(INDEX), "CMP_PATH": str(ROOT / "cmp.json.gz"), "KEYS_PATH": str(ROOT / "keys.json.gz"),
           "BLAST_WORKERS": "1"}
    r = subprocess.run([sys.executable, str(ROOT / "selector.py")], env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    row = json.loads(r.stdout.splitlines()[0])
    return {n for w in row["workers"] for n in w}, r.stderr


@pytest.mark.skipif(not pinned(), reason="needs the pinned sqlglot and its index")
def test_renamed_function_key_keeps_its_probers_only(tmp_path):
    # Hive COLLECT_SET renamed to ARRAY_AGG (t59k00): HiveParser, Spark2,
    # Spark and Databricks inherit it. Failing tests: probers of either key.
    chosen, why = run(tmp_path, "sqlglot/parsers/hive.py", '"COLLECT_SET": exp.ArrayUniqueAgg',
                      '"ARRAY_AGG": exp.ArrayUniqueAgg')
    assert "HiveParser.FUNCTIONS entries s:ARRAY_AGG,s:COLLECT_SET" in why
    assert 0 < len(chosen) < 60  # c/nostr kept the 307 Hive, Spark and Databricks users


@pytest.mark.skipif(not pinned(), reason="needs the pinned sqlglot and its index")
def test_function_parsed_at_import_keeps_class_users(tmp_path):
    # JSON_OBJECT is looked up while sqlglot imports (templates parsed at
    # module level), before the trace wraps the tables.
    chosen, why = run(tmp_path, "sqlglot/parser.py", '"JSON_OBJECT": lambda self',
                      '"JSON_OBJECTS": lambda self')
    assert "looked up while sqlglot imports" in why
    assert len(chosen) > 1000


def test_table_literal_shapes():
    plain = ast.parse("T = {'A': f}").body[0].value
    comp = ast.parse("T = {k: v for k, v in {**B.T, 'A': f}.items() if k != 'X'}").body[0].value
    other = ast.parse("T = dict(A=f)").body[0].value
    assert sel.table_literal(plain)[1] == "dict"
    assert isinstance(sel.table_literal(comp)[0], ast.Dict)
    assert sel.table_literal(other) is None
    assert sel.is_key_filter(ast.parse("T = {k: v for k, v in T.items() if k != 'P'}").body[0].value, "T")


def test_import_call_audit():
    src = '''
def closure(name):
    def f(self, e):
        REGISTRY[name] = e
    return f

def fills_own(*args):
    seen = {}
    for a in args:
        seen[a] = None
    def deco(fn):
        return fn
    return deco

def registers(name):
    REGISTRY[name] = 1
    return lambda self, e: name

def through(name):
    return registers(name)
'''
    defs = sel._defs_by_name({"sqlglot/m.py": src})
    pure = {n: [all(sel._def_pure(d, defs, 3, set()) for d in ds),
                all(sel._def_pure(d, defs, 3, set(), nested=True) for d in ds)] for n, ds in defs.items()}
    call = lambda s: ast.parse(s).body[0].value
    assert sel.import_call_pure(call("closure('X')"), pure)  # the store runs only when called
    assert sel.import_call_pure(call("fills_own('a', 'b')(g)"), pure)
    assert not sel.import_call_pure(call("registers('X')"), pure)
    assert not sel.import_call_pure(call("through('X')"), pure)
    assert not sel.import_call_pure(call("unknown('X')"), pure)
    assert not sel.import_call_pure(call("setattr(a, 'b', 1)"), pure)
