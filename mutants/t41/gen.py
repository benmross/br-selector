"""t41: string-literal-only edits that introduce a new word (main's tok-str branch).

Each patch changes text inside string literals only, one to three lines, against
the pinned sqlglot source. Strata (manifest "kind"):
  a  call-time string (lambda body or function body; runs only when called)
  b  value in a module- or class-level table
  c  key in a module- or class-level table
  d  string parsed, compiled or validated at import (regex, time-format trie)
  e  string used as a name for lookup or dispatch
  f  strings in tests/ and fixtures
  g  docstrings and error text
"""
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'work/sqlglot'
if not SRC.exists():
    SRC = Path('/home/benmross/herald/projects/blast-radius/work/sqlglot')
OUT = Path(__file__).resolve().parent
DROP = set(json.loads((OUT / 'dropped.json').read_text())) if (OUT / 'dropped.json').exists() else set()

C = []  # (stratum, label, path, old, new)


def add(s, label, path, old, new):
    C.append((s, label, path, old, new))


R, P, PG, DK = ('sqlglot/generators/redshift.py', 'sqlglot/generators/presto.py',
                'sqlglot/generators/postgres.py', 'sqlglot/generators/duckdb.py')
# a: call-time strings
add('a', 'presto security property keyword', P, 'f"SECURITY {self.sql(e.this)}"', 'f"SQL SECURITY {self.sql(e.this)}"')
add('a', 'presto file format property name', P, 'f"format={self.sql(exp.Literal.string(e.name))}"', 'f"format_name={self.sql(exp.Literal.string(e.name))}"')
add('a', 'presto unix-to-time-str cast type', P, 'AS VARCHAR)",', 'AS TEXT)",')
add('a', 'postgres partitioned-by wording', PG, 'f"PARTITION BY {self.sql(e, \'this\')}"', 'f"PARTITIONED BY {self.sql(e, \'this\')}"')
add('a', 'postgres file format keyword', PG, 'f"USING {self.sql(e, \'this\')}"', 'f"STORED AS {self.sql(e, \'this\')}"')
add('a', 'postgres tablespace prefix', PG, 'f"TABLESPACE {self.sql(e, \'this\')}"', 'f"IN TABLESPACE {self.sql(e, \'this\')}"')
add('a', 'duckdb unix-to-time-str cast type', DK, 'AS TEXT)",', 'AS VARCHAR)",')
add('a', 'spark2 iso weekday function', 'sqlglot/generators/spark2.py', "self.func('DAYOFWEEK', e.this)", "self.func('WEEKDAY', e.this)")
add('a', 'redshift starts-with operator', R, "LIKE {self.sql(e.expression)} || '%'", "ILIKE {self.sql(e.expression)} || '%'")
add('a', 'presto day-of-week function', P, "self.func('DAY_OF_WEEK', e.this)", "self.func('DOW', e.this)")
add('a', 'presto str-to-date cast type', P, 'f"CAST({_str_to_time_sql(self, e)} AS DATE)"', 'f"CAST({_str_to_time_sql(self, e)} AS TIMESTAMP)"')
add('a', 'redshift distkey function name', R, 'self.func("DISTKEY", e.this)', 'self.func("DIST_KEY", e.this)')
add('a', 'presto bitwise not name', P, 'self.func("BITWISE_NOT", e.this)', 'self.func("BIT_NOT", e.this)')
add('a', 'redshift approx distinct wording', R, 'f"APPROXIMATE COUNT(DISTINCT {', 'f"APPROXIMATE COUNT(DISTINCT ALL {')

# b: table values
add('b', 'redshift binary type name', R, 'exp.DType.BINARY: "VARBYTE",', 'exp.DType.BINARY: "VARBINARY",')
add('b', 'presto int type name', P, 'exp.DType.INT: "INTEGER",', 'exp.DType.INT: "INT4",')
add('b', 'postgres ntz timestamp type', PG, 'exp.DType.TIMESTAMPNTZ: "TIMESTAMP",', 'exp.DType.TIMESTAMPNTZ: "TIMESTAMP WITHOUT TIME ZONE",')
add('b', 'duckdb varbinary type name', DK, 'exp.DType.VARBINARY: "BLOB",', 'exp.DType.VARBINARY: "BYTEA",')
add('b', 'singlestore linestring type', 'sqlglot/generators/singlestore.py', 'exp.DType.LINESTRING: "GEOGRAPHY",', 'exp.DType.LINESTRING: "GEOMETRY",')
add('b', 'exasol blob type', 'sqlglot/generators/exasol.py', 'exp.DType.BLOB: "VARCHAR",', 'exp.DType.BLOB: "CLOB",')
add('b', 'mysql timestamp type', 'sqlglot/generators/mysql.py', 'exp.DType.TIMESTAMP: "DATETIME",', 'exp.DType.TIMESTAMP: "DATETIME2",')
add('b', 'bigquery binary type', 'sqlglot/generators/bigquery.py', 'exp.DType.BINARY: "BYTES",', 'exp.DType.BINARY: "BYTEA",')
add('b', 'mysql hour format value', 'sqlglot/dialects/mysql.py', '"%h": "%I",', '"%h": "%l",')
add('b', 'duckdb iso dow rename', DK, 'rename_func("ISODOW")', 'rename_func("ISO_DOW")')
add('b', 'bigquery json bool rename', 'sqlglot/generators/bigquery.py', 'exp.JSONBool: rename_func("BOOL")', 'exp.JSONBool: rename_func("JSON_BOOL")')
add('b', 'clickhouse current database rename', 'sqlglot/generators/clickhouse.py', 'rename_func("CURRENT_DATABASE")', 'rename_func("currentDatabase")')
add('b', 'snowflake manhattan distance rename', 'sqlglot/generators/snowflake.py', 'rename_func("VECTOR_L1_DISTANCE")', 'rename_func("MANHATTAN_DISTANCE")')
add('b', 'test leakcheck structural types', 'tests/leakcheck.py', '"set", "frozenset"})', '"set", "frozenset", "bytearray"})')

# c: table keys
add('c', 'redshift binary varying keyword', 'sqlglot/dialects/redshift.py', '"BINARY VARYING": TokenType.VARBINARY,', '"BYTE VARYING": TokenType.VARBINARY,')
add('c', 'postgres regcollation keyword', 'sqlglot/dialects/postgres.py', '"REGCOLLATION": TokenType.OBJECT_IDENTIFIER,', '"REGCOLLATE": TokenType.OBJECT_IDENTIFIER,')
add('c', 'duckdb ubigint keyword', 'sqlglot/dialects/duckdb.py', '"UBIGINT": TokenType.UBIGINT,', '"UINT64": TokenType.UBIGINT,')
add('c', 'starrocks resume keyword', 'sqlglot/dialects/starrocks.py', '"RESUME": TokenType.COMMAND,', '"RESUME JOB": TokenType.COMMAND,')
add('c', 'tsql output keyword', 'sqlglot/dialects/tsql.py', '"OUTPUT": TokenType.RETURNING,', '"OUTPUTS": TokenType.RETURNING,')
add('c', 'snowflake byteint keyword', 'sqlglot/dialects/snowflake.py', '"BYTEINT": TokenType.INT,', '"BYTE_INT": TokenType.INT,')
add('c', 'oracle subpartition keyword', 'sqlglot/dialects/oracle.py', '"SUBPARTITION": TokenType.PARTITION,', '"SUBPARTITIONS": TokenType.PARTITION,')
add('c', 'trino refresh keyword', 'sqlglot/dialects/trino.py', '"REFRESH": TokenType.REFRESH,', '"REFRESH MATERIALIZED": TokenType.REFRESH,')
add('c', 'base anti keyword', 'sqlglot/tokens.py', '"ANTI": TokenType.ANTI,', '"ANTIJOIN": TokenType.ANTI,')
add('c', 'base asof keyword', 'sqlglot/tokens.py', '"ASOF": TokenType.ASOF,', '"AS_OF": TokenType.ASOF,')
add('c', 'math binary arg key', 'sqlglot/expressions/math.py', 'arg_types = {"this": True, "expression": True}', 'arg_types = {"this": True, "operand": True}')
add('c', 'optimizer lazy export key', 'sqlglot/optimizer/__init__.py', '    "find_in_scope": ("sqlglot.optimizer.scope", "find_in_scope"),', '    "find_scope": ("sqlglot.optimizer.scope", "find_in_scope"),')

# d: parsed or compiled at import
add('d', 'duckdb timezone pattern accepts Z', DK, 'TIMEZONE_PATTERN = re.compile(r":\\d{2}.*?[+\\-]\\d{2}(?::\\d{2})?")', 'TIMEZONE_PATTERN = re.compile(r":\\d{2}.*?(?:Z|[+\\-]\\d{2}(?::\\d{2})?)")')
add('d', 'bigquery safe json key end anchor', 'sqlglot/generators/bigquery.py', 'SAFE_JSON_PATH_KEY_RE = re.compile(r"^[\\-\\w]*$")', 'SAFE_JSON_PATH_KEY_RE = re.compile(r"^[\\-\\w]*\\Z")')
add('d', 'hive canonical time strict year', 'sqlglot/generators/hive.py', 'r"%(?:[mdHIMS]strict|[-:].|.)"', 'r"%(?:[mdHIMSy]strict|[-:].|.)"')
add('d', 'hive safe json key digits', 'sqlglot/generators/hive.py', 'r"^[_\\-a-zA-Z][\\-\\w]*$"', 'r"^[_\\-a-zA-Z0-9][\\-\\w]*$"')
add('d', 'interval unit allows underscore', 'sqlglot/expressions/builders.py', 'INTERVAL_STRING_RE = re.compile(r"\\s*(-?[0-9]+(?:\\.[0-9]+)?)\\s*([a-zA-Z]+)\\s*")', 'INTERVAL_STRING_RE = re.compile(r"\\s*(-?[0-9]+(?:\\.[0-9]+)?)\\s*([a-zA-Z_]+)\\s*")')
add('d', 'camel case split before lowercase', 'sqlglot/helper.py', 'CAMEL_CASE_PATTERN = re.compile("(?<!^)(?=[A-Z])")', 'CAMEL_CASE_PATTERN = re.compile("(?<!^)(?=[A-Z][a-z])")')
add('d', 'high byte range includes delete', 'sqlglot/generator.py', '_HIGH_BYTE_RE = re.compile(r"[\\x80-\\xff]")', '_HIGH_BYTE_RE = re.compile(r"[\\x7f-\\xff]")')
add('d', 'mysql time mapping key in trie', 'sqlglot/dialects/mysql.py', '"%i": "%M",', '"%n": "%M",')
add('d', 'mysql month-name key in trie', 'sqlglot/dialects/mysql.py', '"%M": "%B",', '"%Mo": "%B",')
add('d', 'test canonical atom regex', 'tests/test_time.py', 'KNOWN_CANONICAL_ATOM = re.compile(r"%(?:[mdHIMS]strict|[-:].|[\\w%])")', 'KNOWN_CANONICAL_ATOM = re.compile(r"%(?:[mdHIMSy]strict|[-:].|[\\w%])")')

# e: names for lookup or dispatch
D = 'sqlglot/dialects/dialect.py'
add('e', 'tsql dialect registry name', D, '    TSQL = "tsql"', '    TSQL = "mssql"')
add('e', 'doris dialect registry name', D, '    DORIS = "doris"', '    DORIS = "apache_doris"')
add('e', 'drill dialect registry name', D, '    DRILL = "drill"', '    DRILL = "apache_drill"')
O = 'sqlglot/optimizer/__init__.py'
add('e', 'optimizer lazy scope module path', O, '    "Scope": ("sqlglot.optimizer.scope", "Scope"),', '    "Scope": ("sqlglot.optimizer.scopes", "Scope"),')
add('e', 'optimizer lazy optimize attribute', O, '    "optimize": ("sqlglot.optimizer.optimizer", "optimize"),', '    "optimize": ("sqlglot.optimizer.optimizer", "run_optimize"),')
M = 'sqlglot/expressions/math.py'
add('e', 'ceil function alias', M, '_sql_names = ["CEIL", "CEILING"]', '_sql_names = ["CEIL", "CEILING", "CEIL_VALUE"]')
add('e', 'isinf function name', M, '_sql_names = ["IS_INF", "ISINF"]', '_sql_names = ["IS_INFINITE", "ISINF"]')
add('e', 'sign function alias', M, '_sql_names = ["SIGN", "SIGNUM"]', '_sql_names = ["SIGN", "SGN"]')
add('e', 'getbit function alias', M, '_sql_names = ["GETBIT", "GET_BIT"]', '_sql_names = ["GETBIT", "BIT_GET"]')
add('e', 'trunc function alias', M, '_sql_names = ["TRUNC", "TRUNCATE"]', '_sql_names = ["TRUNC", "TRUNCATE", "TRUNC_NUMBER"]')
add('e', 'skip integration env name', 'tests/helpers.py', 'os.environ.get("SKIP_INTEGRATION", "0")', 'os.environ.get("SKIP_INTEGRATION_TESTS", "0")')
add('e', 'fabric test dialect name', 'tests/dialects/test_fabric.py', '    dialect = "fabric"', '    dialect = "fabricdw"')
add('e', 'risingwave test dialect name', 'tests/dialects/test_risingwave.py', '    dialect = "risingwave"', '    dialect = "rising_wave"')

# f: tests and fixtures
add('f', 'executor tpch fixture dir', 'tests/test_executor.py', 'DIR_TPCH = FIXTURES_DIR + "/optimizer/tpc-h/"', 'DIR_TPCH = FIXTURES_DIR + "/optimizer/tpch/"')
add('f', 'executor tpcds fixture dir', 'tests/test_executor.py', 'DIR_TPCDS = FIXTURES_DIR + "/optimizer/tpc-ds/"', 'DIR_TPCDS = FIXTURES_DIR + "/optimizer/tpcds/"')
add('f', 'helpers fixtures dir name', 'tests/helpers.py', 'FIXTURES_DIR = os.path.join(FILE_DIR, "fixtures")', 'FIXTURES_DIR = os.path.join(FILE_DIR, "test_fixtures")')
add('f', 'executor skip reason text', 'tests/test_executor.py', '"Skipping Integration Tests since `SKIP_INTEGRATION` is set"', '"Skipping integration tests because `SKIP_INTEGRATION` is set"')
add('f', 'dialect test skip reason', 'tests/dialects/test_dialect.py', '"mypyc compiled parsers cannot be subclassed")', '"mypyc compiled parser classes cannot be subclassed")')
add('f', 'oracle test dialect name', 'tests/dialects/test_oracle.py', '    dialect = "oracle"', '    dialect = "oracle12"')
add('f', 'postgres test dialect name', 'tests/dialects/test_postgres.py', '    dialect = "postgres"', '    dialect = "postgresql"')
add('f', 'leakcheck null stream mode', 'tests/leakcheck.py', '_NULL_STREAM = open(os.devnull, "w")', '_NULL_STREAM = open(os.devnull, "wt")')
add('f', 'sqlite skip reason text', 'tests/dialects/test_sqlite.py', '"Requires variadic SQLite IIF")', '"Requires SQLite 3.49 for variadic IIF")')
add('f', 'zoneinfo skip reason text', 'tests/test_expressions.py', '"zoneinfo only available from python 3.9+")', '"zoneinfo module only available from python 3.9+")')
add('f', 'serde skip reason text', 'tests/test_serde.py', '"mypyc compiled expressions cannot be subclassed")', '"mypyc compiled expression classes cannot be subclassed")')
add('f', 'leakcheck status label', 'tests/leakcheck.py', 'status = "LEAK" if reasons else " OK "', 'status = "LEAKED" if reasons else " OK "')
add('f', 'drill test dialect name', 'tests/dialects/test_drill.py', '    dialect = "drill"', '    dialect = "apache_drill"')
add('f', 'dialect test first skip reason', 'tests/dialects/test_dialect.py', '"mypyc compiled parsers cannot be subclassed")\n    def test_patch_dialect_parser', '"mypyc compiled parser classes cannot be subclassed")\n    def test_patch_dialect_parser')

# g: docstrings and error text
add('g', 'pretty setting docstring', 'sqlglot/__init__.py', '"""Whether to format generated SQL by default."""', '"""Whether generated SQL is pretty-printed by default."""')
add('g', 'error level ignore docstring', 'sqlglot/errors.py', '"""Ignore all errors."""', '"""Ignore all errors silently."""')
add('g', 'error level warn docstring', 'sqlglot/errors.py', '"""Log all errors."""', '"""Log all errors as warnings."""')
add('g', 'error level raise docstring', 'sqlglot/errors.py', '"""Collect all errors and raise a single exception."""', '"""Collect all errors and raise them together in a single exception."""')
add('g', 'error level immediate docstring', 'sqlglot/errors.py', '"""Immediately raise an exception on the first error found."""', '"""Immediately raise an exception on the first error encountered."""')
add('g', 'dialects enum docstring', D, '"""Dialects supported by SQLGLot."""', '"""Dialects supported by SQLGlot out of the box."""')
add('g', 'normalization strategy docstring', D, '"""Specifies the strategy according to which identifiers should be normalized."""', '"""Specifies the strategy used to normalize identifiers."""')
add('g', 'lowercase strategy docstring', D, '"""Unquoted identifiers are lowercased."""', '"""Unquoted identifiers are converted to lowercase."""')
add('g', 'uppercase strategy docstring', D, '"""Unquoted identifiers are uppercased."""', '"""Unquoted identifiers are converted to uppercase."""')
add('g', 'case sensitive strategy docstring', D, '"""Always case-sensitive, regardless of quotes."""', '"""Always case-sensitive, whether quoted or not."""')
add('g', 'optimizer package docstring', O, '"""Lazy re-exports from optimizer submodules.', '"""Lazily loaded re-exports from optimizer submodules.')

if __name__ == '__main__':
    import collections
    (OUT / 'commits').mkdir(exist_ok=True)
    for p in (OUT / 'commits').glob('*.patch'):
        p.unlink()
    manifest, n = {}, 0
    for i, (s, label, path, old, new) in enumerate(C):
        cid = f't41x{i:03d}'
        if cid in DROP:
            continue
        before = (SRC / path).read_text()
        if before.count(old) != 1:
            print('SKIP', cid, label, 'occurrences', before.count(old), file=sys.stderr)
            continue
        after = before.replace(old, new, 1)
        compile(after, path, 'exec')
        diff = f'diff --git a/{path} b/{path}\n' + ''.join(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True), fromfile=f'a/{path}', tofile=f'b/{path}'))
        (OUT / 'commits' / (cid + '.patch')).write_text(diff)
        manifest[cid] = {'kind': s, 'description': label, 'paths': [path],
                         'label_scope': 'full numbered suite except memory-infeasible test 1490'}
    (OUT / 'manifest.json').write_text(json.dumps({'commits': manifest}, indent=2) + '\n')
    print('generated', len(manifest), dict(collections.Counter(v['kind'] for v in manifest.values())))
