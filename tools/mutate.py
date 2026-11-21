"""Generate small mutants of sqlglot at the pinned commit, as unified diffs,
to find where the selector misses. These validate the selector; nothing in
them is looked up when it runs.

Usage: python tools/mutate.py <sqlglot checkout> <out dir> <count> <seed> [kind,...]
Kinds are cycled evenly; manifest.json records validation-only provenance.
"""
import ast
import copy
import difflib
import json
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


# Validation inputs only: the selector never reads the manifest or mutants.
KINDS = (
    "runtime", "import_level", "sql_fixture", "python_comment", "sql_comment",
    "multi_file", "test_assertion", "test_helper", "delete_dict_entry",
    "delete_list_item", "remove_decorator", "default_argument", "import_line",
    "rename_name", "whitespace", "docstring", "new_file", "deleted_file", "delete_set_item", "delete_tuple_item",
)


class Generator:
    def __init__(self, root, rng):
        self.root, self.rng = root, rng
        self.texts, self.trees = {}, {}
        for top in ("sqlglot", "tests"):
            for d, dirs, fs in os.walk(os.path.join(root, top)):
                dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", ".git"))
                for f in sorted(fs):
                    if not f.endswith((".py", ".sql")):
                        continue
                    rel = os.path.relpath(os.path.join(d, f), root)
                    text = open(os.path.join(root, rel), encoding="utf-8").read()
                    self.texts[rel] = text
                    if f.endswith(".py"):
                        self.trees[rel] = ast.parse(text)
        self.code = [f for f in self.trees if f.startswith("sqlglot/")]
        self.test = [f for f in self.trees if f.startswith("tests/")]
        self.fixtures = [f for f in self.texts if f.startswith("tests/fixtures/") and f.endswith(".sql")]

    def replace_node(self, rel, node, replacement):
        # AST columns count UTF-8 bytes, not Unicode characters.
        lines = self.texts[rel].encode().splitlines(keepends=True)
        start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
        end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
        text = self.texts[rel].encode()
        return {rel: (text[:start] + replacement.encode() + text[end:]).decode()}

    def line_edit(self, rel, predicate=lambda i, l: True):
        lines = self.texts[rel].splitlines(keepends=True)
        pool = [i for i, l in enumerate(lines) if predicate(i, l)]
        if not pool:
            return None
        i = self.rng.choice(pool)
        new = mutate_line(lines[i], self.rng)
        if new is None:
            return None
        return {rel: "".join(lines[:i] + [new] + lines[i + 1:])}

    def make(self, kind, serial):
        rng = self.rng
        rel = rng.choice(self.code)
        tree = self.trees[rel]
        if kind in ("runtime", "import_level"):
            imp = import_level_lines(tree)
            return self.line_edit(rel, lambda i, l: ((i + 1 in imp) == (kind == "import_level"))
                                  and not l.lstrip().startswith(("#", "def ", "class ", "from ", "import ")))
        if kind == "sql_fixture":
            rel = rng.choice(self.fixtures)
            return self.line_edit(rel, lambda i, l: bool(l.strip()) and not l.startswith(("#", "--")))
        if kind == "sql_comment":
            rel = rng.choice(self.fixtures)
            lines = self.texts[rel].splitlines(keepends=True)
            pool = [i for i, l in enumerate(lines) if l.strip() and not l.startswith(("#", "--"))]
            if not pool:
                return None
            i = rng.choice(pool)
            # Inline SQL comments are observable by parser/formatter tests.
            lines[i] = "/* mutant comment */ " + lines[i]
            return {rel: "".join(lines)}
        if kind in ("python_comment", "whitespace"):
            lines = self.texts[rel].splitlines(keepends=True)
            if not lines:
                return {rel: "# mutant comment\n" if kind == "python_comment" else "\n"}
            i = rng.randrange(len(lines))
            if kind == "python_comment":
                lines.insert(i, "# mutant comment\n")
            else:
                lines[i] = lines[i].rstrip("\n") + "  \n"
            return {rel: "".join(lines)}
        if kind == "multi_file":
            a = self.make("runtime", serial)
            b = self.make("test_assertion", serial)
            return {**a, **b} if a and b and not (a.keys() & b.keys()) else None
        if kind in ("test_assertion", "test_helper"):
            rel = rng.choice(self.test) if kind == "test_assertion" else "tests/helpers.py"
            nodes = []
            for n in ast.walk(self.trees[rel]):
                if kind == "test_assertion" and isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr.startswith("assert"):
                    nodes += [a for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, (str, int, float, bool))]
                elif kind == "test_helper" and isinstance(n, ast.Return) and n.value is not None:
                    nodes.append(n.value)
            if not nodes:
                return None
            n = rng.choice(nodes)
            if kind == "test_helper":
                return self.replace_node(rel, n, "None")
            v = n.value
            value = not v if isinstance(v, bool) else v + 1 if isinstance(v, (int, float)) else v + "_mutant"
            return self.replace_node(rel, n, repr(value))
        if kind in ("delete_dict_entry", "delete_list_item", "delete_set_item", "delete_tuple_item"):
            options = []
            for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
                for n in cls.body:
                    value = getattr(n, "value", None)
                    if kind == "delete_dict_entry" and isinstance(value, ast.Dict) and value.keys:
                        options.append(value)
                    elif kind != "delete_dict_entry":
                        typ = {"delete_list_item": ast.List, "delete_set_item": ast.Set,
                               "delete_tuple_item": ast.Tuple}[kind]
                        if isinstance(value, typ) and value.elts:
                            options.append(value)
            if not options:
                return None
            n = copy.deepcopy(rng.choice(options))
            i = rng.randrange(len(n.keys if isinstance(n, ast.Dict) else n.elts))
            # Remove structurally, so first/last/one-line items are all legal.
            if isinstance(n, ast.Dict):
                del n.keys[i]
                del n.values[i]
            else:
                del n.elts[i]
            return self.replace_node(rel, n, ast.unparse(n))
        if kind == "remove_decorator":
            options = [d for n in ast.walk(tree) for d in getattr(n, "decorator_list", [])]
            if not options:
                return None
            n = rng.choice(options)
            lines = self.texts[rel].splitlines(keepends=True)
            return {rel: "".join(lines[:n.lineno - 1] + lines[n.end_lineno:])}
        if kind == "default_argument":
            options = [d for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       for d in n.args.defaults + [x for x in n.args.kw_defaults if x is not None]
                       if isinstance(d, ast.Constant)]
            if not options:
                return None
            n = rng.choice(options)
            v = n.value
            value = not v if isinstance(v, bool) else v + 1 if isinstance(v, (int, float)) else "_mutant" if isinstance(v, str) else False
            return self.replace_node(rel, n, repr(value))
        if kind == "import_line":
            options = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
            if not options:
                return None
            n = copy.deepcopy(rng.choice(options))
            n.names[0].name += "_mutant"
            return self.replace_node(rel, n, ast.unparse(n))
        if kind == "rename_name":
            if serial % 2:
                definitions = [n for n in ast.walk(tree)
                               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                if definitions:
                    n = rng.choice(definitions)
                    lines = self.texts[rel].splitlines(keepends=True)
                    line = lines[n.lineno - 1]
                    m = re.search(r"\b(?:def|class)\s+(" + re.escape(n.name) + r")\b", line)
                    if m:
                        lines[n.lineno - 1] = line[:m.start(1)] + n.name + "_mutant" + line[m.end(1):]
                        return {rel: "".join(lines)}
            options = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]
            if not options:
                return None
            n = rng.choice(options)
            return self.replace_node(rel, n, n.id + "_mutant")
        if kind == "docstring":
            options = [n.body[0].value for n in ast.walk(tree)
                       if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body
                       and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
                       and isinstance(n.body[0].value.value, str)]
            if not options:
                return None
            n = rng.choice(options)
            return self.replace_node(rel, n, repr(n.value + "\nMutant documentation."))
        if kind == "new_file":
            # New discovered fixtures can change existing tests; new modules
            # can also shadow a module/package that the baseline imported.
            if serial % 3 == 1:
                return {"tests/conftest.py": "import pytest\n\n@pytest.fixture(autouse=True)\ndef mutant_setup():\n    assert False, 'mutant setup'\n"}
            if serial % 3 == 2:
                return {"sqlglot/_mutant_new.py": "VALUE = 1\n"}
            dirs = sorted({os.path.dirname(f) for f in self.fixtures})
            return {rng.choice(dirs) + "/_mutant_new.sql": "SELECT 1;\nSELECT 2;\n"}
        if kind == "deleted_file":
            if serial % 3 == 0:
                helpers = [f for f in self.test if not os.path.basename(f).startswith("test_")
                           and self.texts[f].strip()]
                return {rng.choice(helpers): None}
            return {rng.choice(self.code + self.test + self.fixtures): None}
        raise ValueError(kind)


def patch_text(rel, before, after):
    old, new = ("/dev/null" if before is None else "a/" + rel), ("/dev/null" if after is None else "b/" + rel)
    lines = list(difflib.unified_diff((before or "").splitlines(keepends=True),
                                    (after or "").splitlines(keepends=True), old, new, n=3))
    # Represent a missing final newline according to unified diff syntax.
    body = "".join(l if l.endswith("\n") else l + "\n\\ No newline at end of file\n" for l in lines)
    mode = "new file mode 100644\n" if before is None else "deleted file mode 100644\n" if after is None else ""
    return f"diff --git a/{rel} b/{rel}\n{mode}{body}"


def main(root, out, count, seed, kinds=None):
    kinds = tuple(kinds.split(",")) if kinds else KINDS
    if not kinds or set(kinds) - set(KINDS):
        raise ValueError(f"kinds must be from {KINDS}")
    rng = random.Random(int(seed))
    gen = Generator(root, rng)
    os.makedirs(os.path.join(out, "commits"), exist_ok=True)
    manifest = {}
    seen = set()
    for i in range(int(count)):
        kind = kinds[i % len(kinds)]
        for attempt in range(10000):
            changes = gen.make(kind, i // len(kinds))
            if not changes:
                continue
            try:
                for rel, text in changes.items():
                    if text is not None and rel.endswith(".py"):
                        ast.parse(text)
            except (SyntaxError, ValueError):
                continue
            patch = "".join(patch_text(rel, gen.texts.get(rel), text) for rel, text in sorted(changes.items()))
            if not patch or patch in seen:
                continue
            seen.add(patch)
            cid = f"m{seed}x{i:03d}"
            with open(os.path.join(out, "commits", cid + ".patch"), "w") as f:
                f.write(patch)
            manifest[cid] = {"kind": kind, "files": sorted(changes)}
            break
        else:
            raise RuntimeError(f"cannot generate {kind}")
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump({"commits": manifest}, f, indent=2)
    print(f"generated {len(manifest)} mutants ({len(set(v['kind'] for v in manifest.values()))} kinds)")


if __name__ == "__main__":
    main(*sys.argv[1:6])
