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
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-n", "4", "-rfE", "-p", "no:cacheprovider",
         "-o", "addopts=", "--timeout=300"],
        cwd=src, env=env, capture_output=True, text=True,
    )
    for p, t in saved.items():
        open(p, "w").write(t)
    failing = set()
    for line in r.stdout.splitlines():
        m = re.match(r"(?:FAILED|ERROR|SUBFAILED)\S*\s+(\S+?)(?:\s+-\s.*)?$", line)
        if m:
            nid = m.group(1).split("[", 1)[0] if m.group(1).split("[", 1)[0] in tests else m.group(1)
            if nid in tests:
                failing.add(tests[nid])
            elif "::" not in nid:  # a whole file failed to import
                failing.update(n for i, n in tests.items() if i.startswith(nid + "::"))
    answers[cid] = {"failing": sorted(failing), "kind": "mutant"}
    json.dump({"commits": answers}, open(out, "w"))
    print(cid, len(failing), f"{time.time() - t0:.0f}s", flush=True)
