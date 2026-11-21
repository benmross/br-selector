"""Diagnostic explicit-import graph; dynamic imports are NOT a safety proof."""
import ast
import gzip
import json
from pathlib import Path
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selector

root = Path(subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[1]),
    'rev-parse', '--path-format=absolute', '--git-common-dir'], text=True).strip()).parent
selector.SRC = str(root / 'work/sqlglot')
source = selector.Selector._load_sources()
modules = {rel: rel[:-3].replace('/', '.').removesuffix('.__init__') for rel in source}
edges = {}
for rel, text in source.items():
    module = modules[rel]
    package = module if rel.endswith('/__init__.py') else module.rpartition('.')[0]
    deps = {'.'.join(module.split('.')[:i]) for i in range(1, len(module.split('.')))}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            deps.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = package.split('.')[:len(package.split('.')) - node.level + 1] if node.level else []
            target = '.'.join(prefix + ([node.module] if node.module else []))
            deps.add(target)
            deps.update(target + '.' + alias.name for alias in node.names)
    edges[module] = deps - {module}

tests = json.load(open(root / 'sample/tests.json'))['tests']
mapping = json.load(gzip.open(Path(__file__).resolve().parents[1] / 'map.json.gz', 'rt'))
line_sets = mapping['sets']
closures = {}
for test in tests:
    module = modules[test['file']]
    if module in closures:
        continue
    seen, todo = set(), [module]
    while todo:
        item = todo.pop()
        if item not in seen:
            seen.add(item)
            todo.extend(edges.get(item, ()))
    closures[module] = seen

work = Path(sys.argv[1])
rows = []
for line in open(work / 'main-hid.why'):
    fields = line.split()
    if fields[1] != str(len(tests)):
        continue
    cid = fields[0]
    patch = root / 'work/wt/t9/work/t9/hid/commits' / (cid + '.patch')
    imported, covered = set(), set()
    for fp in selector.parse_patch(patch.read_text()):
        target = modules[fp.old]
        imported |= {test['number'] for test in tests if target in closures[modules[test['file']]]}
        old = Path(selector.SRC, fp.old).read_text()
        _, changed, inserted = selector.apply(old, fp)
        for ln in changed | inserted | {n + 1 for n in inserted}:
            sid = mapping['files'].get(fp.old, {}).get(str(ln))
            if sid is not None:
                covered.update(line_sets[sid])
    rows.append(dict(commit=cid, explicit_importers=sorted(imported), covered=sorted(covered),
                     union=sorted(imported | covered), reason=line.strip()))
json.dump(rows, open(work / 'hid15-importer-diagnostic.json', 'w'), indent=2)
print('Diagnostic only:', len(rows), 'commits. Dynamic imports and import-time side effects are not modeled.')
