"""t56 label table: class, failing tests, selections and simulated seconds of
c/nostr (8f45adc), main (57506a4) and this branch, misses.
usage: python3 tools/t56_table.py > reviews/t56-table.md (after t56_measure.py nostr/t56b runs)"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'work/t56-eval'
T = json.load(open(ROOT / 'mutants/t56/tests.json'))['tests']
sec = {t['number']: t['seconds'] for t in T}
man = json.load(open(ROOT / 'mutants/t56/manifest.json'))['commits']
cls = json.load(open(ROOT / 'mutants/t56/classes.json'))
ans = json.load(open(ROOT / 'mutants/t56/answers.json'))['commits']


def load(name):
    out = {}
    for r in map(json.loads, open(E / name)):
        ws = [w for w in r['workers'] if w]
        out[r['commit']] = ({n for w in ws for n in w}, max((sum(sec[n] for n in w) for w in ws), default=0) + 2 * len(ws))
    return out


nostr, main, mine = load('t56.nostr.jsonl'), load('t56.main.jsonl'), load('t56.t56b.jsonl')
print('| Mutant | Class | Change | Failing | c/nostr selects | c/nostr s | main s | w/t56 = c/nostr | Miss (c/nostr) |')
print('|---|---:|---|---:|---:|---:|---:|---|---|')
for cid in sorted(man, key=lambda c: (cls[c], c)):
    f = set(ans[cid]['failing']) if cid in ans else None
    s, cost = nostr[cid]
    miss = '-' if f is None else ('MISS ' + str(len(f - s)) if f - s else 'no')
    print(f"| {cid} | {cls[cid]} | {man[cid]['description']} | {'unlabeled' if f is None else len(f)} | {len(s)} | {cost:.1f} | {main[cid][1]:.1f} | {'yes' if mine[cid][0] == s else 'NO'} | {miss} |")
