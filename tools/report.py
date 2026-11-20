"""Per-commit breakdown: cost, misses and the best possible cost."""
import json
import sys

sample, out = sys.argv[1], sys.argv[2]
tests = {t["number"]: round(t["seconds"] * 1000) for t in json.load(open(f"{sample}/tests.json"))["tests"]}
ans = json.load(open(f"{sample}/answers.json"))["commits"]
tot = opt = 0
for line in open(out):
    r = json.loads(line)
    w = [x for x in r["workers"] if x]
    cost = (max(sum(tests[n] for n in x) for x in w) + 2000 * len(w)) if w else 0
    sel = {n for x in w for n in x}
    a = ans[r["commit"]]
    miss = [n for n in a["failing"] if n not in sel]
    best = (sum(tests[n] for n in a["failing"]) + 2000) if a["failing"] else 0
    tot += cost + (300000 if miss else 0)
    opt += best
    flag = "MISS" if miss else ""
    print(f"{r['commit']} {a['kind']:8} sel {len(sel):5} fail {len(a['failing']):3} cost {cost/1000:7.2f} best {best/1000:6.2f} {flag} {miss[:5]}")
print(f"total {tot/1000:.1f} s   floor about {opt/1000:.1f} s")
