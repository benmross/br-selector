"""Merge key_trace output (keys.<worker>.json) into keys.json.gz for the selector.

usage: python3 tools/build_keys.py <trace prefix> <tests.json> <out keys.json.gz>
Setup and teardown probes (class or module fixtures) are credited to every test
of the same test class, or of the same file for module-level tests."""
import glob, gzip, json, sys
prefix, tests_path, out = sys.argv[1:4]
tests = {t['id']: t['number'] for t in json.load(open(tests_path))['tests']}
by_prefix = {}
for nid, n in tests.items():
    base = nid.split('[')[0]
    by_prefix.setdefault(base.rsplit('::', 1)[0], set()).add(n)
tables, glob_, groups, mro, ran, unknown = {}, {}, {}, {}, set(), set()

def nums(ctx):
    if ctx == '@global':
        return None
    nid, _, phase = ctx.partition('|')
    if not phase:
        if nid in tests:
            return {tests[nid]}
        unknown.add(nid)
        return set(by_prefix.get(nid.split('[')[0].rsplit('::', 1)[0], ()))
    return set(by_prefix.get(nid.split('[')[0].rsplit('::', 1)[0], ())) or ({tests[nid]} if nid in tests else set())

files = sorted(glob.glob(prefix + '.*.json'))
assert files, prefix
for fn in files:
    d = json.load(open(fn))
    for name, g in d['groups'].items():
        if name in groups:
            assert groups[name] == g, name  # same import in every worker
        groups[name] = g
    mro.update(d['mro'])
    for nid in d['ran']:
        if nid in tests: ran.add(tests[nid])
        else: unknown.add(nid)
    for ctx, tbls in d['probes'].items():
        ns = nums(ctx)
        for t, ks in tbls.items():
            if ns is None:
                glob_.setdefault(t, {'p': set(), 'w': 0})['p'].update(ks)
                continue
            p = tables.setdefault(t, {'p': {}, 'w': set()})['p']
            for k in ks:
                p.setdefault(k, set()).update(ns)
    for ctx, tbls in d['whole'].items():
        ns = nums(ctx)
        for t in tbls:
            if ns is None:
                glob_.setdefault(t, {'p': set(), 'w': 0})['w'] = 1
            else:
                tables.setdefault(t, {'p': {}, 'w': set()})['w'].update(ns)
gid_ix = {}
res = {'tables': {}, 'global': {t: {'p': sorted(v['p']), 'w': v['w']} for t, v in glob_.items()},
       'ran': sorted(ran), 'tables_traced': sorted(groups)}
for name in sorted(groups):
    v = tables.get(name, {'p': {}, 'w': set()})
    res['tables'][name] = {'p': {k: sorted(s) for k, s in sorted(v['p'].items())}, 'w': sorted(v['w']),
                           'g': {k: gid_ix.setdefault(g, len(gid_ix)) for k, g in groups[name].items()},
                           'mro': mro.get(name, [])}
for t in tables:
    if t not in groups:  # dispatch or other names without a group map
        res['tables'].setdefault(t, {'p': {k: sorted(s) for k, s in tables[t]['p'].items()}, 'w': sorted(tables[t]['w']), 'g': {}, 'mro': []})
# Tests that start another interpreter: their probes are not traced.
import ast, os
src = os.environ.get('SQLGLOT_SRC')
spawn = set()
if src:
    for root, _, fs in os.walk(os.path.join(src, 'tests')):
        for fn in fs:
            if not fn.endswith('.py'): continue
            rel = os.path.relpath(os.path.join(root, fn), src); text = open(os.path.join(root, fn)).read()
            tree = ast.parse(text)
            def visit(node, chain):
                for ch in ast.iter_child_nodes(node):
                    if isinstance(ch, ast.ClassDef): visit(ch, chain + [ch.name])
                    elif isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        seg = ast.get_source_segment(text, ch) or ''
                        if any(w in seg for w in ('subprocess', 'sys.executable', 'os.system', 'multiprocessing', 'Popen')):
                            base = '::'.join([rel] + chain + [ch.name])
                            spawn.update(n for nid, n in tests.items() if nid.split('[')[0] == base or nid.startswith(base + '['))
                            if not ch.name.startswith('test'):  # helper or fixture: the whole class or file
                                spawn.update(by_prefix.get('::'.join([rel] + chain), ()))
            visit(tree, [])
res['spawn'] = sorted(spawn)
# Expression classes bound under their own __name__ (exp.Foo keys in TRANSFORMS).
if src:
    sys.path.insert(0, src)
    import sqlglot.expressions as E
    res['exp_names'] = sorted(n for n, o in vars(E).items() if isinstance(o, type) and o.__name__ == n)
with gzip.open(out, 'wt') as f:
    json.dump(res, f, separators=(',', ':'))
print('spawn', len(spawn), 'tables', len(res['tables']), 'ran', len(ran), 'of', len(tests), 'unknown ids', len(unknown), sorted(unknown)[:5],
      'global', {t: (len(v['p']), v['w']) for t, v in res['global'].items()})
