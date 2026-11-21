"""Misses of a selection file against an answers file: python3 tools/t59_check.py <jsonl> <answers.json>"""
import json, sys
ans = json.load(open(sys.argv[2]))['commits']
rows = {r['commit']: {n for w in r['workers'] for n in w} for r in map(json.loads, open(sys.argv[1]))}
lab = [c for c in ans if c in rows]
miss = {c: sorted(set(ans[c].get('failing', [])) - rows[c]) for c in lab}
miss = {c: m for c, m in miss.items() if m}
fail = sum(1 for c in lab if ans[c].get('failing'))
print(f'labeled {len(lab)} (with failing tests {fail}), misses {len(miss)}', miss)
