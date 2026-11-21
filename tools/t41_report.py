"""t41 report: per-patch labels against main's and dc91341's selections.

Usage: python tools/t41_report.py  (from the worktree root)
Reads mutants/t41/{manifest,answers}.json, mutants/t41/main-select.why,
work/t41/{main,dc}.jsonl and sample tests.json; writes reviews/t41-matrix.md.
"""
import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'mutants/t41')
SAMPLE = os.environ.get('SAMPLE', '/home/benmross/herald/projects/blast-radius/sample/tests.json')
tests = {t['number']: t['id'] for t in json.load(open(SAMPLE))['tests']}
manifest = json.load(open(os.path.join(T, 'manifest.json')))['commits']
answers = json.load(open(os.path.join(T, 'answers.json')))['commits'] if os.path.exists(os.path.join(T, 'answers.json')) else {}


def selections(path):
    out = {}
    for line in open(path):
        r = json.loads(line)
        out[r['commit']] = {n for w in r['workers'] for n in w}
    return out


main = selections(os.path.join(ROOT, 'mutants/t41/main.jsonl'))
dc = selections(os.path.join(ROOT, 'mutants/t41/dc91341.jsonl'))
why = {}
for line in open(os.path.join(T, 'main-select.why')):
    m = re.match(r'(t41x\d+) \d+ tests; (.*)', line)
    if m:
        why[m.group(1)] = m.group(2).strip()


def short(n):
    return tests[n].split('::', 1)[-1] if n in tests else str(n)


rows, agg = [], defaultdict(Counter)
for cid in sorted(manifest):
    v = manifest[cid]
    s = v['kind']
    agg[s]['patches'] += 1
    agg[s]['main fallbacks'] += 'possible import failure, everything' in why.get(cid, '')
    if cid not in answers:
        rows.append((s, cid, v['description'], 'unlabeled', '', len(main[cid]), why.get(cid, ''), len(dc[cid]), ''))
        continue
    fail = set(answers[cid]['failing'])
    agg[s]['labeled'] += 1
    agg[s]['breaking'] += bool(fail)
    missed = fail - dc[cid]
    agg[s]['dc91341 misses'] += bool(missed)
    names = ', '.join(short(n) for n in sorted(fail)[:4]) + (f' (+{len(fail) - 4})' if len(fail) > 4 else '')
    rows.append((s, cid, v['description'], str(len(fail)), names, len(main[cid]), why.get(cid, ''),
                 len(dc[cid]), f'MISS {len(missed)}: ' + ', '.join(short(n) for n in sorted(missed)[:3]) if missed else 'no'))

out = ['# t41 string-literal labels', '',
       '| Stratum | Patches | Labeled | Breaking | Main fallbacks | dc91341 misses |', '|---|---:|---:|---:|---:|---:|']
for s in sorted(agg):
    a = agg[s]
    out.append(f"| {s} | {a['patches']} | {a['labeled']} | {a['breaking']} | {a['main fallbacks']} | {a['dc91341 misses']} |")
tot = sum(agg.values(), Counter())
out.append(f"| all | {tot['patches']} | {tot['labeled']} | {tot['breaking']} | {tot['main fallbacks']} | {tot['dc91341 misses']} |")
out += ['', '| Stratum | Patch | Change | Failing | Failing tests | Main selects | Main reason | dc91341 selects | dc91341 miss |',
        '|---|---|---|---:|---|---:|---|---:|---|']
for r in rows:
    out.append('| ' + ' | '.join(str(x).replace('|', '/') for x in r) + ' |')
os.makedirs(os.path.join(ROOT, 'reviews'), exist_ok=True)
open(os.path.join(ROOT, 'reviews/t41-matrix.md'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(out[:len(agg) + 5]))
