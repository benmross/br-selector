"""Widen map.json.gz for code whose coverage credit depends on test order.

Code that runs once per process and caches its result (a dispatch table built
on first use, a lazily loaded dialect, a fixture file read once into a module
global) is credited by one pytest run only to the first test in each worker
that triggered it, although every later test depends on the result.

Usage:
  python tools/widen_map.py BASE_MAP tests.json OUT_MAP [--run DIR ...] [--fork DIR]
                            [--report report.json]

--run DIR   a coverage run (coverage.db, classes.*.json, fixtures.*.json) such as
            tools/build_coverage.sh or tools/order_cov.sh seq|rev writes
--fork DIR  tools/fork_each.py output: one <index>.json.gz per test run alone in a
            forked child after collection, plus status.*.json

The output is a superset of BASE_MAP everywhere:
  * every line's, class's and fixture's tests become the union over the base map,
    every run and the forked run (each test that runs the line when alone is
    credited, like the first test of a worker already was);
  * a line whose credited tests differ between runs (base map included) and that
    the forked run does not explain, because a sequential run credits a test that
    does not run the line when alone, becomes an import line, so the selector's
    at-import rule selects every test for it.
Lines already in the base map's import lines are left alone. --ignore-tests
leaves tests that fail in some run's environment (sqlglotc build tests) out of
the comparison only.
"""
import argparse
import glob
import gzip
import json
import os
import sys
from collections import Counter


def load_tests(tests_json):
    tests = json.load(open(tests_json))["tests"]
    num = {t["id"]: t["number"] for t in tests}
    by_scope = {}
    for t in tests:
        parts = t["id"].split("::")
        scope = "::".join(parts[:-1]) if len(parts) > 2 else parts[0]
        by_scope.setdefault(scope, set()).add(t["number"])
    return num, by_scope


class Mapper:
    """tools/build_map.py's context -> test numbers rules."""

    def __init__(self, num, by_scope):
        self.num, self.by_scope = num, by_scope

    def to_num(self, ctx):
        nodeid = ctx.rsplit("|", 1)[0] if "|" in ctx else ctx
        n = self.num.get(nodeid)
        if n is None:
            n = self.num.get(nodeid.split("[", 1)[0])
        return n

    def to_nums(self, ctx):
        nodeid, _, phase = ctx.partition("|")
        n = self.to_num(nodeid)
        if n is None:
            return set()
        if phase in ("setup", "teardown"):
            parts = nodeid.split("[", 1)[0].split("::")
            scope = "::".join(parts[:-1]) if len(parts) > 2 else parts[0]
            return self.by_scope.get(scope, {n}) | {n}
        return {n}


def read_run(d, mp):
    """(lines {file: {line: credited}}, raw {file: {line: tests by context}},
    import {file: set}, classes {name: set}, fixtures {path: set})."""
    from coverage import CoverageData

    data = CoverageData(os.path.join(d, "coverage.db"))
    data.read()
    lines, raw, imp = {}, {}, {}
    for path in data.measured_files():
        rel = path.split("/src/", 1)[-1]
        if not rel.endswith(".py"):
            continue
        fl, fr, fi = {}, {}, set()
        for line, ctxs in data.contexts_by_lineno(path).items():
            nums, rnums = set(), set()
            for c in ctxs:
                if c:
                    nums |= mp.to_nums(c)
                    n = mp.to_num(c)
                    if n is not None:
                        rnums.add(n)
                else:
                    fi.add(line)
            if nums:
                fl[line] = nums
                fr[line] = rnums
        lines[rel], raw[rel], imp[rel] = fl, fr, fi
    classes, fixtures = {}, {}
    for f in glob.glob(os.path.join(d, "classes.*.json")):
        for nodeid, names in json.load(open(f)).items():
            for c in names:
                classes.setdefault(c, set()).update(mp.to_nums(nodeid))
    for f in glob.glob(os.path.join(d, "fixtures.*.json")):
        for nodeid, paths in json.load(open(f)).items():
            for p in paths:
                if "__pycache__" not in p:
                    fixtures.setdefault(p, set()).update(mp.to_nums(nodeid))
    return lines, raw, imp, classes, fixtures


def read_fork(d, mp):
    """Per-test lines, classes and fixtures from forked children. Every child
    the parents launched must have exited 0 and written its file."""
    status = {}
    for f in glob.glob(os.path.join(d, "status.*.json")):
        status.update(json.load(open(f)))
    bad = {k: v for k, v in status.items() if v != 0}
    lines, classes, fixtures = {}, {}, {}
    seen, outcomes, unknown = set(), Counter(), set()
    for f in glob.glob(os.path.join(d, "*.json.gz")):
        o = json.load(gzip.open(f, "rt"))
        seen.add(o["nodeid"])
        outcomes[o["outcome"]] += 1
        n = mp.to_num(o["nodeid"])
        if n is None:
            unknown.add(o["nodeid"])
            continue
        for rel, ls in o["lines"].items():
            if not rel.endswith(".py"):
                continue
            fl = lines.setdefault(rel, {})
            for l in ls:
                fl.setdefault(l, set()).add(n)
        # the child ran only this test, so every phase belongs to it
        for names in o["classes"].values():
            for c in names:
                classes.setdefault(c, set()).add(n)
        for paths in o["fixtures"].values():
            for p in paths:
                if "__pycache__" not in p:
                    fixtures.setdefault(p, set()).add(n)
    missing = sorted(set(status) - seen)
    info = {"children": len(status), "files": len(seen), "nonzero_exit": bad,
            "missing_output": missing, "outcomes": dict(outcomes), "unknown_ids": sorted(unknown)[:20],
            "tests_covered": len({mp.to_num(s) for s in seen} - {None})}
    return lines, classes, fixtures, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("tests")
    ap.add_argument("out")
    ap.add_argument("--run", action="append", default=[])
    ap.add_argument("--fork")
    ap.add_argument("--report")
    ap.add_argument("--ignore-tests", default="",
                    help="comma-separated test numbers left out of the order comparison (still in the union): "
                         "tests that fail in one run's environment, not because of order")
    a = ap.parse_args()
    ignore = {int(x) for x in a.ignore_tests.split(",") if x}

    num, by_scope = load_tests(a.tests)
    mp = Mapper(num, by_scope)
    base = json.load(gzip.open(a.base, "rt"))
    sets = [set(s) for s in base["sets"]]
    base_lines = {f: {int(k): sets[v] for k, v in ls.items()} for f, ls in base["files"].items()}
    base_imp = {f: set(v) for f, v in base["import_lines"].items()}

    runs = {"base": base_lines}
    raws, run_classes, run_fixtures = {}, {}, {}
    for d in a.run:
        name = os.path.basename(os.path.normpath(d))
        lines, raw, _imp, cls, fix = read_run(d, mp)
        runs[name], raws[name], run_classes[name], run_fixtures[name] = lines, raw, cls, fix
        print(f"run {name}: {sum(len(v) for v in lines.values())} credited lines", file=sys.stderr)
    fork_lines, fork_cls, fork_fix, fork_info = ({}, {}, {}, None)
    if a.fork:
        fork_lines, fork_cls, fork_fix, fork_info = read_fork(a.fork, mp)
        print("fork:", json.dumps({k: (v if not isinstance(v, (list, dict)) or len(v) < 20 else len(v))
                                   for k, v in fork_info.items()}), file=sys.stderr)

    # order-dependent lines: credited sets differ between any two sequential runs
    names = list(runs)
    all_files = set().union(*[set(r) for r in runs.values()])
    orderdep = []  # (file, line, sizes by run, fork size, explained)
    union_lines = {}
    for rel in sorted(all_files):
        imp = base_imp.get(rel, set())
        ls = set().union(*[set(r.get(rel, {})) for r in runs.values()]) | set(fork_lines.get(rel, {}))
        for l in sorted(ls):
            u = set()
            for r in runs.values():
                u |= r.get(rel, {}).get(l, set())
            fk = fork_lines.get(rel, {}).get(l, set())
            u |= fk
            union_lines.setdefault(rel, {})[l] = u
            if l in imp:
                continue
            # compare only runs that measured this file at all (an older kit
            # may not have traced it)
            measured = [n for n in names if rel in runs[n]]
            got = [frozenset(set(runs[n][rel].get(l, ())) - ignore) for n in measured]
            if len(set(got)) <= 1:
                continue
            # Explained when every test a sequential run credited by its own
            # context also runs the line alone (raw, without setup widening).
            seq_raw = set()
            for n in raws:
                seq_raw |= raws[n].get(rel, {}).get(l, set())
            explained = bool(a.fork) and seq_raw - ignore <= fk
            orderdep.append((rel, l, {n: len(g) for n, g in zip(measured, got)}, len(fk), explained))

    new_imp = {f: set(v) for f, v in base_imp.items()}
    for rel, l, _sizes, _fk, explained in orderdep:
        if not explained:
            new_imp.setdefault(rel, set()).add(l)

    def union_named(base_named, run_named, fork_named):
        out = {k: set(sets[v]) for k, v in base_named.items()}
        for src in list(run_named.values()) + [fork_named]:
            for k, s in src.items():
                out.setdefault(k, set()).update(s)
        return out

    classes = union_named(base["classes"], run_classes, fork_cls)
    fixtures = union_named(base["fixtures"], run_fixtures, fork_fix)

    new_sets, ids = [], {}

    def sid(s):
        key = tuple(sorted(s))
        if key not in ids:
            ids[key] = len(new_sets)
            new_sets.append(list(key))
        return ids[key]

    files = {}
    for rel in base["files"]:
        files[rel] = {}
    for rel, ls in union_lines.items():
        if rel not in base["files"]:
            continue  # files the base map never measured (data, other roots) stay out
        files[rel] = {str(l): sid(s) for l, s in sorted(ls.items()) if s}
    setup_files = {f: {k: sid(sets[v]) for k, v in ls.items()} for f, ls in base.get("setup_files", {}).items()}
    out = dict(base)
    out.update({
        "sets": new_sets,
        "files": files,
        "setup_files": setup_files,
        "import_lines": {f: sorted(v) for f, v in new_imp.items()},
        "classes": {k: sid(v) for k, v in classes.items()},
        "fixtures": {k: sid(v) for k, v in fixtures.items()},
    })
    # superset check against the base map
    for rel, ls in base["files"].items():
        for k, v in ls.items():
            assert sets[v] <= set(new_sets[files[rel][k]]), (rel, k)
    for key in ("classes", "fixtures"):
        for k, v in base[key].items():
            assert sets[v] <= set(new_sets[out[key][k]]), (key, k)
    with gzip.open(a.out, "wt") as f:
        json.dump(out, f, separators=(",", ":"))

    by_file = Counter(r for r, *_ in orderdep)
    unexplained = [(r, l) for r, l, _s, _f, e in orderdep if not e]
    grown_cls = sum(1 for k, v in base["classes"].items() if classes[k] != sets[v]) + len(set(classes) - set(base["classes"]))
    grown_fix = sum(1 for k, v in base["fixtures"].items() if fixtures[k] != sets[v]) + len(set(fixtures) - set(base["fixtures"]))
    grown_lines = sum(1 for rel, ls in base["files"].items() for k, v in ls.items()
                      if len(new_sets[files[rel][k]]) > len(sets[v]))
    new_lines = sum(len(ls) for ls in files.values()) - sum(len(ls) for ls in base["files"].values())
    summary = {
        "runs": names, "fork": fork_info,
        "orderdep_lines": len(orderdep), "orderdep_by_file": dict(by_file.most_common()),
        "unexplained_marked_import": len(unexplained),
        "base_lines_widened": grown_lines, "lines_added": new_lines,
        "classes_widened_or_added": grown_cls, "fixtures_widened_or_added": grown_fix,
        "size_bytes": os.path.getsize(a.out),
    }
    print(json.dumps(summary, indent=1), file=sys.stderr)
    if a.report:
        json.dump({"summary": summary,
                   "orderdep": [{"file": r, "line": l, "sizes": s, "fork": fk, "explained": e}
                                for r, l, s, fk, e in orderdep]},
                  open(a.report, "w"), indent=0)


if __name__ == "__main__":
    main()
