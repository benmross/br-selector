"""Markdown table of class-4 commits: c/nostr vs candidate selections, failing tests, deciding rule."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; REPO = Path('/home/benmross/herald/projects/blast-radius'); E = ROOT / 'work/t59-eval'
nv, cv = sys.argv[1], sys.argv[2]
tests = {r['number']: round(r['seconds'] * 1000) for r in json.load(open(REPO / 'sample/tests.json'))['tests']}
ans = {'t41': REPO / 'mutants/t41/answers.json', 't46': ROOT / 'mutants/t46/answers.json',
       't56': E / 't56-legion-answers.json', 't59': ROOT / 'mutants/t59/answers.json'}
fb = set(l.split()[0] for l in open(REPO / 'work/wt/t54/work/t54/fresha.why') if 'census5 tok-str class 4' in l)
def load(s, v):
    rows = {r['commit']: r for r in map(json.loads, open(E / f'{s}.{v}.jsonl'))}
    why = {}
    for l in open(E / f'{s}.{v}.why'):
        m = re.match(r'(\S+) (\d+) tests; (.*)', l.rstrip('\n'))
        if m: why[m.group(1)] = m.group(3)
    return rows, why
def cost(r):
    ws = [w for w in r['workers'] if w]; return len({n for w in ws for n in w}), (max((sum(tests[n] for n in w) for w in ws), default=0) + 2000 * len(ws)) / 1000
def rule(w):
    parts = w.split('; ')
    ev = [p for p in parts if 'everything' in p or 'declined' in p or 'keep class users' in p or 'not audited' in p]
    key = [p for p in parts if ' entries ' in p]
    if key: return 'key rule: ' + re.sub(r'^\S+:\d+ ', '', key[0]).split(':', 1)[0] + ' ' + re.search(r'entries (\S+?):', key[0]).group(1)[:40]
    if ev: return re.sub(r'^sqlglot/', '', ev[0])[:90]
    big = sorted(((int(x.group(1)), p) for p in parts for x in [re.search(r'(\d+)(?: consumer tests| read it)?$', p)] if x), reverse=True)
    return re.sub(r'^sqlglot/', '', big[0][1])[:90] if big else ''
print('| set | commit | c/nostr tests | c/nostr s | candidate tests | candidate s | failing | rule on c/nostr | rule on candidate |')
print('|---|---|---:|---:|---:|---:|---:|---|---|')
tot = [0, 0]
for s in sys.argv[3:]:
    cls = json.load(open(E / f'{s}.cls.json')) if (E / f'{s}.cls.json').exists() else {}
    a = json.load(open(ans[s]))['commits'] if s in ans and Path(ans[s]).exists() else {}
    (nr, nw), (cr, cw) = load(s, nv), load(s, cv)
    for c in nr:
        if s == 't59' or cls.get(c) == 4 or (s == 'fresha' and c in fb):
            n, ns = cost(nr[c]); k, ks = cost(cr[c]); f = a.get(c, {}).get('failing')
            tot[0] += ns; tot[1] += ks
            print(f"| {s} | {c} | {n} | {ns:.1f} | {k} | {ks:.1f} | {'-' if f is None else len(f)} | {rule(nw.get(c, ''))} | {rule(cw.get(c, ''))} |")
print(f'\nTotal over these commits: c/nostr {tot[0]:.1f} s, candidate {tot[1]:.1f} s.')
