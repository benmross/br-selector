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
INDEX = os.environ.get("INDEX_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.json.gz"))
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
        removed_run = False
        for l in lines:
            tag, body = l[:1], l[1:]
            if tag == " ":
                out.append(old[pos] if pos < len(old) else body)
                pos += 1
                removed_run = False
            elif tag == "-":
                changed.add(pos + 1)
                pos += 1
                removed_run = True
            elif tag == "+":
                out.append(body)
                if not removed_run:
                    inserts.add(pos)  # between old line pos and pos + 1
            # "\\ No newline at end of file" leaves the run as it was
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

    def in_func(self, line, names):
        for s in self.stmts:
            if s[0] <= line <= s[1] and isinstance(s[3], (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and s[3].name in names:
                return True
        return False

    def at(self, line):
        """Innermost statement containing line, or None. A blank or comment
        line inside a block resolves to the nearest statement of that block,
        which runs exactly when the block does."""
        best = None
        for s in self.stmts:
            if s[0] <= line <= s[1] and (best is None or (s[1] - s[0]) <= (best[1] - best[0])):
                best = s
        if best is not None and line > best[2] and isinstance(best[3], (ast.stmt,)):
            node = best[3]
            kids = [c for f in ("body", "orelse", "finalbody", "handlers") for c in (getattr(node, f, None) or [])
                    if isinstance(c, ast.AST) and hasattr(c, "lineno")]
            if kids:
                k = min(kids, key=lambda c: min(abs(c.lineno - line), abs(c.end_lineno - line)))
                target = k if isinstance(k, ast.stmt) else (k.body[0] if getattr(k, "body", None) else None)
                for s in self.stmts:
                    if s[3] is target:
                        return s
                return best
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
        self.pending_import = []
        self.index = None
        try:
            with gzip.open(INDEX, "rt") as f:
                self.index = json.load(f)
        except Exception:
            pass

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
        if path.endswith(".py") and (path.startswith("sqlglot/") or path.startswith("tests/") or path in self.files):
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
        touched = set(changed) | set(inserts) | {i + 1 for i in inserts}
        if same_ast(old_tree.body, new_tree.body, min(touched or {0}), max(touched or {0})):
            why.append(f"{path}: syntax tree unchanged")
            return set()

        scopes = Scopes(old_tree)
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        out = set()
        import_level = False
        points = set(changed)
        for ins in inserts:
            # An inserted line sits between old lines ins and ins + 1. If either
            # neighbour runs inside a function, the new line runs when that
            # block does; otherwise it runs at import.
            before, after = scopes.at(ins) if ins >= 1 else None, scopes.at(ins + 1)
            rt = [s for s in (before, after) if s is not None and s[4]]
            if rt:
                for s in rt:
                    got = self.cov(path, range(s[0], min(s[2], s[1]) + 1))
                    why.append(f"{path}:+{ins} runtime {len(got)}")
                    out |= got
            else:
                points.add(ins if ins >= 1 else 1)
                points.add(ins + 1)
                import_level = True
        for line in sorted(points):
            s = scopes.at(line)
            if s is None:
                out |= self.module_level(path, module, None, why, line)
                import_level = True
                continue
            start, end, header_end, node, runtime, cls = s
            if runtime:
                span = range(start, (header_end if header_end < end else end) + 1)
                got = self.cov(path, span)
                why.append(f"{path}:{line} runtime {len(got)}")
                out |= got
            else:
                out |= self.cov(path, range(start, end + 1))
                out |= self.module_level(path, module, cls, why, line, node)
                import_level = True
        if import_level and could_raise(fp):
            self.pending_import.append((path, module, new_text))
        return out

    def module_level(self, path, module, cls, why, line, stmt=None):
        """A statement that runs at import: a class attribute, decorator,
        default argument or module constant."""
        if path.startswith("tests/"):
            got = self.by_file.get(path, set()) | self.file_users(path)
            why.append(f"{path}:{line} test module level {len(got)}")
            return got
        if cls:
            parts = cls.split(".")
            users = set()
            for i in range(1, len(parts) + 1):
                # a nested Tokenizer's settings are read through its dialect
                users |= self.class_users(module, ".".join(parts[:i]))
            names = assigned_names(stmt) if stmt is not None else None
            if names:
                # tests whose own code reads the attribute (for example by
                # looping over every class) need not instantiate the class
                code_readers, test_readers = self.readers(names)
                if code_readers is not None:
                    got = (users & code_readers) | test_readers
                    why.append(f"{path}:{line} class {cls} attr {','.join(sorted(names))}: "
                               f"{len(users)} users, {len(got)} read it")
                    return got
                users = users | test_readers
            why.append(f"{path}:{line} class {cls} users {len(users)}")
            return users
        got = self.file_users(path) | self.module_classes_users(module)
        why.append(f"{path}:{line} module level {len(got)}")
        return got

    @staticmethod
    def _assigned_names(node):
        """Names set by a plain class-level assignment, or None."""
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            return None
        names = set()
        for t in targets:
            if not isinstance(t, ast.Name):
                return None
            names.add(t.id)
        return names

    _sources = None

    @staticmethod
    def _load_sources():
        out = {}
        for top in ("sqlglot", "tests"):
            for root, _, fs in os.walk(os.path.join(SRC, top)):
                for f in fs:
                    if f.endswith(".py"):
                        full = os.path.join(root, f)
                        try:
                            with open(full, encoding="utf-8") as fh:
                                out[os.path.relpath(full, SRC)] = fh.read()
                        except OSError:
                            pass
        return out

    def _all_sources(self):
        if Selector._sources is None:
            Selector._sources = self._load_sources()
        return Selector._sources

    def readers(self, names):
        """Tests that run a line reading any of these attribute names, and
        tests whose own code reads them. The first is None when a read
        happens where coverage cannot attribute it (import time, metaclasses,
        string lookups)."""
        idx = self.index
        if idx is not None and all(n in idx for n in names):
            sites = {"u": False, "c": [], "t": [], "tf": []}
            for n in names:
                e = idx[n]
                sites["u"] |= e["u"]
                for k in ("c", "t", "tf"):
                    sites[k].extend(e[k])
        else:
            sites = reference_sites(self._all_sources(), names, self._scopes)
        code = set()
        for rel, a, b in sites["c"]:
            code |= self.cov(rel, range(a, b + 1))
        tests = set()
        for rel, a, b in sites["t"]:
            tests |= self.cov(rel, range(a, b + 1))
        for rel in sites["tf"]:
            tests |= self.by_file.get(rel, set())
        return (None if sites["u"] else code), tests

    _scope_cache = {}

    def _scopes(self, rel, text):
        sc = Selector._scope_cache.get(rel)
        if sc is None:
            sc = Selector._scope_cache[rel] = Scopes(ast.parse(text))
        return sc

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


def _dump(v):
    if isinstance(v, ast.AST):
        return ast.dump(v)
    if isinstance(v, list):
        return "[" + ",".join(_dump(x) for x in v) + "]"
    return repr(v)


def same_ast(a_list, b_list, lo, hi):
    """Are two statement lists the same tree? Statements wholly outside the
    patched lines lo..hi (original numbering) are textually unchanged, so
    only the ones that overlap are compared."""
    if len(a_list) != len(b_list):
        return False
    for a, b in zip(a_list, b_list):
        if type(a) is not type(b):
            return False
        if hasattr(a, "lineno") and (a.end_lineno < lo or a.lineno > hi):
            continue
        for field in a._fields:
            va, vb = getattr(a, field, None), getattr(b, field, None)
            if field in ("body", "orelse", "finalbody", "handlers") and isinstance(va, list) \
                    and isinstance(vb, list):
                if not same_ast(va, vb, lo, hi):
                    return False
            elif _dump(va) != _dump(vb):
                return False
    return True


UNSAFE_FUNCS = {"__new__", "__init_subclass__", "__set_name__", "__class_getitem__"}
DYNAMIC = re.compile(r"getattr\(|__dict__|vars\(")


def assigned_names(node):
    """Names set by a plain assignment statement, or None."""
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return None
    names = set()
    for t in targets:
        if not isinstance(t, ast.Name):
            return None
        names.add(t.id)
    return names


def classify(rel, text, lines, scopes, ln, names):
    """One line of source that mentions one of names: how does it read it?"""
    st = scopes.at(ln)
    if rel.startswith("tests/"):
        if st is None or not st[4]:
            return ("tf", rel)
        return ("t", rel, st[0], min(st[2], st[1]))
    if st is None:
        return ("u",)
    start, end, header_end, node, runtime, _ = st
    if not runtime:
        an = assigned_names(node)
        if isinstance(node, ast.AnnAssign) and node.value is None:
            return None
        if an and not (an - names):
            value = getattr(node, "value", None)
            seg = ast.get_source_segment(text, value) if value is not None else ""
            if not any(re.search(r"\b%s\b" % re.escape(n), seg or "") for n in names):
                return None  # another class defining the same setting
        return ("u",)
    if scopes.in_func(ln, UNSAFE_FUNCS) or DYNAMIC.search(lines[ln - 1]):
        return ("u",)
    return ("c", rel, start, min(header_end, end))


def _add(sites, r):
    if r is None:
        return
    if r[0] == "u":
        sites["u"] = True
    elif r[0] == "tf":
        sites["tf"].append(r[1])
    else:
        sites[r[0]].append(list(r[1:]))


def reference_sites(sources, names, scopes_for):
    pat = re.compile(r"\b(" + "|".join(map(re.escape, names)) + r")\b")
    sites = {"u": False, "c": [], "t": [], "tf": []}
    for rel, text in sources.items():
        if not pat.search(text):
            continue
        lines = text.split("\n")
        try:
            scopes = scopes_for(rel, text)
        except SyntaxError:
            sites["u"] = True
            continue
        for ln in sorted({text.count("\n", 0, m.start()) + 1 for m in pat.finditer(text)}):
            _add(sites, classify(rel, text, lines, scopes, ln, set(names)))
    return sites


def build_index(out_path):
    """Run at image build: every name assigned at class or module level in
    sqlglot, with where it is read. Saves parsing the source at run time."""
    sources = Selector._load_sources()
    parsed = {}
    for rel, text in sources.items():
        try:
            parsed[rel] = Scopes(ast.parse(text))
        except SyntaxError:
            pass
    cands = set()
    for rel, sc in parsed.items():
        if rel.startswith("sqlglot/"):
            for st in sc.stmts:
                if not st[4]:
                    an = assigned_names(st[3])
                    if an:
                        cands |= an
    index = {n: {"u": False, "c": [], "t": [], "tf": []} for n in cands}
    for rel, text in sources.items():
        sc = parsed.get(rel)
        lines = text.split("\n")
        seen = set()
        for ln, line in enumerate(lines, 1):
            for name in set(IDENT.findall(line)) & cands:
                if (name, ln) in seen:
                    continue
                seen.add((name, ln))
                if sc is None:
                    index[name]["u"] = True
                    continue
                _add(index[name], classify(rel, text, lines, sc, ln, {name}))
    for e in index.values():
        e["tf"] = sorted(set(e["tf"]))
        e["c"] = sorted({tuple(x) for x in e["c"]})
        e["t"] = sorted({tuple(x) for x in e["t"]})
    with gzip.open(out_path, "wt") as f:
        json.dump(index, f, separators=(",", ":"))
    log(f"index: {len(index)} names")


IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
KEYWORDS = set(__import__("keyword").kwlist)


def could_raise(fp):
    """Could this patch make a module fail to import? Swapping literals or
    operators cannot; a new name, attribute, call or import can."""
    removed, added = [], []
    for _, lines in fp.hunks:
        for l in lines:
            if l[:1] == "-":
                removed.append(l[1:])
            elif l[:1] == "+":
                added.append(l[1:])
    before = set(IDENT.findall("\n".join(removed)))
    after = set(IDENT.findall("\n".join(added)))
    after -= KEYWORDS
    return bool(after - before) or "import" in after


IMPORT_CHECK = r"""
import importlib, importlib.abc, importlib.machinery, json, os, sys
d = json.load(sys.stdin)
sys.path.insert(0, d["src"])
files = d["files"]
class L(importlib.abc.Loader):
    def __init__(self, n): self.n = n
    def create_module(self, spec): return None
    def exec_module(self, m):
        fn, code, _ = files[self.n]
        exec(compile(code, fn, "exec"), m.__dict__)
class F(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name not in files: return None
        fn, _, pkg = files[name]
        spec = importlib.machinery.ModuleSpec(name, L(name), origin=fn, is_package=pkg)
        if pkg: spec.submodule_search_locations = [os.path.dirname(fn)]
        spec.has_location = True
        return spec
sys.meta_path.insert(0, F())
import sqlglot
for name in files: importlib.import_module(name)
"""


def import_fails(pending):
    """Import the patched modules in a fresh interpreter. True if any raises."""
    import subprocess

    files = {}
    for path, module, text in pending:
        files[module] = (os.path.join(SRC, path), text, path.endswith("__init__.py"))
    try:
        r = subprocess.run(
            [sys.executable, "-I", "-c", IMPORT_CHECK],
            input=json.dumps({"src": SRC, "files": files}),
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:
        log("import check failed to run:", repr(e))
        return True
    if r.returncode:
        log("import check:", (r.stderr.strip().splitlines() or ["?"])[-1])
    return r.returncode != 0


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
            sel.pending_import = []
            for fp in files:
                chosen |= sel.for_file(fp, why)
            if sel.pending_import and import_fails(sel.pending_import):
                for path, module, _ in sel.pending_import:
                    if sel.m.get("import_lines", {}).get(path):
                        why.append(f"{path}: fails to import and loads with sqlglot, everything")
                        chosen |= sel.all
                    else:
                        got = sel.broad(path)
                        why.append(f"{path}: fails to import, its users {len(got)}")
                        chosen |= got
            chosen &= set(tests)
        except Exception as e:
            why.append(f"error {e!r}: everything")
            chosen = set(tests)
        workers = pack(chosen, tests)
        log(cid, len(chosen), "tests;", "; ".join(why))
        sys.stdout.write(json.dumps({"commit": cid, "workers": workers}) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--index":
        build_index(sys.argv[2])
    else:
        main()
