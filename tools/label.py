"""Label mutants: apply each to /src, run the whole suite, record failing tests.

Runs inside python:3.13-slim with requirements.lock installed.
Usage: python label.py /muts /src /out/answers.json
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/kit")
from selector import apply, parse_patch  # noqa: E402

muts, src, out = sys.argv[1:4]
shard, nshards = (int(x) for x in (sys.argv[4:6] if len(sys.argv) > 5 else ("0", "1")))
tests = {t["id"]: t["number"] for t in json.load(open("/kit/sample/tests.json"))["tests"]}
answers = json.load(open(out))["commits"] if os.path.exists(out) else {}
env = dict(os.environ, SKIP_INTEGRATION="0", PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1")


def run_suite(tag="baseline"):
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-n", os.environ.get("LABEL_N", "3"), "-rfE", "-p", "no:cacheprovider",
         "-o", "addopts=", "--timeout=300"],
        cwd=src, env=env, capture_output=True, text=True,
    )
    # Keep the raw report so labels can be re-parsed without rerunning the suite.
    try:
        os.makedirs(os.path.join(os.path.dirname(out), "raw"), exist_ok=True)
        open(os.path.join(os.path.dirname(out), "raw", tag + ".txt"), "w").write(r.stdout)
    except OSError:
        pass
    failing = set()
    for line in r.stdout.splitlines():
        if not line.startswith(("FAILED", "ERROR", "SUBFAILED")):
            continue
        # pytest 9 writes SUBFAILED[<subtest description, may hold spaces>]
        # (params) <test id> - message: take the test id token itself
        ids = re.findall(r"(?<!\S)(tests/[^\s\[]+\.py(?:::[^\s\[]+)?)", line)
        m = re.match(r"(?:FAILED|ERROR|SUBFAILED)\S*\s+(\S+?)(?:\s+-\s.*)?$", line)
        if ids or m:
            known = [i for i in ids if i.split("[", 1)[0] in tests]
            raw = known[0] if known else ids[0] if ids else m.group(1)
            nid = raw.split("[", 1)[0] if raw.split("[", 1)[0] in tests else raw
            if nid in tests:
                failing.add(tests[nid])
            elif "::" not in nid:  # a whole file failed to import
                failing.update(n for i, n in tests.items() if i.startswith(nid + "::"))
    return failing


# Tests that fail on the unmodified source here (memory or time limits of
# this machine) say nothing about a mutant.
base_path = out + ".baseline"
if os.path.exists(base_path):
    baseline = set(json.load(open(base_path)))
else:
    baseline = run_suite()
    json.dump(sorted(baseline), open(base_path, "w"))
print("baseline failures:", sorted(baseline), flush=True)
for k, name in enumerate(sorted(os.listdir(os.path.join(muts, "commits")))):
    cid = name[:-6]
    if k % nshards != shard or cid in answers:
        continue
    fps = parse_patch(open(os.path.join(muts, "commits", name)).read())
    saved = {}
    for fp in fps:
        p = os.path.join(src, fp.old)
        saved[p] = open(p).read()
        new, _, _ = apply(saved[p], fp)
        open(p, "w").write(new)
    t0 = time.time()
    failing = run_suite(cid) - baseline
    for p, t in saved.items():
        open(p, "w").write(t)
    answers[cid] = {"failing": sorted(failing), "kind": "mutant"}
    json.dump({"commits": answers}, open(out, "w"))
    print(cid, len(failing), f"{time.time() - t0:.0f}s", flush=True)
