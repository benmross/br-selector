"""t62 adversarial mutants for the key-trace rule (862aa2a). Each edit finds a
unique line by substring. ops: ('sub', match, new line), ('del', match),
('ins', match, new line inserted before), ('mv', match, anchor): move the line
before the anchor line. usage: python3 mutants/t62/gen.py <sqlglot src>"""
import difflib, json, os, sys
SRC = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(__file__))
P, G = 'sqlglot/parser.py', 'sqlglot/generator.py'
HP, HG = 'sqlglot/parsers/hive.py', 'sqlglot/generators/hive.py'
M = {
 # 1. dispatch / cache: base Generator entries read through the per-class dispatch copy
 't62k01': ([(G, 'sub', 'exp.Ceil: lambda self, e: self.ceil_floor(e),', '        exp.Ceil: lambda self, e: self.func("CEILING", e.this),')], 'base TRANSFORMS value edit, every dialect dispatch copy'),
 't62k02': ([(G, 'del', 'exp.Floor: lambda self, e: self.ceil_floor(e),')], 'base TRANSFORMS entry removed (dispatch falls back)'),
 't62k03': ([(G, 'ins', 'exp.ArrayContainsAll: lambda self, e: self.binary(e, "@>"),', '        exp.AnyValue: lambda self, e: self.func("ANYV", e.this),')], 'base TRANSFORMS entry added that shadows anyvalue_sql in the dispatch copy'),
 't62k04': ([(G, 'ins', 'exp.ArrayContainsAll: lambda self, e: self.binary(e, "@>"),', '        exp.TryCast: lambda self, e: self.cast_sql(e),')], 'base TRANSFORMS entry added that shadows trycast_sql'),
 # 2. readers outside the parser's own lookups; import-time evaluation of values
 't62k05': ([('sqlglot/parsers/snowflake.py', 'sub', 'step=seq_get(args, 2),', '            step=seq_get(args, 1),')], 'Snowflake ARRAY_GENERATE_RANGE lambda body (read by the Snowflake generator through SnowflakeParser.FUNCTIONS)'),
 't62k06': ([('sqlglot/parsers/teradata.py', 'sub', '"TRYCAST": parser.Parser.FUNCTION_PARSERS["TRY_CAST"],', '        "TRYCAST": parser.Parser.FUNCTION_PARSERS["CAST"],')], 'alias value subscript changed to another valid key'),
 't62k07': ([('sqlglot/parsers/teradata.py', 'sub', '"TRYCAST": parser.Parser.FUNCTION_PARSERS["TRY_CAST"],', '        "TRYCAST": parser.Parser.FUNCTION_PARSERS["TRY_CASTS"],')], 'alias value subscript changed to a missing key: KeyError at import'),
 't62k08': ([(HP, 'sub', '"BASE64": exp.ToBase64.from_arg_list,', '        "BASE64": exp.ToBase64.from_arg_lists,')], 'value attribute misspelled: AttributeError at import'),
 't62k09': ([(HP, 'sub', '"TO_DATE": _build_to_date,', '        "TO_DATE": _build_to_date([]),')], 'value turned into an import-time call of a builder'),
 't62k10': ([(P, 'sub', '"TRIM": lambda self: self._parse_trim(),', '        "TRIMS": lambda self: self._parse_trim(),')], 'FUNCTION_PARSERS key renamed (anonymize reads it; Snowflake and BigQuery filter TRIM)'),
 't62k11': ([(P, 'sub', '"EXTRACT": lambda self: self._parse_extract(),', '        "EXTRACT": lambda self: self._parse_convert(False),')], 'base FUNCTION_PARSERS value swapped to another parser'),
 # 3. value side
 't62k12': ([(G, 'sub', 'exp.ArrayContainsAll: lambda self, e: self.binary(e, "@>"),', '        exp.ArrayContainsAll: lambda self, e: self.binary(e, "&&"),'),
             (G, 'sub', 'exp.ArrayOverlaps: lambda self, e: self.binary(e, "&&"),', '        exp.ArrayOverlaps: lambda self, e: self.binary(e, "@>"),')], 'base TRANSFORMS values swapped'),
 't62k13': ([(P, 'sub', '"LOG2": lambda args: exp.Log(this=exp.Literal.number(2),', '        "LOG2": lambda args: exp.Log(this=exp.Literal.number(10), expression=seq_get(args, 0)),'),
             (P, 'sub', '"LOG10": lambda args: exp.Log(this=exp.Literal.number(10),', '        "LOG10": lambda args: exp.Log(this=exp.Literal.number(2), expression=seq_get(args, 0)),')], 'base FUNCTIONS lambda bodies swapped'),
 't62k14': ([('sqlglot/parsers/spark.py', 'ins', '"ANY_VALUE": build_with_ignore_nulls(exp.AnyValue),', '        "COLLECT_SET": exp.ArrayAgg.from_arg_list,')], 'subclass entry added that shadows an inherited Hive entry'),
 't62k15': ([(HG, 'mv', 'exp.VarMap: var_map_sql,', '**generator.Generator.TRANSFORMS,')], 'entry moved above the parent splat (parent value now wins)'),
 't62k16': ([(HP, 'ins', '"COLLECT_SET": exp.ArrayUniqueAgg.from_arg_list,', '        "BASE64": exp.Hex.from_arg_list,')], 'duplicate key added (later value wins)'),
 't62k17': ([('sqlglot/generators/presto.py', 'sub', 'exp.AnyValue: rename_func("ARBITRARY"),', '        exp.AnyValue: rename_func("ANY_VALUE"),')], 'value edit inherited by Trino and Athena'),
 't62k18': ([('sqlglot/parsers/mysql.py', 'sub', '"GROUP_CONCAT": lambda self: self._parse_group_concat(),', '        "GROUP_CONCAT": lambda self: self._parse_string_agg(),')], 'FUNCTION_PARSERS value edit; Doris filters the key, StarRocks and SingleStore inherit'),
 't62k19': ([('sqlglot/parsers/postgres.py', 'sub', 'this=seq_get(args, 0), expression=seq_get(args, 1), zero_is_msb=True', '            this=seq_get(args, 1), expression=seq_get(args, 0), zero_is_msb=True')], 'lambda body edit on a key Redshift filters out'),
 't62k20': ([('sqlglot/parsers/duckdb.py', 'sub', 'if k not in ("DATE_SUB", "GLOB")},', '        **{k: v for k, v in parser.Parser.FUNCTIONS.items() if k not in ("DATE_SUB",)},')], 'filter of a comprehension splat changed'),
 't62k21': ([(G, 'sub', '"RETURNS NULL ON NULL INPUT" if e.args.get("null") else self.naked_property(e)', '            "RETURNS NULL ON NULL INPUT" if not e.args.get("null") else self.naked_property(e)')], 'base multi-line entry body edit; TSQL filters the key'),
 # 4. staleness: line shifts, several edits
 't62k22': ([(HP, 'ins', 'class HiveParser(', '_T62_SHIFT = 1'), (HP, 'sub', '"COLLECT_SET": exp.ArrayUniqueAgg.from_arg_list,', '        "COLLECT_SET": exp.ArrayAgg.from_arg_list,')], 'module line inserted above the class plus an entry edit (line numbers shift)'),
 't62k23': ([(HP, 'sub', '"COLLECT_SET": exp.ArrayUniqueAgg.from_arg_list,', '        "COLLECT_SET": exp.ArrayAgg.from_arg_list,'),
             (HP, 'sub', '"PERCENTILE": lambda self: self._parse_distinct_arg_function(exp.Quantile),', '        "PERCENTILE": lambda self: self._parse_distinct_arg_function(exp.ApproxQuantile),')], 'FUNCTIONS and FUNCTION_PARSERS entries edited in one class'),
 't62k24': ([(HP, 'sub', '"BASE64": exp.ToBase64.from_arg_list,', '        "BASE64": exp.Hex.from_arg_list,'), (HP, 'sub', 'with_collation: bool = False,', '        with_collation: bool = True,')], 'entry edit plus a method default edit in the same file'),
 't62k25': ([(HP, 'sub', '"COLLECT_SET": exp.ArrayUniqueAgg.from_arg_list,', '        "COLLECT_SET": exp.ArrayAgg.from_arg_list,'), (HG, 'sub', 'exp.AnyValue: rename_func("FIRST"),', '        exp.AnyValue: rename_func("ANY_VALUE"),')], 'parser and generator entries edited in two files'),
 't62k26': ([('sqlglot/generators/presto.py', 'sub', 'exp.AnyValue: rename_func("ARBITRARY"),', '        exp.AnyValue: rename_func("ANY_VALUE"),'), ('sqlglot/generators/presto.py', 'sub', 'exp.DType.BINARY: "VARBINARY",', '        exp.DType.BINARY: "VARBINARYX",')], 'entry edit plus another table of the same class'),
 't62k27': ([(HP, 'sub', 'coalesce=dialect.CONCAT_WS_COALESCE,', '            coalesce=not dialect.CONCAT_WS_COALESCE,')], 'Hive CONCAT_WS (overrides the base entry) multi-line lambda body'),
 't62k28': ([(HP, 'sub', '"CONCAT_WS": lambda args, dialect: exp.ConcatWs(', '        "CONCAT_WSX": lambda args, dialect: exp.ConcatWs(')], 'override key renamed: the base entry reappears'),
 # 5. import-time calls in a changed entry that raise (the purity audit checks side effects only)
 't62m01': ([('sqlglot/generators/duckdb.py', 'sub', 'exp.ArraySum: rename_func("LIST_SUM"),', '        exp.ArraySum: rename_func(),')], 'factory called with a missing argument: TypeError at import'),
 't62m02': ([('sqlglot/parsers/snowflake.py', 'sub', '"TO_DATE": _build_datetime("TO_DATE", exp.DType.DATE),', '        "TO_DATE": _build_datetime("TO_DATE"),')], 'factory called with a missing argument: TypeError at import'),
 't62m03': ([(HG, 'sub', 'exp.DateStrToDate: datestrtodate_sql,', '        exp.DateStrToDate: datestrtodate_sql(None, None),')], 'generator function called at import with None: raises at import'),
 't62m04': ([('sqlglot/parsers/snowflake.py', 'sub', '"APPROX_PERCENTILE": exp.ApproxQuantile.from_arg_list,', '        "APPROX_PERCENTILE": exp.ApproxQuantile.from_arg_list(None),')], 'from_arg_list called at import with None'),
 't62m05': ([('sqlglot/generators/presto.py', 'sub', 'exp.AnyValue: rename_func("ARBITRARY"),', '        exp.AnyValue: rename_func("ARBITRARY", 1),')], 'factory called with an extra argument: TypeError at import'),
 # 6. base selector siblings: import-time lines outside the key tables
 't62b01': ([('sqlglot/parsers/duckdb.py', 'sub', 'exp.DType.DECIMAL: build_default_decimal_type(precision=18, scale=3),', '        exp.DType.DECIMAL: build_default_decimal_type(precision=18, scales=3),')], 'class table call keyword renamed: TypeError at import'),
 't62b02': ([('sqlglot/parsers/snowflake.py', 'sub', 'exp.DType.DECIMAL: build_default_decimal_type(precision=38, scale=0),', '        exp.DType.DECIMAL: build_default_decimal_type(38, 0, 1),')], 'class table call arity changed: TypeError at import'),
 't62b03': ([(HG, 'sub', '@unsupported_args("decimals")', '    @unsupported_args(("decimals",))')], 'method decorator argument changed to a 1-tuple: IndexError at class creation'),
 't62b04': ([('sqlglot/generators/clickhouse.py', 'sub', '@unsupported_args(("expression", "ClickHouse\'s arraySort does not support a comparator."))', '@unsupported_args(("expression",))')], 'module-level decorator argument shortened: IndexError at import'),
 't62b05': ([('sqlglot/generators/clickhouse.py', 'sub', '@unsupported_args("json_scope")', '    @unsupported_args(arg="json_scope")')], 'decorator argument turned into a keyword: TypeError at class creation'),
 't62b06': ([('sqlglot/generators/presto.py', 'sub', 'SELECT_KINDS = ()', '    SELECT_KINDS = tuple((), ())')], 'class attribute call with wrong arity: TypeError at class creation'),
 't62b07': ([('sqlglot/parsers/duckdb.py', 'sub', 'exp.DType.DECIMAL: build_default_decimal_type(precision=18, scale=3),', '        exp.DType.DECIMALS: build_default_decimal_type(precision=18, scale=3),')], 'attribute that does not exist in a class table key: AttributeError at import'),
 # 7. part B: one string edit per t46 proof
 't62s1': ([(G, 'sub', '"RETURNS NULL ON NULL INPUT" if e.args.get("null") else self.naked_property(e)', '            "RETURNS NULL ON EMPTY INPUT" if e.args.get("null") else self.naked_property(e)')], 'proof 1: string on a continuation line of a stored lambda'),
 't62s2': ([(HP, 'sub', '"""Map named_struct(\'k\', v, ...) to exp.Struct so _annotate_struct sees it."""', '    """Map named_struct(\'k\', v, ...) to exp.Struct so _annotate_struct sees it. Example: NAMED_STRUCT."""')], 'proof 2: docstring of a builder stored in a FUNCTIONS table'),
 't62s3': ([('sqlglot/generators/postgres.py', 'sub', 'exp.DType.TINYINT: "SMALLINT",', '        exp.DType.TINYINT: "SMALLINTEGER",')], 'proof 3: type spelling copied by Redshift and Materialize, parsed back in round trips'),
 't62s4': ([('sqlglot/dialects/oracle.py', 'sub', '"(+)": TokenType.JOIN_MARKER,', '            "(+ )": TokenType.JOIN_MARKER,')], 'proof 4: dialect keyword key that _Dialect.__new__ reads by membership (SUPPORTS_COLUMN_JOIN_MARKS)'),
 't62s5': ([('sqlglot/generators/presto.py', 'sub', 'exp.ArgMax: rename_func("MAX_BY"),', '        exp.ArgMax: rename_func("MAXIMUM_BY"),')], 'proof 5: rename_func argument inherited by Trino and Athena'),
}
manifest = {}
for cid, (edits, kind) in M.items():
    files = {}
    for rel, op, match, *rest in edits:
        lines = files.setdefault(rel, open(os.path.join(SRC, rel)).read().split('\n'))
        hits = [i for i, l in enumerate(lines) if match in l]
        assert len(hits) == 1, (cid, rel, match, len(hits))
        i = hits[0]
        if op == 'sub': lines[i] = rest[0]
        elif op == 'del': del lines[i]
        elif op == 'ins': lines.insert(i, rest[0])
        elif op == 'mv':
            l = lines.pop(i); a = [j for j, x in enumerate(lines) if rest[0] in x]; assert len(a) == 1; lines.insert(a[0], l)
    patch = ''
    for rel, new in files.items():
        old = open(os.path.join(SRC, rel)).read().split('\n')
        patch += ''.join(l + '\n' for l in difflib.unified_diff(old, new, f'a/{rel}', f'b/{rel}', lineterm='', n=3)).replace(f'--- a/{rel}', f'diff --git a/{rel} b/{rel}\n--- a/{rel}', 1)
    open(os.path.join(OUT, 'commits', cid + '.patch'), 'w').write(patch)
    manifest[cid] = {'files': sorted(files), 'kind': kind}
json.dump({'commits': manifest}, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(len(manifest))
