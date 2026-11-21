"""t30: deterministic new-kind probes against the pinned sqlglot source."""
import ast
import difflib
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'work/sqlglot'
OUT = Path(__file__).resolve().parent
manifest = {}

def emit(kind, label, changes):
    cid = f't30x{len(manifest):03d}'
    patches = []
    for path, before, after in changes:
        if after is not None and path.endswith('.py'):
            compile(after, path, 'exec')
        dest = path
        patches.append(f'diff --git a/{path} b/{dest}\n' + ''.join(difflib.unified_diff(
            (before or '').splitlines(True), (after or '').splitlines(True),
            fromfile=f'a/{path}' if before is not None else '/dev/null',
            tofile=f'b/{dest}' if after is not None else '/dev/null')))
    (OUT / 'commits' / (cid + '.patch')).write_text(''.join(patches))
    manifest[cid] = {'kind': kind, 'description': label, 'paths': [c[0] for c in changes]}

def replace(kind, label, path, old, new, count=1):
    before = (SRC / path).read_text()
    assert old in before, (label, old)
    emit(kind, label, [(path, before, before.replace(old, new, count))])

# 1. Class creation and string-name readers. No repeats of t15's pop/decorator probes.
M = 'metaclass'
D = 'sqlglot/dialects/dialect.py'
T = 'sqlglot/tokens.py'
E = 'sqlglot/expressions/core.py'
for label, path, old, new in [
 ('metaclass registry key', D, 'enum.value if enum is not None else clsname.lower()', 'clsname.upper()'),
 ('metaclass time trie', D, 'klass.TIME_TRIE = new_trie(klass.TIME_MAPPING)', 'klass.TIME_TRIE = new_trie(klass.FORMAT_MAPPING)'),
 ('metaclass string parser lookup', D, '"Parser", klass.__dict__.get("parser_class", base_parser[0])', '"Generator", klass.__dict__.get("parser_class", base_parser[0])'),
 ('metaclass inherited generator lookup', D, 'getattr(base, "generator_class", Generator)', 'getattr(base, "parser_class", Generator)'),
 ('metaclass shared transform mutation', D, 'gen_cls.TRANSFORMS.pop(part, None)', 'gen_cls.TRANSFORMS.pop(exp.Literal, None)'),
 ('metaclass quote endpoint', D, 'klass.QUOTE_START, klass.QUOTE_END = list(klass.tokenizer_class._QUOTES.items())[0]', 'klass.QUOTE_END, klass.QUOTE_START = list(klass.tokenizer_class._QUOTES.items())[0]'),
 ('tokenizer init-subclass quote source', T, 'cls._QUOTES = _convert_quotes(cls.QUOTES)', 'cls._QUOTES = _convert_quotes(cls.IDENTIFIERS)'),
 ('tokenizer string-name inheritance', T, '"BYTE_STRING_ESCAPES" in k.__dict__', '"STRING_ESCAPES" in k.__dict__'),
 ('expression required-args comprehension', E, 'cls.required_args = {k for k, v in cls.arg_types.items() if v}', 'cls.required_args = {k for k, v in cls.arg_types.items() if not v}'),
 ('quote converter at import', T, 'isinstance(item, str) else (item[0], item[1])', 'not isinstance(item, str) else (item[0], item[1])'),
 ('hive quote tuple value', 'sqlglot/dialects/hive.py', 'IDENTIFIERS = ["`"]', 'IDENTIFIERS = [("`", "!")]'),
 ('bigquery quote scalar value', 'sqlglot/dialects/bigquery.py', 'IDENTIFIERS = ["`"]', 'IDENTIFIERS = ["!"]'),
 ('generator string-read setting', 'sqlglot/generator.py', 'SUPPORTED_JSON_PATH_PARTS: t.ClassVar = ALL_JSON_PATH_PARTS.copy()', 'SUPPORTED_JSON_PATH_PARTS: t.ClassVar = {exp.Literal}'),
 ('snowflake inverse time map value', 'sqlglot/dialects/snowflake.py', '"T": "T",', '"T": "t",'),
]: replace(M, label, path, old, new)

# 2. Lazy globals, shared class memoization, rule registries, and per-instance negative controls.
C = 'cache'
G = 'sqlglot/generator.py'
O = 'sqlglot/optimizer/__init__.py'
for label, path, old, new in [
 ('dispatch memo stored under base class', G, '_DISPATCH_CACHE[cls] = dispatch', '_DISPATCH_CACHE[Generator] = dispatch'),
 ('dispatch memo read under base class', G, '_DISPATCH_CACHE.get(cls)', '_DISPATCH_CACHE.get(Generator)'),
 ('dispatch memo mutates previous cached table', G, '_DISPATCH_CACHE[cls] = dispatch', '_DISPATCH_CACHE[cls] = next(iter(_DISPATCH_CACHE.values()), dispatch)'),
 ('optimizer lazy global cached wrong name', O, 'globals()[name] = value', 'globals()["Scope"] = value'),
 ('optimizer lazy global writes extra name', O, 'globals()[name] = value', 'globals()[name] = value; globals()["optimize"] = value'),
 ('optimizer lazy RULES registry target', O, '"RULES": ("sqlglot.optimizer.optimizer", "RULES")', '"RULES": ("sqlglot.optimizer.optimizer", "optimize")'),
 ('optimizer lazy scope registry target', O, '"build_scope": ("sqlglot.optimizer.scope", "build_scope")', '"build_scope": ("sqlglot.optimizer.scope", "traverse_scope")'),
 ('optimizer rule registry swap', 'sqlglot/optimizer/optimizer.py', '    qualify,\n    pushdown_projections,\n    normalize,', '    normalize,\n    pushdown_projections,\n    qualify,'),
 ('scope column-cache reset', 'sqlglot/optimizer/scope.py', '        self._columns = None\n        self._external_columns = None\n        self._local_columns = None', '        self._columns = []\n        self._external_columns = []\n        self._local_columns = []'),
 ('resolver cache key loses only-visible', 'sqlglot/optimizer/resolver.py', 'cache_key = (name, only_visible)', 'cache_key = (name, False)'),
 ('dialect registry reload pollutes base', D, 'cls._classes[key] = attr', 'cls._classes[""] = attr'),
 ('dialect registry lazy result fallback', D, 'return cls._classes.get(key, default)', 'return cls._classes.get("", default)'),
]: replace(C, label, path, old, new)

# 3. Data, helpers, collection settings, exports, deletion, shadow modules and Rust path.
I = 'infrastructure'
for label, path, old, new in [
 ('identity SQL whitespace literal', 'tests/fixtures/identity.sql', 'SELECT', 'SE LECT'),
 ('optimizer fixture metadata', 'tests/fixtures/optimizer/qualify_columns.sql', '#', '##'),
 ('fixture comment becomes statement', 'tests/fixtures/optimizer/qualify_columns.sql', '--', 'SELECT 999; --'),
 ('test helper fixture separator', 'tests/helpers.py', 'f.read()).split(";")', 'f.read()).split(";;")'),
 ('test helper comment-filter sense', 'tests/helpers.py', 'line and not line.startswith("--")', 'line and line.startswith("--")'),
 ('test infrastructure collection config', 'pyproject.toml', '[project]', '[tool.pytest.ini_options]\naddopts = "--strict-markers"\nfilterwarnings = ["error"]\n\n[project]'),
 ('public re-export changes bound target', 'sqlglot/__init__.py', 'alias_ as alias,', 'column as alias,'),
 ('public re-export removed', 'sqlglot/__init__.py', '    select as select,\n', ''),
 ('TYPE_CHECKING made runtime', 'sqlglot/__init__.py', 'if t.TYPE_CHECKING:', 'if not t.TYPE_CHECKING:'),
 ('Rust import fallback catch narrowed', T, 'except ImportError:\n    pass', 'except ModuleNotFoundError:\n    pass'),
]: replace(I, label, path, old, new)
for label, path, text in [
 ('new module shadows stdlib json', 'json.py', 'raise RuntimeError("t30 shadow json")\n'),
 ('new Rust module triggers deprecation warning', 'sqlglotrs.py', '# Optional Rust package shadow\n'),
 ('new conftest fails all setup', 'tests/conftest.py', 'import pytest\n@pytest.fixture(autouse=True)\ndef t30_fixture():\n    assert False\n'),
]: emit(I, label, [(path, None, text)])
p = 'tests/helpers.py'
emit(I, 'deleted test support file', [(p, (SRC / p).read_text(), None)])

# 4. Patch shapes and runtime annotations.
S = 'shape'
for label, path, old, new in [
 ('dataclass field becomes ClassVar', 'sqlglot/lineage.py', '    name: str\n', '    name: t.ClassVar[str]\n'),
 ('dataclass required field becomes InitVar', 'sqlglot/diff.py', '    expression: exp.Expr\n', '    expression: t.ClassVar[exp.Expr]\n'),
 ('dataclass decorator argument', 'sqlglot/lineage.py', '@dataclass(frozen=True)', '@dataclass(frozen=False)'),
 ('dataclass field default factory', 'sqlglot/lineage.py', 'field(default_factory=list)', 'field(default_factory=dict)'),
 ('default argument references changed runtime expression', 'sqlglot/optimizer/optimizer.py', 'rules: Sequence[OptimizerFn] = RULES,', 'rules: Sequence[OptimizerFn] = RULES[1:],'),
 ('boolean and-or', 'tests/helpers.py', 'line and not line.startswith("--")', 'line or not line.startswith("--")'),
 ('membership operator', T, 'if cls.HINT_START in cls.KEYWORDS:', 'if cls.HINT_START not in cls.KEYWORDS:'),
 ('slice bound', 'sqlglot/optimizer/optimizer.py', 'inspect.getfullargspec(rule).args', 'inspect.getfullargspec(rule).args[1:]'),
 ('arithmetic operator', 'tests/helpers.py', 'if i + 1 < size:', 'if i - 1 < size:'),
 ('f-string comment text', 'sqlglot/lineage.py', 'f"<pre>SELECT {node.name} FROM {node.expression.this}</pre>"', 'f"<pre>SELECT {node.name # t30\n} FROM {node.expression.this}</pre>"'),
 ('multiline string whitespace', 'sqlglot/lineage.py', '<pre>SELECT {node.name} FROM', '<pre>SELECT  {node.name} FROM'),
]:
    if label == 'f-string comment text':
        # PEP 701 syntax: compile validated by the pinned 3.13 label container.
        continue
    replace(S, label, path, old, new)
# Pure move of a runtime helper's position, no semantic change.
p = 'tests/helpers.py'; before = (SRC / p).read_text(); tree = ast.parse(before)
n = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'is_compiled')
ls = before.splitlines(True); block = ''.join(ls[n.lineno-1:n.end_lineno])
emit(S, 'pure function move', [(p, before, ''.join(ls[:n.lineno-1] + ls[n.end_lineno:]) + '\n' + block)])
# Class-body order changes of defaulted dataclass fields.
replace(S, 'dataclass field declaration order', 'sqlglot/lineage.py', '    source_name: str = ""\n    reference_node_name: str = ""', '    reference_node_name: str = ""\n    source_name: str = ""')
# Two files: each read mapping changes only together for some consumers.
p = 'sqlglot/optimizer/__init__.py'; q = 'sqlglot/optimizer/optimizer.py'
a = (SRC / p).read_text(); b = (SRC / q).read_text()
emit(S, 'two-file lazy registry and rule default', [(p, a, a.replace('"optimize": ("sqlglot.optimizer.optimizer", "optimize")', '"optimize": ("sqlglot.optimizer.optimizer", "normalize")')),
    (q, b, b.replace('rules: Sequence[OptimizerFn] = RULES,', 'rules: Sequence[OptimizerFn] = RULES[1:],'))])
# SQL indentation inside a fixture is data, even when only whitespace changes.
p = 'tests/fixtures/identity.sql'; a = (SRC/p).read_text()
emit(S, 'SQL fixture whitespace only', [(p,a,a.replace('SELECT', ' SELECT', 1))])

# 5. Safe-by-profile swaps: low-context sites, calls, comprehensions and lambdas.
prof = json.load(gzip.open(ROOT / 'cmp.json.gz', 'rt'))
ops = [ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot]
spell = ['==','!=','<','<=','>','>=','is','is not']
candidates = []
for path, entries in prof['sites'].items():
    text = (SRC/path).read_text(); tree = ast.parse(text)
    for n in ast.walk(tree):
        if not isinstance(n,ast.Compare) or len(n.ops)!=1: continue
        e = entries.get(f'{n.lineno}:{n.col_offset}')
        if e is None: continue
        op, union, unattr, evaluated, flipped = e
        fam = (0,1,6,7) if op in (0,1,6,7) else (0,1,2,3,4,5)
        alts = [x for x in fam if x!=op and not union & (1<<x)]
        if not alts: continue
        count = len(prof['sets'][evaluated]); seg = ast.get_source_segment(text,n)
        if not count or '\n' in seg: continue
        candidates.append((count, path, n.lineno, n.col_offset, n, alts[0], text, seg))
seen = set()
for count,path,line,col,n,alt,text,seg in sorted(candidates,key=lambda x:x[:4]):
    if path in seen: continue
    nn = ast.parse(seg,mode='eval').body; nn.ops[0] = ops[alt]()
    ls = text.splitlines(True); s = ls[line-1]
    # AST columns count UTF-8 bytes; all chosen sites are ASCII.
    ls[line-1] = s[:col] + ast.unparse(nn) + s[n.end_col_offset:]
    emit('comparison',f'profile safe {count}-test site {path}:{line} {spell[alt]}',[(path,text,''.join(ls))])
    seen.add(path)
    if len(seen)==10: break

# Additional adversarial nested shapes: the outer table remains non-empty.
for label,path,old,new in [
 ('nested quote pair loses endpoint','sqlglot/dialects/hive.py','IDENTIFIERS = ["`"]','IDENTIFIERS = [("`",)]'),
 ('nested quote entry becomes empty list','sqlglot/dialects/bigquery.py','IDENTIFIERS = ["`"]','IDENTIFIERS = [[]]'),
 ('escape item changes type','sqlglot/dialects/hive.py','STRING_ESCAPES = ["\\\\"]','STRING_ESCAPES = [0]'),
 ('time-map value changes type','sqlglot/dialects/mysql.py','"%M": "%B"','"%M": 0'),
]: replace('metaclass',label,path,old,new)

for label,path,old,new in [
 ('chained lower bound','sqlglot/anonymize.py','start <= open_end < close_start','start < open_end < close_start'),
 ('chained upper bound','sqlglot/generators/bigquery.py','0 <= value <= 1','0 <= value < 1'),
 ('comparison lambda equality','sqlglot/executor/env.py','lambda this, e: this == e','lambda this, e: this is e'),
 ('comparison lambda mapping read','sqlglot/diff.py','matchings.get(t.cast(int, l)) == r','matchings.get(t.cast(int, l)) != r'),
 ('comparison in comprehension','sqlglot/dialects/athena.py','t.token_type != TokenType.SELECT','t.token_type is not TokenType.SELECT'),
 ('comparison in import-time generator','sqlglot/dialects/dialect.py','if t == token_type','if t is token_type'),
 ('comparison operand advances parser','sqlglot/parser.py','(atom := self._parse_atom()) is not None','(atom := self._parse_atom()) != None'),
]: replace('comparison',label,path,old,new)
p = 'sqlglot/lineage.py'; a = (SRC/p).read_text()
emit('shape','PEP 701 comment in f-string expression',[(p,a,a.replace('f"<pre>SELECT {node.name} FROM {node.expression.this}</pre>"',
    'f"<pre>SELECT {node.name # t30\\n} FROM {node.expression.this}</pre>"'.replace('\\n','\n'),1))])

replace('metaclass','time-map key changes type','sqlglot/dialects/mysql.py','"%M": "%B"','0: "%B"')
replace('metaclass','quote tuple arity shrinks','sqlglot/dialects/sqlite.py','("[", "]")','("[",)')
assert len(manifest) == 78, len(manifest)
(OUT/'manifest.json').write_text(json.dumps({'commits':manifest},indent=2)+'\n')
print('generated',len(manifest))
