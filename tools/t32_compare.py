"""Compare measured selections, retaining every test difference and reason."""
import collections
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
datasets = sys.argv[2:] or ['hid', 'fresha', 'freshb', 'gate238']
tests = json.load(open(Path(__file__).resolve().parents[4] / 'sample/tests.json'))['tests']
ms = {t['number']: round(t['seconds'] * 1000) for t in tests}

def load(path):
    return {r['commit']: r for r in map(json.loads, open(path))}

def nums(r):
    return {n for w in r['workers'] for n in w}

def cost(r):
    w = [g for g in r['workers'] if g]
    return max((sum(ms[n] for n in g) for g in w), default=0) + 2000 * len(w)

def rule(why):
    # The final widening can override an earlier reason; prioritize it.
    for needle, name in [('possible import failure', 'could_raise'),
                         ('also runs at import', 'at_import'),
                         ('module constant read at import', 'read_at_import'),
                         ('removed key of', 'removed_key'),
                         ('changed constant in an import-time parse', 'parse_at_import'),
                         ('regex no longer', 'regex_at_import'),
                         ('lookup changed', 'lookup_at_import'),
                         ('definition header', 'definition_header'),
                         ('shared setup', 'shared_setup'),
                         ('never instantiated', 'uninstantiated_class'),
                         ('changed shape', 'reshaped'),
                         ('syntax error', 'syntax_error'),
                         ('comparison swap', 'comparison_profile')]:
        if needle in why:
            return name
    return 'coverage_or_other'

allrows = []
for data in datasets:
    old, main = (load(root / f'{v}-{data}.jsonl') for v in ('old', 'main'))
    why = {l.split(' ', 1)[0]: l.rstrip().split('tests; ', 1)[-1] for l in open(root / f'main-{data}.why')}
    rows = []
    for cid in sorted(main):
        a, b = nums(old[cid]), nums(main[cid])
        if a == b:
            continue
        rows.append(dict(dataset=data, commit=cid, rule=rule(why[cid]), reason=why[cid],
                         added=sorted(b-a), removed=sorted(a-b), old_ms=cost(old[cid]), main_ms=cost(main[cid]),
                         delta_ms=cost(main[cid])-cost(old[cid])))
    json.dump(rows, open(root / f'{data}-diff.json', 'w'), indent=2)
    allrows.extend(rows)
    print(data, 'old', sum(map(cost, old.values()))/1000, 'main', sum(map(cost, main.values()))/1000,
          'changed', len(rows))
json.dump(allrows, open(root / 'all-diff.json', 'w'), indent=2)
for direction in ('added', 'removed'):
    groups = collections.defaultdict(list)
    for row in allrows:
        if row[direction]:
            groups[row['rule']].append(row)
    total = sum(abs(r['delta_ms']) for group in groups.values() for r in group)
    print(direction, '| rule | commits | seconds | share |')
    for name, group in sorted(groups.items(), key=lambda item: -sum(abs(r['delta_ms']) for r in item[1])):
        sec = sum(abs(r['delta_ms']) for r in group)/1000
        print(f'| {name} | {len(group)} | {sec:.3f} | {sec*100000/total:.1f}% |')
