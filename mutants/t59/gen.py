"""t59 adversarial labels for the class-table key rule: each patch edits one
or two entries of a Parser FUNCTIONS/FUNCTION_PARSERS or Generator TRANSFORMS
literal in the pinned source. usage: python3 mutants/t59/gen.py <sqlglot src>"""
import difflib, json, os, sys
SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
# id: (file, [(line number, expected old substring, new line or None to delete)], kind)
M = {
 't59k00': ('sqlglot/parsers/hive.py', [(84, '"COLLECT_SET":', '        "ARRAY_AGG": exp.ArrayUniqueAgg.from_arg_list,')], 'key renamed to a name other dialects probe (inherited by Spark2, Spark, Databricks)'),
 't59k01': ('sqlglot/parsers/hive.py', [(101, '"DATE_SUB": _build_date_add,', None)], 'entry removed (inherited by three dialects)'),
 't59k02': ('sqlglot/parsers/hive.py', [(107, '"FIRST": build_with_ignore_nulls(exp.First),', '        "FIRST": build_with_ignore_nulls(exp.FirstValue),'),
                                         (108, '"FIRST_VALUE": build_with_ignore_nulls(exp.FirstValue),', '        "FIRST_VALUE": build_with_ignore_nulls(exp.First),')], 'values swapped between two keys'),
 't59k03': ('sqlglot/parsers/hive.py', [(106, 'exp.Day(this=', '        "DAY": lambda args: exp.Month(this=exp.TsOrDsToDate(this=seq_get(args, 0))),')], 'lambda body edit inherited by three dialects'),
 't59k04': ('sqlglot/parsers/trino.py', [(47, '"LISTAGG": lambda self: self._parse_string_agg(),', None)], 'entry removed, read through parser_class without an instance (t52x092)'),
 't59k05': ('sqlglot/parser.py', [(1633, '"TRY_CAST": lambda self: self._parse_cast(False, safe=True),', '        "TRY_CAST": lambda self: self._parse_cast(False, safe=False),')], 'base entry aliased by Teradata TRYCAST'),
 't59k06': ('sqlglot/parser.py', [(405, '"SORT_ARRAY": build_sort_array,', '        "SORT_ARRAYS": build_sort_array,')], 'base key renamed (all dialects inherit it)'),
 't59k07': ('sqlglot/parser.py', [(462, '"LOG": build_logarithm,', '        "LOGS": build_logarithm,')], 'base key renamed, a common function'),
 't59k08': ('sqlglot/parsers/snowflake.py', [(442, '"APPROX_PERCENTILE": exp.ApproxQuantile.from_arg_list,', '        "PREDICT": exp.ApproxQuantile.from_arg_list,')], 'key renamed to a name the class body filters out'),
 't59k09': ('sqlglot/parsers/snowflake.py', [(431, '"CHARINDEX": lambda args: exp.StrPosition(', '        "CHARINDEXX": lambda args: exp.StrPosition(')], 'key renamed in a table with a filtered rebind'),
 't59k10': ('sqlglot/parser.py', [(1621, '"JSON_OBJECT": lambda self: self._parse_json_object(),', '        "JSON_OBJECTS": lambda self: self._parse_json_object(),')], 'FUNCTION_PARSERS key renamed (anonymize reads it through parser_class)'),
 't59k11': ('sqlglot/generators/postgres.py', [(360, 'exp.BitwiseAndAgg: rename_func("BIT_AND"),', '        exp.BitwiseAndAgg: rename_func("BIT_ANDX"),')], 'entry inherited by Redshift and Materialize through filtered comprehensions'),
 't59k12': ('sqlglot/generators/spark2.py', [(161, 'exp.ApproxDistinct: rename_func("APPROX_COUNT_DISTINCT"),', '            exp.ApproxDistinct: rename_func("APPROX_DISTINCT"),')], 'entry inside a comprehension literal, inherited by Spark and Databricks'),
 't59k13': ('sqlglot/generators/duckdb.py', [(1678, 'exp.ArraySum: rename_func("LIST_SUM"),', '        exp.ArraySum: rename_func("LIST_MAX"),'),
                                              (1679, 'exp.ArrayMax: rename_func("LIST_MAX"),', '        exp.ArrayMax: rename_func("LIST_SUM"),')], 'values swapped between two keys'),
 't59k14': ('sqlglot/generators/presto.py', [(330, 'exp.ArgMax: rename_func("MAX_BY"),', '        exp.ArgMin: rename_func("MAX_BY"),'),
                                              (331, 'exp.ArgMin: rename_func("MIN_BY"),', '        exp.ArgMax: rename_func("MIN_BY"),')], 'keys swapped between two values (inherited by Trino, Athena)'),
 't59k15': ('sqlglot/generators/presto.py', [(322, 'exp.AnyValue: rename_func("ARBITRARY"),', None)], 'entry removed, inherited by Trino and Athena'),
 't59k16': ('sqlglot/generators/mysql.py', [(161, 'exp.BitwiseAndAgg: rename_func("BIT_AND"),', '        exp.BitwiseAndAgg: rename_func("BIT_AND2"),')], 'entry copied by StarRocks, Doris and SingleStore comprehensions'),
 't59k17': ('sqlglot/generators/hive.py', [(291, 'exp.ArrayConcat: rename_func("CONCAT"),', '        exp.ArrayConcat: rename_func("ARRAY_CONCAT"),')], 'entry inherited by Spark2, Spark, Databricks'),
 't59k18': ('sqlglot/generators/hive.py', [(310, 'exp.IsNan: rename_func("ISNAN"),', '        exp.IsInf: rename_func("ISNAN"),')], 'key renamed to an expression class with its own generator method'),
 't59k19': ('sqlglot/generator.py', [(133, 'exp.Adjacent: lambda self, e: self.binary(e, "-|-"),', '        exp.Adjacent: lambda self, e: self.binary(e, "-||-"),')], 'base Generator entry inherited by every dialect and filtered copies'),
 't59k20': ('sqlglot/generator.py', [(137, 'exp.AnalyzeColumns: lambda self, e: self.sql(e, "this"),', '        exp.AnalyzeColumns: lambda self, e: self.sql(e, "expression"),')], 'base Generator lambda body edit'),
 't59k21': ('sqlglot/generators/redshift.py', [(99, 'exp.GroupConcat: rename_func("LISTAGG"),', '        exp.GroupConcat: rename_func("STRING_AGG"),')], 'own entry of a table built from a filtered parent copy'),
 't59k22': ('sqlglot/generators/bigquery.py', [(409, 'exp.AIGenerate: rename_func("GENERATE"),', None)], 'entry removed'),
 't59k23': ('sqlglot/parsers/snowflake.py', [(437, '"ADD_MONTHS": lambda args: exp.AddMonths(', '        "ADD_MONTH": lambda args: exp.AddMonths(')], 'key renamed (multi-line lambda)'),
}
manifest = {}
for cid, (rel, edits, kind) in M.items():
    old = open(os.path.join(SRC, rel)).read().split('\n')
    new = list(old)
    for ln, want, rep in sorted(edits, reverse=True):
        assert want in old[ln - 1], (cid, ln, old[ln - 1])
        if rep is None: del new[ln - 1]
        else: new[ln - 1] = rep
    diff = difflib.unified_diff([l + '\n' for l in old], [l + '\n' for l in new], f'a/{rel}', f'b/{rel}', n=3)
    text = f'diff --git a/{rel} b/{rel}\n' + ''.join(diff)
    open(os.path.join(OUT, 'commits', cid + '.patch'), 'w').write(text)
    manifest[cid] = {'file': rel, 'kind': kind}
json.dump({'commits': manifest}, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(len(manifest))
