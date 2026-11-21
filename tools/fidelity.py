"""Fidelity check for verification: run real pytest on each commit's static
candidates against the patched tree.

Runs inside the br-t24 image (python:3.13-slim, requirements.lock, pristine
sqlglot at /opt/sqlglot). Usage:
  python fidelity.py DATASET JOBS.json OUT.json
JOBS.json is {commit: [test numbers]}. For each commit the patched tree is a
fresh copy of the pristine checkout with the patch applied (selector.apply),
and pytest runs the given node ids as tools/label.py runs the suite
(SKIP_INTEGRATION=0, one xdist worker, --timeout=300, the label_trace plugin
so failing subtests and collection errors count). OUT.json maps each commit
to the numbers pytest failed (or "error: ..." when pytest could not run).
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from selector import apply, parse_patch  # noqa: E402
from label_reports import report_failures  # noqa: E402

data, jobs_path, out_path = sys.argv[1:4]
tests = {t["number"]: t["id"] for t in json.load(open(os.path.join(data, "tests.json")))["tests"]}
ids = {v: k for k, v in tests.items()}
jobs = json.load(open(jobs_path))
out = json.load(open(out_path)) if os.path.exists(out_path) else {}
PRISTINE = "/opt/sqlglot"
WORK = os.environ.get("FID_WORK", "/work")

for cid, nums in sorted(jobs.items()):
    if cid in out:
        continue
    src = os.path.join(WORK, "src")
    shutil.rmtree(src, ignore_errors=True)
    os.makedirs(src)
    for d in ("sqlglot", "tests"):
        shutil.copytree(os.path.join(PRISTINE, d), os.path.join(src, d), symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    try:
        text = open(os.path.join(data, "commits", cid + ".patch"), encoding="utf-8").read()
        for fp in parse_patch(text):
            old = ""
            if fp.old is not None:
                old = open(os.path.join(PRISTINE, fp.old), encoding="utf-8", newline="").read()
                if fp.new != fp.old and os.path.exists(os.path.join(src, fp.old)):
                    os.remove(os.path.join(src, fp.old))
            if fp.new is not None:
                p = os.path.join(src, fp.new)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(apply(old, fp)[0])
    except Exception as e:
        out[cid] = f"error: patch {e!r}"
        continue
    prefix = os.path.join(WORK, "rep", cid)
    env = dict(os.environ, SKIP_INTEGRATION="0", PYTHONPATH=src + os.pathsep + HERE,
               PYTHONDONTWRITEBYTECODE="1", LABEL_REPORT_PREFIX=prefix)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *[tests[n] for n in nums], "-q", "-n", "1", "--dist", "load",
         "-rfE", "-p", "no:cacheprovider", "-o", "addopts=", "--timeout=300", "--tb=short", "-p", "label_trace"],
        cwd=src, env=env, capture_output=True, text=True)
    try:
        failed = sorted(report_failures(prefix, ids))
    except Exception as e:
        out[cid] = f"error: {e!r} rc={r.returncode} {r.stdout[-400:]}"
        continue
    if r.returncode not in (0, 1):
        out[cid] = f"error: pytest exited {r.returncode} {r.stdout[-400:]}"
    elif r.returncode == 1 and not failed:
        out[cid] = f"error: pytest failed with no failure ids {r.stdout[-400:]}"
    else:
        out[cid] = failed
    print(cid, len(nums), "->", out[cid] if isinstance(out[cid], str) else len(failed), flush=True)
    json.dump(out, open(out_path, "w"), indent=0)
json.dump(out, open(out_path, "w"), indent=0)
