# Gate narrowing versus dc91341

Each inherited comparison row uses the existing operand-pair profile proof: the replacement comparison has no observed result change, the profile union bit is zero, and import guards remain in force. Every original frozen failing label is covered. Each unused-help row uses the stricter complete-module stock-parser/map proof described in REPORT.md.

| Commit | Change/site | Safety reason |
|---|---|---|
| c21x001 | cmp is -> ==; sqlglot/optimizer/qualify_columns.py:1369:48 | Inherited comparison-profile proof; original labels contain no failure |
| c21x012 | cmp is -> ==; sqlglot/generator.py:1648:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x038 | cmp != -> is not; sqlglot/parsers/oracle.py:272:47 | Inherited comparison-profile proof; original labels contain no failure |
| c21x039 | cmp is -> ==; sqlglot/generator.py:4985:13 | Inherited comparison-profile proof; original labels contain no failure |
| c21x045 | cmp == -> is; sqlglot/generators/presto.py:539:13 | Inherited comparison-profile proof; original labels contain no failure |
| c21x046 | cmp != -> is not; sqlglot/parsers/presto.py:69:8 | Inherited comparison-profile proof; original labels contain no failure |
| c21x080 | cmp >= -> >; sqlglot/tokenizer_core.py:1208:15 | Inherited comparison-profile proof; original labels contain no failure |
| c21x085 | cmp is not -> !=; sqlglot/generators/postgres.py:318:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x089 | cmp == -> is; sqlglot/expressions/core.py:2089:13 | Inherited comparison-profile proof; original labels contain no failure |
| c21x104 | cmp is -> ==; sqlglot/parser.py:6102:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x108 | cmp < -> <=; sqlglot/tokenizer_core.py:910:15 | Inherited comparison-profile proof; original labels contain no failure |
| c21x109 | cmp is not -> !=; sqlglot/dialects/dialect.py:2667:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x113 | cmp is -> ==; sqlglot/optimizer/scope.py:228:17 | Inherited comparison-profile proof; original labels contain no failure |
| c21x114 | cmp is -> ==; sqlglot/expressions/core.py:1228:14 | Inherited comparison-profile proof; original labels contain no failure |
| c21x116 | cmp < -> <=; sqlglot/generators/hive.py:88:44 | Inherited comparison-profile proof; original labels contain no failure |
| c21x118 | cmp is not -> !=; sqlglot/optimizer/simplify.py:446:36 | Inherited comparison-profile proof; original labels contain no failure |
| c21x138 | cmp is -> ==; sqlglot/generator.py:5427:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x151 | cmp < -> <=; sqlglot/executor/env.py:205:24 | Inherited comparison-profile proof; original labels contain no failure |
| c21x156 | cmp >= -> >; sqlglot/tokenizer_core.py:1251:27 | Inherited comparison-profile proof; original labels contain no failure |
| c21x162 | cmp < -> <=; sqlglot/optimizer/pushdown_predicates.py:238:46 | Inherited comparison-profile proof; original labels contain no failure |
| c21x174 | cmp is -> ==; sqlglot/parsers/redshift.py:25:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x188 | cmp < -> <=; sqlglot/parser.py:6109:48 | Inherited comparison-profile proof; original labels contain no failure |
| c21x189 | cmp != -> is not; sqlglot/executor/python.py:130:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x194 | cmp == -> is; sqlglot/parsers/teradata.py:121:12 | Inherited comparison-profile proof; original labels contain no failure |
| c21x204 | cmp is -> ==; sqlglot/dialects/dialect.py:1226:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x207 | cmp == -> is; sqlglot/parsers/duckdb.py:80:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x213 | cmp < -> <=; sqlglot/dialects/dialect.py:1719:40 | Inherited comparison-profile proof; original labels contain no failure |
| c21x216 | cmp == -> is; sqlglot/generators/duckdb.py:1218:18 | Inherited comparison-profile proof; original labels contain no failure |
| c21x219 | cmp is -> ==; sqlglot/generator.py:6036:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x222 | cmp >= -> >; sqlglot/generators/duckdb.py:3341:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x238 | cmp is -> ==; sqlglot/executor/env.py:134:7 | Inherited comparison-profile proof; original labels contain no failure |
| c21x239 | cmp is not -> !=; sqlglot/optimizer/pushdown_projections.py:449:27 | Inherited comparison-profile proof; original labels contain no failure |
| c21x246 | cmp == -> is; sqlglot/parsers/spark2.py:153:11 | Inherited comparison-profile proof; original labels contain no failure |
| c21x249 | cmp is -> ==; sqlglot/expressions/core.py:859:25 | Inherited comparison-profile proof; original labels contain no failure |
| c21x258 | cmp is not -> !=; sqlglot/parser.py:2959:19 | Inherited comparison-profile proof; original labels contain no failure |
| c21x259 | cmp > -> >=; sqlglot/generators/clickhouse.py:590:15 | Inherited comparison-profile proof; original labels contain no failure |
| t32x015 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x016 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x017 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x018 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x019 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x020 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x021 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x022 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x023 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x024 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x025 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x026 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x027 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x028 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
| t32x029 | Stock argparse help metadata | Single-file AST-equivalent module except help text; stock unescaped parser, no runtime/data consumers |
