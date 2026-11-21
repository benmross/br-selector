"""Generate t15's mutants against the pinned sqlglot checkout.

Usage: python3 gen.py <sqlglot checkout> <out dir>
Each spec replaces one exact snippet (which must occur once) in one file.
Kinds target residual risks no earlier set covers: dict keys that class-body
code pops by name at import, literal edits that raise at import, package
exports, fixture and helper data, renamed modules, test-file internals and
decorators.
"""
import difflib
import json
import os
import sys

SRC, OUT = sys.argv[1], sys.argv[2]

SPECS = [
    # (a) A base dict key that subclass bodies pop by name. 15 dialect tokenizers
    # run KEYWORDS.pop("/*+") at import; BigQuery, Snowflake and DuckDB are
    # imported by tests/dialects/test_dialect.py, which 33 test files import.
    ("t15x000", "base_key_popped_by_subclass", "sqlglot/tokens.py",
     "        HINT_START: TokenType.HINT,\n", ""),
    # (a) Renamed key; only Trino (and Athena through it) pops the old name.
    ("t15x001", "base_key_renamed_popped_by_subclass", "sqlglot/tokens.py",
     "        \"SQL SECURITY\": TokenType.SQL_SECURITY,\n",
     "        \"SQL_SECURITY\": TokenType.SQL_SECURITY,\n"),
    # (b) The literal in a class-body pop: no new identifier, KeyError at import.
    ("t15x002", "class_body_pop_literal", "sqlglot/dialects/duckdb.py",
     "        KEYWORDS.pop(\"SORT BY\")\n", "        KEYWORDS.pop(\"SORT\")\n"),
    ("t15x003", "class_body_pop_literal", "sqlglot/dialects/trino.py",
     "        KEYWORDS.pop(\"SQL SECURITY\")\n", "        KEYWORDS.pop(\"SECURITY\")\n"),
    # (a) A base key removed that a non-imported dialect pops (Teradata).
    ("t15x004", "base_key_popped_by_subclass", "sqlglot/tokens.py",
     "        \"%\": TokenType.MOD,\n", ""),
    # (c) A star re-export dropped from a package __init__: exp.JSON* vanish.
    ("t15x005", "package_star_export_removed", "sqlglot/expressions/__init__.py",
     "from sqlglot.expressions.json import *  # noqa: F401,F403\n", ""),
    # (c) A dialect dropped from the lazy registry list.
    ("t15x006", "dialect_registry_entry_removed", "sqlglot/dialects/__init__.py",
     "    \"Tableau\",\n", ""),
    # (g) @classmethod removed from a method called at import
    # (FUNCTION_BY_NAME = {... func.sql_names() ...}).
    ("t15x007", "decorator_removed_import_call", "sqlglot/expressions/core.py",
     "    @classmethod\n    def sql_names(cls) -> list[str]:\n",
     "    def sql_names(cls) -> list[str]:\n"),
    # (g) @classmethod removed from a classmethod called on the class.
    ("t15x008", "decorator_removed_classmethod", "sqlglot/dialects/dialect.py",
     "    @classmethod\n    def get_or_raise(cls, dialect: DialectType) -> Dialect:\n",
     "    def get_or_raise(cls, dialect: DialectType) -> Dialect:\n"),
    # (d) Fixture files the tests read.
    ("t15x009", "sql_fixture_line", "tests/fixtures/identity.sql",
     "1.\n(1.)\n1.0\n", "1.\n(1.))\n1.0\n"),
    ("t15x010", "sql_fixture_expected", "tests/fixtures/optimizer/qualify_columns.sql",
     "SELECT a FROM x AS z;\nSELECT z.a AS a FROM x AS z;\n",
     "SELECT a FROM x AS z;\nSELECT x.a AS a FROM x AS z;\n"),
    ("t15x011", "json_fixture", "tests/fixtures/jsonpath/cts.json",
     "      \"selector\": \" $\",\n      \"invalid_selector\": true\n",
     "      \"selector\": \"$\",\n      \"invalid_selector\": true\n"),
    ("t15x012", "sql_fixture_metadata", "tests/fixtures/optimizer/qualify_columns.sql",
     "# schema: {\"zz\": {\"a\": \"INT\"}}\nSELECT a FROM zz GROUP BY a ORDER BY a;\n",
     "# schema: {\"zz\": {\"b\": \"INT\"}}\nSELECT a FROM zz GROUP BY a ORDER BY a;\n"),
    # (d) A shared test helper module's function body.
    ("t15x013", "test_helper_function", "tests/helpers.py",
     "    return \"\\n\".join([line for line in s.splitlines() if line and not line.startswith(\"--\")])\n",
     "    return \"\\n\".join([line for line in s.splitlines() if not line.startswith(\"--\")])\n"),
    # (f) Inside test files: a helper's default argument, setUp, module helper.
    ("t15x014", "test_helper_default_arg", "tests/dialects/test_dialect.py",
     "        self, sql, write_sql=None, pretty=False, check_command_warning=False, identify=False\n",
     "        self, sql, write_sql=None, pretty=False, check_command_warning=False, identify=True\n"),
    ("t15x015", "test_setup_edit", "tests/test_optimizer.py",
     "            \"x\": {\n                \"a\": \"INT\",\n                \"b\": \"INT\",\n            },\n            # non-nullable",
     "            \"x\": {\n                \"a\": \"INT\",\n                \"b\": \"TEXT\",\n            },\n            # non-nullable"),
    ("t15x016", "test_module_helper", "tests/test_optimizer.py",
     "    optimized = func(parse_one(sql, read=read_dialect), **kwargs)\n",
     "    optimized = func(parse_one(sql), **kwargs)\n"),
]

EXTRA = [
    # One-line lambda bodies (orchestrator, from t20's research): a public
    # entry missed an edit inside a lambda credited to no test.
    ("t15x018", "lambda_body_class_table", "sqlglot/generators/duckdb.py",
     "        exp.BitwiseAnd: lambda self, e: self._bitwise_op(e, \"&\"),\n",
     "        exp.BitwiseAnd: lambda self, e: self._bitwise_op(e, \"|\"),\n"),
    ("t15x019", "lambda_body_module_table", "sqlglot/jsonpath.py",
     "    exp.JSONPathRecursive: lambda _, e: f\"..{e.this or ''}\",\n",
     "    exp.JSONPathRecursive: lambda _, e: f\".{e.this or ''}\",\n"),
    ("t15x020", "lambda_sort_key", "sqlglot/errors.py",
     "    sorted_positions = sorted(positions, key=lambda pos: pos[0])\n",
     "    sorted_positions = sorted(positions, key=lambda pos: -pos[0])\n"),
    ("t15x021", "lambda_body_parser_table", "sqlglot/parser.py",
     "        \"ARRAY_INTERSECT\": lambda args: exp.ArrayIntersect(expressions=args),\n",
     "        \"ARRAY_INTERSECT\": lambda args: exp.ArrayIntersect(expressions=args[:1]),\n"),
]


def read(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


def diff(rel, old, new, old_rel=None, new_rel=None):
    a = f"a/{old_rel or rel}" if old is not None else "/dev/null"
    b = f"b/{new_rel or rel}" if new is not None else "/dev/null"
    body = difflib.unified_diff((old or "").splitlines(True), (new or "").splitlines(True), a, b, n=3)
    head = f"diff --git a/{old_rel or rel} b/{new_rel or rel}\n"
    if old is None:
        head += "new file mode 100644\n"
    if new is None:
        head += "deleted file mode 100644\n"
    return head + "".join(body)


def rename_module():
    """(e) sqlglot/serde.py moved to sqlglot/serialize.py, its imports updated."""
    text = read("sqlglot/serde.py")
    parts = [diff("sqlglot/serde.py", text, None), diff("sqlglot/serialize.py", None, text)]
    for rel in ("sqlglot/expressions/core.py", "tests/test_serde.py"):
        old = read(rel)
        new = old.replace("sqlglot.serde", "sqlglot.serialize")
        if new != old:
            parts.append(diff(rel, old, new))
    return "".join(parts)


RAW = [("t15x017", "module_renamed_imports_updated", rename_module)]


def main():
    os.makedirs(os.path.join(OUT, "commits"), exist_ok=True)
    manifest = {}
    for cid, kind, rel, old, new in SPECS + EXTRA:
        text = read(rel)
        assert text.count(old) == 1, (cid, "snippet must occur once")
        patch = diff(rel, text, text.replace(old, new))
        with open(os.path.join(OUT, "commits", cid + ".patch"), "w") as f:
            f.write(patch)
        manifest[cid] = {"kind": kind, "file": rel}
    for cid, kind, make in RAW:
        with open(os.path.join(OUT, "commits", cid + ".patch"), "w") as f:
            f.write(make())
        manifest[cid] = {"kind": kind}
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump({"commits": manifest}, f, indent=1)
    print(len(manifest), "mutants")


if __name__ == "__main__":
    main()
