"""Reproducible single-process selector measurement (old import checks remain)."""
import argparse
import contextlib
import gzip
import importlib.util
import json
import os
from pathlib import Path
import resource
import time

p = argparse.ArgumentParser()
p.add_argument("worktree")
p.add_argument("dataset")
p.add_argument("output")
a = p.parse_args()
wt, data, output = map(lambda x: Path(x).resolve(), (a.worktree, a.dataset, a.output))
os.environ.update(DATA_DIR=str(data), SQLGLOT_SRC=str(Path(__file__).resolve().parents[4] / "work/sqlglot"),
                  MAP_PATH=str(wt / "map.json.gz"), INDEX_PATH=str(wt / "index.json.gz"))
# The caller also pins one CPU; never allow more than 1 GiB virtual memory.
resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
spec = importlib.util.spec_from_file_location("measured_selector", wt / "selector.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
t0, c0 = time.monotonic(), time.process_time()
r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
with open(str(output) + ".jsonl", "w") as out, open(str(output) + ".why", "w") as err:
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        if not hasattr(s, "select_patch"):
            s.main()
        else:
            tj = json.load(open(data / "tests.json"))
            tests = {t["number"]: (t["id"], t["file"], round(t["seconds"] * 1000)) for t in tj["tests"]}
            m = json.load(gzip.open(s.MAP, "rt"))
            ids = {v[0]: n for n, v in tests.items()}
            remap = {n: ids[tid] for tid, n in m["tests"].items() if tid in ids}
            m["sets"] = [[remap[n] for n in group if n in remap] for group in m["sets"]]
            sel = s.Selector(tests, m)
            if hasattr(sel, "prepare_shared_setup"):
                sel.prepare_shared_setup()
            for patch in sorted((data / "commits").glob("*.patch")):
                try:
                    chosen, why = s.select_patch(str(patch), sel, tests, float("inf"))
                except Exception as e:
                    chosen, why = set(tests), [f"analysis error {e!r}: everything"]
                print(json.dumps({"commit": patch.stem, "workers": s.pack(chosen, tests)}))
                print(patch.stem, len(chosen), "tests;", "; ".join(why), file=err)
r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
metrics = dict(wall=time.monotonic()-t0, cpu_self=time.process_time()-c0,
               cpu_children=r1.ru_utime+r1.ru_stime-r0.ru_utime-r0.ru_stime)
json.dump(metrics, open(str(output) + ".time.json", "w"), indent=2)
print(output.name, metrics)
