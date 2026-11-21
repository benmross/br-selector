"""t44 adversarial mutants against cba6718's three proofs. Each is a single-file edit of the
pinned sqlglot (eb11aec). Usage: python3 gen.py <pinned sqlglot dir>"""
import difflib, json, os, sys
SRC = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
M = []

def add(cid, proof, path, edits, intent):
    text = open(os.path.join(SRC, path)).read()
    new = text
    for old, rep in edits:
        assert new.count(old) == 1, (cid, old, new.count(old))
        new = new.replace(old, rep)
    d = difflib.unified_diff(text.splitlines(True), new.splitlines(True), f"a/{path}", f"b/{path}")
    with open(os.path.join(HERE, "commits", cid + ".patch"), "w") as f:
        f.write(f"diff --git a/{path} b/{path}\n" + "".join(d))
    M.append((cid, dict(kind=proof, paths=[path], description=intent)))

MAIN = "sqlglot/__main__.py"
# Proof 3: stock argparse help in sqlglot/__main__.py
add("a44h01", "help", MAIN, [('help="Dialect to read default is generic"', 'help="==SUPPRESS=="')],
    "help set to argparse.SUPPRESS sentinel text")
add("a44h02", "help", MAIN, [('help="Dialect to write default is generic"', 'help="Dialect to write, default %(default)s"')],
    "help with a percent format (rendered at --help, checked at add_argument on 3.14)")
add("a44h03", "help", MAIN, [('help="Whether to quote identifiers (safe, true, false)"', 'help="Whether to quote identifiers — safe, true, false"')],
    "non-ASCII help")
add("a44h04", "help", MAIN, [('description="Transpile SQL"', 'description="Transpile SQL text"'),
                             ('help="Parse and return the expression tree"', 'help="Parse and print the tree"')],
    "parser description plus a help string")
add("a44h05", "help", MAIN, [('help="Display the SQLGlot version"', 'help="Show the installed version"')],
    "help on the --version argument, whose version= is not a constant")
add("a44h06", "help", MAIN, [('metavar="sql"', 'metavar="query"'), ('help="Tokenize and return the tokens list"', 'help="Tokenize only"')],
    "metavar plus a help string")
add("a44h07", "help", MAIN, [('help="Compress sql"', 'help="Compress sql {pretty}\\nsingle line"'),
                             ('help="Parse and return the expression tree"', 'help="Parse {and} return the AST"')],
    "two help strings with braces and an escaped newline")
add("a44h08", "help", MAIN, [('help="IGNORE, WARN, RAISE, IMMEDIATE (default)"', 'help=""')],
    "help emptied")
add("a44h09", "help", MAIN, [('help="SQL statement(s) to transpile, or - to parse stdin."', 'help="SQL to transpile; - reads stdin."'),
                             ('import argparse\n', 'import argparse  # stdlib parser\n')],
    "positional help plus a comment")
add("a44h10", "help", MAIN, [('dest="identify",', 'dest="identifiers",')],
    "dest string changed (behavior: args.identify no longer exists)")

# Proof 1: tables accepted only because their other import-time mentions are comments or docstrings
add("a44i01", "inert", "sqlglot/expressions/array.py", [('_sql_names = ["ARRAY_CONCAT", "ARRAY_CAT"]', '_sql_names = ["ARRAY_CONCAT", "ARRAY_CATX"]')],
    "_sql_names alias renamed: ARRAY_CAT no longer parses to ArrayConcat (registry built at import)")
add("a44i02", "inert", "sqlglot/expressions/array.py", [('_sql_names = ["ARRAY_SIZE", "ARRAY_LENGTH"]', '_sql_names = ["ARRAY_SIZEX", "ARRAY_LENGTH"]')],
    "_sql_names primary renamed: generated function name changes")
add("a44i03", "inert", "sqlglot/expressions/array.py", [('_sql_names = ["FILTER", "ARRAY_FILTER"]', '_sql_names = ["FILTER", "ARRAY_FILTERS"]')],
    "_sql_names alias renamed")
add("a44i04", "inert", "sqlglot/expressions/string.py", [('arg_types = {"expressions": True, "safe": False, "coalesce": False}', 'arg_types = {"expressions": True, "safe": True, "coalesce": False}')],
    "arg_types flag: Concat.safe becomes required; ConcatWs extends it")
add("a44i05", "inert", "sqlglot/expressions/query.py", [('        "grant_option": False,\n    }\n', '        "grant_opt": False,\n    }\n')],
    "arg_types key rename in Grant (parser passes grant_option=)")
add("a44i06", "inert", "sqlglot/dialects/clickhouse.py", [('STRING_ESCAPES = ["\'", "\\\\"]', 'STRING_ESCAPES = ["\'", "~"]')],
    "ClickHouse tokenizer STRING_ESCAPES; dialect metaclass derives STRINGS_SUPPORT_ESCAPED_SEQUENCES")
add("a44i07", "inert", "sqlglot/dialects/databricks.py", [('IDENTIFIERS = ["`", \'"\']', 'IDENTIFIERS = ["`", "["]')],
    "Databricks tokenizer IDENTIFIERS")
add("a44i08", "inert", "sqlglot/dialects/bigquery.py", [('QUOTES = ["\'", \'"\', \'"""\', "\'\'\'"]', 'QUOTES = ["\'", \'"\', \'"""\', "~~~"]')],
    "BigQuery tokenizer QUOTES")

# Proof 2: same-type literal tables with audited consumers
MY = "sqlglot/dialects/mysql.py"
add("a44l01", "table", MY, [('"%i": "%M",', '"%i": "%-M",')],
    "MySQL TIME_MAPPING value; changes MySQL.INVERSE_TIME_MAPPING read by SingleStore as MYSQL_INVERSE_TIME_MAPPING and Presto's alias")
add("a44l02", "table", MY, [('"%h": "%I",', '"%h": "%Ix",')],
    "MySQL TIME_MAPPING value with a lax %I followed by a word character (generic all-dialect vocabulary test)")
add("a44l03", "table", "sqlglot/dialects/hive.py", [('"MM": "%mstrict",', '"MM": "%m",')],
    "Hive strict month to lax; Spark2/Spark extend Hive.TIME_MAPPING, test_time checks strict MM")
add("a44l04", "table", "sqlglot/dialects/tsql.py", [('"n": "%M",', '"n": "%S",')],
    "TSQL TIME_MAPPING value; tsql parser/generator read TSQL.TIME_MAPPING and TSQL.INVERSE_TIME_MAPPING by class")
add("a44l05", "table", "sqlglot/dialects/oracle.py", [('"MI": "%M",', '"MI": "%-M",')],
    "Oracle TIME_MAPPING value (Oracle-derived dialects)")
add("a44l07", "table", "sqlglot/dialects/dialect.py", [('"%Mstrict": "%M",', '"%Mstrict": "%-M",')],
    "STRICT_TIME_FORMATS value, read inside _with_strict_time_inverse at import")
add("a44l08", "table", "sqlglot/expressions/string.py", [('arg_types = {**Concat.arg_types, "flatten": False}', 'arg_types = {**Concat.arg_types, "flatten": True}')],
    "Expression arg_types flag: optional arg becomes required (validation at parse)")
add("a44l09", "table", "sqlglot/expressions/query.py", [('arg_types = {**Grant.arg_types, "cascade": False}', 'arg_types = {**Grant.arg_types, "cascades": False}')],
    "Expression arg_types key rename (builders pass the old key)")
add("a44l10", "table", "sqlglot/dialects/snowflake.py", [('"T": "T",  # in TIME_MAPPING', '"T": "TT",  # in TIME_MAPPING')],
    "Snowflake class INVERSE_TIME_MAPPING value next to a comment mention; hook reads it via __dict__.get")
add("a44l11", "table", MY, [('"%W": "%A",', '"%M": "%A",')],
    "MySQL TIME_MAPPING key collides with an existing key")

json.dump({"commits": dict(M)}, open(os.path.join(HERE, "manifest.json"), "w"), indent=1)
print(len(M), "mutants")
