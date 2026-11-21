"""t59 step 1: for class-4 commits, selection size and cost on a variant, failing tests, and the reasons that sized it."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; REPO = Path('/home/benmross/herald/projects/blast-radius')
E = ROOT / 'work/t59-eval'
variant = sys.argv[1]; only4 = '--all' not in sys.argv
tests = {r['number']: round(r['seconds'] * 1000) for r in json.load(open(REPO / 'sample/tests.json'))['tests']}
ans_paths = {'t41': REPO / 'mutants/t41/answers.json', 't46': ROOT / 'mutants/t46/answers.json',
             't56': REPO / 'work/wt/t56/mutants/t56/answers.json', 't59': ROOT / 'mutants/t59/answers.json'}
fresha_fb = set(l.split()[0] for l in open(REPO / 'work/wt/t54/work/t54/fresha.why') if 'census5 tok-str class 4' in l)
rows = []
for name in sys.argv[2:]:
    if name.startswith('--'): continue
    cls = json.load(open(E / f'{name}.cls.json')) if (E / f'{name}.cls.json').exists() else {}
    ans = json.load(open(ans_paths[name]))['commits'] if name in ans_paths and ans_paths[name].exists() else {}
    why = {}
    for l in open(E / f'{name}.{variant}.why'):
        m = re.match(r'(\S+) (\d+) tests; (.*)', l.rstrip('\n'))
        if m: why[m.group(1)] = m.group(3)
    for r in map(json.loads, open(E / f'{name}.{variant}.jsonl')):
        c = r['commit']
        if only4 and cls.get(c) != 4 and not (name == 'fresha' and c in fresha_fb): continue
        ws = [w for w in r['workers'] if w]; chosen = {n for w in ws for n in w}
        cost = (max((sum(tests[n] for n in w) for w in ws), default=0) + 2000 * len(ws)) / 1000
        f = ans.get(c, {}).get('failing')
        reasons = why.get(c, '')
        big = sorted(((int(x.group(1)), part) for part in reasons.split('; ')
                      for x in [re.search(r'(\d+)(?: tests| consumer tests| read it)?$', part)] if x), reverse=True)[:2]
        ev = [p for p in reasons.split('; ') if 'everything' in p][:1]
        rows.append((name, c, len(chosen), cost, '-' if f is None else len(f), ev[0] if ev else ' | '.join(p for _, p in big)))
for r in rows: print('%-6s %-9s %5d %6.1f %4s  %s' % r)
print('total', len(rows), 'cost', round(sum(r[3] for r in rows), 1))
