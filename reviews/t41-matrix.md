# t41 string-literal labels

| Stratum | Patches | Labeled | Breaking | Main fallbacks | dc91341 misses |
|---|---:|---:|---:|---:|---:|
| a | 14 | 1 | 1 | 14 | 0 |
| b | 12 | 1 | 1 | 12 | 0 |
| c | 11 | 1 | 1 | 11 | 0 |
| d | 10 | 1 | 0 | 10 | 0 |
| e | 13 | 1 | 1 | 13 | 1 |
| f | 12 | 1 | 1 | 12 | 0 |
| g | 10 | 0 | 0 | 10 | 0 |
| all | 82 | 6 | 5 | 82 | 1 |

| Stratum | Patch | Change | Failing | Failing tests | Main selects | Main reason | dc91341 selects | dc91341 miss |
|---|---|---|---:|---|---:|---|---:|---|
| a | t41x000 | presto security property keyword | 3 | TestPresto::test_ddl, TestTrino::test_inline_udf, TestTranspile::test_sql_security | 1620 | sqlglot/generators/presto.py:408 class PrestoGenerator users 200; sqlglot/generators/presto.py: possible import failure, everything | 200 | no |
| a | t41x001 | presto file format property name | unlabeled |  | 1620 | sqlglot/generators/presto.py:370 class PrestoGenerator users 200; sqlglot/generators/presto.py: possible import failure, everything | 200 |  |
| a | t41x002 | presto unix-to-time-str cast type | unlabeled |  | 1620 | sqlglot/generators/presto.py:437 class PrestoGenerator users 200; sqlglot/generators/presto.py: possible import failure, everything | 200 |  |
| a | t41x003 | postgres partitioned-by wording | unlabeled |  | 1620 | sqlglot/generators/postgres.py:408 class PostgresGenerator users 261; sqlglot/generators/postgres.py: possible import failure, everything | 261 |  |
| a | t41x004 | postgres file format keyword | unlabeled |  | 1620 | sqlglot/generators/postgres.py:465 class PostgresGenerator users 261; sqlglot/generators/postgres.py: possible import failure, everything | 261 |  |
| a | t41x005 | postgres tablespace prefix | unlabeled |  | 1620 | sqlglot/generators/postgres.py:466 class PostgresGenerator users 261; sqlglot/generators/postgres.py: possible import failure, everything | 261 |  |
| a | t41x006 | duckdb unix-to-time-str cast type | unlabeled |  | 1620 | sqlglot/generators/duckdb.py:1844 class DuckDBGenerator users 377; sqlglot/generators/duckdb.py: possible import failure, everything | 377 |  |
| a | t41x007 | spark2 iso weekday function | unlabeled |  | 1620 | sqlglot/generators/spark2.py:188 class Spark2Generator users 272; sqlglot/generators/spark2.py: possible import failure, everything | 272 |  |
| a | t41x008 | redshift starts-with operator | unlabeled |  | 1620 | sqlglot/generators/redshift.py:114 class RedshiftGenerator users 96; sqlglot/generators/redshift.py: possible import failure, everything | 96 |  |
| a | t41x009 | presto day-of-week function | unlabeled |  | 1620 | sqlglot/generators/presto.py:363 class PrestoGenerator users 200; sqlglot/generators/presto.py: possible import failure, everything | 200 |  |
| a | t41x010 | presto str-to-date cast type | unlabeled |  | 1620 | sqlglot/generators/presto.py:410 class PrestoGenerator users 200; sqlglot/generators/presto.py: possible import failure, everything | 200 |  |
| a | t41x011 | redshift distkey function name | unlabeled |  | 1620 | sqlglot/generators/redshift.py:91 class RedshiftGenerator users 96; sqlglot/generators/redshift.py: possible import failure, everything | 96 |  |
| a | t41x012 | presto bitwise not name | unlabeled |  | 1620 | sqlglot/generators/presto.py:346 class PrestoGenerator users 200; sqlglot/generators/presto.py: possible import failure, everything | 200 |  |
| a | t41x013 | redshift approx distinct wording | unlabeled |  | 1620 | sqlglot/generators/redshift.py:86 class RedshiftGenerator users 96; sqlglot/generators/redshift.py: possible import failure, everything | 96 |  |
| b | t41x014 | redshift binary type name | 3 | TestDialect::test_cast, TestDialect::test_limit, TestRedshift::test_redshift | 1620 | sqlglot/generators/redshift.py:57 class RedshiftGenerator users 96; sqlglot/generators/redshift.py: possible import failure, everything | 96 | no |
| b | t41x015 | presto int type name | unlabeled |  | 1620 | sqlglot/generators/presto.py:312 class PrestoGenerator users 200; sqlglot/generators/presto.py: possible import failure, everything | 200 |  |
| b | t41x016 | postgres ntz timestamp type | unlabeled |  | 1620 | sqlglot/generators/postgres.py:345 class PostgresGenerator users 261; sqlglot/generators/postgres.py: possible import failure, everything | 261 |  |
| b | t41x017 | duckdb varbinary type name | unlabeled |  | 1620 | sqlglot/generators/duckdb.py:1887 class DuckDBGenerator users 377; sqlglot/generators/duckdb.py: possible import failure, everything | 377 |  |
| b | t41x018 | singlestore linestring type | unlabeled |  | 1620 | sqlglot/generators/singlestore.py:357 class SingleStoreGenerator users 34; sqlglot/generators/singlestore.py: possible import failure, everything | 34 |  |
| b | t41x021 | bigquery binary type | unlabeled |  | 1620 | sqlglot/generators/bigquery.py:566 class BigQueryGenerator users 226; sqlglot/generators/bigquery.py: possible import failure, everything | 226 |  |
| b | t41x022 | mysql hour format value | unlabeled |  | 1620 | sqlglot/dialects/mysql.py:49 class MySQL users 291; sqlglot/dialects/mysql.py: possible import failure, everything | 291 |  |
| b | t41x023 | duckdb iso dow rename | unlabeled |  | 1620 | sqlglot/generators/duckdb.py:1709 class DuckDBGenerator users 377; sqlglot/generators/duckdb.py: possible import failure, everything | 377 |  |
| b | t41x024 | bigquery json bool rename | unlabeled |  | 1620 | sqlglot/generators/bigquery.py:466 class BigQueryGenerator users 226; sqlglot/generators/bigquery.py: possible import failure, everything | 226 |  |
| b | t41x025 | clickhouse current database rename | unlabeled |  | 1620 | sqlglot/generators/clickhouse.py:321 class ClickHouseGenerator users 123; sqlglot/generators/clickhouse.py: possible import failure, everything | 123 |  |
| b | t41x026 | snowflake manhattan distance rename | unlabeled |  | 1620 | sqlglot/generators/snowflake.py:523 class SnowflakeGenerator users 283; sqlglot/generators/snowflake.py: possible import failure, everything | 283 |  |
| b | t41x027 | test leakcheck structural types | unlabeled |  | 1620 | tests/leakcheck.py:92 test module level 0; tests/leakcheck.py: possible import failure, everything | 0 |  |
| c | t41x028 | redshift binary varying keyword | 1 | TestRedshift::test_redshift | 1620 | sqlglot/dialects/redshift.py:51 class Redshift.Tokenizer users 107; sqlglot/dialects/redshift.py: possible import failure, everything | 107 | no |
| c | t41x029 | postgres regcollation keyword | unlabeled |  | 1620 | sqlglot/dialects/postgres.py:140 class Postgres.Tokenizer users 320; sqlglot/dialects/postgres.py: possible import failure, everything | 320 |  |
| c | t41x030 | duckdb ubigint keyword | unlabeled |  | 1620 | sqlglot/dialects/duckdb.py:139 class DuckDB.Tokenizer users 437; sqlglot/dialects/duckdb.py: possible import failure, everything | 437 |  |
| c | t41x031 | starrocks resume keyword | unlabeled |  | 1620 | sqlglot/dialects/starrocks.py:52 class StarRocks.Tokenizer users 73; sqlglot/dialects/starrocks.py: possible import failure, everything | 73 |  |
| c | t41x032 | tsql output keyword | unlabeled |  | 1620 | sqlglot/dialects/tsql.py:179 class TSQL.Tokenizer users 171; sqlglot/dialects/tsql.py: possible import failure, everything | 171 |  |
| c | t41x033 | snowflake byteint keyword | unlabeled |  | 1620 | sqlglot/dialects/snowflake.py:143 class Snowflake.Tokenizer users 358; sqlglot/dialects/snowflake.py: possible import failure, everything | 358 |  |
| c | t41x034 | oracle subpartition keyword | unlabeled |  | 1620 | sqlglot/dialects/oracle.py:115 class Oracle.Tokenizer users 137; sqlglot/dialects/oracle.py: possible import failure, everything | 137 |  |
| c | t41x035 | trino refresh keyword | unlabeled |  | 1620 | sqlglot/dialects/trino.py:17 class Trino.Tokenizer users 143; sqlglot/dialects/trino.py: possible import failure, everything | 143 |  |
| c | t41x036 | base anti keyword | unlabeled |  | 1620 | sqlglot/tokens.py:264 class Tokenizer users 1564; sqlglot/tokens.py: possible import failure, everything | 1564 |  |
| c | t41x037 | base asof keyword | unlabeled |  | 1620 | sqlglot/tokens.py:268 class Tokenizer users 1564; sqlglot/tokens.py: possible import failure, everything | 1564 |  |
| c | t41x039 | optimizer lazy export key | unlabeled |  | 1620 | sqlglot/optimizer/__init__.py:44 module constant read at import, everything; sqlglot/optimizer/__init__.py: possible import failure, everything | 1620 |  |
| d | t41x040 | duckdb timezone pattern accepts Z | 0 |  | 1620 | sqlglot/generators/duckdb.py:52 module constant TIMEZONE_PATTERN: 5 read it; sqlglot/generators/duckdb.py: possible import failure, everything | 5 | no |
| d | t41x041 | bigquery safe json key end anchor | unlabeled |  | 1620 | sqlglot/generators/bigquery.py:372 class BigQueryGenerator users 226; sqlglot/generators/bigquery.py: possible import failure, everything | 226 |  |
| d | t41x042 | hive canonical time strict year | unlabeled |  | 1620 | sqlglot/generators/hive.py:57 module constant CANONICAL_TIME_FORMAT: 19 read it; sqlglot/generators/hive.py: possible import failure, everything | 19 |  |
| d | t41x043 | hive safe json key digits | unlabeled |  | 1620 | sqlglot/generators/hive.py:245 class HiveGenerator users 304; sqlglot/generators/hive.py: possible import failure, everything | 304 |  |
| d | t41x044 | interval unit allows underscore | unlabeled |  | 1620 | sqlglot/expressions/builders.py:347 module constant INTERVAL_STRING_RE: 55 read it; sqlglot/expressions/builders.py: possible import failure, everything | 55 |  |
| d | t41x045 | camel case split before lowercase | unlabeled |  | 1620 | sqlglot/helper.py:37 module constant read at import, everything; sqlglot/helper.py: possible import failure, everything | 1620 |  |
| d | t41x046 | high byte range includes delete | unlabeled |  | 1620 | sqlglot/generator.py:28 module constant _HIGH_BYTE_RE: 3 read it; sqlglot/generator.py: possible import failure, everything | 3 |  |
| d | t41x047 | mysql time mapping key in trie | unlabeled |  | 1620 | sqlglot/dialects/mysql.py:50 class MySQL users 291; sqlglot/dialects/mysql.py: possible import failure, everything | 291 |  |
| d | t41x048 | mysql month-name key in trie | unlabeled |  | 1620 | sqlglot/dialects/mysql.py:46 class MySQL users 291; sqlglot/dialects/mysql.py: possible import failure, everything | 291 |  |
| d | t41x049 | test canonical atom regex | unlabeled |  | 1620 | tests/test_time.py:9 test module level 4; tests/test_time.py: possible import failure, everything | 4 |  |
| e | t41x050 | tsql dialect registry name | 1 | TestGenerator::test_generator_memory | 1620 | sqlglot/dialects/dialect.py:133 class Dialects never instantiated, module runs at import: everything; sqlglot/dialects/dialect.py: possible import failure, everything | 2 | MISS 1: TestGenerator::test_generator_memory |
| e | t41x051 | doris dialect registry name | unlabeled |  | 1620 | sqlglot/dialects/dialect.py:108 class Dialects never instantiated, module runs at import: everything; sqlglot/dialects/dialect.py: possible import failure, everything | 0 |  |
| e | t41x052 | drill dialect registry name | unlabeled |  | 1620 | sqlglot/dialects/dialect.py:110 class Dialects never instantiated, module runs at import: everything; sqlglot/dialects/dialect.py: possible import failure, everything | 0 |  |
| e | t41x053 | optimizer lazy scope module path | unlabeled |  | 1620 | sqlglot/optimizer/__init__.py:41 module constant read at import, everything; sqlglot/optimizer/__init__.py: possible import failure, everything | 1620 |  |
| e | t41x054 | optimizer lazy optimize attribute | unlabeled |  | 1620 | sqlglot/optimizer/__init__.py:40 module constant read at import, everything; sqlglot/optimizer/__init__.py: possible import failure, everything | 1620 |  |
| e | t41x055 | ceil function alias | unlabeled |  | 1620 | sqlglot/expressions/math.py:136 class Ceil users 10; sqlglot/expressions/math.py: possible import failure, everything | 10 |  |
| e | t41x056 | isinf function name | unlabeled |  | 1620 | sqlglot/expressions/math.py:152 class IsInf users 5; sqlglot/expressions/math.py: possible import failure, everything | 5 |  |
| e | t41x057 | sign function alias | unlabeled |  | 1620 | sqlglot/expressions/math.py:194 class Sign users 4; sqlglot/expressions/math.py: possible import failure, everything | 4 |  |
| e | t41x058 | getbit function alias | unlabeled |  | 1620 | sqlglot/expressions/math.py:285 class Getbit users 8; sqlglot/expressions/math.py: possible import failure, everything | 8 |  |
| e | t41x059 | trunc function alias | unlabeled |  | 1620 | sqlglot/expressions/math.py:203 class Trunc users 19; sqlglot/expressions/math.py: possible import failure, everything | 19 |  |
| e | t41x060 | skip integration env name | unlabeled |  | 1620 | tests/helpers.py:66 test module level 1377; tests/helpers.py: possible import failure, everything | 96 |  |
| e | t41x061 | fabric test dialect name | unlabeled |  | 1620 | tests/dialects/test_fabric.py:5 test module level 7; tests/dialects/test_fabric.py: possible import failure, everything | 7 |  |
| e | t41x062 | risingwave test dialect name | unlabeled |  | 1620 | tests/dialects/test_risingwave.py:5 test module level 2; tests/dialects/test_risingwave.py: possible import failure, everything | 2 |  |
| f | t41x063 | executor tpch fixture dir | 60 | TestExecutor::test_agg_order, TestExecutor::test_aggregate_without_group_by, TestExecutor::test_array_slice, TestExecutor::test_case_sensitivity (+56) | 1620 | tests/test_executor.py:30 test module level 60; tests/test_executor.py: possible import failure, everything | 1620 | no |
| f | t41x064 | executor tpcds fixture dir | unlabeled |  | 1620 | tests/test_executor.py:31 test module level 60; tests/test_executor.py: possible import failure, everything | 1620 |  |
| f | t41x065 | helpers fixtures dir name | unlabeled |  | 1620 | tests/helpers.py:4 test module level 1377; tests/helpers.py: possible import failure, everything | 96 |  |
| f | t41x066 | executor skip reason text | unlabeled |  | 1620 | tests/test_executor.py:70 test module level 60; tests/test_executor.py: possible import failure, everything | 0 |  |
| f | t41x068 | oracle test dialect name | unlabeled |  | 1620 | tests/dialects/test_oracle.py:7 test module level 41; tests/dialects/test_oracle.py: possible import failure, everything | 41 |  |
| f | t41x069 | postgres test dialect name | unlabeled |  | 1620 | tests/dialects/test_postgres.py:12 test module level 45; tests/dialects/test_postgres.py: possible import failure, everything | 45 |  |
| f | t41x070 | leakcheck null stream mode | unlabeled |  | 1620 | tests/leakcheck.py:97 test module level 0; tests/leakcheck.py: possible import failure, everything | 0 |  |
| f | t41x071 | sqlite skip reason text | unlabeled |  | 1620 | tests/dialects/test_sqlite.py:36 definition header of test_variadic_iif_execution: callers 0; tests/dialects/test_sqlite.py:36 test module level 42; tests/dialects/test_sqlite.py: possible import failure, everything | 0 |  |
| f | t41x072 | zoneinfo skip reason text | unlabeled |  | 1620 | tests/test_expressions.py:1235 definition header of test_convert_python39: callers 1; tests/test_expressions.py:1235 test module level 79; tests/test_expressions.py: possible import failure, everything | 0 |  |
| f | t41x073 | serde skip reason text | unlabeled |  | 1620 | tests/test_serde.py:30 definition header of test_custom_expression: callers 1; tests/test_serde.py:30 test module level 5; tests/test_serde.py: possible import failure, everything | 0 |  |
| f | t41x075 | drill test dialect name | unlabeled |  | 1620 | tests/dialects/test_drill.py:5 test module level 3; tests/dialects/test_drill.py: possible import failure, everything | 3 |  |
| f | t41x076 | dialect test first skip reason | unlabeled |  | 1620 | tests/dialects/test_dialect.py:6100 definition header of test_patch_dialect_parser: callers 1; tests/dialects/test_dialect.py:6100 test module level 1020; tests/dialects/test_dialect.py: possible import failure, everything | 0 |  |
| g | t41x077 | pretty setting docstring | unlabeled |  | 1620 | sqlglot/__init__.py:74 module level 1518; sqlglot/__init__.py: possible import failure, everything | 1518 |  |
| g | t41x078 | error level ignore docstring | unlabeled |  | 1620 | sqlglot/errors.py:17 class ErrorLevel never instantiated, module runs at import: everything; sqlglot/errors.py: possible import failure, everything | 0 |  |
| g | t41x079 | error level warn docstring | unlabeled |  | 1620 | sqlglot/errors.py:20 class ErrorLevel never instantiated, module runs at import: everything; sqlglot/errors.py: possible import failure, everything | 0 |  |
| g | t41x080 | error level raise docstring | unlabeled |  | 1620 | sqlglot/errors.py:23 class ErrorLevel never instantiated, module runs at import: everything; sqlglot/errors.py: possible import failure, everything | 0 |  |
| g | t41x081 | error level immediate docstring | unlabeled |  | 1620 | sqlglot/errors.py:26 class ErrorLevel never instantiated, module runs at import: everything; sqlglot/errors.py: possible import failure, everything | 0 |  |
| g | t41x082 | dialects enum docstring | unlabeled |  | 1620 | sqlglot/dialects/dialect.py:99 class Dialects never instantiated, module runs at import: everything; sqlglot/dialects/dialect.py: possible import failure, everything | 0 |  |
| g | t41x084 | lowercase strategy docstring | unlabeled |  | 1620 | sqlglot/dialects/dialect.py:141 class NormalizationStrategy never instantiated, module runs at import: everything; sqlglot/dialects/dialect.py: possible import failure, everything | 0 |  |
| g | t41x085 | uppercase strategy docstring | unlabeled |  | 1620 | sqlglot/dialects/dialect.py:144 class NormalizationStrategy never instantiated, module runs at import: everything; sqlglot/dialects/dialect.py: possible import failure, everything | 0 |  |
| g | t41x086 | case sensitive strategy docstring | unlabeled |  | 1620 | sqlglot/dialects/dialect.py:147 class NormalizationStrategy never instantiated, module runs at import: everything; sqlglot/dialects/dialect.py: possible import failure, everything | 0 |  |
| g | t41x087 | optimizer package docstring | unlabeled |  | 1620 | sqlglot/optimizer/__init__.py:2 module level 0; sqlglot/optimizer/__init__.py: possible import failure, everything | 1620 |  |
