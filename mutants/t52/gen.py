"""t52 new-kind probes: parent-class values inherited by child dialects, derived
metaclass tables, module constants and order, re-exports, import-time table
operators and protocol dunders. Every edit adds no new identifier."""
import difflib, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = Path('/home/benmross/herald/projects/blast-radius/work/sqlglot')
OUT = Path(__file__).resolve().parent
(OUT / 'commits').mkdir(exist_ok=True)
old_manifest = json.load(open(OUT / 'manifest.json'))['commits'] if (OUT / 'manifest.json').exists() else {}
manifest = {}


def emit(kind, label, path, before, after):
    assert before != after, label
    compile(after, path, 'exec')
    cid = f't52x{len(manifest):03d}'
    patch = f'diff --git a/{path} b/{path}\n' + ''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/' + path, tofile='b/' + path))
    (OUT / 'commits' / f'{cid}.patch').write_text(patch)
    manifest[cid] = {'kind': kind, 'description': label, 'paths': [path]}
    if old_manifest.get(cid, {}).get('description') == label:
        manifest[cid].update({k: v for k, v in old_manifest[cid].items() if k in ('tests', 'label_scope', 'deselect')})


def replace(kind, label, path, old, new):
    a = (SRC / path).read_text()
    assert a.count(old) >= 1, (path, old)
    emit(kind, label, path, a, a.replace(old, new, 1))


FLIP = {'True': 'False', 'False': 'True', '1': '0', '0': '1'}


def flag(kind, child, path, name):
    a = (SRC / path).read_text()
    m = re.search(rf'^    {name} = (True|False|\d+)$', a, re.M)
    assert m, (path, name)
    old, new = m.group(0), f'    {name} = {FLIP[m.group(1)]}'
    emit(kind, f'{path.split("/")[-2]}/{path.split("/")[-1]} {name} {m.group(1)}->{FLIP[m.group(1)]} (inherited by {child})', path, a, a.replace(old, new, 1))


D, G, P = 'sqlglot/dialects/', 'sqlglot/generators/', 'sqlglot/parsers/'
# 1. Inheritance consumers: a parent class flag read by child dialects that override methods.
for path, names, child in [
    (D + 'postgres.py', ['TYPED_DIVISION', 'CONCAT_COALESCE', 'TABLESAMPLE_SIZE_IS_PERCENT', 'TABLES_REFERENCEABLE_AS_COLUMNS', 'SUPPORTS_LIMIT_ALL'], 'Redshift/Materialize/RisingWave'),
    (D + 'mysql.py', ['DPIPE_IS_STRING_CONCAT', 'SAFE_DIVISION', 'IDENTIFIERS_CAN_START_WITH_DIGIT'], 'Doris/StarRocks/SingleStore'),
    (D + 'hive.py', ['ALIAS_POST_TABLESAMPLE', 'SAFE_DIVISION', 'REGEXP_EXTRACT_DEFAULT_GROUP'], 'Spark2/Spark/Databricks'),
    (D + 'presto.py', ['STRICT_STRING_CONCAT', 'TYPED_DIVISION', 'INDEX_OFFSET'], 'Trino/Athena/Dune'),
    (D + 'tsql.py', ['TYPED_DIVISION', 'LOG_BASE_FIRST'], 'Fabric'),
    (G + 'postgres.py', ['SINGLE_STRING_INTERVAL', 'LOCKING_READS_SUPPORTED', 'RENAME_TABLE_WITH_DB'], 'Redshift/Materialize/RisingWave'),
    (G + 'mysql.py', ['SUPPORTS_MODIFY_COLUMN', 'INTERVAL_ALLOWS_PLURAL_FORM'], 'Doris/StarRocks/SingleStore'),
    (G + 'hive.py', ['SUPPORTS_GROUPING_SETS_AS_SUFFIX', 'TABLESAMPLE_WITH_METHOD'], 'Spark2/Spark/Databricks'),
    (G + 'presto.py', ['CAST_TO_INT_ROUNDS', 'SUPPORTS_LEFT_JOIN_UNNEST'], 'Trino/Athena/Dune'),
    (G + 'tsql.py', ['LIMIT_IS_TOP', 'SET_OP_LIMITS'], 'Fabric'),
    (P + 'postgres.py', ['SUPPORTS_OMITTED_INTERVAL_SPAN_UNIT', 'ALTER_TABLE_MIXED_ACTIONS'], 'Redshift/Materialize/RisingWave'),
    (P + 'mysql.py', ['STRING_ALIASES', 'VALUES_FOLLOWED_BY_PAREN'], 'Doris/StarRocks/SingleStore'),
    (P + 'hive.py', ['STRICT_CAST', 'JOINS_HAVE_EQUAL_PRECEDENCE', 'NORMALIZE_DECIMAL_LITERALS'], 'Spark2/Spark/Databricks'),
]:
    for name in names:
        flag('inherit-flag', child, path, name)

# 1b. Inheritance consumers: a parent Tokenizer KEYWORDS value swapped to a
# TokenType already named in the file; child tests use the keyword.
for path, old, new, child in [
    (D + 'postgres.py', '"TYPE": TokenType.TYPE,', '"TYPE": TokenType.COMMAND,', 'Redshift'),
    (D + 'postgres.py', '"POINT": TokenType.POINT,', '"POINT": TokenType.NAME,', 'Redshift'),
    (D + 'postgres.py', '"NAME": TokenType.NAME,', '"NAME": TokenType.POINT,', 'Materialize'),
    (D + 'mysql.py', '"START": TokenType.BEGIN,', '"START": TokenType.COMMAND,', 'StarRocks'),
    (D + 'mysql.py', '"KEY": TokenType.KEY,', '"KEY": TokenType.IGNORE,', 'Doris/StarRocks'),
    (D + 'mysql.py', '"LONGTEXT": TokenType.LONGTEXT,', '"LONGTEXT": TokenType.BLOB,', 'SingleStore'),
    (D + 'hive.py', '"REFRESH": TokenType.REFRESH,', '"REFRESH": TokenType.COMMAND,', 'Spark/Databricks'),
    (D + 'presto.py', '"ROW": TokenType.STRUCT,', '"ROW": TokenType.BEGIN,', 'Trino/Athena'),
    (D + 'tsql.py', '"DATETIME2": TokenType.DATETIME2,', '"DATETIME2": TokenType.SMALLDATETIME,', 'Fabric'),
    (D + 'tsql.py', '"UNIQUEIDENTIFIER": TokenType.UUID,', '"UNIQUEIDENTIFIER": TokenType.XML,', 'Fabric'),
]:
    replace('inherit-table', f'{path.split("/")[-1]} Tokenizer {old} -> {new} (used by {child})', path, old, new)

# 3. Module-level table copied by `from x import NAME` into a child module at import (typing chain).
T = 'sqlglot/typing/'
for path, old, new, label in [
    (T + 'hive.py', '{exp.Ceil, exp.Floor}', '{exp.Floor}', 'hive typing drops Ceil from floor/ceil set (Spark2/Spark/Databricks copy)'),
    (T + 'hive.py', '        expr_type: {"returns": exp.DType.BINARY}', '        expr_type: {"returns": exp.DType.DOUBLE}', 'hive typing BINARY group returns DOUBLE'),
    (T + 'hive.py', '        expr_type: {"returns": exp.DType.BIGINT}', '        expr_type: {"returns": exp.DType.INT}', 'hive typing BIGINT group returns INT'),
    (T + 'hive.py', '        expr_type: {"returns": exp.DType.INT}', '        expr_type: {"returns": exp.DType.BIGINT}', 'hive typing INT group returns BIGINT'),
    (T + 'hive.py', '    exp.Grouping: {"returns": exp.DType.BIGINT},', '    exp.Grouping: {"returns": exp.DType.DOUBLE},', 'hive typing Grouping returns DOUBLE'),
    (T + 'postgres.py', '        expr_type: {"returns": exp.DType.INT}', '        expr_type: {"returns": exp.DType.TEXT}', 'postgres typing INT group returns TEXT (Redshift copy)'),
    (T + 'postgres.py', '        expr_type: {"returns": exp.DType.TIMESTAMP}', '        expr_type: {"returns": exp.DType.TIME}', 'postgres typing TIMESTAMP group returns TIME (Redshift copy)'),
]:
    replace('typing-chain', label, path, old, new)

# 4. Re-exports retargeted to another object of the same shape already imported there.
for old, new in [('    and_ as and_,', '    or_ as and_,'), ('    union as union,', '    intersect as union,'),
                 ('    column as column,', '    to_column as column,'), ('    table_ as table,', '    to_table as table,'),
                 ('    except_ as except_,', '    intersect as except_,')]:
    replace('reexport-retarget', 'sqlglot/__init__.py ' + old.strip() + ' -> ' + new.strip(), 'sqlglot/__init__.py', old, new)

# 6a. Order of _sql_names: the first entry is the default generated name.
X = 'sqlglot/expressions/'
for old, new in [('["ARG_MAX", "ARGMAX", "MAX_BY"]', '["MAX_BY", "ARGMAX", "ARG_MAX"]'),
                 ('["COUNT_IF", "COUNTIF"]', '["COUNTIF", "COUNT_IF"]'),
                 ('["LOGICAL_AND", "BOOL_AND", "BOOLAND_AGG"]', '["BOOL_AND", "LOGICAL_AND", "BOOLAND_AGG"]'),
                 ('["APPROXIMATE_SIMILARITY", "APPROXIMATE_JACCARD_INDEX"]', '["APPROXIMATE_JACCARD_INDEX", "APPROXIMATE_SIMILARITY"]')]:
    replace('sql-names-order', 'aggregate.py _sql_names ' + old + ' -> ' + new, X + 'aggregate.py', old, new)

# 5. Import-time table operators: drop one operand of a merge or union.
for path, old, new, label in [
    (D + 'postgres.py', 'COMMANDS = {*tokens.Tokenizer.COMMANDS, TokenType.LOCK}', 'COMMANDS = {TokenType.LOCK}', 'postgres Tokenizer COMMANDS drops inherited operand (Redshift inherits)'),
    (T + 'hive.py', '    **EXPRESSION_METADATA,\n    **{expr_type: {"annotator": _annotate_floor_ceil}', '    **{expr_type: {"annotator": _annotate_floor_ceil}', 'hive typing drops base metadata operand'),
]:
    replace('table-operator', label, path, old, new)

# 6b. Protocol flags read by the library: is_var_len_args, and arg_types required
# values that Expr.__init_subclass__ turns into derived required-argument sets.
for cls, old, new in [
    ('Chr', '    arg_types = {"expressions": True, "charset": False}\n    is_var_len_args = True', '    arg_types = {"expressions": True, "charset": False}\n    is_var_len_args = False'),
    ('Elt', '    arg_types = {"this": True, "expressions": True}\n    is_var_len_args = True', '    arg_types = {"this": True, "expressions": True}\n    is_var_len_args = False'),
    ('Format', '    arg_types = {"this": True, "expressions": False, "is_fmt": False}\n    is_var_len_args = True', '    arg_types = {"this": True, "expressions": False, "is_fmt": False}\n    is_var_len_args = False'),
    ('FarmFingerprint', '    arg_types = {"expressions": True}\n    is_var_len_args = True', '    arg_types = {"expressions": True}\n    is_var_len_args = False'),
    ('MD5Digest', '    arg_types = {"this": True, "expressions": False}\n    is_var_len_args = True', '    arg_types = {"this": True, "expressions": False}\n    is_var_len_args = False'),
    ('Chr', '    arg_types = {"expressions": True, "charset": False}', '    arg_types = {"expressions": True, "charset": True}'),
    ('Format', 'arg_types = {"this": True, "expressions": False, "is_fmt": False}', 'arg_types = {"this": True, "expressions": True, "is_fmt": False}'),
    ('Concat', 'arg_types = {"expressions": True, "safe": False, "coalesce": False}', 'arg_types = {"expressions": False, "safe": False, "coalesce": False}'),
]:
    kind = 'var-len-flag' if 'is_var_len_args = False' in new else 'arg-types-required'
    replace(kind, f'string.py {cls}: ' + ('is_var_len_args True->False' if kind == 'var-len-flag' else 'required flag flipped in arg_types'), X + 'string.py', old, new)

# 3b. Module constants copied by `from x import NAME` into another module.
for path, old, new, label in [
    (P + 'exasol.py', 'DATE_UNITS = {"DAY", "WEEK", "MONTH", "YEAR", "HOUR", "MINUTE", "SECOND"}', 'DATE_UNITS = {"DAY", "MONTH", "YEAR", "HOUR", "MINUTE", "SECOND"}', 'parsers/exasol.py DATE_UNITS drops WEEK (read by generators/exasol.py)'),
    (P + 'exasol.py', 'DATE_UNITS = {"DAY", "WEEK", "MONTH", "YEAR", "HOUR", "MINUTE", "SECOND"}', 'DATE_UNITS = {"DAY", "WEEK", "MONTH", "YEAR", "MINUTE", "SECOND"}', 'parsers/exasol.py DATE_UNITS drops HOUR (read by generators/exasol.py)'),
    (P + 'tsql.py', 'OPTIONS_THAT_REQUIRE_EQUAL = ("MAX_GRANT_PERCENT", "MIN_GRANT_PERCENT", "LABEL")', 'OPTIONS_THAT_REQUIRE_EQUAL = ("MAX_GRANT_PERCENT", "MIN_GRANT_PERCENT")', 'parsers/tsql.py OPTIONS_THAT_REQUIRE_EQUAL drops LABEL (read by generators/tsql.py)'),
    ('sqlglot/helper.py', 'DATE_UNITS = {"day", "week", "month", "quarter", "year", "year_month"}', 'DATE_UNITS = {"day", "month", "quarter", "year", "year_month"}', 'helper.py DATE_UNITS drops week'),
]:
    replace('module-const-import', label, path, old, new)

# 7. Session 2 (8:45 AM): lazy-loading tables, metaclass-derived values of
# another class, module tuple order, and the dialect metaclass hash protocol.
O = 'sqlglot/optimizer/'
for kind, path, old, new, label in [
    ('lazy-table', O + '__init__.py', '"traverse_scope": ("sqlglot.optimizer.scope", "traverse_scope")', '"traverse_scope": ("sqlglot.optimizer.scope", "walk_in_scope")', 'optimizer _LAZY_ATTRS traverse_scope resolves to walk_in_scope'),
    ('lazy-table', O + '__init__.py', '"find_all_in_scope": ("sqlglot.optimizer.scope", "find_all_in_scope")', '"find_all_in_scope": ("sqlglot.optimizer.scope", "find_in_scope")', 'optimizer _LAZY_ATTRS find_all_in_scope resolves to find_in_scope'),
    ('lazy-table', O + '__init__.py', '"build_scope": ("sqlglot.optimizer.scope", "build_scope")', '"build_scope": ("sqlglot.optimizer.scope", "traverse_scope")', 'optimizer _LAZY_ATTRS build_scope resolves to traverse_scope'),
    ('metaclass-derived', 'sqlglot/dialects/dialect.py', 'if enum not in ("", "bigquery", "snowflake"):', 'if enum not in ("", "bigquery"):', '_Dialect: Snowflake loses INITCAP_SUPPORTS_CUSTOM_DELIMITERS'),
    ('metaclass-derived', 'sqlglot/dialects/dialect.py', '            *klass.DATE_PART_MAPPING.values(),\n        }', '        }', '_Dialect: VALID_INTERVAL_UNITS drops DATE_PART_MAPPING values operand'),
    ('metaclass-derived', 'sqlglot/generators/hive.py', '        exp.JSONPathSubscript,\n        exp.JSONPathWildcard,\n    }', '        exp.JSONPathWildcard,\n    }', 'Hive SUPPORTED_JSON_PATH_PARTS drops JSONPathSubscript (metaclass pops TRANSFORMS; Spark/Databricks inherit)'),
    ('metaclass-derived', 'sqlglot/dialects/mysql.py', '        STRING_ESCAPES = ["\'", \'"\', "\\\\"]', '        STRING_ESCAPES = ["\'", \'"\']', 'MySQL Tokenizer STRING_ESCAPES drops backslash (dialect STRINGS_SUPPORT_ESCAPED_SEQUENCES derived; Doris/StarRocks inherit)'),
    ('metaclass-derived', 'sqlglot/dialects/hive.py', '        NUMERIC_ESCAPES = {"u": (16, 4, 4, 0xFFFF), "0": (8, 3, 3, 0x7F)}', '        NUMERIC_ESCAPES = {"u": (16, 4, 4, 0xFFFF)}', 'Hive Tokenizer NUMERIC_ESCAPES drops octal (dialect ESCAPED_SEQUENCES derived; Spark/Databricks inherit)'),
    ('module-tuple-order', O + 'optimizer.py', '    eliminate_joins,\n    eliminate_ctes,\n', '    eliminate_ctes,\n    eliminate_joins,\n', 'optimizer RULES swaps eliminate_joins and eliminate_ctes'),
    ('module-tuple-order', O + 'optimizer.py', '    canonicalize,\n    simplify,\n', '    simplify,\n    canonicalize,\n', 'optimizer RULES swaps canonicalize and simplify'),
    ('module-tuple-order', O + 'optimizer.py', '    pushdown_projections,\n    normalize,\n', '    normalize,\n    pushdown_projections,\n', 'optimizer RULES swaps pushdown_projections and normalize'),
    ('hash-protocol', 'sqlglot/dialects/dialect.py', '        return hash(cls.__name__.lower())', '        return hash(cls.__name__)', '_Dialect.__hash__ drops lower() (eq with lowercase name strings)'),
]:
    replace(kind, label, path, old, new)

# 5b. Import-time set operators in dialect parser class bodies that child
# dialects inherit (Doris/StarRocks/SingleStore, Fabric, Trino/Athena).
P_ = 'sqlglot/parsers/'
for path, old, new, label in [
    (P_ + 'mysql.py', 'ID_VAR_TOKENS = parser.Parser.ID_VAR_TOKENS - {TokenType.STRAIGHT_JOIN}', 'ID_VAR_TOKENS = parser.Parser.ID_VAR_TOKENS | {TokenType.STRAIGHT_JOIN}', 'MySQLParser ID_VAR_TOKENS set difference becomes union (STRAIGHT_JOIN; children inherit)'),
    (P_ + 'tsql.py', 'ID_VAR_TOKENS = (parser.Parser.ID_VAR_TOKENS | {TokenType.RETURNING}) - {TokenType.BEGIN}', 'ID_VAR_TOKENS = parser.Parser.ID_VAR_TOKENS | {TokenType.RETURNING}', 'TSQLParser ID_VAR_TOKENS drops the BEGIN difference operand (Fabric inherits)'),
    (P_ + 'tsql.py', 'COMMENT_TABLE_ALIAS_TOKENS = parser.Parser.COMMENT_TABLE_ALIAS_TOKENS - {TokenType.BEGIN}', 'COMMENT_TABLE_ALIAS_TOKENS = parser.Parser.COMMENT_TABLE_ALIAS_TOKENS | {TokenType.BEGIN}', 'TSQLParser COMMENT_TABLE_ALIAS_TOKENS difference becomes union (Fabric inherits)'),
    (P_ + 'presto.py', 'TABLE_ALIAS_TOKENS = parser.Parser.TABLE_ALIAS_TOKENS | {', 'TABLE_ALIAS_TOKENS = parser.Parser.TABLE_ALIAS_TOKENS - {', 'PrestoParser TABLE_ALIAS_TOKENS union becomes difference (Trino/Athena inherit)'),
    (P_ + 'snowflake.py', 'COLON_PLACEHOLDER_TOKENS = ID_VAR_TOKENS | {TokenType.NUMBER}', 'COLON_PLACEHOLDER_TOKENS = ID_VAR_TOKENS - {TokenType.NUMBER}', 'SnowflakeParser COLON_PLACEHOLDER_TOKENS union becomes difference (derived from ID_VAR_TOKENS in the class body)'),
    (P_ + 'snowflake.py', 'TIMESTAMPS = parser.Parser.TIMESTAMPS - {TokenType.TIME}', 'TIMESTAMPS = parser.Parser.TIMESTAMPS | {TokenType.TIME}', 'SnowflakeParser TIMESTAMPS difference becomes union'),
]:
    replace('class-body-operator', label, path, old, new)

# 8. Parser tables read through dialect.parser_class with no parser instance
# (anonymize.py checks FUNCTIONS and FUNCTION_PARSERS on the class).
for path, old, new, label in [
    (P_ + 'trino.py', '        "JSON_VALUE": lambda self: self._parse_json_value(),\n        "LISTAGG": lambda self: self._parse_string_agg(),\n', '        "JSON_VALUE": lambda self: self._parse_json_value(),\n', 'TrinoParser FUNCTION_PARSERS drops LISTAGG (AthenaParser inherits; anonymize reads the class)'),
]:
    replace('class-read-no-instance', label, path, old, new)

# Scoped labels: the files these edits plausibly break. Failing ids are lower
# bounds; a failure in a scoped file outside the selection is a real miss.
FULL = {'t52x004', 't52x016', 't52x018', 't52x020', 't52x022', 't52x026', 't52x027', 't52x028'}
for cid in FULL:
    manifest[cid].update(tests=['tests'], label_scope='full suite')
SCOPE = ['tests/dialects', 'tests/test_transpile.py', 'tests/test_optimizer.py']
for cid, m in manifest.items():
    if m['kind'] in ('var-len-flag', 'arg-types-required', 'sql-names-order', 'module-const-import', 'lazy-table', 'metaclass-derived', 'module-tuple-order', 'hash-protocol', 'table-operator', 'class-body-operator', 'class-read-no-instance') and m['description'] != 'hive typing drops base metadata operand':
        m.setdefault('tests', ['tests'])
        m.setdefault('label_scope', 'full suite')
        continue
    m.setdefault('tests', SCOPE)
    m.setdefault('label_scope', 'scoped to ' + ', '.join(m['tests']) + '; failing ids are lower bounds')
json.dump({'commits': manifest}, open(OUT / 'manifest.json', 'w'), indent=1)
print(len(manifest), 'mutants')
