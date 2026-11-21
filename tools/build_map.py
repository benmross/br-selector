"""Turn the coverage, fixture and class traces into map.json.gz for selector.py.

Usage: python tools/build_map.py work/cov sample/tests.json map.json.gz
Everything here comes from running sqlglot's own tests at the pinned commit.
"""
import glob
import gzip
import json
import os
import sys

from coverage import CoverageData


def main(cov_dir, tests_json, out):
    tests = json.load(open(tests_json))["tests"]
    num = {t["id"]: t["number"] for t in tests}
    unknown = set()

    by_scope = {}
    for t in tests:
        parts = t["id"].split("::")
        scope = "::".join(parts[:-1]) if len(parts) > 2 else parts[0]
        by_scope.setdefault(scope, set()).add(t["number"])

    def to_nums(ctx):
        """A context's tests. Setup and teardown run class-level setup
        (setUpClass, class and module fixtures) for every test in the class,
        so they count for all of them."""
        nodeid, _, phase = ctx.partition("|")
        n = to_num(nodeid)
        if n is None:
            return set()
        if phase in ("setup", "teardown"):
            parts = nodeid.split("[", 1)[0].split("::")
            scope = "::".join(parts[:-1]) if len(parts) > 2 else parts[0]
            return by_scope.get(scope, {n}) | {n}
        return {n}

    def to_num(ctx):
        nodeid = ctx.rsplit("|", 1)[0]
        n = num.get(nodeid)
        if n is None:
            # parametrized or subtest ids collapse to their base test
            base = nodeid.split("[", 1)[0]
            n = num.get(base)
        if n is None:
            unknown.add(nodeid)
        return n

    data = CoverageData(os.path.join(cov_dir, "coverage.db"))
    data.read()
    sets, set_ids = [], {}

    def sid(s):
        key = tuple(sorted(s))
        if key not in set_ids:
            set_ids[key] = len(sets)
            sets.append(list(key))
        return set_ids[key]

    files = {}
    import_lines = {}
    for path in data.measured_files():
        rel = path.split("/src/", 1)[-1]
        if not rel.endswith(".py"):
            continue
        by_line = data.contexts_by_lineno(path)
        lines, imp = {}, []
        for line, ctxs in by_line.items():
            nums = set()
            for c in ctxs:
                if c:
                    nums |= to_nums(c)
            if nums:
                lines[line] = sid(nums)
            if "" in ctxs:
                imp.append(line)
        files[rel] = lines
        import_lines[rel] = sorted(imp)

    fixtures = {}
    for f in glob.glob(os.path.join(cov_dir, "fixtures.*.json")):
        for nodeid, paths in json.load(open(f)).items():
            ns = to_nums(nodeid)
            if not ns:
                continue
            for p in paths:
                if "__pycache__" in p:
                    continue
                fixtures.setdefault(p, set()).update(ns)

    classes = {}
    for f in glob.glob(os.path.join(cov_dir, "classes.*.json")):
        for nodeid, names in json.load(open(f)).items():
            ns = to_nums(nodeid)
            if not ns:
                continue
            for c in names:
                classes.setdefault(c, set()).update(ns)

    out_obj = {
        "sets": sets,
        "files": files,
        "import_lines": import_lines,
        "fixtures": {k: sid(v) for k, v in fixtures.items()},
        "classes": {k: sid(v) for k, v in classes.items()},
        "tests": {t["id"]: t["number"] for t in tests},
    }
    with gzip.open(out, "wt") as f:
        json.dump(out_obj, f, separators=(",", ":"))
    print(f"files {len(files)} sets {len(sets)} fixtures {len(fixtures)} classes {len(classes)} "
          f"unknown ids {len(unknown)} size {os.path.getsize(out)/1e6:.1f} MB", file=sys.stderr)
    if unknown:
        print("unknown sample:", sorted(unknown)[:5], file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
