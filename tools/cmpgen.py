"""Operator-swap mutants at sites the comparison profile calls equivalent.

Usage: python tools/cmpgen.py <sqlglot root> cmp.json.gz <out dir> <count> <seed>
Each mutant swaps one single-operator comparison to a substitute the profile
never saw give a different result, so the selector's comparison rule selects
nothing for it. Labeling these checks that rule against real test runs.
"""
import ast
import difflib
import gzip
import json
import os
import random
import re
import sys

TEXT = ["==", "!=", "<", "<=", ">", ">=", "is", "is not"]
OPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot)
# swaps a mutation tool plausibly makes: original -> substitute
SWAPS = {6: [0], 7: [1], 2: [3], 3: [2], 4: [5], 5: [4], 0: [6], 1: [7]}


def main(root, prof_path, out, count, seed):
    prof = json.load(gzip.open(prof_path, "rt"))
    rng = random.Random(int(seed))
    cands = []
    for rel, sites in sorted(prof["sites"].items()):
        for key, (op, union, *_rest) in sorted(sites.items()):
            for new in SWAPS.get(op, []):
                if not union >> new & 1:
                    cands.append((rel, key, op, new))
    rng.shuffle(cands)
    os.makedirs(os.path.join(out, "commits"), exist_ok=True)
    manifest, n = {}, 0
    for rel, key, op, new in cands:
        if n >= int(count):
            break
        text = open(os.path.join(root, rel)).read()
        lines = text.splitlines(True)
        line, col = (int(x) for x in key.split(":"))
        tree = ast.parse(text)
        node = next((c for c in ast.walk(tree) if isinstance(c, ast.Compare) and c.lineno == line
                     and c.col_offset == col and len(c.ops) == 1), None)
        if node is None or node.left.end_lineno != node.comparators[0].lineno:
            continue  # operator not on one line with both operands
        src = lines[line - 1]
        lo, hi = node.left.end_col_offset, node.comparators[0].col_offset
        between = src.encode()[lo:hi].decode()
        if not re.fullmatch(r"\s*" + re.escape(TEXT[op]).replace(r"\ ", r"\s+") + r"\s*", between):
            continue
        new_src = (src.encode()[:lo].decode() + f" {TEXT[new]} " + src.encode()[hi:].decode())
        new_lines = lines[:line - 1] + [new_src] + lines[line:]
        cid = f"c{seed}x{n:03d}"
        patch = f"diff --git a/{rel} b/{rel}\n" + "".join(
            difflib.unified_diff(lines, new_lines, "a/" + rel, "b/" + rel, n=3))
        open(os.path.join(out, "commits", cid + ".patch"), "w").write(patch)
        manifest[cid] = {"kind": f"cmp {TEXT[op]} -> {TEXT[new]}", "site": f"{rel}:{key}"}
        n += 1
    json.dump({"commits": manifest}, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    print(f"{n} mutants from {len(cands)} equivalent swaps", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:6])
