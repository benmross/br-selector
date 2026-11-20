"""Blast Radius selector.

For each patch, decide which sqlglot tests can catch it, then split them over
workers to minimise (busiest worker + 2 s a worker).

Evidence, all recorded by running sqlglot's own tests at the pinned commit
(tools/build_map.py):
  - line coverage per test, for code that runs inside a test;
  - which files each test opens, for SQL fixtures and other data files;
  - which sqlglot classes each test instantiates, for class-level tables
    (KEYWORDS, TRANSFORMS, arg_types) that run at import, before any test.

The pristine source lives in the image, so each patch is applied in memory and
both versions are parsed. A patch that leaves the module's syntax tree
unchanged (comments, blank lines) cannot change behaviour and selects nothing.
"""
import ast
import gzip
import json
import os
import re
import sys

DATA = os.environ.get("DATA_DIR", "/data")
SRC = os.environ.get("SQLGLOT_SRC", "/opt/sqlglot")
MAP = os.environ.get("MAP_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "map.json.gz"))
WORKER_MS = 2000
MAX_WORKERS = 8


def log(*a):
    print(*a, file=sys.stderr)


# ---------------------------------------------------------------- patches

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class FilePatch:
    def __init__(self):
        self.old = None  # path or None for a new file
        self.new = None  # path or None for a deleted file
        self.hunks = []  # (old_start, [lines])
        self.binary = False


def parse_patch(text):
    files, cur, hunk = [], None, None
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            cur = FilePatch()
            files.append(cur)
            m = re.match(r"diff --git a/(.*) b/(.*)$", line)
            if m:
                cur.old, cur.new = m.group(1), m.group(2)
            hunk = None
            continue
        if cur is None:
            continue
        if hunk is None:
            if line.startswith("--- "):
                p = line[4:].split("\t")[0]
                cur.old = None if p == "/dev/null" else p[2:] if p.startswith("a/") else p
            elif line.startswith("+++ "):
                p = line[4:].split("\t")[0]
                cur.new = None if p == "/dev/null" else p[2:] if p.startswith("b/") else p
            elif line.startswith("new file mode"):
                cur.old = None
            elif line.startswith("deleted file mode"):
                cur.new = None
            elif line.startswith("rename from "):
                cur.old = line[len("rename from "):]
            elif line.startswith("rename to "):
                cur.new = line[len("rename to "):]
            elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
                cur.binary = True
        m = HUNK.match(line)
        if m:
            hunk = (int(m.group(1)), [])
            cur.hunks.append(hunk)
            continue
        if hunk is not None and line[:1] in (" ", "-", "+", "\\"):
            hunk[1].append(line)
        elif hunk is not None and line == "":
            hunk[1].append(" ")  # a blank context line whose space was stripped
    return files


def apply(old_text, fp):
    """Return (new_text, changed_old_lines, insertion_points)."""
    old = old_text.split("\n") if old_text is not None else []
    out, pos = [], 0
    changed, inserts = set(), set()
    for start, lines in fp.hunks:
        start_idx = max(start - 1, 0) if lines and any(l[:1] in " -" for l in lines) else start
        out.extend(old[pos:start_idx])
        pos = start_idx
        for l in lines:
            tag, body = l[:1], l[1:]
            if tag == " ":
                out.append(old[pos] if pos < len(old) else body)
                pos += 1
            elif tag == "-":
                changed.add(pos + 1)
                pos += 1
            elif tag == "+":
                out.append(body)
                inserts.add(pos)  # between old line pos and pos + 1
    out.extend(old[pos:])
    return "\n".join(out), changed, inserts


# ---------------------------------------------------------------- scopes


class Scopes:
    """Answers, for a line of the original file: the innermost statement, and
    whether it runs inside a function call (runtime) or at import."""

    def __init__(self, tree):
        self.stmts = []  # (lineno, end, header_end, node, runtime, class_qualname)
        self._walk(tree, runtime=False, cls=[])

    def _walk(self, node, runtime, cls):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                header_end = child.end_lineno
                body = getattr(child, "body", None)
                if isinstance(body, list) and body and isinstance(body[0], ast.AST):
                    header_end = max(child.lineno, body[0].lineno - 1)
                deco = [d.lineno for d in getattr(child, "decorator_list", [])]
                start = min([child.lineno] + deco)
                self.stmts.append((start, child.end_lineno, header_end, child, runtime, ".".join(cls)))
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._walk(child, True, cls)
                elif isinstance(child, ast.ClassDef):
                    self._walk(child, runtime, cls + [child.name])
                else:
                    self._walk(child, runtime, cls)

    def at(self, line):
        """Innermost statement containing line, or None."""
        best = None
        for s in self.stmts:
            if s[0] <= line <= s[1] and (best is None or (s[1] - s[0]) <= (best[1] - best[0])):
                best = s
        return best


# ---------------------------------------------------------------- selection


class Selector:
    def __init__(self, tests, m):
        self.tests = tests  # number -> (id, file, ms)
        self.m = m
        self.sets = [frozenset(s) for s in m["sets"]]
        self.files = {f: {int(k): v for k, v in lines.items()} for f, lines in m["files"].items()}
        self.by_file = {}
        for n, (_, f, _) in tests.items():
            self.by_file.setdefault(f, set()).add(n)
        self.all = set(tests)
        self._file_users = {}

    def cov(self, path, lines):
        fl = self.files.get(path)
        out = set()
        if not fl:
            return out
        for l in lines:
            sid = fl.get(l)
            if sid is not None:
                out |= self.sets[sid]
        return out

    def file_users(self, path):
        if path not in self._file_users:
            s = set()
            for sid in set(self.files.get(path, {}).values()):
                s |= self.sets[sid]
            self._file_users[path] = s
        return self._file_users[path]

    def class_users(self, module, qualname):
        sid = self.m["classes"].get(f"{module}:{qualname}")
        return set(self.sets[sid]) if sid is not None else set()

    def module_classes_users(self, module):
        prefix = module + ":"
        out = set()
        for k, sid in self.m["classes"].items():
            if k.startswith(prefix):
                out |= self.sets[sid]
        return out

    def fixture_users(self, path):
        out = set()
        sid = self.m["fixtures"].get(path)
        if sid is not None:
            out |= self.sets[sid]
        d = os.path.dirname(path) + "/"
        sid = self.m["fixtures"].get(d)
        if sid is not None:
            out |= self.sets[sid]
        return out

    # -- one file of a patch

    def for_file(self, fp, why):
        path = fp.new or fp.old
        if fp.binary:
            why.append(f"{path}: binary, every user")
            return self.fixture_users(path) | self.file_users(path)
        if path.endswith(".py") and (path.startswith("sqlglot/") or path.startswith("tests/")):
            return self.for_python(fp, path, why)
        if path.startswith("tests/") or path.startswith("sqlglot/"):
            users = self.fixture_users(path)
            if fp.old is None and fp.new is not None:
                users |= self.fixture_users(os.path.dirname(path) + "/")
            why.append(f"{path}: data file read by {len(users)}")
            return users
        base = os.path.basename(path)
        if base in ("pyproject.toml", "setup.cfg", "setup.py", "pytest.ini", "tox.ini", "conftest.py", "Makefile"):
            why.append(f"{path}: build or test config, everything")
            return set(self.all)
        why.append(f"{path}: outside code and tests, nothing")
        return set()

    def for_python(self, fp, path, why):
        old_text = None
        if fp.old is not None:
            try:
                with open(os.path.join(SRC, fp.old), encoding="utf-8") as f:
                    old_text = f.read()
            except OSError:
                old_text = None
        if fp.old is not None and old_text is None:
            why.append(f"{path}: original missing, file users")
            return self.broad(path)
        new_text, changed, inserts = apply(old_text, fp)
        if fp.new is None:
            why.append(f"{path}: deleted, broad")
            return self.broad(path) | self.importers(path)
        try:
            new_tree = ast.parse(new_text)
        except SyntaxError:
            why.append(f"{path}: syntax error, importers")
            return self.broad(path) | self.importers(path)
        if old_text is None:
            why.append(f"{path}: new module, importers only")
            return self.importers(path)
        try:
            old_tree = ast.parse(old_text)
        except SyntaxError:
            return self.broad(path)
        if ast.dump(old_tree) == ast.dump(new_tree):
            why.append(f"{path}: syntax tree unchanged")
            return set()

        scopes = Scopes(old_tree)
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        out = set()
        points = set(changed)
        for ins in inserts:
            # an inserted line sits between old lines ins and ins + 1
            points.add(ins if ins >= 1 else 1)
            points.add(ins + 1)
        for line in sorted(points):
            s = scopes.at(line)
            if s is None:
                out |= self.module_level(path, module, None, why, line)
                continue
            start, end, header_end, node, runtime, cls = s
            if runtime:
                span = range(start, (header_end if header_end < end else end) + 1)
                got = self.cov(path, span)
                why.append(f"{path}:{line} runtime {len(got)}")
                out |= got
            else:
                out |= self.cov(path, range(start, end + 1))
                out |= self.module_level(path, module, cls, why, line)
        return out

    def module_level(self, path, module, cls, why, line):
        """A statement that runs at import: a class attribute, decorator,
        default argument or module constant."""
        if path.startswith("tests/"):
            got = self.by_file.get(path, set()) | self.file_users(path)
            why.append(f"{path}:{line} test module level {len(got)}")
            return got
        if cls:
            got = self.class_users(module, cls) | self.cov(path, self._class_span(path, cls))
            why.append(f"{path}:{line} class {cls} users {len(got)}")
            return got
        got = self.file_users(path) | self.module_classes_users(module)
        why.append(f"{path}:{line} module level {len(got)}")
        return got

    def _class_span(self, path, cls):
        return []

    def broad(self, path):
        if path.startswith("tests/"):
            return self.by_file.get(path, set()) | self.file_users(path)
        module = path[:-3].replace("/", ".")
        return self.file_users(path) | self.module_classes_users(module)

    def importers(self, path):
        # A module that fails to import breaks every test that imports it,
        # which for anything under sqlglot/ is nearly everything.
        if path.startswith("sqlglot/"):
            return set(self.all)
        return self.by_file.get(path, set()) | self.file_users(path)


# ---------------------------------------------------------------- packing


def pack(nums, tests):
    """Split tests over 1..8 workers, minimising busiest load + 2 s a worker."""
    items = sorted(nums, key=lambda n: -tests[n][2])
    if not items:
        return []
    best = None
    for k in range(1, min(MAX_WORKERS, len(items)) + 1):
        loads = [0] * k
        bins = [[] for _ in range(k)]
        for n in items:
            i = min(range(k), key=loads.__getitem__)
            loads[i] += tests[n][2]
            bins[i].append(n)
        cost = max(loads) + WORKER_MS * k
        if best is None or cost < best[0]:
            best = (cost, bins)
    return [sorted(b) for b in best[1] if b]


# ---------------------------------------------------------------- main


def main():
    with open(os.path.join(DATA, "tests.json")) as f:
        tj = json.load(f)
    tests = {t["number"]: (t["id"], t["file"], round(t["seconds"] * 1000)) for t in tj["tests"]}
    try:
        with gzip.open(MAP, "rt") as f:
            m = json.load(f)
        # renumber the map's tests by id, in case the hidden tests.json differs
        remap = {}
        ids = {t[0]: n for n, t in tests.items()}
        for tid, n in m["tests"].items():
            if tid in ids:
                remap[n] = ids[tid]
        m["sets"] = [[remap[n] for n in s if n in remap] for s in m["sets"]]
        sel = Selector(tests, m)
    except Exception as e:  # never fail the run: fall back to everything
        log("map unavailable:", repr(e))
        sel = None

    cdir = os.path.join(DATA, "commits")
    for name in sorted(os.listdir(cdir)):
        if not name.endswith(".patch"):
            continue
        cid = name[: -len(".patch")]
        why = []
        try:
            with open(os.path.join(cdir, name), encoding="utf-8", errors="replace") as f:
                text = f.read()
            if sel is None:
                raise RuntimeError("no map")
            chosen = set()
            files = parse_patch(text)
            if not files:
                raise RuntimeError("no files in patch")
            for fp in files:
                chosen |= sel.for_file(fp, why)
            chosen &= set(tests)
        except Exception as e:
            why.append(f"error {e!r}: everything")
            chosen = set(tests)
        workers = pack(chosen, tests)
        log(cid, len(chosen), "tests;", "; ".join(why))
        sys.stdout.write(json.dumps({"commit": cid, "workers": workers}) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
