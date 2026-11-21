"""Generate t14's review mutants against the pinned sqlglot checkout.

Usage: python3 gen.py <sqlglot checkout> <out dir>
Each spec replaces one exact snippet (which must occur once) in one file.
Kinds are new relative to work/mut, mutB, mutC and t3's 20 generator kinds.
"""
import difflib
import json
import os
import sys

SRC, OUT = sys.argv[1], sys.argv[2]

SPECS = [
    # Appended after a nested block at function level: the selector credits it to
    # the inner block's last line (1 test) although every constructor runs it.
    ("t14x000", "append_after_block", "sqlglot/dialects/dialect.py",
     "            suggest_closest_match_and_fail(\"setting\", unsupported_setting, self.SUPPORTED_SETTINGS)\n",
     "            suggest_closest_match_and_fail(\"setting\", unsupported_setting, self.SUPPORTED_SETTINGS)\n"
     "\n        self.normalization_strategy = self.NORMALIZATION_STRATEGY\n"),
    ("t14x001", "append_after_block", "sqlglot/parser.py",
     "        if not self._match(TokenType.R_PAREN, expression=expression):\n"
     "            self.raise_error(\"Expecting )\")\n",
     "        if not self._match(TokenType.R_PAREN, expression=expression):\n"
     "            self.raise_error(\"Expecting )\")\n"
     "        self._add_comments(expression)\n"),
    # A statement moved out of its block (dedent): the changed old line ran in 36
    # tests, the new line runs for every caller.
    ("t14x002", "dedent_statement", "sqlglot/parser.py",
     "        if expression and self._prev_comments:\n"
     "            expression.add_comments(self._prev_comments)\n"
     "            self._prev_comments = []\n",
     "        if expression and self._prev_comments:\n"
     "            expression.add_comments(self._prev_comments)\n"
     "        self._prev_comments = []\n"),
    ("t14x003", "widen_except", "sqlglot/parser.py",
     "            this = parse_method()\n        except ParseError:\n",
     "            this = parse_method()\n        except Exception:\n"),
    # Enum without a sqlglot __init__: never recorded as instantiated.
    ("t14x004", "enum_value_swap", "sqlglot/dialects/dialect.py",
     "    SPARK = \"spark\"\n    SPARK2 = \"spark2\"\n",
     "    SPARK = \"spark2\"\n    SPARK2 = \"spark\"\n"),
    ("t14x005", "class_number_constant", "sqlglot/dialects/postgres.py",
     "    INDEX_OFFSET = 1\n", "    INDEX_OFFSET = 0\n"),
    ("t14x006", "base_class_flag_flip", "sqlglot/generator.py",
     "    LOCKING_READS_SUPPORTED = False\n", "    LOCKING_READS_SUPPORTED = True\n"),
    ("t14x007", "module_constant_default_arg", "sqlglot/errors.py",
     "ERROR_MESSAGE_CONTEXT_DEFAULT = 100\n", "ERROR_MESSAGE_CONTEXT_DEFAULT = 50\n"),
    ("t14x008", "test_class_attribute", "tests/dialects/test_presto.py",
     "    dialect = \"presto\"\n", "    dialect = \"trino\"\n"),
]


def read(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


def diff(rel, old, new):
    body = difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}", n=3)
    return f"diff --git a/{rel} b/{rel}\n" + "".join(body)


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
    for cid, kind, patch in RAW:
        with open(os.path.join(OUT, "commits", cid + ".patch"), "w") as f:
            f.write(patch)
        manifest[cid] = {"kind": kind}
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump({"commits": manifest}, f, indent=1)
    print(len(manifest), "mutants")


EXTRA = [
    ("t14x009", "module_dict_reorder", "sqlglot/generator.py",
     "    \"windows\": lambda self, e: (\n"
     "        self.seg(\"WINDOW \") + self.expressions(e, key=\"windows\", flat=True)\n"
     "        if e.args.get(\"windows\")\n"
     "        else \"\"\n"
     "    ),\n"
     "    \"qualify\": lambda self, e: self.sql(e, \"qualify\"),\n}\n",
     "    \"qualify\": lambda self, e: self.sql(e, \"qualify\"),\n"
     "    \"windows\": lambda self, e: (\n"
     "        self.seg(\"WINDOW \") + self.expressions(e, key=\"windows\", flat=True)\n"
     "        if e.args.get(\"windows\")\n"
     "        else \"\"\n"
     "    ),\n}\n"),
    ("t14x011", "decorator_argument", "sqlglot/generators/duckdb.py",
     "    @unsupported_args(\"ins_cost\", \"del_cost\", \"sub_cost\")\n",
     "    @unsupported_args(\"ins_cost\", \"del_cost\")\n"),
    ("t14x012", "guard_removal", "sqlglot/generator.py",
     "    def lock_sql(self, expression: exp.Lock) -> str:\n"
     "        if not self.LOCKING_READS_SUPPORTED:\n"
     "            self.unsupported(\"Locking reads using 'FOR UPDATE/SHARE' are not supported\")\n"
     "            return \"\"\n\n",
     "    def lock_sql(self, expression: exp.Lock) -> str:\n"),
    ("t14x013", "subtest_case_edit", "tests/test_transforms.py",
     "                \"CREATE TABLE t (a INT, PRIMARY KEY (a), FOREIGN KEY (a) REFERENCES u (b))\",\n            ),\n        ):\n",
     "                \"CREATE TABLE t (a INT, UNIQUE (a), PRIMARY KEY (a), FOREIGN KEY (a) REFERENCES u (b))\",\n            ),\n        ):\n"),
    ("t14x014", "import_time_empty_table", "sqlglot/dialects/hive.py",
     "        IDENTIFIERS = [\"`\"]\n", "        IDENTIFIERS = []\n"),
    ("t14x015", "redundant_override_drop", "sqlglot/generators/redshift.py",
     "    QUERY_HINTS = False\n", ""),
    ("t14x016", "append_method_to_class", "sqlglot/generators/drill.py",
     "        return f\"NOT {ilike}\" if expression.args.get(\"negate\") else ilike\n\n\ndef _drill_dateint_format",
     "        return f\"NOT {ilike}\" if expression.args.get(\"negate\") else ilike\n\n"
     "    def interval_sql(self, expression: exp.Interval) -> str:\n"
     "        return f\"INTERVAL {self.sql(expression, 'this')} {self.sql(expression, 'unit')}S\"\n"
     "\n\ndef _drill_dateint_format"),
]
RAW = [
    ("t14x010", "fixture_rename",
     "diff --git a/tests/fixtures/optimizer/normalize.sql b/tests/fixtures/optimizer/normalize_cases.sql\n"
     "similarity index 100%\n"
     "rename from tests/fixtures/optimizer/normalize.sql\n"
     "rename to tests/fixtures/optimizer/normalize_cases.sql\n"),
]

if __name__ == "__main__":
    main()
