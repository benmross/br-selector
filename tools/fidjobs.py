"""Build fidelity jobs: commits a verification run dropped to zero, with the
static selection from a run without verification.
Usage: fidjobs.py VERIFY_OUT.jsonl STATIC_OUT.jsonl JOBS.json"""
import json, re, sys
v_out, s_out, dst = sys.argv[1:4]
passed = set()
for line in open(v_out + ".why"):
    m = re.match(r"^(\S+) \d+ tests;.*verify: \d+ tests \(\d+ ms recorded\) passed", line)
    if m:
        passed.add(m.group(1))
static = {}
for line in open(s_out):
    d = json.loads(line)
    static[d["commit"]] = sorted(n for w in d["workers"] for n in w)
dropped = {json.loads(l)["commit"] for l in open(v_out) if not any(json.loads(l)["workers"])}
jobs = {c: static[c] for c in passed if static.get(c)}
assert all(c in dropped for c in jobs)
json.dump(jobs, open(dst, "w"))
print(len(jobs), "jobs")
