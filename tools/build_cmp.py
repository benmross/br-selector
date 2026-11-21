"""Merge the comparison probe's per-process records into cmp.json.gz.

Usage: python tools/build_cmp.py work/cmpprof sample/tests.json cmp.json.gz

Output: {"tests": {id: number}, "sets": [[test numbers]],
         "sites": {relpath: {"line:col": [op, union, unattributed, evaluated, {bit: flipped}]}}}

op is the site's operator (index into tools/cmp_profile.OPS); union is the
mask of substitutes that gave a different bool in any evaluation;
unattributed is that mask for evaluations outside a test (import,
collection, subprocesses); evaluated and flipped are set ids: tests that
evaluated the site, and tests in which substitute `bit` changed a result.
Sites whose every substitute differed are left out: selection treats a
missing site like one that never ran, with normal coverage selection.
"""
import glob
import gzip
import json
import os
import sys

EQ_FAMILY = (0, 1, 6, 7)
ORDER_FAMILY = (0, 1, 2, 3, 4, 5)


def full(op):
    fam = EQ_FAMILY if op in EQ_FAMILY else ORDER_FAMILY
    return sum(1 << k for k in fam if k != op)


def main(prof_dir, tests_json, out):
    tests = json.load(open(tests_json))["tests"]
    num = {t["id"]: t["number"] for t in tests}
    by_scope = {}
    for t in tests:
        parts = t["id"].split("::")
        scope = "::".join(parts[:-1]) if len(parts) > 2 else parts[0]
        by_scope.setdefault(scope, set()).add(t["number"])
    unknown = set()

    def to_nums(ctx):
        # Same attribution as tools/build_map.py: setup and teardown run
        # class-level setup for the whole class.
        nodeid, _, phase = ctx.partition("|")
        n = num.get(nodeid)
        if n is None:
            n = num.get(nodeid.split("[", 1)[0])
        if n is None:
            unknown.add(nodeid)
            return None
        if phase in ("setup", "teardown"):
            parts = nodeid.split("[", 1)[0].split("::")
            scope = "::".join(parts[:-1]) if len(parts) > 2 else parts[0]
            return by_scope.get(scope, {n}) | {n}
        return {n}

    ops = {}       # key -> op
    union = {}     # key -> mask
    unattr = {}    # key -> mask
    evaluated = {}  # key -> set of tests
    flipped = {}   # key -> {bit: set of tests}
    conflict = set()
    files = sorted(glob.glob(os.path.join(prof_dir, "cmp.*.jsonl")))
    records = []
    for f in files:
        keys = []  # site ids are per process; each line adds the new ones
        for line in open(f):
            d = json.loads(line)
            for rel, ln, col, op in d["sites"]:
                k = (rel, f"{ln}:{col}")
                if ops.setdefault(k, op) != op:
                    conflict.add(k)  # nested comparisons sharing a start
                keys.append(k)
            records.append((list(keys), d["ctx"]))
    for keys, ctxs in records:
        for ctx, rows in ctxs.items():
            nums = None if ctx.startswith("@") else to_nums(ctx)
            for sid, m in rows:
                k = keys[sid]
                union[k] = union.get(k, 0) | m
                if nums is None:
                    unattr[k] = unattr.get(k, 0) | m
                    continue
                evaluated.setdefault(k, set()).update(nums)
                b = 0
                while m >> b:
                    if m >> b & 1:
                        flipped.setdefault(k, {}).setdefault(b, set()).update(nums)
                    b += 1

    sets, set_ids = [], {}

    def sid(s):
        key = tuple(sorted(s))
        if key not in set_ids:
            set_ids[key] = len(sets)
            sets.append(list(key))
        return set_ids[key]

    sites = {}
    kept = 0
    for k, m in union.items():
        op = ops[k]
        if k in conflict or m == full(op):
            continue
        fl = {str(b): sid(s) for b, s in sorted(flipped.get(k, {}).items())}
        sites.setdefault(k[0], {})[k[1]] = [op, m, unattr.get(k, 0), sid(evaluated.get(k, ())), fl]
        kept += 1
    obj = {"tests": num, "sets": sets, "sites": sites}
    with gzip.open(out, "wt", compresslevel=9) as f:
        json.dump(obj, f, separators=(",", ":"))
    print(f"process files {len(files)} sites seen {len(ops)} evaluated {len(union)} "
          f"kept {kept} conflicts {len(conflict)} sets {len(sets)} unknown ids {len(unknown)} "
          f"size {os.path.getsize(out) / 1e3:.0f} kB", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
