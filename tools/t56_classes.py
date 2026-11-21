"""Per-class evidence for dropping the string-word fallback: t56 labels plus
the gate mutants where c/nostr is narrower than main (string edits main sent
to everything). Prints mutants, breaking share, c/nostr misses and the 95%
upper bound on the miss chance per breaking edit (3/n when 0 misses)."""
import json, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ans = json.load(open(ROOT / 'mutants/t56/answers.json'))['commits']
cls = json.load(open(ROOT / 'mutants/t56/classes.json'))
sel = {r['commit']: {n for w in r['workers'] for n in w} for r in map(json.loads, open(ROOT / 'work/t56-eval/t56.nostr.jsonl'))}
gate = json.load(open(ROOT / 'reviews/t56/gate651-narrower-than-main.json'))
gcls = json.load(open(ROOT / 'reviews/t56/gate651-narrower-classes.json'))
st = collections.defaultdict(lambda: {'t56': [0, 0, 0], 'gate': [0, 0, 0]})
for c, a in ans.items():
    f = set(a['failing']); s = st[cls[c]]['t56']
    s[0] += 1; s[1] += bool(f); s[2] += bool(f - sel[c])
for c, v in gate.items():
    s = st[gcls[c]]['gate']; s[0] += 1; s[1] += v['failing'] > 0  # gate misses: 0 (c/nostr gate PASS)
print('| Class | t56 labeled | t56 breaking | gate narrowed | gate breaking | c/nostr misses | breaking share | 95% bound per breaking edit |')
print('|---:|---:|---:|---:|---:|---:|---:|---:|')
for k in sorted(st):
    a, g = st[k]['t56'], st[k]['gate']
    n, b, m = a[0] + g[0], a[1] + g[1], a[2]
    print(f"| {k} | {a[0]} | {a[1]} | {g[0]} | {g[1]} | {m} | {b}/{n} = {b / n:.0%} | {'%.1f%%' % min(100, 300 / b) if b and not m else '-'} |")
