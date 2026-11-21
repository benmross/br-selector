"""Label dropped heavy tests with real pytest.

    python tools/heavy_label.py SRC DATA EVAL_LOG OUT.jsonl [jobs]

For every commit in EVAL_LOG (tools/heavy_eval.py output) with a dropped
test, copy SRC, apply the patch with git apply, and run that one test with
pytest (SKIP_INTEGRATION=0, no xdist). The pristine source runs first and
must pass. Writes {"commit", "test", "passed", "tail"} per line.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

IDS = {1106: "tests/test_executor.py::TestExecutor::test_execute_tpcds",
       1107: "tests/test_executor.py::TestExecutor::test_execute_tpch"}


def run(src, patch, num):
    d = tempfile.mkdtemp(prefix="hl-")
    try:
        tree = os.path.join(d, "t")
        shutil.copytree(src, tree, ignore=shutil.ignore_patterns("__pycache__", ".git"), symlinks=True)
        if patch:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            os.environ["SQLGLOT_SRC"] = src
            import selector
            selector.SRC = src
            files = selector.overlay_files(patch)
            if not files:
                return None, "patch not applied"
            for rel, text in files.items():
                path = os.path.join(tree, rel)
                if text is None:
                    if os.path.exists(path):
                        os.remove(path)
                    continue
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)
        env = dict(os.environ, SKIP_INTEGRATION="0", PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
                            IDS[num]], cwd=tree, capture_output=True, text=True, env=env)
        return p.returncode == 0, (p.stdout + p.stderr)[-400:]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main(src, data, log, out, jobs):
    todo = []
    for l in open(log):
        d = json.loads(l)
        for n in d["dropped"]:
            todo.append((d["commit"], n))
    for n in sorted({n for _, n in todo}):
        ok, tail = run(src, None, n)
        print(json.dumps({"commit": "PRISTINE", "test": n, "passed": ok, "tail": tail}), flush=True)
        if not ok:
            sys.exit("pristine fails: " + tail)
    with open(out, "a") as f, ThreadPoolExecutor(jobs) as pool:
        futs = [(c, n, pool.submit(run, src, os.path.join(data, "commits", c + ".patch"), n)) for c, n in todo]
        for c, n, fu in futs:
            ok, tail = fu.result()
            row = {"commit": c, "test": n, "passed": ok, "tail": tail}
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 2)
