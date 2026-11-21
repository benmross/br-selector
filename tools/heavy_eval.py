"""Run the heavy-test drop on a candidate output and report each decision.

    SQLGLOT_SRC=src python tools/heavy_eval.py DATA CAND.jsonl OUT.jsonl [jobs]

DATA holds tests.json and commits/; CAND.jsonl is a selector output. Writes
the narrowed output and prints one line per commit that selected a heavy test.
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def one(args):
    data, cid, chosen = args
    os.environ.setdefault("BR_H_WALL_S", "100000")
    import selector
    import heavy
    selector.H_WALL_S = 1e9
    tests = load_tests(data)
    r = [cid, set(chosen), [], os.path.join(data, "commits", cid + ".patch")]
    t0 = time.monotonic()
    heavy._CPU.cpu = 0.0
    selector.drop_heavy_tests([r], tests)
    return cid, sorted(r[1]), r[2], heavy._CPU.cpu, time.monotonic() - t0


def load_tests(data):
    with open(os.path.join(data, "tests.json")) as f:
        tj = json.load(f)
    return {t["number"]: (t["id"], t["file"], round(t["seconds"] * 1000)) for t in tj["tests"]}


def main(data, cand, out, jobs):
    import selector
    tests = load_tests(data)
    rows = [json.loads(l) for l in open(cand)]
    todo, keep = [], {}
    for d in rows:
        s = {x for w in d["workers"] for x in w}
        if (1106 in s or 1107 in s) and len(s) < len(tests):
            todo.append((data, d["commit"], sorted(s)))
        keep[d["commit"]] = d["workers"]
    # pristine digests once, before the workers fork
    import heavy
    rec = os.path.join(selector.HERE, "heavy_fp.json")
    if not os.path.exists(rec):
        heavy.record(selector.SRC, rec)
    print("record:", open(rec).read(), file=sys.stderr)
    tot_cpu = 0.0
    with ProcessPoolExecutor(jobs) as pool:
        for cid, chosen, why, cpu, wall in pool.map(one, todo):
            before = {x for w in keep[cid] for x in w}
            dropped = sorted(before - set(chosen))
            if dropped:
                keep[cid] = selector.pack(set(chosen), tests)
            tot_cpu += cpu
            print(json.dumps({"commit": cid, "dropped": dropped, "cpu": round(cpu, 2), "wall": round(wall, 2),
                              "why": [w for w in why if w.startswith("heavy")]}), flush=True)
    with open(out, "w") as f:
        for d in rows:
            f.write(json.dumps({"commit": d["commit"], "workers": keep[d["commit"]]}) + "\n")
    print(f"checked {len(todo)}, child CPU {tot_cpu:.1f} s", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 2)
