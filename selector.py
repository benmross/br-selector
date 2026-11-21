"""Blast Radius selector.

For each patch, decide which sqlglot tests can catch it, then split them over
workers to minimise (busiest worker + 2 s a worker).

Evidence, all recorded by running sqlglot's own tests at the pinned commit
(tools/build_map.py):
  - line coverage per test, for code that runs inside a test;
  - which files each test opens, for SQL fixtures and other data files;
  - which sqlglot classes each test instantiates, for class-level tables
    (KEYWORDS, TRANSFORMS, arg_types) that run at import, before any test;
  - static imports between pinned test modules, for support files and package
    initializers whose import-time effects are outside per-test coverage.

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
import time

DATA = os.environ.get("DATA_DIR", "/data")
SRC = os.environ.get("SQLGLOT_SRC", "/opt/sqlglot")
MAP = os.environ.get("MAP_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "map.json.gz"))
INDEX = os.environ.get("INDEX_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.json.gz"))
WORKER_MS = 2000
MAX_WORKERS = 8
# Leave ample time to serialize fallbacks before the scorer's 180 s deadline.
MAX_SELECT_SECONDS = 120
MAX_PATCH_BYTES = 4 * 1024 * 1024
MAX_PATCH_LINES = 50000
MAX_PATCH_FILES = 256
MAX_COMMIT_SECONDS = 2


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
        self.ranges = []  # (old_count, new_start, new_count), parallel to hunks
        self.modes = []
        self.inserted_lines = set()  # added without replacing an old line


def patch_path(value, prefix=None):
    """Decode Git's C-quoted UTF-8 paths; reject ambiguous/escaping paths."""
    if value.startswith('"'):
        if not value.endswith('"'):
            raise ValueError("unterminated quoted path")
        value = value[1:-1]
        raw = bytearray()
        i = 0
        escapes = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12,
                   "r": 13, '"': 34, "\\": 92}
        while i < len(value):
            if value[i] != "\\":
                raw.extend(value[i].encode("utf-8"))
                i += 1
            elif i + 1 < len(value) and value[i + 1] in "01234567":
                m = re.match(r"[0-7]{1,3}", value[i + 1:])
                raw.append(int(m.group(), 8))
                i += 1 + len(m.group())
            elif i + 1 < len(value) and value[i + 1] in escapes:
                raw.append(escapes[value[i + 1]])
                i += 2
            else:
                raise ValueError("invalid path escape")
        value = raw.decode("utf-8")
    if value == "/dev/null":
        return None
    if prefix and value.startswith(prefix):
        value = value[len(prefix):]
    if not value or value.startswith("/") or any(p in ("", ".", "..") for p in value.split("/")) \
            or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("unsafe patch path")
    return value


def diff_paths(header):
    # Git does not quote ordinary spaces. File headers below disambiguate the
    # uncommon case where a path itself contains ' b/'.
    quoted = r'"(?:[^"\\]|\\.)*"'
    m = re.fullmatch(f"({quoted}|a/.*?) ({quoted}|b/.*)", header)
    if not m:
        raise ValueError("invalid diff header")
    return patch_path(m[1], "a/"), patch_path(m[2], "b/")


def parse_patch(text):
    text = text.replace("\r\n", "\n")
    if len(text) > MAX_PATCH_BYTES or text.count("\n") > MAX_PATCH_LINES:
        raise ValueError("patch exceeds analysis limit")
    files, cur, hunk = [], None, None
    remaining = [0, 0]

    def finish_hunk():
        if any(remaining):
            raise ValueError("truncated hunk")

    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()  # patch terminator is not a context line
    for line in lines:
        if line.startswith("diff --git "):
            finish_hunk()
            cur = FilePatch()
            files.append(cur)
            if len(files) > MAX_PATCH_FILES:
                raise ValueError("too many patch files")
            cur.old, cur.new = diff_paths(line[len("diff --git "):])
            hunk = None
            continue
        if cur is None:
            if line.startswith(("--- ", "+++ ", "@@", "diff ")):
                raise ValueError("unsupported diff format")
            continue
        if line == "\\ No newline at end of file":
            if hunk is None or not hunk[1] or not hunk[1][-1].endswith("\n"):
                raise ValueError("misplaced no-newline marker")
            hunk[1][-1] = hunk[1][-1][:-1]
            continue
        m = HUNK.match(line)
        if m:
            finish_hunk()
            start, old_count, new_start, new_count = (
                int(m[1]), int(m[2]) if m[2] is not None else 1,
                int(m[3]), int(m[4]) if m[4] is not None else 1)
            if (old_count and not start) or (new_count and not new_start):
                raise ValueError("invalid hunk position")
            hunk = (start, [])
            cur.hunks.append(hunk)
            cur.ranges.append((old_count, new_start, new_count))
            remaining = [old_count, new_count]
            continue
        if hunk is not None and any(remaining):
            tag = line[:1]
            if tag not in (" ", "-", "+"):
                raise ValueError("invalid hunk body")
            remaining[0] -= tag in (" ", "-")
            remaining[1] -= tag in (" ", "+")
            if min(remaining) < 0:
                raise ValueError("hunk count mismatch")
            hunk[1].append(line + "\n")
            continue
        if hunk is not None:
            if line and not line.startswith("-- "):
                raise ValueError("unexpected data after hunk")
            continue
        if hunk is None:
            if line.startswith("--- "):
                cur.old = patch_path(line[4:].split("\t")[0], "a/")
            elif line.startswith("+++ "):
                cur.new = patch_path(line[4:].split("\t")[0], "b/")
            elif line.startswith("new file mode"):
                cur.old = None
                cur.modes.append(line.rsplit(" ", 1)[-1])
            elif line.startswith("deleted file mode"):
                cur.new = None
                cur.modes.append(line.rsplit(" ", 1)[-1])
            elif line.startswith(("old mode ", "new mode ")):
                cur.modes.append(line.rsplit(" ", 1)[-1])
            elif line.startswith("rename from "):
                cur.old = patch_path(line[len("rename from "):])
            elif line.startswith("rename to "):
                cur.new = patch_path(line[len("rename to "):])
            elif line.startswith("copy from "):
                cur.old = patch_path(line[len("copy from "):])
            elif line.startswith("copy to "):
                cur.new = patch_path(line[len("copy to "):])
            elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
                cur.binary = True
            elif line.startswith(("@@", "+", "-", " ")) and not cur.binary:
                raise ValueError("unrecognized patch data")
    finish_hunk()
    for fp in files:
        if fp.old is None and fp.new is None:
            raise ValueError("patch has no path")
        if not fp.hunks and not fp.binary and not fp.modes and fp.old == fp.new:
            raise ValueError("file patch has no changes")
    return files


def apply(old_text, fp):
    """Return (new_text, changed_old_lines, insertion_points)."""
    old = []
    if old_text:
        parts = old_text.split("\n")
        old = [line + "\n" for line in parts[:-1]]
        if parts[-1]:
            old.append(parts[-1])
    out, pos = [], 0
    changed, inserts = set(), set()
    fp.inserted_lines = set()
    for (start, lines), (old_count, new_start, new_count) in zip(fp.hunks, fp.ranges):
        start_idx = start - 1 if old_count else start
        if start_idx < pos or start_idx > len(old) or start_idx + old_count > len(old):
            raise ValueError("overlapping or out-of-bounds hunk")
        out.extend(old[pos:start_idx])
        if (new_start - 1 if new_count else new_start) != len(out):
            raise ValueError("inconsistent new hunk position")
        pos = start_idx
        removed_run = False
        for l in lines:
            tag, body = l[:1], l[1:]
            if tag == " ":
                if old[pos] != body:
                    raise ValueError("patch context does not match source")
                out.append(old[pos])
                pos += 1
                removed_run = False
            elif tag == "-":
                if old[pos] != body:
                    raise ValueError("patch removal does not match source")
                changed.add(pos + 1)
                pos += 1
                removed_run = True
            elif tag == "+":
                out.append(body)
                if not removed_run:
                    inserts.add(pos)  # between old line pos and pos + 1
                    fp.inserted_lines.add(len(out))
    out.extend(old[pos:])
    return "".join(out), changed, inserts


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
        self.setup_files = {f: {int(k): v for k, v in lines.items()}
                            for f, lines in m.get("setup_files", {}).items()}
        self.has_setup_phases = "setup_files" in m
        self.pending_shared = set()
        self.by_file = {}
        for n, (_, f, _) in tests.items():
            self.by_file.setdefault(f, set()).add(n)
        self.all = set(tests)
        self.import_lines = {f: set(v) for f, v in m.get("import_lines", {}).items()}
        self._file_users = {}
        self.index = None
        self._test_import_map = None
        self._shared_setup_map = None
        try:
            with gzip.open(INDEX, "rt") as f:
                self.index = json.load(f)
        except Exception:
            pass

    def cov(self, path, lines, mark_shared=True):
        fl = self.files.get(path)
        out = set()
        if not fl:
            return out
        setup = self.setup_files.get(path, {})
        for l in lines:
            if mark_shared:
                ssid = setup.get(l)
                if ssid is not None:
                    self.pending_shared |= self.sets[ssid]
            sid = fl.get(l)
            if sid is not None:
                out |= self.sets[sid]
        return out

    def file_users(self, path):
        for sid in set(self.setup_files.get(path, {}).values()):
            self.pending_shared |= self.sets[sid]
        if path not in self._file_users:
            s = set()
            for sid in set(self.files.get(path, {}).values()):
                s |= self.sets[sid]
            self._file_users[path] = s
        return self._file_users[path]

    def class_users(self, module, qualname):
        sid = self.m["classes"].get(f"{module}:{qualname}")
        out = set(self.sets[sid]) if sid is not None else set()
        # Phase-tagged traces (setup_files present) already credit setup
        # observations to the whole class in the map. Older maps cannot tell
        # setup from call, so mark every user.
        if not self.has_setup_phases:
            self.pending_shared |= out
        return out

    def module_classes_users(self, module):
        prefix = module + ":"
        out = set()
        for k, sid in self.m["classes"].items():
            if k.startswith(prefix):
                out |= self.sets[sid]
        if not self.has_setup_phases:
            self.pending_shared |= out
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
        if not self.has_setup_phases:
            self.pending_shared |= out
        return out

    def test_importers(self, path):
        """Pinned-source imports, including transitive test helper/package users.

        Import-time test support changes have no per-test line coverage.
        Resolve their importing test files without using mutant outcomes.
        """
        if self._test_import_map is None:
            self._test_import_map = (self.index or {}).get("@test_importers")
            if self._test_import_map is None:
                self._test_import_map = build_test_importers(self._all_sources())
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-len(".__init__")]
        out = self.by_file.get(path, set()) | self.file_users(path)
        for rel in self._test_import_map.get(module, []):
            out |= self.by_file.get(rel, set())
        return out

    def expand_shared_setup(self, chosen, why):
        """A shared setup runs under its first test's coverage context, but
        its state or failure affects every test in the class/module/session.
        Expand those contexts using setup scopes from the pinned source.
        """
        if not chosen:
            return chosen
        self.prepare_shared_setup()
        chosen = set(chosen)
        more = True
        while more:
            more = False
            for triggers, users, prefix in self._shared_setup_map:
                affected = (self.pending_shared & chosen) if self.has_setup_phases else chosen
                if affected & triggers and not users <= chosen:
                    why.append(f"shared setup {prefix}: +{len(users - chosen)} tests")
                    chosen |= users
                    more = True
        return chosen

    def prepare_shared_setup(self):
        """Build the setup-scope and test-import tables once, in the parent,
        so each forked commit analysis inherits them."""
        pending = set(self.pending_shared)
        if self._shared_setup_map is None:
            specs = (self.index or {}).get("@shared_setup")
            if specs is None:
                specs = build_shared_setups(self._all_sources())
            self._shared_setup_map = []
            for rel, start, end, prefix in specs:
                if self.has_setup_phases:
                    # Only tests whose own setup phase ran the shared setup.
                    # The map's files entries credit setup lines to the whole
                    # class, which would make every class member a trigger.
                    setup = self.setup_files.get(rel, {})
                    triggers = set()
                    for line in range(start, end + 1):
                        if line in setup:
                            triggers |= self.sets[setup[line]]
                else:
                    triggers = self.cov(rel, range(start, end + 1), mark_shared=False)
                if prefix == "*":
                    users = self.all
                elif prefix.startswith("@imports:"):
                    # Imported shared fixtures can serve a different test
                    # file.
                    users = self.test_importers(prefix[len("@imports:"):])
                else:
                    users = {n for n, (tid, _, _) in self.tests.items() if tid.startswith(prefix)}
                if triggers and users:
                    self._shared_setup_map.append((triggers, users, prefix))
        if self._test_import_map is None:
            self.test_importers("tests/__init__.py")
        # Building tables reads coverage; it must not mark affected setups.
        self.pending_shared = pending

    # -- one file of a patch

    def for_file(self, fp, why):
        path = fp.new or fp.old
        paths = {p for p in (fp.old, fp.new) if p is not None}
        # Config can live inside tests/ too. Check it before Python coverage.
        configs = {"pyproject.toml", "setup.cfg", "setup.py", "pytest.ini", "tox.ini",
                   "conftest.py", "Makefile", "Dockerfile", "uv.lock", "poetry.lock",
                   "Pipfile", "Pipfile.lock", "environment.yml", "environment.yaml"}
        if any(os.path.basename(p) in configs or os.path.basename(p).startswith("requirements")
               for p in paths):
            why.append(f"{path}: build or test config, everything")
            return set(self.all)
        if any(mode not in ("100644", "100755") for mode in fp.modes):
            why.append(f"{path}: special file mode, everything")
            return set(self.all)
        python = any(p.endswith((".py", ".pyi", ".so", ".pth")) for p in paths)
        if python and (fp.binary or fp.old != fp.new):
            why.append(f"{path}: binary or structural Python change, everything")
            return set(self.all)
        if not fp.hunks and not fp.binary and fp.old == fp.new and fp.modes \
                and path.endswith(".py") and path.startswith("sqlglot/"):
            why.append(f"{path}: executable bit only")
            return set()
        users = set()
        pending = set(self.pending_shared)
        for p in paths:
            users |= self.fixture_users(p) | self.file_users(p) | self.by_file.get(p, set())
        if fp.binary:
            why.append(f"{path}: binary, every user")
            return users or set(self.all)
        if path.endswith(".py") and (path.startswith("sqlglot/") or path.startswith("tests/") or path in self.files):
            # Listing a source directory depends on file names, not changes to
            # an existing module's contents. Structural changes widened above.
            direct = self.m["fixtures"].get(path)
            readers = set(self.sets[direct]) if direct is not None else set()
            # The eager whole-file lookup above must not mark setup contexts
            # for lines this patch leaves alone; for_python marks changed ones.
            self.pending_shared = pending
            return self.for_python(fp, path, why) | readers
        if users:
            why.append(f"{path}: data file read by {len(users)}")
            return users
        if all(p.lower().endswith((".md", ".rst")) and not p.startswith(("sqlglot/", "tests/"))
               for p in paths):
            why.append(f"{path}: documentation, nothing")
            return set()
        why.append(f"{path}: untracked code or data, everything")
        return set(self.all)

    def for_python(self, fp, path, why):
        old_text = None
        if fp.old is not None:
            try:
                with open(os.path.join(SRC, fp.old), encoding="utf-8") as f:
                    old_text = f.read()
            except OSError:
                old_text = None
        if fp.old is not None and old_text is None:
            why.append(f"{path}: original missing, everything")
            return set(self.all)
        new_text, changed, inserts = apply(old_text, fp)
        if fp.new is None:
            why.append(f"{path}: deleted, broad")
            return self.broad(path) | self.importers(path)
        try:
            # Parse bytes, as Python's importer does: coding cookies can change
            # semantics or break import even when a string AST is unchanged.
            new_tree = ast.parse(new_text.encode("utf-8"))
            # Parsing alone accepts constructs such as a top-level 'return',
            # duplicate parameters, and unresolved nonlocal declarations.
            compile(new_tree, path, "exec")
        except SyntaxError:
            why.append(f"{path}: syntax error, importers")
            return self.broad(path) | self.importers(path)
        if old_text is None:
            if path.startswith("tests/"):
                # A newly collected module can add fixtures/hooks or mutate
                # shared state before any existing test starts.
                why.append(f"{path}: new test support/collection code, everything")
                return set(self.all)
            why.append(f"{path}: new module, importers only")
            return self.importers(path)
        try:
            old_tree = ast.parse(old_text.encode("utf-8"))
        except SyntaxError:
            return self.broad(path)
        if encoding_cookie(old_text) != encoding_cookie(new_text):
            # A new encoding can reinterpret string literals on otherwise
            # untouched lines, invalidating same_ast's line-based shortcut.
            if ast.dump(old_tree) != ast.dump(new_tree):
                why.append(f"{path}: source encoding changed semantics, everything")
                return set(self.all)
        touched = set(changed) | set(inserts) | {i + 1 for i in inserts}
        # Lines inserted after blank or comment lines can extend the block that
        # ends at the last code line before them (a statement appended to a
        # function, a method appended to a class). That block must be compared
        # too, although it ends before the insertion point.
        old_lines = old_text.split("\n")
        # A blank or comment line replaced by code is the same hazard.
        for ins in set(inserts) | {c for c in changed
                                   if not old_lines[c - 1].strip()
                                   or old_lines[c - 1].lstrip().startswith("#")}:
            q = ins
            while q >= 1 and (not old_lines[q - 1].strip() or old_lines[q - 1].lstrip().startswith("#")):
                q -= 1
            if q >= 1:
                touched.add(q)
        if same_ast(old_tree.body, new_tree.body, min(touched or {0}), max(touched or {0})):
            why.append(f"{path}: syntax tree unchanged")
            return set()

        # An insertion next to a function need not run inside it. In particular,
        # dedented code appended at EOF executes during import, even though its
        # only old neighbour was a runtime statement. New import-time code has
        # no recorded coverage; it can affect any later test.
        if fp.inserted_lines:
            new_scopes = Scopes(new_tree)
            if any((new_scopes.at(line) is None or not new_scopes.at(line)[4])
                   for line in fp.inserted_lines):
                why.append(f"{path}: inserted import-time code, everything")
                return set(self.all)

        scopes = Scopes(old_tree)
        new_scopes = Scopes(new_tree)
        def definitions(sc):
            return {(s[5], s[3].name) for s in sc.stmts
                    if not s[4] and isinstance(s[3], (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        if definitions(scopes) != definitions(new_scopes):
            # A changed exported definition can break importing modules whose
            # other tests never execute the old function/class themselves.
            why.append(f"{path}: definition names changed, import/collection users")
            return self.broad(path) | self.importers(path)
        reshaped = reshaped_names(scopes, new_scopes)
        if reshaped:
            # A table emptied or turned into another kind of value can make
            # the class's own construction fail (a metaclass indexing [0]),
            # which breaks importing the module and every test file that
            # imports it at collection. Only a read at import can do that.
            names = {n for _, n in reshaped}
            code, _ = self.readers(names)
            if code is None:
                why.append(f"{path}: import-time value of {','.join(sorted(names))} changed shape, everything")
                return set(self.all)
        removed = bound_names(scopes) - bound_names(new_scopes)
        removed_readers = set()
        if removed:
            # Removing a class attribute, enum member, constant or imported
            # name turns every read of it into an error. A read during import
            # (TokenType.X inside another class body) breaks loading sqlglot,
            # which no coverage context records.
            names = {n for _, n in removed}
            code, tests = self.readers(names)
            if code is None:
                why.append(f"{path}: removed import-level name {','.join(sorted(names))} "
                           f"read at import, everything")
                return set(self.all)
            removed_readers = code | tests
            why.append(f"{path}: removed name {','.join(sorted(names))}, readers {len(removed_readers)}")
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        out = set(removed_readers)
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
                    span = range(s[0], min(s[2], s[1]) + 1)
                    got = self.cov(path, span)
                    why.append(f"{path}:+{ins} runtime {len(got)}")
                    out |= got
                    out |= self.at_import(path, span, why)
            else:
                points.add(ins if ins >= 1 else 1)
                points.add(ins + 1)
                import_level = True
        out |= self.dedented_blocks(fp, old_text, scopes, path, why)
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
                out |= self.at_import(path, span, why)
            else:
                out |= self.cov(path, range(start, end + 1))
                out |= self.module_level(path, module, cls, why, line, node)
                import_level = True
        if import_level and could_raise(fp):
            # Never execute patch-supplied code in the selector. Even an
            # innocent import may loop, fork, write files, or produce unlimited
            # output. Unknown import effects need a conservative selection.
            why.append(f"{path}: possible import failure, everything")
            return set(self.all)
        return out

    def dedented_blocks(self, fp, old_text, scopes, path, why):
        """An added line indented less than the old code line it follows or
        replaces belongs to an outer block (a statement appended after a nested
        if/for, or moved out of one). It runs whenever that outer block runs,
        not only when the inner line did."""
        old_lines = old_text.split("\n")

        def indent(text):
            return len(text) - len(text.lstrip(" \t"))

        def code(text):
            body = text.strip()
            return bool(body) and not body.startswith("#")

        out = set()
        for start, lines in fp.hunks:
            pos = start - 1 if start else 0  # old lines consumed so far
            ref = pos
            while ref >= 1 and not code(old_lines[ref - 1]):
                ref -= 1
            for l in lines:
                tag, body = l[:1], l[1:].rstrip("\n")
                if tag in (" ", "-"):
                    pos += 1
                    if code(body):
                        ref = pos
                    continue
                if not code(body) or ref < 1 or indent(body) >= indent(old_lines[ref - 1]):
                    continue
                d = indent(body)
                parent = None
                for st in scopes.stmts:
                    node = st[3]
                    blocks = [b for f in ("body", "orelse", "finalbody") for b in [getattr(node, f, None)] if b]
                    if st[0] <= ref <= st[1] and any(b[0].col_offset == d for b in blocks if isinstance(b[0], ast.stmt)):
                        if parent is None or st[1] - st[0] <= parent[1] - parent[0]:
                            parent = st
                if parent is None:
                    continue
                node = parent[3]
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    first = node.body[0]
                    span = range(first.lineno, first.end_lineno + 1)
                elif parent[4]:
                    span = range(parent[0], min(parent[2], parent[1]) + 1)
                else:
                    continue
                got = self.cov(path, span)
                why.append(f"{path}:{ref} dedented line runs with its outer block: {len(got)}")
                out |= got | self.at_import(path, span, why)
        return out

    def at_import(self, path, span, why):
        """A function line that also ran while modules were imported (a
        metaclass, a trie or registry builder) leaves state every later test
        sees, which coverage credits to no test. Import/collection failures
        can affect every test, including ones that run in subprocesses."""
        imp = self.import_lines.get(path)
        if not imp or not any(l in imp for l in span):
            return set()
        # It ran while sqlglot or a test module was loading, before any test:
        # whatever it computed then (tables, parsed SQL at collection) reaches
        # tests that never run the line themselves. Only everything is safe.
        why.append(f"{path}:{span.start} also runs at import, everything")
        return set(self.all)

    def module_level(self, path, module, cls, why, line, stmt=None):
        """A statement that runs at import: a class attribute, decorator,
        default argument or module constant."""
        if path.startswith("tests/"):
            got = self.test_importers(path)
            why.append(f"{path}:{line} test module level {len(got)}")
            return got
        if cls:
            parts = cls.split(".")
            users = set()
            for i in range(1, len(parts) + 1):
                # a nested Tokenizer's settings are read through its dialect
                users |= self.class_users(module, ".".join(parts[:i]))
            names = assigned_names(stmt) if stmt is not None else None
            if not any(f"{module}:{'.'.join(parts[:i])}" in self.m["classes"]
                       for i in range(1, len(parts) + 1)):
                # No test ever instantiated this class (an Enum, a namespace
                # read through the class, __members__ or a metaclass), so its
                # instance users cannot narrow anything.
                if self.import_lines.get(path):
                    why.append(f"{path}:{line} class {cls} never instantiated, module runs at import: everything")
                    return set(self.all)
                got = self.file_users(path) | self.module_classes_users(module)
                why.append(f"{path}:{line} class {cls} never instantiated: module users {len(got)}")
                return got
            if names and any(n.startswith("__") and n.endswith("__") for n in names):
                # Python reads protocol attributes implicitly (e.g. __slots__
                # during type construction). Explicit name readers cannot
                # safely narrow users: construction during test collection
                # can fail a whole file before any individual test runs.
                got = set(self.all)
                why.append(f"{path}:{line} class {cls} protocol attribute: all import/collection users")
                return got
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
        names = assigned_names(stmt) if stmt is not None else None
        eager = bool(self.import_lines.get(path))
        if names:
            code_readers, test_readers = self.readers(names)
            if code_readers is not None:
                got = code_readers | test_readers
                why.append(f"{path}:{line} module constant {','.join(sorted(names))}: {len(got)} read it")
                return got
            if eager:
                why.append(f"{path}:{line} module constant read at import, everything")
                return set(self.all)
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
        unsafe = sites["u"]
        for rel, a, b in sites["c"]:
            code |= self.cov(rel, range(a, b + 1))
            imp = self.import_lines.get(rel)
            if imp and any(l in imp for l in range(a, b + 1)):
                unsafe = True  # read while modules load: its effect outlives any test
        tests = set()
        for rel, a, b in sites["t"]:
            tests |= self.cov(rel, range(a, b + 1))
        for rel in sites["tf"]:
            tests |= self.by_file.get(rel, set())
        return (None if unsafe else code), tests

    _scope_cache = {}

    def _scopes(self, rel, text):
        sc = Selector._scope_cache.get(rel)
        if sc is None:
            sc = Selector._scope_cache[rel] = Scopes(ast.parse(text))
        return sc

    def broad(self, path):
        if path.startswith("tests/"):
            return self.test_importers(path)
        module = path[:-3].replace("/", ".")
        return self.file_users(path) | self.module_classes_users(module)

    def importers(self, path):
        # A module that fails to import breaks every test that imports it,
        # which for anything under sqlglot/ is nearly everything.
        if path.startswith("sqlglot/"):
            return set(self.all)
        return self.test_importers(path)


def _dump(v):
    if isinstance(v, ast.AST):
        return ast.dump(v)
    if isinstance(v, list):
        return "[" + ",".join(_dump(x) for x in v) + "]"
    return repr(v)


def encoding_cookie(text):
    return re.findall(r"coding[:=]\s*([-\w.]+)", "\n".join(text.split("\n")[:2]))


def same_ast(a_list, b_list, lo, hi):
    """Are two statement lists the same tree? Statements wholly outside the
    patched lines lo..hi (original numbering) are textually unchanged, so
    only the ones that overlap are compared."""
    if len(a_list) != len(b_list):
        return False
    for a, b in zip(a_list, b_list):
        if type(a) is not type(b):
            return False
        start = min([getattr(a, "lineno", 0)] +
                    [d.lineno for d in getattr(a, "decorator_list", [])])
        if hasattr(a, "lineno") and (a.end_lineno < lo or start > hi):
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


def bound_names(scopes):
    """(class qualname, name) bound at import: assignments and imports."""
    out = set()
    for start, end, header_end, node, runtime, cls in scopes.stmts:
        if runtime:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = {(a.asname or a.name).split(".")[0] for a in node.names if a.name != "*"}
        else:
            names = assigned_names(node)
        for n in names or ():
            out.add((cls, n))
    return out


def _shape(value):
    """Kind and emptiness of a literal value; None for anything computed."""
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return (type(value).__name__, bool(value.elts))
    if isinstance(value, ast.Dict):
        return ("Dict", bool(value.keys))
    if isinstance(value, ast.Constant):
        # Numbers and flags may become 0 or False harmlessly; strings and
        # containers that become empty are what construction code indexes.
        v = value.value
        return (type(v).__name__, bool(v) if isinstance(v, (str, bytes)) else True)
    return None


def reshaped_names(old_scopes, new_scopes):
    """(class, name) assigned at import whose literal value changed kind or
    became empty, such as IDENTIFIERS = ["`"] -> IDENTIFIERS = []."""
    def values(sc):
        out = {}
        for start, end, header_end, node, runtime, cls in sc.stmts:
            if runtime or not cls or not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            names = assigned_names(node)
            if names and len(names) == 1 and node.value is not None:
                out[(cls, next(iter(names)))] = _shape(node.value)
        return out
    old, new = values(old_scopes), values(new_scopes)
    out = set()
    for key, shape in old.items():
        if key in new and shape is not None and new[key] != shape:
            if new[key] is None or new[key][0] != shape[0] or (shape[1] and not new[key][1]):
                out.add(key)
    return out


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




def build_shared_setups(sources):
    """Locate shared unittest/pytest setup in pristine test source."""
    specs = []
    for rel, text in sources.items():
        if not rel.startswith("tests/"):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        def walk(node, classes):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    walk(child, classes + [child.name])
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = None
                    if child.name == "setUpClass" and classes:
                        prefix = rel + "::" + "::".join(classes) + "::"
                    elif child.name == "setUpModule" and not classes:
                        prefix = rel + "::"
                    for deco in child.decorator_list:
                        if not isinstance(deco, ast.Call):
                            continue
                        name = deco.func.attr if isinstance(deco.func, ast.Attribute) else getattr(deco.func, "id", "")
                        if name != "fixture":
                            continue
                        for kw in deco.keywords:
                            if kw.arg == "scope" and isinstance(kw.value, ast.Constant):
                                if kw.value.value == "session":
                                    prefix = "*"
                                elif kw.value.value in ("module", "class", "package"):
                                    prefix = "@imports:" + rel
                    if prefix is not None:
                        specs.append([rel, child.body[0].lineno, child.end_lineno, prefix])
                else:
                    walk(child, classes)
        walk(tree, [])
    return specs


def build_test_importers(sources):
    """Static dependency map from pristine tests, built with the name index."""
    edges, paths = {}, {}
    for rel, text in sources.items():
        if not rel.startswith("tests/") or not rel.endswith(".py"):
            continue
        module = rel[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-len(".__init__")]
        paths[module] = rel
        # pytest imports the containing packages even without an explicit
        # import statement in the test file itself.
        parts = module.split(".")
        deps = {".".join(parts[:i]) for i in range(1, len(parts))}
        try:
            tree = ast.parse(text)
        except SyntaxError:
            edges[module] = deps
            continue
        package = rel.rsplit("/", 1)[0].split("/")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                deps.update(a.name for a in node.names if a.name.startswith("tests"))
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    prefix = package[:len(package) - node.level + 1]
                    base = ".".join(prefix + ([base] if base else []))
                if base == "tests" or base.startswith("tests."):
                    deps.add(base)
                    deps.update(base + "." + a.name for a in node.names if a.name != "*")
        edges[module] = deps
    users = {}
    for module, rel in paths.items():
        pending, seen = [module], set()
        while pending:
            dep = pending.pop()
            if dep in seen:
                continue
            seen.add(dep)
            pending.extend(edges.get(dep, ()))
            users.setdefault(dep, set()).add(rel)
    return {module: sorted(files) for module, files in users.items()}


def build_index(out_path):
    """Index pinned-source name readers and test imports at image build.
    Saves parsing the source at run time; contains no mutation outcomes."""
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
    index["@test_importers"] = build_test_importers(sources)
    index["@shared_setup"] = build_shared_setups(sources)
    with gzip.open(out_path, "wt") as f:
        json.dump(index, f, separators=(",", ":"))
    log(f"index: {len(cands)} names; test imports and shared setup scopes")


IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
KEYWORDS = set(__import__("keyword").kwlist)


def could_raise(fp):
    """Conservatively flag new import effects, without executing patch code."""
    removed, added = [], []
    for _, lines in fp.hunks:
        for l in lines:
            if l[:1] == "-":
                removed.append(l[1:])
            elif l[:1] == "+":
                added.append(l[1:])
    before = set(IDENT.findall("\n".join(removed)))
    added_text = "\n".join(added)
    after = set(IDENT.findall(added_text))
    if after & {"import", "while", "for", "raise", "assert", "del", "with", "try",
                "yield", "await", "return", "global", "nonlocal"}:
        return True
    if any(op in added_text for op in ("/", "%", "**", "<<", ">>")):
        return True
    after -= KEYWORDS
    return bool(after - before)


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


def select_patch(patch_path, sel, tests, deadline):
    """Analyze one commit. Any exception is handled by the parent process."""
    if time.monotonic() >= deadline:
        raise RuntimeError("batch analysis deadline reached")
    with open(patch_path, "rb") as f:
        raw = f.read(MAX_PATCH_BYTES + 1)
    if len(raw) > MAX_PATCH_BYTES:
        raise ValueError("patch exceeds size limit")
    text = raw.decode("utf-8")
    chosen, why = set(), []
    sel.pending_shared = set()
    files = parse_patch(text)
    if not files and text.strip():
        raise RuntimeError("no files in patch")
    for fp in files:
        if time.monotonic() >= deadline:
            raise RuntimeError("batch analysis deadline reached")
        chosen |= sel.for_file(fp, why)
        if chosen >= sel.all:
            break
    if not chosen >= sel.all:
        chosen = sel.expand_shared_setup(chosen, why)
    return chosen & set(tests), why


def _analyze_child(connection, patch_path, sel, tests, deadline):
    try:
        # AST creation can exhaust memory or the interpreter's C stack before
        # Python can raise an exception. Isolate it, and bound its address space
        # well below the container's 4 GB limit. The pristine maps are inherited
        # through fork, rather than decoded again for every commit.
        import resource

        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        limit = 768 * 1024 * 1024
        if soft != resource.RLIM_INFINITY:
            limit = min(limit, soft)
        resource.setrlimit(resource.RLIMIT_AS, (limit, hard))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        chosen, why = select_patch(patch_path, sel, tests, deadline)
        # Keep IPC and diagnostics bounded even for many edits or huge paths.
        diagnostics = [message[:500] for message in why[:100]]
        if len(why) > 100:
            diagnostics.append(f"{len(why) - 100} further reasons omitted")
        connection.send((chosen, diagnostics))
    except BaseException as e:
        connection.send((set(tests), [f"analysis error {type(e).__name__}: everything"]))
    finally:
        connection.close()


def analyze_patch(context, patch_path, sel, tests, deadline):
    """A broken/slow commit cannot reject the rest of the batch."""
    budget = min(MAX_COMMIT_SECONDS, deadline - time.monotonic())
    if budget <= 0:
        return set(tests), ["batch analysis deadline reached: everything"]
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_analyze_child,
                              args=(sender, patch_path, sel, tests, deadline))
    try:
        process.start()
        sender.close()
        if receiver.poll(budget):
            return receiver.recv()
        return set(tests), ["commit analysis timed out: everything"]
    except Exception as e:
        return set(tests), [f"analysis process failed {type(e).__name__}: everything"]
    finally:
        receiver.close()
        sender.close()
        if process.pid is not None:
            process.join(0.01)
            if process.is_alive():
                process.terminate()
                process.join(0.1)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()


def main():
    import multiprocessing

    deadline = time.monotonic() + MAX_SELECT_SECONDS
    context = multiprocessing.get_context("fork")
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
        sel.prepare_shared_setup()
    except Exception as e:  # never fail the run: fall back to everything
        log("map unavailable:", repr(e))
        sel = None

    cdir = os.path.join(DATA, "commits")
    fallback_workers = pack(set(tests), tests)
    for name in sorted(os.listdir(cdir)):
        if not name.endswith(".patch"):
            continue
        cid = name[: -len(".patch")]
        if sel is None:
            chosen, why = set(tests), ["map unavailable: everything"]
        else:
            chosen, why = analyze_patch(context, os.path.join(cdir, name), sel, tests, deadline)
        workers = fallback_workers if chosen == set(tests) else pack(chosen, tests)
        log(cid, len(chosen), "tests;", "; ".join(why))
        sys.stdout.write(json.dumps({"commit": cid, "workers": workers}) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--index":
        build_index(sys.argv[2])
    else:
        main()
