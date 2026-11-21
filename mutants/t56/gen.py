"""t56: string edits against c/nostr (string-edit fallback off).

Each mutant is one realistic edit inside a string literal that adds a word
absent from the old file. Class numbers follow t54's census_string_class
(1 dict value or plain constant, 2 key of a constant, 3 key of a name,
4 callable tables: lambda strings, call arguments in tables, keys of calls or
lambdas, 5 collection member, 6 import-time call argument or default)."""
import difflib, json
from pathlib import Path
SRC = Path('/home/benmross/herald/projects/blast-radius/work/sqlglot')
OUT = Path(__file__).resolve().parent
(OUT / 'commits').mkdir(exist_ok=True)
manifest = {}


def replace(cls, label, path, old, new, nth=1):
    a = (SRC / path).read_text()
    assert a.count(old) >= nth, (path, old, a.count(old))
    if nth == 1:
        assert a.count(old) == 1, (path, old, a.count(old))
    i = -1
    for _ in range(nth):
        i = a.index(old, i + 1)
    b = a[:i] + new + a[i + len(old):]
    assert a != b
    compile(b, path, 'exec')
    cid = f't56x{len(manifest):03d}'
    patch = f'diff --git a/{path} b/{path}\n' + ''.join(difflib.unified_diff(
        a.splitlines(True), b.splitlines(True), fromfile='a/' + path, tofile='b/' + path))
    (OUT / 'commits' / f'{cid}.patch').write_text(patch)
    manifest[cid] = {'kind': f'class{cls}', 'description': label, 'paths': [path]}


P, G, D, T = 'sqlglot/parsers/', 'sqlglot/generators/', 'sqlglot/dialects/', 'sqlglot/typing/'
# ---- class 4: callable tables
replace(4, 'base FUNCTION_PARSERS key GAP_FILL renamed GAPFILL', 'sqlglot/parser.py',
        '"GAP_FILL": lambda self: self._parse_gap_fill(),', '"GAPFILL": lambda self: self._parse_gap_fill(),')
replace(4, 'base FUNCTION_PARSERS key JSON_OBJECTAGG renamed JSON_OBJECT_AGG', 'sqlglot/parser.py',
        '"JSON_OBJECTAGG": lambda self:', '"JSON_OBJECT_AGG": lambda self:')
replace(4, 'base FUNCTION_PARSERS key WEIGHT_STRING renamed WEIGHTSTRING', 'sqlglot/parser.py',
        '"WEIGHT_STRING": lambda self:', '"WEIGHTSTRING": lambda self:')
replace(4, 'base NO_PAREN_FUNCTION_PARSERS key CONNECT_BY_ROOT renamed CONNECTBYROOT', 'sqlglot/parser.py',
        '"CONNECT_BY_ROOT": lambda self:', '"CONNECTBYROOT": lambda self:')
replace(4, 'base FUNCTIONS key ARRAY_INTERSECTION renamed ARRAY_INTERSECT_ALL', 'sqlglot/parser.py',
        '"ARRAY_INTERSECTION": lambda args:', '"ARRAY_INTERSECT_ALL": lambda args:')
replace(4, 'base FUNCTIONS key DATE_TO_DATE_STR renamed DATE_TO_DATESTR', 'sqlglot/parser.py',
        '"DATE_TO_DATE_STR": lambda args:', '"DATE_TO_DATESTR": lambda args:')
replace(4, 'Trino FUNCTION_PARSERS key LISTAGG renamed LIST_AGG (Athena inherits; anonymize reads it)', P + 'trino.py',
        '"LISTAGG": lambda self:', '"LIST_AGG": lambda self:')
replace(4, 'Oracle FUNCTION_PARSERS key LISTAGG renamed LIST_AGG', P + 'oracle.py',
        '"LISTAGG": lambda self:', '"LIST_AGG": lambda self:')
replace(4, 'Snowflake FUNCTION_PARSERS key LISTAGG renamed LIST_AGG', P + 'snowflake.py',
        '"LISTAGG": lambda self: self._parse_listagg(),', '"LIST_AGG": lambda self: self._parse_listagg(),')
replace(4, 'Hive FUNCTIONS key GET_JSON_OBJECT renamed GET_JSON (Spark2/Spark/Databricks inherit)', P + 'hive.py',
        '"GET_JSON_OBJECT": lambda args, dialect:', '"GET_JSON": lambda args, dialect:')
replace(4, 'Hive FUNCTIONS key DATE_FORMAT renamed DATEFORMAT (Spark family inherits)', P + 'hive.py',
        '"DATE_FORMAT": lambda args, dialect:', '"DATEFORMAT": lambda args, dialect:')
replace(4, 'MySQL FUNCTIONS DATE_FORMAT lambda reads Dialect["mysql"] changed to Dialect["doris"]', P + 'mysql.py',
        'format=Dialect["mysql"].format_time(seq_get(args, 1)),', 'format=Dialect["doris"].format_time(seq_get(args, 1)),')
replace(4, 'Snowflake FUNCTIONS key ARRAY_TO_STRING renamed ARRAY_TOSTRING', P + 'snowflake.py',
        '"ARRAY_TO_STRING": lambda args:', '"ARRAY_TOSTRING": lambda args:')
replace(4, 'Postgres FUNCTION_PARSERS key DATE_PART renamed DATEPART (Redshift/Materialize/RisingWave inherit)', P + 'postgres.py',
        '"DATE_PART": lambda self:', '"DATEPART": lambda self:')
replace(4, 'Postgres FUNCTION_PARSERS key JSONB_EXISTS renamed JSONB_KEY_EXISTS', P + 'postgres.py',
        '"JSONB_EXISTS": lambda self:', '"JSONB_KEY_EXISTS": lambda self:')
replace(4, 'Postgres PROPERTY_PARSERS key TABLESPACE renamed TABLE_SPACE', P + 'postgres.py',
        '"TABLESPACE": lambda self:', '"TABLE_SPACE": lambda self:')
replace(4, 'Oracle NO_PAREN_FUNCTION_PARSERS key SYSDATE renamed SYS_DATE', P + 'oracle.py',
        '"SYSDATE": lambda self:', '"SYS_DATE": lambda self:')
replace(4, 'Oracle FUNCTION_PARSERS key TO_NUMBER renamed TONUMBER', P + 'oracle.py',
        '"TO_NUMBER": lambda self:', '"TONUMBER": lambda self:')
replace(4, 'Doris PROPERTY_PARSERS key REFRESH renamed REFRESH_MODE', P + 'doris.py',
        '"REFRESH": lambda self:', '"REFRESH_MODE": lambda self:')
replace(4, 'Databricks NO_PAREN_FUNCTION_PARSERS key CURDATE renamed CUR_DATE', P + 'databricks.py',
        '"CURDATE": lambda self:', '"CUR_DATE": lambda self:')
replace(4, 'SingleStore FUNCTIONS build_formatted_time(exp.StrToDate, "mysql") dialect name changed to "hive"', P + 'singlestore.py',
        '"STR_TO_DATE": build_formatted_time(exp.StrToDate, "mysql"),', '"STR_TO_DATE": build_formatted_time(exp.StrToDate, "hive"),')
replace(4, 'Databricks generator TRANSFORMS date_delta_sql("DATEADD") changed to "DATE_ADD"', G + 'databricks.py',
        'exp.DateAdd: date_delta_sql("DATEADD"),', 'exp.DateAdd: date_delta_sql("DATE_ADD"),')
replace(4, 'Drill generator TRANSFORMS date_add_sql("ADD") changed to "PLUS"', G + 'drill.py',
        'exp.DateAdd: date_add_sql("ADD"),', 'exp.DateAdd: date_add_sql("PLUS"),')
replace(4, 'ClickHouse generator TRANSFORMS _datetime_delta_sql("TIMESTAMP_ADD") changed to "TIMESTAMPADD"', G + 'clickhouse.py',
        'exp.TimestampAdd: _datetime_delta_sql("TIMESTAMP_ADD"),', 'exp.TimestampAdd: _datetime_delta_sql("TIMESTAMPADD"),')
replace(4, 'BigQuery generator TRANSFORMS date_add_interval_sql("DATETIME", "ADD") unit DATETIME changed to TIMESTAMP', G + 'bigquery.py',
        'exp.DatetimeAdd: date_add_interval_sql("DATETIME", "ADD"),', 'exp.DatetimeAdd: date_add_interval_sql("TIMESTAMP", "ADD"),')
replace(4, 'BigQuery generator TRANSFORMS lambda self.func("REGEXP_EXTRACT_ALL") changed to "REGEXP_EXTRACTALL"', G + 'bigquery.py',
        'self.func("REGEXP_EXTRACT_ALL", e.this, e.expression)', 'self.func("REGEXP_EXTRACTALL", e.this, e.expression)')
replace(4, 'DuckDB annotator DateBin _annotate_by_args(e, "expression") changed to "origin"', T + 'duckdb.py',
        'exp.DateBin: {"annotator": lambda self, e: self._annotate_by_args(e, "expression")},',
        'exp.DateBin: {"annotator": lambda self, e: self._annotate_by_args(e, "origin")},')
replace(4, 'Snowflake annotator ConcatWs _annotate_by_args(e, "expressions") changed to "this"', T + 'snowflake.py',
        'exp.ConcatWs: {"annotator": lambda self, e: self._annotate_by_args(e, "expressions")},',
        'exp.ConcatWs: {"annotator": lambda self, e: self._annotate_by_args(e, "this")},')
replace(4, 'Spark2 annotator Concat _annotate_by_similar_args(.., "expressions") changed to "this"', T + 'spark2.py',
        'exp.Concat: {"annotator": lambda self, e: _annotate_by_similar_args(self, e, "expressions")},',
        'exp.Concat: {"annotator": lambda self, e: _annotate_by_similar_args(self, e, "this")},')
replace(4, 'base annotator _annotate_by_args(e, "this", "expressions") second arg changed to "expression"', T + '__init__.py',
        'expr_type: {"annotator": lambda self, e: self._annotate_by_args(e, "this", "expressions")}',
        'expr_type: {"annotator": lambda self, e: self._annotate_by_args(e, "this", "expression")}')
replace(4, 'executor ENV key COALESCE renamed NVL (lambda value; the executor resolves names at run time)', 'sqlglot/executor/env.py',
        '"COALESCE": lambda *args:', '"NVL": lambda *args:')
replace(4, 'executor ENV key FIRST renamed FIRST_VALUE (lambda value)', 'sqlglot/executor/env.py',
        '"FIRST": lambda acc:', '"FIRST_VALUE": lambda acc:')
replace(4, 'executor ENV key IF renamed IIF (lambda value)', 'sqlglot/executor/env.py',
        '"IF": lambda predicate, true, false:', '"IIF": lambda predicate, true, false:')
replace(4, 'Postgres FUNCTIONS JSON_EXTRACT_PATH_TEXT key renamed JSON_EXTRACT_PATH_TXT (value is a build_ call)', P + 'postgres.py',
        '"JSON_EXTRACT_PATH_TEXT": build_json_extract_path(exp.JSONExtractScalar),', '"JSON_EXTRACT_PATH_TXT": build_json_extract_path(exp.JSONExtractScalar),')
replace(4, 'Hive FUNCTIONS key LAST_VALUE renamed LASTVALUE (value build_with_ignore_nulls call)', P + 'hive.py',
        '"LAST_VALUE": build_with_ignore_nulls(exp.LastValue),', '"LASTVALUE": build_with_ignore_nulls(exp.LastValue),')
replace(4, 'executor ENV key ORD renamed ASCII (value null_if_any(ord) call)', 'sqlglot/executor/env.py',
        '"ORD": null_if_any(ord),', '"ASCII": null_if_any(ord),')
# ---- class 1: dict values and plain constants
replace(1, 'MySQL TIME_MAPPING value of %W changed %A to %a (Presto aliases MySQL.TIME_MAPPING)', D + 'mysql.py',
        '"%W": "%A",', '"%W": "%a",')
replace(1, 'BigQuery TIME_MAPPING value of %e changed %-d to %d', D + 'bigquery.py',
        '"%e": "%-d",', '"%e": "%d",')
replace(1, 'ClickHouse NULL_ORDERING nulls_are_last changed to nulls_are_large', D + 'clickhouse.py',
        'NULL_ORDERING = "nulls_are_last"', 'NULL_ORDERING = "nulls_are_large"')
replace(1, 'Drill NULL_ORDERING nulls_are_last changed to nulls_are_small', D + 'drill.py',
        'NULL_ORDERING = "nulls_are_last"', 'NULL_ORDERING = "nulls_are_small"')
replace(1, 'Doris TIME_FORMAT changed to include milliseconds', D + 'doris.py',
        "TIME_FORMAT = \"'yyyy-MM-dd HH:mm:ss'\"", "TIME_FORMAT = \"'yyyy-MM-dd HH:mm:ss.SSS'\"")
replace(1, 'ClickHouse TIME_MAPPING value of %i changed %M to %m', D + 'clickhouse.py',
        '"%i": "%M",', '"%i": "%m",')
# ---- class 2: keys of constants
replace(2, 'BigQuery TIME_MAPPING key %E6S renamed %E3S', D + 'bigquery.py', '"%E6S": "%S.%f",', '"%E3S": "%S.%f",')
replace(2, 'ClickHouse TIME_MAPPING key %W renamed %a', D + 'clickhouse.py', '"%W": "%A",', '"%a": "%A",')
replace(2, 'temporal.py arg_types key unit renamed part (this, unit expression at line 352)', 'sqlglot/expressions/temporal.py',
        'arg_types = {"this": True, "unit": False}', 'arg_types = {"this": True, "part": False}')
# ---- class 3: keys of names
replace(3, 'base FUNCTIONS key SORT_ARRAY renamed SORTARRAY (value build_sort_array)', 'sqlglot/parser.py',
        '"SORT_ARRAY": build_sort_array,', '"SORTARRAY": build_sort_array,')
replace(3, 'base FUNCTIONS key ARRAY_APPEND renamed ARRAY_PUSH_BACK (value build_array_append)', 'sqlglot/parser.py',
        '"ARRAY_APPEND": build_array_append,', '"ARRAY_PUSH_BACK": build_array_append,')
replace(3, 'MySQL FUNCTIONS key STR_TO_DATE renamed STRTODATE (value _str_to_date)', P + 'mysql.py',
        '"STR_TO_DATE": _str_to_date,', '"STRTODATE": _str_to_date,')
replace(3, 'BigQuery FUNCTIONS key TO_HEX renamed TOHEX (value _build_to_hex)', P + 'bigquery.py',
        '"TO_HEX": _build_to_hex,', '"TOHEX": _build_to_hex,')
replace(3, 'executor ENV key STRPOSITION renamed STR_POSITION (value str_position)', 'sqlglot/executor/env.py',
        '"STRPOSITION": str_position,', '"STR_POSITION": str_position,')
replace(3, 'ClickHouse Tokenizer KEYWORDS key UINT8 renamed UINT08', D + 'clickhouse.py',
        '"UINT8": TokenType.UTINYINT,', '"UINT08": TokenType.UTINYINT,')
# ---- class 5: collection members
replace(5, 'Presto RESERVED_KEYWORDS member alter renamed analyze (Trino/Athena inherit)', G + 'presto.py',
        '        "alter",\n        "and",', '        "analyze",\n        "and",')
replace(5, 'Redshift RESERVED_KEYWORDS member aes128 renamed aes192', G + 'redshift.py',
        '        "aes128",', '        "aes192",')
replace(5, 'array.py ArrayContains _sql_names ARRAY_HAS renamed ARRAY_HAS_ANY', 'sqlglot/expressions/array.py',
        '_sql_names = ["ARRAY_CONTAINS", "ARRAY_HAS"]', '_sql_names = ["ARRAY_CONTAINS", "ARRAY_HAS_ANY"]')
replace(5, 'array.py ArraySize _sql_names ARRAY_LENGTH renamed ARRAY_LEN', 'sqlglot/expressions/array.py',
        '_sql_names = ["ARRAY_SIZE", "ARRAY_LENGTH"]', '_sql_names = ["ARRAY_SIZE", "ARRAY_LEN"]')
replace(5, 'DuckDB FUNCTIONS_WITH_ALIASED_ARGS member STRUCT_PACK renamed ROW_PACK', P + 'duckdb.py',
        '"STRUCT_PACK"}', '"ROW_PACK"}')
# ---- class 6: import-time call arguments and defaults
replace(6, 'Hive generator SAFE_JSON_PATH_KEY_RE drops the hyphen (Spark family inherits)', G + 'hive.py',
        'SAFE_JSON_PATH_KEY_RE = re.compile(r"^[_\\-a-zA-Z][\\-\\w]*$")', 'SAFE_JSON_PATH_KEY_RE = re.compile(r"^[_a-zA-Z][\\w]*$")')
replace(6, 'builders.py INTERVAL_STRING_RE unit group also allows underscores', 'sqlglot/expressions/builders.py',
        'INTERVAL_STRING_RE = re.compile(r"\\s*(-?[0-9]+(?:\\.[0-9]+)?)\\s*([a-zA-Z]+)\\s*")',
        'INTERVAL_STRING_RE = re.compile(r"\\s*(-?[0-9]+(?:\\.[0-9]+)?)\\s*([a-zA-Z_]+)\\s*")')
replace(6, 'generator.properties default sep ", " changed to ","', 'sqlglot/generator.py',
        '        sep: str = ", ",\n        suffix: str = "",', '        sep: str = ",",\n        suffix: str = "",')
replace(6, 'lineage.py logger name sqlglot changed to sqlglot.lineage', 'sqlglot/lineage.py',
        'logger = logging.getLogger("sqlglot")', 'logger = logging.getLogger("sqlglot.lineage")')
replace(6, 'DuckDB generator TIMEZONE_PATTERN minutes optional', G + 'duckdb.py',
        'TIMEZONE_PATTERN = re.compile(r":\\d{2}.*?[+\\-]\\d{2}(?::\\d{2})?")', 'TIMEZONE_PATTERN = re.compile(r":\\d{2}.*?[+\\-]\\d{2}(?::?\\d{2})?")')
replace(6, 'generator.table_sql default sep " AS " changed to " as "', 'sqlglot/generator.py',
        'def table_sql(self, expression: exp.Table, sep: str = " AS ") -> str:', 'def table_sql(self, expression: exp.Table, sep: str = " as ") -> str:')

# ---- reader probes for the retired/kept unit tests (subscript, pop and getattr readers)
replace(4, 'generator.py AFTER_HAVING_MODIFIER_TRANSFORMS key windows renamed window (BigQuery subscripts ["windows"] at import)', 'sqlglot/generator.py',
        'AFTER_HAVING_MODIFIER_TRANSFORMS: dict[str, t.Any] = {\n    "windows": lambda self, e: (',
        'AFTER_HAVING_MODIFIER_TRANSFORMS: dict[str, t.Any] = {\n    "window": lambda self, e: (')
replace(4, 'base FUNCTION_PARSERS key TRY_CAST renamed TRYCAST (Teradata subscripts ["TRY_CAST"] at import)', 'sqlglot/parser.py',
        '"TRY_CAST": lambda self: self._parse_cast(False, safe=True),', '"TRYCAST": lambda self: self._parse_cast(False, safe=True),')
replace(4, 'Snowflake FUNCTIONS key ARRAY_GENERATE_RANGE renamed ARRAY_GENERATE_RANGES (generator subscripts it at run time)', P + 'snowflake.py',
        '"ARRAY_GENERATE_RANGE": lambda args:', '"ARRAY_GENERATE_RANGES": lambda args:')
replace(3, 'MySQL Tokenizer KEYWORDS key IGNORE renamed IGNORED (StarRocks pops "IGNORE" at import)', D + 'mysql.py',
        '"IGNORE": TokenType.IGNORE,', '"IGNORED": TokenType.IGNORE,')

replace(4, 'SQLite FUNCTIONS DATETIME lambda Anonymous(this="DATETIME") changed to "DATE_TIME"', P + 'sqlite.py',
        '"DATETIME": lambda args: exp.Anonymous(this="DATETIME", expressions=args),', '"DATETIME": lambda args: exp.Anonymous(this="DATE_TIME", expressions=args),')
replace(4, 'MySQL FUNCTIONS TO_DAYS lambda epoch literal 0000-01-01 changed to 0001-01-01', P + 'mysql.py',
        'exp.Literal.string("0000-01-01")', 'exp.Literal.string("0001-01-01")')
replace(4, 'DuckDB generator TRANSFORMS rename_func("LIST_FILTER") changed to "ARRAY_FILTER"', G + 'duckdb.py',
        'exp.ArrayFilter: rename_func("LIST_FILTER"),', 'exp.ArrayFilter: rename_func("ARRAY_FILTER"),')

replace(6, 'DuckDB generator _SEQ_BASE template parsed at import: ORDER BY 1 dropped (still parses)', G + 'duckdb.py',
        '_SEQ_BASE: exp.Expr = exp.maybe_parse("(ROW_NUMBER() OVER (ORDER BY 1) - 1)")', '_SEQ_BASE: exp.Expr = exp.maybe_parse("(ROW_NUMBER() OVER () - 1)")')
replace(6, 'DuckDB generator _SEQ_UNSIGNED template parsed at import loses an operand (parse error at import)', G + 'duckdb.py',
        '_SEQ_UNSIGNED: exp.Expr = exp.maybe_parse(":base % :max_val")', '_SEQ_UNSIGNED: exp.Expr = exp.maybe_parse(":base % :max_val %")')

replace(6, 'Postgres Tokenizer pops "DIVIDE" instead of "DIV" (no such key: KeyError at import)', D + 'postgres.py',
        '        KEYWORDS.pop("DIV")\n', '        KEYWORDS.pop("DIVIDE")\n')
replace(6, 'Postgres Tokenizer pops "OFFSET" instead of "DIV" (key exists: OFFSET stops being a keyword)', D + 'postgres.py',
        '        KEYWORDS.pop("DIV")\n', '        KEYWORDS.pop("OFFSET")\n')
replace(6, 'DuckDB dialect DATE_PART_MAPPING.pop("WEEKDAY") changed to "WEEKDAY_ISO" (no such key: KeyError at import)', D + 'duckdb.py',
        'DATE_PART_MAPPING.pop("WEEKDAY")', 'DATE_PART_MAPPING.pop("WEEKDAY_ISO")')

json.dump({'commits': manifest}, open(OUT / 'manifest.json', 'w'), indent=1)
print(len(manifest))
