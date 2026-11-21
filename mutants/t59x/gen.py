"""t59x: t62k09 and siblings, edits that change what runs at import without a
new name. usage: python3 mutants/t59x/gen.py <sqlglot src>"""
import difflib, json, os, sys
SRC = sys.argv[1]; OUT = os.path.dirname(os.path.abspath(__file__))
M = {
 't59x00': ('sqlglot/parsers/hive.py', '"TO_DATE": _build_to_date,', '"TO_DATE": _build_to_date([]),', 't62k09: a call added, wrong arity at import'),
 't59x01': ('sqlglot/generators/spark2.py', 'exp.ApproxDistinct: rename_func("APPROX_COUNT_DISTINCT"),', 'exp.ApproxDistinct: rename_func("APPROX_COUNT_DISTINCT", "X"),', 'arity change of a builder call (TypeError at import)'),
 't59x02': ('sqlglot/generators/presto.py', 'exp.AnyValue: rename_func("ARBITRARY"),', 'exp.AnyValue: rename_func,', 'call removed, bare builder left as the value'),
 't59x03': ('sqlglot/parsers/hive.py', '"COLLECT_SET": exp.ArrayUniqueAgg.from_arg_list,', '"COLLECT_SET": exp.ArrayUniqueAgg.from_arg_list([]),', 'call added in an entry'),
 't59x04': ('sqlglot/parsers/hive.py', '"FROM_UNIXTIME": build_formatted_time(exp.UnixToStr, default=True),', '"FROM_UNIXTIME": build_formatted_time(exp.UnixToStr, defaults=True),', 'keyword renamed in a builder call'),
 't59x05': ('sqlglot/parsers/teradata.py', '"TRYCAST": parser.Parser.FUNCTION_PARSERS["TRY_CAST"],', '"TRYCAST": parser.Parser.FUNCTION_PARSERS["TRY_CASTS"],', 'subscript key changed on a table at import (KeyError)'),
 't59x06': ('sqlglot/generators/clickhouse.py', '    @unsupported_args("json_scope")', '    @unsupported_args("json_scope", "path")', 'decorator call arguments changed'),
 't59x07': ('sqlglot/parsers/clickhouse.py', '"DATEADD": build_date_delta(exp.DateAdd, default_unit=None),', '"DATEADD": build_date_delta(exp.DateAdd, None, None, None, None),', 'arity change in a parser builder'),
 't59x08': ('sqlglot/parsers/hive.py', '"FIRST": build_with_ignore_nulls(exp.First),', '"FIRST": build_with_ignore_nulls,', 'call removed in a parser entry'),
 't59x09': ('sqlglot/generators/duckdb.py', 'exp.ArraySum: rename_func("LIST_SUM"),', 'exp.ArraySum: rename_func(name="LIST_SUM"),', 'positional argument made a keyword (same behaviour, shape changed)'),
 't59x10': ('sqlglot/generators/duckdb.py', 'exp.ArraySum: rename_func("LIST_SUM"),', 'exp.ArraySumm: rename_func("LIST_SUM"),', 'attribute that does not exist (AttributeError at import)'),
 't59x11': ('sqlglot/parsers/tsql.py', '"DATEADD": build_date_delta(exp.DateAdd, unit_mapping=DATE_DELTA_INTERVAL),', '"DATEADD": build_date_delta(exp.DateAdd, unit_map=DATE_DELTA_INTERVAL),', 'keyword renamed (TypeError at import)'),
}
man = {}
for cid, (rel, old, new, kind) in M.items():
    text = open(os.path.join(SRC, rel)).read()
    assert text.count(old) == 1, (cid, text.count(old))
    a = text.split('\n'); b = text.replace(old, new).split('\n')
    d = difflib.unified_diff([l + '\n' for l in a], [l + '\n' for l in b], f'a/{rel}', f'b/{rel}', n=3)
    open(os.path.join(OUT, 'commits', cid + '.patch'), 'w').write(f'diff --git a/{rel} b/{rel}\n' + ''.join(d))
    man[cid] = {'file': rel, 'kind': kind}
json.dump({'commits': man}, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(len(man))
