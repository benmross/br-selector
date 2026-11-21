"""Label mutants: apply each to /src, run the whole suite, record failing tests.

Runs inside python:3.13-slim with requirements.lock installed.
Usage: python label.py /muts /src /out/answers.json

Writes baseline, structured pytest reports and compact logs beside the answers.
Touch <answers>.stop to finish the current mutant and stop with source restored.
An optional <answers>.order JSON list prioritizes ids for an unsharded run.
"""
import json
import os
import subprocess
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/kit")
from selector import apply, parse_patch  # noqa: E402
from label_reports import report_failures  # noqa: E402

muts, src, out = (os.path.abspath(p) for p in sys.argv[1:4])
shard, nshards = (int(x) for x in (sys.argv[4:6] if len(sys.argv) > 5 else ("0", "1")))
tests = {t["id"]: t["number"] for t in json.load(open("/kit/sample/tests.json"))["tests"]}
answers = json.load(open(out))["commits"] if os.path.exists(out) else {}
manifest_path = os.path.join(muts, "manifest.json")
manifest = json.load(open(manifest_path))["commits"] if os.path.exists(manifest_path) else {}
env = dict(os.environ, SKIP_INTEGRATION="0", PYTHONPATH=src + os.pathsep + os.path.dirname(os.path.abspath(__file__)), PYTHONDONTWRITEBYTECODE="1")


def oom_kills():
    """OOM kills in this container's memory cgroup (t7's relabeler check)."""
    try:
        with open("/sys/fs/cgroup/memory.events") as f:
            return int(dict(line.split() for line in f)["oom_kill"])
    except (OSError, KeyError, ValueError):
        return 0


def run_suite(tag, targets=("tests",), test_filter=None):
    oom_before = oom_kills()
    prefix = out + ".reports/" + tag
    suite_env = dict(env, LABEL_REPORT_PREFIX=prefix,
                     LABEL_STOP_AFTER_FILE=out + ".stop-after", LABEL_STOP_REQUEST_FILE=out + ".stop")
    process = subprocess.Popen(
        [sys.executable, "-m", "pytest", *targets, *(["-k", test_filter] if test_filter else []), "-q", "-n", os.environ.get("LABEL_N", "1"), "--dist", os.environ.get("LABEL_DIST", "load"), "-rfE", "-p", "no:cacheprovider",
         "-o", "addopts=", "--timeout=90",
         *sum((["--deselect", nid] for nid in json.loads(os.environ.get("T32_DESELECT", "[]"))), []), "--tb=no", "-p", "label_trace"],
        cwd=src, env=suite_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    started = time.monotonic()
    while True:
        try:
            stdout, stderr = process.communicate(timeout=2)
            break
        except subprocess.TimeoutExpired:
            if oom_kills() > oom_before or time.monotonic() - started > 180:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                break
    r = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
    log_dir = out + ".logs"
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, tag + ".log"), "w") as f:
        f.write(r.stdout + "\nSTDERR\n" + r.stderr)
    # Keep the raw report under raw/ too (main's layout) so labels can be re-parsed.
    try:
        os.makedirs(os.path.join(os.path.dirname(out), "raw"), exist_ok=True)
        open(os.path.join(os.path.dirname(out), "raw", tag + ".txt"), "w").write(r.stdout)
    except OSError:
        pass
    if oom_kills() > oom_before:
        raise RuntimeError(f"OOM during pytest {tag}; refusing an infrastructure-dependent label")
    if r.returncode not in (0, 1, 2):
        raise RuntimeError(f"pytest exited {r.returncode}; see {log_dir}/{tag}.log")
    return report_failures(prefix, tests)


# Tests that fail on the unmodified source here (memory or time limits of
# this machine) say nothing about a mutant.
base_path = out + ".baseline"
if os.path.exists(base_path):
    baseline = set(json.load(open(base_path)))
else:
    # A manifest may list the tests to run per mutant (a candidate selection
    # checked against real outcomes); the baseline then covers their union.
    subset = sorted({t for v in manifest.values() for t in v.get("tests", [])})
    full = any(not v.get("tests") for v in manifest.values())
    baseline = run_suite("baseline", ["tests"] if full else subset or ["tests"])
    json.dump(sorted(baseline), open(base_path, "w"))
print("baseline failures:", sorted(baseline), flush=True)
if os.environ.get("T32_REQUIRE_CLEAN_BASELINE") == "1" and baseline:
    raise RuntimeError("Refusing labels with an unexpected baseline failure")
names = sorted(n for n in os.listdir(os.path.join(muts, "commits")) if n.endswith(".patch"))
order_path = out + ".order"
if os.path.exists(order_path):
    if nshards != 1:
        raise ValueError("priority ordering requires an unsharded run")
    priority = {cid: i for i, cid in enumerate(json.load(open(order_path)))}
    names.sort(key=lambda n: (priority.get(n[:-6], len(priority)), n))
for k, name in enumerate(names):
    cid = name[:-6]
    available = int(dict(line.split(":", 1) for line in open("/proc/meminfo"))["MemAvailable"].split()[0])
    if available < 5 * 1024 * 1024:
        print("STOP host MemAvailable below 5 GiB", available, flush=True)
        break
    if k % nshards != shard or cid in answers:
        continue
    if os.path.exists(out + ".stop"):
        print("stop requested; source restored and completed labels saved", flush=True)
        break
    fps = parse_patch(open(os.path.join(muts, "commits", name)).read())
    saved = {}
    def save(p):
        if p not in saved:
            saved[p] = open(p).read() if os.path.exists(p) else None

    try:
        for fp in fps:
            old_path = os.path.join(src, fp.old) if fp.old is not None else None
            new_path = os.path.join(src, fp.new) if fp.new is not None else None
            for p in {old_path, new_path} - {None}:
                save(p)
            old_text = saved[old_path] if old_path is not None else None
            new, _, _ = apply(old_text, fp)
            if new_path is not None:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                open(new_path, "w").write(new)
            if old_path is not None and old_path != new_path:
                os.unlink(old_path)
        t0 = time.time()
        failing = run_suite(cid, manifest.get(cid, {}).get("tests") or ["tests"],
                            manifest.get(cid, {}).get("pytest_filter")) - baseline
    finally:
        for p, text in saved.items():
            if text is None:
                if os.path.exists(p):
                    os.unlink(p)
            else:
                open(p, "w").write(text)
    answers[cid] = {"failing": sorted(failing), "kind": manifest.get(cid, {}).get("kind", "mutant")}
    temp = out + ".tmp"
    json.dump({"commits": answers}, open(temp, "w"))
    os.replace(temp, out)
    print(cid, answers[cid]["kind"], len(failing), f"{time.time() - t0:.0f}s", flush=True)
