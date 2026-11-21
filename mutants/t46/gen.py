"""Adversarial string edits against the pinned source, independent of t41 labels."""
import ast, difflib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=Path('/home/benmross/herald/projects/blast-radius/work/sqlglot')
OUT=Path(__file__).resolve().parent
manifest={}
def emit(cid,path,old,new,kind,proof):
    before=(SRC/path).read_text()
    assert before.count(old)==1,(cid,path,old,before.count(old))
    after=before.replace(old,new,1)
    compile(after,path,'exec')
    patch=f'diff --git a/{path} b/{path}\n'+''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    (OUT/'commits'/f'{cid}.patch').write_text(patch)
    manifest[cid]={'kind':kind,'path':path,'proof_challenge':proof}
# Choose actual lambda-body string constants, including keys passed to runtime
# helper calls. Corrupting a key can raise rather than merely alter SQL text.
paths=['sqlglot/generator.py']+[f'sqlglot/generators/{d}.py' for d in ['bigquery','duckdb','presto','postgres','redshift']]
for i,path in enumerate(paths):
    text=(SRC/path).read_text(); tree=ast.parse(text)
    chosen=None
    for n in ast.walk(tree):
        if not isinstance(n,ast.Lambda): continue
        for c in ast.walk(n.body):
            if not isinstance(c,ast.Constant) or not isinstance(c.value,str) or not c.value: continue
            seg=ast.get_source_segment(text,c)
            try: good=ast.literal_eval(seg)==c.value
            except Exception: good=False
            if good and text.count(seg)==1:
                chosen=(seg,repr('T46_BROKEN_'+c.value));break
        if chosen:break
    assert chosen,path
    emit(f't46a{i:02}',path,*chosen,'a lambda body','wrong runtime name or SQL; base/subclass copies must retain lambda coverage')
# Module/class/function docstrings and inert attribute documentation.
docs=[('sqlglot/__init__.py','Whether to format generated SQL by default.'),
('sqlglot/errors.py','Ignore all errors.'),
('sqlglot/dialects/dialect.py','Dialects supported by SQLGLot.'),
('sqlglot/dialects/dialect.py','Unquoted identifiers are lowercased.'),
('sqlglot/expressions/core.py','This is so that docstrings are not inherited in pdoc'),
('sqlglot/optimizer/__init__.py','Lazy re-exports from optimizer submodules.')]
# The core case changes the actual Expr docstring: its metaclass normalizes
# __doc__ at import, but does not consume its content to construct behavior.
text=(SRC/'sqlglot/expressions/core.py').read_text()
tree=ast.parse(text)
expr=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Expr')
seg=ast.get_source_segment(text,expr.body[0].value)
docs[4]=('sqlglot/expressions/core.py',seg)
for i,(path,old) in enumerate(docs):
    new=old[:-3]+' T46_DOCSTRING_ADVERSARY\n"""' if i==4 else old+' T46_DOCSTRING_ADVERSARY'
    emit(f't46g{i:02}',path,old,new,'g inert string','docstring consumer/enum/metaclass must not change behavior')
# Additional values attack the generator-specific same-type table proof.
for i,(d,old,new) in enumerate([
 ('redshift','exp.DType.BLOB: "VARBYTE",','exp.DType.BLOB: "T46_BLOB",'),
 ('presto','exp.DType.FLOAT: "REAL",','exp.DType.FLOAT: "T46_FLOAT",'),
 ('postgres','exp.DType.TINYINT: "SMALLINT",','exp.DType.TINYINT: "T46_TINYINT",'),
 ('duckdb','exp.DType.BINARY: "BLOB",','exp.DType.BINARY: "T46_BINARY",'),
 ('bigquery','exp.DType.TEXT: "STRING",','exp.DType.TEXT: "T46_TEXT",'),
 ('mysql','exp.DType.VARCHAR: "CHAR",','exp.DType.VARCHAR: "T46_VARCHAR",')]):
    path='sqlglot/generators/'+d+'.py'
    before=(SRC/path).read_text()
    if before.count(old)!=1:
        # Choose a unique direct string value from TYPE_MAPPING, independent
        # of its test failures; never use the held-out t41 patch text.
        tree=ast.parse(before)
        stmt=next(n for n in ast.walk(tree) if isinstance(n,(ast.Assign,ast.AnnAssign))
            and any(isinstance(t,ast.Name) and t.id=='TYPE_MAPPING' for t in (n.targets if isinstance(n,ast.Assign) else [n.target]))
            and isinstance(n.value,ast.Dict))
        c=next(v for v in stmt.value.values if isinstance(v,ast.Constant) and isinstance(v.value,str)
            and before.count(ast.get_source_segment(before,v))==1)
        old=ast.get_source_segment(before,c);new=repr('T46_TYPE_'+c.value)
    emit(f't46b{i:02}',path,old,new,'b table value','type-name runtime consumers, aliases and cross-dialect casts')
# Keys include a base tokenizer key used throughout unrelated dialects and
# keys that import-time pop calls require (those must remain conservative).
for i,(d,old,new) in enumerate([
 ('redshift','"BINARY VARYING": TokenType.VARBINARY,','"T46 BINARY": TokenType.VARBINARY,'),
 ('duckdb','"SORT BY": TokenType.ORDER_BY,','"T46 SORT BY": TokenType.ORDER_BY,'),
 ('snowflake','"QUALIFY": TokenType.QUALIFY,','"T46 QUALIFY": TokenType.QUALIFY,'),
 ('tsql','"DATETIME2": TokenType.DATETIME2,','"T46_DATETIME2": TokenType.DATETIME2,'),
 ('bigquery','"INT64": TokenType.BIGINT,','"T46_INT64": TokenType.BIGINT,'),
 ('base','"SELECT": TokenType.SELECT,','"T46_SELECT": TokenType.SELECT,')]):
    path='sqlglot/tokens.py' if d=='base' else 'sqlglot/dialects/'+d+'.py'
    before=(SRC/path).read_text()
    if before.count(old)!=1:
        tree=ast.parse(before)
        stmt=next(n for n in ast.walk(tree) if isinstance(n,(ast.Assign,ast.AnnAssign))
            and any(isinstance(t,ast.Name) and t.id=='KEYWORDS' for t in (n.targets if isinstance(n,ast.Assign) else [n.target]))
            and isinstance(n.value,ast.Dict))
        c=next(k for k in stmt.value.keys if isinstance(k,ast.Constant) and isinstance(k.value,str)
            and before.count(ast.get_source_segment(before,k))==1)
        old=ast.get_source_segment(before,c);new=repr('T46_KEY_'+c.value)
    emit(f't46c{i:02}',path,old,new,'c table key','token trie, cross-dialect imports and required popped keys')
# A sixth proof-positive callback; the BigQuery first-lambda control above
# deliberately remains outside the direct-storage proof.
path='sqlglot/generators/snowflake.py'
text=(SRC/path).read_text();tree=ast.parse(text)
for stmt in ast.walk(tree):
    if not isinstance(stmt,ast.Assign) or not any(isinstance(t,ast.Name) and t.id=='TRANSFORMS' for t in stmt.targets) or not isinstance(stmt.value,ast.Dict):continue
    done=False
    for value in stmt.value.values:
        if not isinstance(value,ast.Lambda):continue
        for c in ast.walk(value.body):
            if not isinstance(c,ast.Constant) or not isinstance(c.value,str) or not c.value:continue
            seg=ast.get_source_segment(text,c)
            try:good=ast.literal_eval(seg)==c.value
            except Exception:good=False
            if good and ast.get_source_segment(text,value).count(seg)==1:
                full=ast.get_source_segment(text,value)
                emit('t46a06',path,full,full.replace(seg,repr('T46_CALLBACK_'+c.value),1),'a lambda body','subclass dispatch callback after table copies')
                done=True;break
        if done:break
    if done:break
assert 't46a06' in manifest
path='sqlglot/typing/annotators.py';text=(SRC/path).read_text();tree=ast.parse(text)
for node in ast.walk(tree):
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):
        old=ast.get_source_segment(text,node.body[0].value)
        if text.count(old)==1:
            emit('t46g06',path,old,repr(node.body[0].value.value+'\nT46_DOC_CODE_CONSTANT'),'g inert string','function doc is a co_consts input; retain TestTyping even without function execution')
            break
assert 't46g06' in manifest
# rename_func stores its argument in a closure and only formats it at runtime.
for i,d in enumerate(['bigquery','clickhouse','snowflake','mysql','presto','duckdb']):
    path='sqlglot/generators/'+d+'.py';text=(SRC/path).read_text();tree=ast.parse(text)
    done=False
    for stmt in ast.walk(tree):
        if not isinstance(stmt,ast.Assign) or not any(isinstance(t,ast.Name) and t.id=='TRANSFORMS' for t in stmt.targets) or not isinstance(stmt.value,ast.Dict):continue
        for value in stmt.value.values:
            if not isinstance(value,ast.Call) or not isinstance(value.func,ast.Name) or value.func.id!='rename_func' or len(value.args)!=1 or not isinstance(value.args[0],ast.Constant) or not isinstance(value.args[0].value,str):continue
            full=ast.get_source_segment(text,value);c=value.args[0];seg=ast.get_source_segment(text,c)
            if text.count(full)==1:
                emit(f't46r{i:02}',path,full,full.replace(seg,repr('T46_RENAME_'+c.value),1),'b stored rename factory','closure capture, inherited dispatch, runtime function name formatting')
                done=True;break
        if done:break
    assert done,path
path='sqlglot/generators/oracle.py';text=(SRC/path).read_text();tree=ast.parse(text)
done=False
for stmt in ast.walk(tree):
    if not isinstance(stmt,ast.Assign) or not any(isinstance(t,ast.Name) and t.id=='TRANSFORMS' for t in stmt.targets) or not isinstance(stmt.value,ast.Dict):continue
    for value in stmt.value.values:
        if not isinstance(value,ast.Lambda):continue
        for c in ast.walk(value.body):
            if not isinstance(c,ast.Constant) or not isinstance(c.value,str) or not c.value:continue
            seg=ast.get_source_segment(text,c);full=ast.get_source_segment(text,value)
            try:good=ast.literal_eval(seg)==c.value
            except Exception:good=False
            if good and full.count(seg)==1 and text.count(full)==1:
                emit('t46a07',path,full,full.replace(seg,repr('T46_ORACLE_'+c.value),1),'a lambda body','runtime helper name corruption in a distinct stored callback')
                done=True;break
        if done:break
    if done:break
assert done
json.dump({'commits':manifest},open(OUT/'manifest.json','w'),indent=2)
