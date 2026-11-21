"""New-kind probes: hierarchy, exception dispatch, generator protocols and binding."""
import ast, difflib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; SRC=ROOT/'work/sqlglot'; OUT=Path(__file__).resolve().parent
old_manifest=json.load(open(OUT/"manifest.json"))["commits"] if (OUT/"manifest.json").exists() else {}
manifest={}
def emit(kind,label,path,before,after):
    compile(after,path,'exec')
    cid=f't47x{len(manifest):03d}'
    patch=f'diff --git a/{path} b/{path}\n'+''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    (OUT/'commits'/f'{cid}.patch').write_text(patch)
    manifest[cid]={'kind':kind,'description':label,'paths':[path]}
    if old_manifest.get(cid,{}).get('description')==label:
        manifest[cid].update({k:v for k,v in old_manifest[cid].items() if k in ('tests','label_scope','deselect')})
def replace(kind,label,path,old,new):
    a=(SRC/path).read_text(); assert old in a,(path,old); emit(kind,label,path,a,a.replace(old,new,1))
E='sqlglot/errors.py'; C='sqlglot/expressions/core.py'; S='sqlglot/schema.py'; H='sqlglot/helper.py'
# Exception inheritance affects except/isinstance without executing the class body.
for name in ['UnsupportedError','ParseError','TokenError','OptimizeError','SchemaError','ExecuteError']:
    replace('exception-hierarchy',name+' bypasses SqlglotError',E,f'class {name}(SqlglotError):',f'class {name}(ValueError):')
replace('exception-hierarchy','root bypasses Exception',E,'class SqlglotError(Exception):','class SqlglotError(BaseException):')
replace('exception-hierarchy','ParseError also matches ValueError',E,'class ParseError(SqlglotError):','class ParseError(SqlglotError, ValueError):')
# Base removal and MRO reorder: object construction coverage need not credit isinstance consumers.
for name,base in [('Condition','Expr'),('Predicate','Condition'),('Binary','Condition'),('Connector','Binary'),('Func','Condition'),('AggFunc','Func')]:
    replace('hierarchy-base-swap',name+' parent bypassed',C,f'class {name}({base}):',f'class {name}(Expr):' if base!='Expr' else f'class {name}(object):')
for name,bases in [('Column','Expression, Condition'),('Literal','Expression, Condition'),('Dot','Expression, Binary'),('All','Expression, SubqueryPredicate'),('Anonymous','Expression, Func'),('Add','Expression, Binary'),('EQ','Expression, Binary, Predicate'),('DynamicIdentifier','Expression, Func')]:
    replace('hierarchy-MRO',name+' bases reversed',C,f'class {name}({bases}):',f'class {name}({", ".join(reversed(bases.split(", ")))}):')
replace('hierarchy-MRO','schema bases reversed',S,'class MappingSchema(AbstractMappingSchema, Schema):','class MappingSchema(Schema, AbstractMappingSchema):')
replace('hierarchy-base-removal','mapping loses Schema marker',S,'class MappingSchema(AbstractMappingSchema, Schema):','class MappingSchema(AbstractMappingSchema):')
# Exception handlers: replace the first handler in each distinct function.
seen=set()
for rel in ['sqlglot/helper.py','sqlglot/expressions/core.py','sqlglot/schema.py','sqlglot/parser.py','sqlglot/generator.py','sqlglot/optimizer/scope.py','sqlglot/optimizer/qualify_columns.py','sqlglot/executor/python.py','sqlglot/jsonpath.py','sqlglot/dialects/dialect.py']:
    a=(SRC/rel).read_text(); lines=a.splitlines(True); tree=ast.parse(a)
    for fn in ast.walk(tree):
        if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        hs=[h for h in ast.walk(fn) if isinstance(h,ast.ExceptHandler) and h.type is not None]
        if not hs or (rel,fn.name) in seen: continue
        h=hs[0]; old=ast.get_source_segment(a,h.type)
        if old=='RuntimeError': continue
        ls=lines.copy(); ln=ls[h.type.lineno-1]; start=h.type.col_offset; end=h.type.end_col_offset
        if h.type.lineno!=h.type.end_lineno: continue
        ls[h.type.lineno-1]=ln[:start]+'RuntimeError'+ln[end:]
        emit('except-dispatch',f'{rel}:{fn.name} catches RuntimeError instead of {old}',rel,a,''.join(ls)); seen.add((rel,fn.name))
        if len(seen)>=18: break
    if len(seen)>=18: break
# Generator protocol changes, termination and traversal direction.
for label,path,old,new in [
 ('flatten stops after first scalar',H,'            yield value','            yield value\n            return'),
 ('flatten returns nested iterator as element',H,'yield from flatten(value)','yield flatten(value)'),
 ('walk returns generator as element',C,'yield from self.bfs(prune=prune)','yield self.bfs(prune=prune)'),
 ('walk uses dfs on bfs branch',C,'yield from self.bfs(prune=prune)','yield from self.dfs(prune=prune)'),
 ('walk uses bfs on dfs branch',C,'yield from self.dfs(prune=prune)','yield from self.bfs(prune=prune)'),
 ('find-all terminates at first match',C,'                yield expression','                yield expression\n                return'),
 ('iter-expressions terminates in nested list',C,'                        yield t.cast(E, v)','                        yield t.cast(E, v)\n                        return'),
 ('toposort removes sorted order',H,'result.extend(sorted(current))','result.extend(current)'),
 ('merge-ranges removes sorted order',H,'ranges = sorted(ranges)','ranges = list(ranges)'),
 ('highlights preserve unsorted positions',E,'sorted_positions = sorted(positions, key=lambda pos: pos[0])','sorted_positions = list(positions)'),
]: replace('iteration-protocol',label,path,old,new)
# Signature category specifically keyword-only/positional-only (generic defaults already tested).
for label,path,old,new in [
 ('seq_get forces keyword index',H,'def seq_get(seq: Sequence[T], index: int)','def seq_get(seq: Sequence[T], *, index: int)'),
 ('new_trie forces keyword collection','sqlglot/trie.py','def new_trie(keywords: Iterable[key],','def new_trie(*, keywords: Iterable[key],'),
 ('in_trie forces positional-only','sqlglot/trie.py','def in_trie(trie: dict, key: key)','def in_trie(trie: dict, key: key, /)'),
 ('ParseError message keyword only',E,'        message: str,\n        errors:','        *,\n        message: str,\n        errors:'),
]: replace('signature-binding',label,path,old,new)
# Implicit descriptor binding beyond decorator removal: property becomes non-data descriptor.
for rel,clsname,method in [('sqlglot/tokens.py','Tokenizer','sql'),('sqlglot/tokens.py','Tokenizer','tokens'),(S,'MappingSchema','dialect'),(S,'AbstractMappingSchema','empty'),(C,'Expression','name'),(C,'Expression','output_name')]:
    a=(SRC/rel).read_text(); tree=ast.parse(a)
    cls=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name==clsname)
    fn=next((n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==method),None)
    if fn is None: continue
    dec=next((n for n in fn.decorator_list if isinstance(n,ast.Name) and n.id=='property'),None)
    if dec is None: continue
    ls=a.splitlines(True); ls[dec.lineno-1]=ls[dec.lineno-1].replace('@property','@staticmethod')
    emit('descriptor-binding',f'{clsname}.{method} property becomes staticmethod',rel,a,''.join(ls))
# Implicit mapping protocol and inherited super call; different from table shape/slots changes.
replace('mapping-protocol','mapping no longer inherits Mapping',H,'class SingleValuedMapping(Mapping[K, V]):','class SingleValuedMapping:')
replace('super-protocol','ParseError omits Exception initialization',E,'        super().__init__(message)','        pass')
replace('super-protocol','TokenError omits Exception initialization',E,'        super().__init__(message)\n        self.start','        pass\n        self.start')
# Parent removal introduces no new lexical names, bypassing could_raise widening.
for name in ['UnsupportedError','ParseError','TokenError','OptimizeError','SchemaError','ExecuteError']:
    replace('exception-base-removal',name+' ceases to be exception',E,f'class {name}(SqlglotError):',f'class {name}:')
for name,bases in [('Column','Expression, Condition'),('Literal','Expression, Condition'),('Dot','Expression, Binary'),('All','Expression, SubqueryPredicate'),('Anonymous','Expression, Func'),('Add','Expression, Binary'),('EQ','Expression, Binary, Predicate'),('DynamicIdentifier','Expression, Func')]:
    replace('hierarchy-base-removal',name+' loses concrete Expression implementation',C,f'class {name}({bases}):',f'class {name}({bases.replace('Expression, ', '')}):')
# Keep one fully labeled MRO-reorder representative (014). Prioritize the other
# new mechanisms over seven redundant reorder variants within the task budget.
# --all regenerates the initial 79-probe exploration pool with stable ids.
if '--all' not in sys.argv:
    for i in range(15,22):
        cid=f't47x{i:03d}'
        manifest.pop(cid)
        (OUT/'commits'/f'{cid}.patch').unlink()
(OUT/'manifest.json').write_text(json.dumps({'commits':manifest},indent=2)+'\n')
print('generated',len(manifest))
