| Mutant | Class | Change | Failing | c/nostr selects | c/nostr s | main s | w/t56 = c/nostr | Miss (c/nostr) |
|---|---:|---|---:|---:|---:|---:|---|---|
| t56x036 | 1 | MySQL TIME_MAPPING value of %W changed %A to %a (Presto aliases MySQL.TIME_MAPPING) | unlabeled | 444 | 12.7 | 13.4 | yes | - |
| t56x038 | 1 | ClickHouse NULL_ORDERING nulls_are_last changed to nulls_are_large | unlabeled | 150 | 11.5 | 36.8 | yes | - |
| t56x039 | 1 | Drill NULL_ORDERING nulls_are_last changed to nulls_are_small | unlabeled | 36 | 10.7 | 36.8 | yes | - |
| t56x040 | 1 | Doris TIME_FORMAT changed to include milliseconds | unlabeled | 45 | 10.2 | 36.8 | yes | - |
| t56x041 | 1 | ClickHouse TIME_MAPPING value of %i changed %M to %m | unlabeled | 150 | 11.5 | 12.9 | yes | - |
| t56x037 | 2 | BigQuery TIME_MAPPING value of %e changed %-d to %d | unlabeled | 293 | 12.7 | 12.7 | yes | - |
| t56x042 | 2 | BigQuery TIME_MAPPING key %E6S renamed %E3S | unlabeled | 293 | 12.7 | 13.9 | yes | - |
| t56x043 | 2 | ClickHouse TIME_MAPPING key %W renamed %a | unlabeled | 150 | 11.5 | 12.9 | yes | - |
| t56x044 | 2 | temporal.py arg_types key unit renamed part (this, unit expression at line 352) | unlabeled | 13 | 5.4 | 36.8 | yes | - |
| t56x045 | 3 | base FUNCTIONS key SORT_ARRAY renamed SORTARRAY (value build_sort_array) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x046 | 3 | base FUNCTIONS key ARRAY_APPEND renamed ARRAY_PUSH_BACK (value build_array_append) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x047 | 3 | MySQL FUNCTIONS key STR_TO_DATE renamed STRTODATE (value _str_to_date) | unlabeled | 298 | 9.8 | 36.8 | yes | - |
| t56x048 | 3 | BigQuery FUNCTIONS key TO_HEX renamed TOHEX (value _build_to_hex) | unlabeled | 287 | 10.4 | 36.8 | yes | - |
| t56x049 | 3 | executor ENV key STRPOSITION renamed STR_POSITION (value str_position) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x050 | 3 | ClickHouse Tokenizer KEYWORDS key UINT8 renamed UINT08 | unlabeled | 150 | 11.5 | 36.8 | yes | - |
| t56x065 | 3 | MySQL Tokenizer KEYWORDS key IGNORE renamed IGNORED (StarRocks pops "IGNORE" at import) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x000 | 4 | base FUNCTION_PARSERS key GAP_FILL renamed GAPFILL | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x001 | 4 | base FUNCTION_PARSERS key JSON_OBJECTAGG renamed JSON_OBJECT_AGG | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x002 | 4 | base FUNCTION_PARSERS key WEIGHT_STRING renamed WEIGHTSTRING | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x003 | 4 | base NO_PAREN_FUNCTION_PARSERS key CONNECT_BY_ROOT renamed CONNECTBYROOT | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x004 | 4 | base FUNCTIONS key ARRAY_INTERSECTION renamed ARRAY_INTERSECT_ALL | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x005 | 4 | base FUNCTIONS key DATE_TO_DATE_STR renamed DATE_TO_DATESTR | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x006 | 4 | Trino FUNCTION_PARSERS key LISTAGG renamed LIST_AGG (Athena inherits; anonymize reads it) | 4 | 95 | 7.0 | 36.8 | yes | no |
| t56x007 | 4 | Oracle FUNCTION_PARSERS key LISTAGG renamed LIST_AGG | 1 | 98 | 6.1 | 36.8 | yes | no |
| t56x008 | 4 | Snowflake FUNCTION_PARSERS key LISTAGG renamed LIST_AGG | 1 | 276 | 9.1 | 36.8 | yes | no |
| t56x009 | 4 | Hive FUNCTIONS key GET_JSON_OBJECT renamed GET_JSON (Spark2/Spark/Databricks inherit) | 7 | 307 | 10.9 | 36.8 | yes | no |
| t56x010 | 4 | Hive FUNCTIONS key DATE_FORMAT renamed DATEFORMAT (Spark family inherits) | 2 | 307 | 10.9 | 36.8 | yes | no |
| t56x011 | 4 | MySQL FUNCTIONS DATE_FORMAT lambda reads Dialect["mysql"] changed to Dialect["doris"] | 0 | 298 | 9.8 | 36.8 | yes | no |
| t56x012 | 4 | Snowflake FUNCTIONS key ARRAY_TO_STRING renamed ARRAY_TOSTRING | 2 | 323 | 9.6 | 36.8 | yes | no |
| t56x013 | 4 | Postgres FUNCTION_PARSERS key DATE_PART renamed DATEPART (Redshift/Materialize/RisingWave inherit) | 4 | 224 | 10.0 | 36.8 | yes | no |
| t56x014 | 4 | Postgres FUNCTION_PARSERS key JSONB_EXISTS renamed JSONB_KEY_EXISTS | 1 | 224 | 10.0 | 36.8 | yes | no |
| t56x015 | 4 | Postgres PROPERTY_PARSERS key TABLESPACE renamed TABLE_SPACE | 1 | 219 | 10.0 | 36.8 | yes | no |
| t56x016 | 4 | Oracle NO_PAREN_FUNCTION_PARSERS key SYSDATE renamed SYS_DATE | 2 | 93 | 6.1 | 36.8 | yes | no |
| t56x017 | 4 | Oracle FUNCTION_PARSERS key TO_NUMBER renamed TONUMBER | 1 | 98 | 6.1 | 36.8 | yes | no |
| t56x018 | 4 | Doris PROPERTY_PARSERS key REFRESH renamed REFRESH_MODE | 0 | 27 | 2.8 | 36.8 | yes | no |
| t56x019 | 4 | Databricks NO_PAREN_FUNCTION_PARSERS key CURDATE renamed CUR_DATE | 1 | 108 | 6.9 | 36.8 | yes | no |
| t56x020 | 4 | SingleStore FUNCTIONS build_formatted_time(exp.StrToDate, "mysql") dialect name changed to "hive" | 2 | 117 | 6.7 | 36.8 | yes | no |
| t56x021 | 4 | Databricks generator TRANSFORMS date_delta_sql("DATEADD") changed to "DATE_ADD" | 1 | 158 | 10.7 | 36.8 | yes | no |
| t56x022 | 4 | Drill generator TRANSFORMS date_add_sql("ADD") changed to "PLUS" | 1 | 32 | 10.7 | 36.8 | yes | no |
| t56x023 | 4 | ClickHouse generator TRANSFORMS _datetime_delta_sql("TIMESTAMP_ADD") changed to "TIMESTAMPADD" | 1 | 123 | 11.3 | 36.8 | yes | no |
| t56x024 | 4 | BigQuery generator TRANSFORMS date_add_interval_sql("DATETIME", "ADD") unit DATETIME changed to TIMESTAMP | 1 | 226 | 12.2 | 36.8 | yes | no |
| t56x025 | 4 | BigQuery generator TRANSFORMS lambda self.func("REGEXP_EXTRACT_ALL") changed to "REGEXP_EXTRACTALL" | 1 | 226 | 12.2 | 36.8 | yes | no |
| t56x026 | 4 | DuckDB annotator DateBin _annotate_by_args(e, "expression") changed to "origin" | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x027 | 4 | Snowflake annotator ConcatWs _annotate_by_args(e, "expressions") changed to "this" | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x028 | 4 | Spark2 annotator Concat _annotate_by_similar_args(.., "expressions") changed to "this" | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x029 | 4 | base annotator _annotate_by_args(e, "this", "expressions") second arg changed to "expression" | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x030 | 4 | executor ENV key COALESCE renamed NVL (lambda value; the executor resolves names at run time) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x031 | 4 | executor ENV key FIRST renamed FIRST_VALUE (lambda value) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x032 | 4 | executor ENV key IF renamed IIF (lambda value) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x033 | 4 | Postgres FUNCTIONS JSON_EXTRACT_PATH_TEXT key renamed JSON_EXTRACT_PATH_TXT (value is a build_ call) | 4 | 285 | 10.4 | 36.8 | yes | no |
| t56x034 | 4 | Hive FUNCTIONS key LAST_VALUE renamed LASTVALUE (value build_with_ignore_nulls call) | 2 | 307 | 10.9 | 36.8 | yes | no |
| t56x035 | 4 | executor ENV key ORD renamed ASCII (value null_if_any(ord) call) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x062 | 4 | generator.py AFTER_HAVING_MODIFIER_TRANSFORMS key windows renamed window (BigQuery subscripts ["windows"] at import) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x063 | 4 | base FUNCTION_PARSERS key TRY_CAST renamed TRYCAST (Teradata subscripts ["TRY_CAST"] at import) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x064 | 4 | Snowflake FUNCTIONS key ARRAY_GENERATE_RANGE renamed ARRAY_GENERATE_RANGES (generator subscripts it at run time) | 3 | 323 | 9.6 | 36.8 | yes | no |
| t56x066 | 4 | SQLite FUNCTIONS DATETIME lambda Anonymous(this="DATETIME") changed to "DATE_TIME" | 1 | 155 | 8.1 | 36.8 | yes | no |
| t56x067 | 4 | MySQL FUNCTIONS TO_DAYS lambda epoch literal 0000-01-01 changed to 0001-01-01 | 1 | 298 | 9.8 | 9.8 | yes | no |
| t56x068 | 4 | DuckDB generator TRANSFORMS rename_func("LIST_FILTER") changed to "ARRAY_FILTER" | 7 | 377 | 27.5 | 36.8 | yes | no |
| t56x051 | 5 | Presto RESERVED_KEYWORDS member alter renamed analyze (Trino/Athena inherit) | unlabeled | 180 | 8.5 | 8.5 | yes | - |
| t56x052 | 5 | Redshift RESERVED_KEYWORDS member aes128 renamed aes192 | unlabeled | 87 | 7.9 | 7.9 | yes | - |
| t56x053 | 5 | array.py ArrayContains _sql_names ARRAY_HAS renamed ARRAY_HAS_ANY | unlabeled | 11 | 6.3 | 36.8 | yes | - |
| t56x054 | 5 | array.py ArraySize _sql_names ARRAY_LENGTH renamed ARRAY_LEN | unlabeled | 27 | 8.6 | 36.8 | yes | - |
| t56x055 | 5 | DuckDB FUNCTIONS_WITH_ALIASED_ARGS member STRUCT_PACK renamed ROW_PACK | unlabeled | 247 | 12.5 | 36.8 | yes | - |
| t56x056 | 6 | Hive generator SAFE_JSON_PATH_KEY_RE drops the hyphen (Spark family inherits) | unlabeled | 304 | 12.7 | 36.8 | yes | - |
| t56x057 | 6 | builders.py INTERVAL_STRING_RE unit group also allows underscores | unlabeled | 55 | 25.5 | 36.8 | yes | - |
| t56x058 | 6 | generator.properties default sep ", " changed to "," | unlabeled | 1347 | 27.6 | 27.6 | yes | - |
| t56x059 | 6 | lineage.py logger name sqlglot changed to sqlglot.lineage | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x060 | 6 | DuckDB generator TIMEZONE_PATTERN minutes optional | unlabeled | 5 | 2.7 | 2.7 | yes | - |
| t56x061 | 6 | generator.table_sql default sep " AS " changed to " as " | unlabeled | 1347 | 27.6 | 27.6 | yes | - |
| t56x069 | 6 | DuckDB generator _SEQ_BASE template parsed at import: ORDER BY 1 dropped (still parses) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x070 | 6 | DuckDB generator _SEQ_UNSIGNED template parsed at import loses an operand (parse error at import) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x071 | 6 | Postgres Tokenizer pops "DIVIDE" instead of "DIV" (no such key: KeyError at import) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x072 | 6 | Postgres Tokenizer pops "OFFSET" instead of "DIV" (key exists: OFFSET stops being a keyword) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
| t56x073 | 6 | DuckDB dialect DATE_PART_MAPPING.pop("WEEKDAY") changed to "WEEKDAY_ISO" (no such key: KeyError at import) | unlabeled | 1620 | 36.8 | 36.8 | yes | - |
