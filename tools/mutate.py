"""Generate small mutants of sqlglot at the pinned commit, as unified diffs,
to find where the selector misses. These validate the selector; nothing in
them is looked up when it runs.

Usage: python tools/mutate.py <sqlglot checkout> <out dir> <count> <seed>
"""
import ast
import difflib
import os
import random
import re
import sys

SWAPS = [
    (r" == ", " != "), (r" != ", " == "), (r" is not ", " is "), (r" is ", " is not "),
    (r" and ", " or "), (r" or ", " and "), (r" < ", " <= "), (r" > ", " >= "),
    (r"\bTrue\b", "False"), (r"\bFalse\b", "True"), (r" not ", " "), (r" in ", " not in "),
    (r"\+ 1\b", "- 1"), (r"- 1\b", "+ 1"),
]


def candidates(root):
    out = []
    for d, _, fs in os.walk(os.path.join(root, "sqlglot")):
        for f in fs:
            if f.endswith(".py"):
                out.append(os.path.relpath(os.path.join(d, f), root))
    return sorted(out)


def import_level_lines(tree):
    """Lines of statements that run at import (module or class body)."""
    lines = set()

    def walk(node, in_func):
        for c in ast.iter_child_nodes(node):
            if isinstance(c, ast.stmt):
                if not in_func and not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    lines.update(range(c.lineno, c.end_lineno + 1))
                walk(c, in_func or isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)))

    walk(tree, False)
    return lines


def mutate_line(line, rng):
    opts = [(p, r) for p, r in SWAPS if re.search(p, line)]
    nums = list(re.finditer(r"(?<![\w.])(\d+)(?![\w.])", line))
    strs = list(re.finditer(r'"([a-z_]{2,})"', line))
    kinds = []
    if opts:
        kinds.append("op")
    if nums:
        kinds.append("num")
    if strs:
        kinds.append("str")
    if not kinds:
        return None
    k = rng.choice(kinds)
    if k == "op":
        p, r = rng.choice(opts)
        ms = list(re.finditer(p, line))
        m = rng.choice(ms)
        return line[: m.start()] + re.sub(p, r, m.group(0)) + line[m.end():]
    if k == "num":
        m = rng.choice(nums)
        return line[: m.start()] + str(int(m.group(1)) + 1) + line[m.end():]
    m = rng.choice(strs)
    return line[: m.start(1)] + m.group(1) + "x" + line[m.end(1):]


def main(root, out, count, seed):
    rng = random.Random(int(seed))
    files = candidates(root)
    os.makedirs(os.path.join(out, "commits"), exist_ok=True)
    made = 0
    while made < int(count):
        rel = rng.choice(files)
        text = open(os.path.join(root, rel)).read()
        lines = text.split("\n")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        imp = import_level_lines(tree)
        # half the mutants at import level, where the selector is weakest
        pool = [i for i in range(len(lines)) if ((i + 1) in imp) == (made % 2 == 0)
                and lines[i].strip() and not lines[i].strip().startswith(("#", '"""', "def ", "class ", "import ", "from "))]
        if not pool:
            continue
        i = rng.choice(pool)
        new = mutate_line(lines[i], rng)
        if new is None or new == lines[i]:
            continue
        new_lines = lines[:i] + [new] + lines[i + 1:]
        try:
            ast.parse("\n".join(new_lines))
        except SyntaxError:
            continue
        diff = difflib.unified_diff(lines, new_lines, f"a/{rel}", f"b/{rel}", lineterm="", n=3)
        body = "\n".join(diff)
        cid = f"m{seed}x{made:03d}"
        with open(os.path.join(out, "commits", cid + ".patch"), "w") as f:
            f.write(f"diff --git a/{rel} b/{rel}\n{body}\n")
        made += 1


if __name__ == "__main__":
    main(*sys.argv[1:5])
