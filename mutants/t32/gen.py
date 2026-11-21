"""Regenerate the 30 t32 patches from their pinned-source manifest."""
import ast
import difflib
import json
import os
from pathlib import Path

here = Path(__file__).resolve().parent
root = Path(os.environ.get('SQLGLOT_SRC', str(here.parents[1] / 'work/sqlglot')))
manifest = json.load(open(here / 'manifest.json'))['commits']
for cid, row in manifest.items():
    old = (root / row['file']).read_text()
    if row['kind'] == 'stock_argparse_help_only':
        assert old.count(row['old']) == 1
        new = old.replace(row['old'], row['new'])
    else:
        candidates = [n for n in ast.walk(ast.parse(old)) if isinstance(n, ast.Constant)
                      and n.lineno == row['line'] and n.value == row['old']]
        assert len(candidates) == 1
        node = candidates[0]
        lines = old.splitlines(keepends=True)
        line = lines[node.lineno - 1]
        lines[node.lineno - 1] = line[:node.col_offset] + repr(row['new']) + line[node.end_col_offset:]
        new = ''.join(lines)
    path = row['file']
    patch = f'diff --git a/{path} b/{path}\n' + ''.join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile='a/' + path, tofile='b/' + path))
    (here / 'commits' / (cid + '.patch')).write_text(patch)
print(f'{len(manifest)} patches regenerated')
