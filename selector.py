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
import hashlib
import json
import os
import re
import sys
import time

DATA = os.environ.get("DATA_DIR", "/data")
SRC = os.environ.get("SQLGLOT_SRC", "/opt/sqlglot")
MAP = os.environ.get("MAP_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "map.json.gz"))
INDEX = os.environ.get("INDEX_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.json.gz"))
CMP = os.environ.get("CMP_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmp.json.gz"))
# Per-test narrowing of comparison swaps that change some results (off: only
# swaps that change no result anywhere in the suite select nothing).
CMP_PER_TEST = os.environ.get("CMP_PER_TEST", "0") == "1"
WORKER_MS = 2000
MAX_WORKERS = 8
# The scorer stops a run at 180 s of wall time. Analysis stops at 150 s. The
# 30 s margin: writing a fallback line takes about 95 us (8.6 KB, measured),
# so 10,000 leftover commits at ten times that cost take about 10 s; the
# other 20 s cover container start, interpreter start and exit on a stalled
# host.
MAX_SELECT_SECONDS = 150
MAX_PATCH_BYTES = 4 * 1024 * 1024
MAX_PATCH_LINES = 50000
MAX_PATCH_FILES = 256
# Per-commit limit on the analysis child's own CPU time, enforced by the
# kernel (RLIMIT_CPU). CPU time, unlike wall time, does not grow when a busy
# host stalls the child, so an ordinary commit is never cut off by load.
MAX_COMMIT_SECONDS = 2
# Wall-time backstop for a child that makes no CPU progress, capped by what is
# left of the batch budget.
MAX_COMMIT_WALL_SECONDS = 10


def log(*a):
    # Diagnostics only: a closed or broken stderr must never stop a stdout line.
    try:
        print(*a, file=sys.stderr)
    except Exception:
        pass


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
        self._cmp = None
        self._cmp_drop = None
        self._single_file_patch = True
        self._test_import_map = None
        self._shared_setup_map = None
        # Filled by prepare_batch in the parent, before any commit is forked:
        # parsed patches by path. Children only read them. (Caching parsed
        # original files here was measured and rejected: it doubles the
        # parent, and the extra fork and page-copy CPU on every commit
        # outweighs the parsing it saves.)
        self.patches = {}
        self.vm_base = None
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

    # -- comparison value profile

    def cmp_profile(self):
        """tools/build_cmp.py's record of which operator swaps changed a
        comparison result while the suite ran, renumbered like the map."""
        if self._cmp is None:
            self._cmp = False
            try:
                with gzip.open(CMP, "rt") as f:
                    prof = json.load(f)
                ids = {t[0]: n for n, t in self.tests.items()}
                remap = {n: ids[tid] for tid, n in prof["tests"].items() if tid in ids}
                prof["sets"] = [frozenset(remap[n] for n in s if n in remap) for s in prof["sets"]]
                self._cmp = prof
            except Exception:
                pass
        return self._cmp

    def comparison_verdict(self, path, swaps, why):
        """Swapping a comparison operator changes nothing for this suite when
        the profile saw the site evaluated and the new operator never gave a
        different bool there. Then every run of the suite executes exactly as
        before. Returns "equivalent", or None for normal selection; with
        CMP_PER_TEST, also sets tests to drop: those that evaluated the site
        and saw no different result (_cmp_drop)."""
        prof = self.cmp_profile()
        if not prof:
            return None
        entries = prof["sites"].get(path)
        imp = self.import_lines.get(path, set())
        drop = None
        for node, old_op, new_op in swaps:
            where = f"{path}:{node.lineno}:{node.col_offset}"
            if any(l in imp for l in range(node.lineno, node.end_lineno + 1)):
                # Code that also ran at import: keep the at-import rule.
                why.append(f"{where}: comparison runs at import, no shortcut")
                return None
            e = (entries or {}).get(f"{node.lineno}:{node.col_offset}")
            if e is None:
                why.append(f"{where}: comparison not profiled")
                return None
            op, union, unattributed, evaluated, flipped = e
            if op != old_op or not (new_op in CMP_FAMILY[op] and new_op != op):
                why.append(f"{where}: substitute not profiled")
                return None
            bit = 1 << new_op
            if not union & bit:
                continue
            if not CMP_PER_TEST or unattributed & bit:
                why.append(f"{where}: swap changes a result")
                return None
            safe = prof["sets"][evaluated] - prof["sets"][flipped[str(new_op)]]
            drop = safe if drop is None else drop & safe
        if drop is None:
            why.append(f"{path}: comparison swap changes no result anywhere in the suite, nothing")
            return "equivalent"
        self._cmp_drop = drop
        return None

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
        self._cmp_drop = None
        out = self._for_python(fp, path, why)
        if self._cmp_drop and not out >= self.all:
            dropped = out & self._cmp_drop
            if dropped:
                why.append(f"{path}: comparison swap changes no result in {len(dropped)} selected tests")
            out = out - self._cmp_drop
        return out

    def _for_python(self, fp, path, why):
        self._literal_extra_users = set()
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
        if self._single_file_patch and (self.index or {}).get('@pinned_string_audit') \
                and inert_string_changes(old_tree, new_tree) and self.docstrings_unobserved():
            why.append(f'{path}: only inert string statements changed; audited doc consumers have no numbered runtime users')
            return set()
        if path.startswith("tests/"):
            shared = changed_test_state(old_tree, new_tree, touched)
            if shared:
                why.append(f"{path}: edited {shared} mutates shared test state, everything")
                return set(self.all)
        swaps = comparison_swaps(old_tree.body, new_tree.body, min(touched or {0}), max(touched or {0}))
        if swaps:
            verdict = self.comparison_verdict(path, swaps, why)
            if verdict == "equivalent":
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
        dropped = removed_dict_keys(old_tree, new_tree, scopes, new_scopes)
        if dropped:
            # A key removed or renamed in a table that import-time code pops,
            # deletes or indexes by that key (KEYWORDS.pop("/*+") in a dialect
            # tokenizer body) raises KeyError while that module loads.
            hit = popped_at_import(self._all_sources(), dropped, self._scopes)
            if hit:
                why.append(f"{path}: removed key of {hit[0]} looked up at import in {hit[1]}, everything")
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
                if any(l[:1] == "+" for _, ls in fp.hunks for l in ls) \
                        and lookup_at_import(node, line, changed):
                    # A changed key in an import-time pop/del/index (a class
                    # body's KEYWORDS.pop("SORT BY")) can raise while the
                    # module loads, failing every importer at collection.
                    why.append(f"{path}:{line} import-time lookup changed, importers")
                    return self.importers(path)
                if changed_call_at_import(new_tree, fp):
                    # SQL templates (maybe_parse), type strings (DataType.build)
                    # and similar parsers run on their literal while the module
                    # loads; a literal that no longer parses fails every importer.
                    why.append(f"{path}:{line} changed constant in an import-time parse call, importers")
                    return self.importers(path)
                if bad_regex_at_import(node, line, changed, new_tree, fp):
                    why.append(f"{path}:{line} import-time regex no longer compiles, importers")
                    return self.importers(path)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and line <= header_end:
                    # A decorator or signature edit reaches every caller of the
                    # function, including callers through the class (class and
                    # static methods) and calls made while modules load.
                    body = range(node.body[0].lineno, node.end_lineno + 1)
                    got = self.cov(path, body)
                    why.append(f"{path}:{line} definition header of {node.name}: callers {len(got)}")
                    out |= got | self.at_import(path, body, why)
                out |= self.cov(path, range(start, end + 1))
                out |= self.module_level(path, module, cls, why, line, node)
                out |= self.qualified_consumers(cls, node, why)
                import_level = True
        if import_level and could_raise(fp, old_text, new_text) and not self.literal_only(path, old_tree, new_tree, why) \
                and not self.runtime_strings_safe(path, old_tree, new_tree, why):
            # Never execute patch-supplied code in the selector. Even an
            # innocent import may loop, fork, write files, or produce unlimited
            # output. Unknown import effects need a conservative selection.
            # Argument registration may run in the map's preload pass. Help
            # is only stored there. Its sole permitted reader, parse_args,
            # must never have run at import; no test may run/read this module.
            safe_help = False
            if self._single_file_patch and argparse_help_only(old_tree, new_tree):
                imp = self.import_lines.get(path, set())
                unread = not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                 and n.func.attr == 'parse_args'
                                 and any(line in imp for line in range(n.lineno, n.end_lineno + 1))
                                 for n in ast.walk(old_tree))
                unused = not self.broad(path) and not self.fixture_users(path)
                safe_help = unused and unread
            if not safe_help:
                why.append(f"{path}: possible import failure, everything")
                return set(self.all)
            why.append(f"{path}: no runtime/data users, stock argparse help stored but never read at import")
        out |= self._literal_extra_users
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

    def docstrings_unobserved(self):
        # Complete source-tree fingerprint guards this closed reader audit.
        # pytest does not collect unittest.load_tests; test_docs has no
        # numbered tests. leakcheck reads its own module doc only in main(),
        # which no numbered test invokes. Expr.__init_subclass__ copies a
        # nonempty __doc__ or ""; no runtime code consumes that content.
        for rel in ('tests/test_docs.py', 'tests/leakcheck.py'):
            if self.by_file.get(rel) or self.file_users(rel) or self.fixture_users(rel):
                return False
        return True

    def runtime_strings_safe(self, path, old_tree, new_tree, why):
        """Stored generator callbacks are invoked only by runtime dispatch.

        The source audit is bound to the complete pinned Python source tree at
        index build. A one-file patch may change only string constants in the
        body of a lambda stored directly in a generator dispatch table. It
        cannot change defaults, keys, registration, readers or other code.
        Import hooks copy/filter callbacks; they never invoke them. The three
        dispatch consumers and preprocess's adapter must have no import-time
        execution in the map. Keep coverage of every changed lambda body even
        when its table is copied to an unrelated generator class.
        """
        if not self._single_file_patch or not (self.index or {}).get('@pinned_string_audit'):
            return False
        if path != 'sqlglot/generator.py' and not path.startswith('sqlglot/generators/'):
            return False
        lambdas = runtime_lambda_changes(old_tree, new_tree)
        if not lambdas:
            return False
        for rel, first, last in self.index['@generator_string_calls']:
            if any(line in self.import_lines.get(rel, ()) for line in range(first, last + 1)):
                return False
        for node in lambdas:
            self._literal_extra_users |= self.cov(path, range(node.lineno, node.end_lineno + 1))
        why.append(f'{path}: only stored generator lambda-body strings changed; runtime dispatch coverage retained')
        return True

    # Import-time hooks reviewed at the pinned commit. Given non-empty strings
    # of unchanged type and no lost dict keys, they cannot raise on a changed
    # setting value: they build tries, inverse maps and sets, and test
    # membership. Any other import-time reader fails the proof.
    HOOKS = {("sqlglot/dialects/dialect.py", "__new__"), ("sqlglot/tokens.py", "__init_subclass__"),
             ("sqlglot/expressions/core.py", "__init_subclass__")}
    ENUM_BASES = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "AutoName"}
    DISPLAYS = (ast.Dict, ast.List, ast.Tuple, ast.Set)

    def literal_only(self, path, old_tree, new_tree, why):
        """True when the patch provably cannot make the module fail to import:
        every difference is a same-type constant inside a plain display that a
        module or class body assigns to a non-dunder name, and no code that
        runs at import reads that name except the reviewed hooks or a pure
        `{**Base.NAME, ...}` extension. The caller keeps the baseline
        selection (coverage and readers), which handles changed behaviour."""
        self._literal_extra_users = set()
        if not self._single_file_patch:
            return False
        diffs = []

        def walk(a, b, chain):
            if type(a) is not type(b):
                return False
            if isinstance(a, ast.Constant):
                if type(a.value) is type(b.value) and a.value == b.value and a.kind == b.kind:
                    return True
                if type(a.value) is not type(b.value) or type(a.value) not in (bool, int, float, str) \
                        or a.kind != b.kind:
                    return False
                if isinstance(a.value, str) and not (a.value and b.value):
                    return False
                diffs.append((chain + [a], b))
                return True
            for field in a._fields:
                va, vb = getattr(a, field, None), getattr(b, field, None)
                if isinstance(va, list) or isinstance(vb, list):
                    if not (isinstance(va, list) and isinstance(vb, list)) or len(va) != len(vb):
                        return False
                    pairs = zip(va, vb)
                else:
                    pairs = [(va, vb)]
                for x, y in pairs:
                    if isinstance(x, ast.AST) or isinstance(y, ast.AST):
                        if not walk(x, y, chain + [a]):
                            return False
                    elif x != y or type(x) is not type(y):
                        return False
            return True

        if not walk(old_tree, new_tree, []) or not diffs:
            return False
        names = set()
        for chain, new in diffs:
            i = max(k for k, n in enumerate(chain) if isinstance(n, ast.stmt))
            stmt, outer, inner = chain[i], chain[:i], chain[i + 1:]
            if not isinstance(outer[0], ast.Module) or not all(isinstance(n, ast.ClassDef) for n in outer[1:]):
                return False
            for c in outer[1:]:
                bases = {b.id if isinstance(b, ast.Name) else getattr(b, "attr", None) for b in c.bases}
                if c.decorator_list or c.keywords or None in bases or bases & self.ENUM_BASES \
                        or any(b.endswith("Enum") for b in bases):
                    return False
            if isinstance(stmt, ast.Assign):
                targets = stmt.targets
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                targets = [stmt.target]
            else:
                return False
            if not all(isinstance(t, ast.Name) and not t.id.startswith("__") for t in targets):
                return False
            if inner[0] is not stmt.value or not all(isinstance(n, self.DISPLAYS) for n in inner[:-1]):
                return False
            const, parent = inner[-1], inner[-2] if len(inner) > 1 else None
            if isinstance(parent, ast.Dict):
                if any(v is const for v in parent.keys):
                    siblings = parent.keys
                else:
                    siblings = []
            elif isinstance(parent, (ast.Set, ast.List, ast.Tuple)):
                siblings = parent.elts
            else:
                siblings = []
            # a duplicate key or element would shrink the built dict or set
            if any(isinstance(s, ast.Constant) and s is not const and type(s.value) is type(new.value)
                   and s.value == new.value for s in siblings):
                return False
            names |= {t.id for t in targets}
        if not self.import_readers_safe(names, why):
            return False
        why.append(f"{path}: only display literals of {','.join(sorted(names))} changed, import cannot fail")
        return True

    def import_readers_safe(self, names, why=None):
        """No statement that runs at import reads any of names, except the
        reviewed hooks and pure dict/sequence unpacking into another display.
        Reads in tests are their own files' readers and stay selected."""
        self._literal_extra_users = set()
        seen_bindings = set()
        pat = re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\b")
        for rel, text in self._all_sources().items():
            if not rel.startswith("sqlglot/") or not pat.search(text):
                continue
            try:
                scopes = self._scopes(rel, text)
            except SyntaxError:
                return False
            imp = self.import_lines.get(rel) or set()
            lines = text.split("\n")
            # Comments and standalone string expressions cannot read a name.
            # Keep strings in executable expressions: getattr(C, "SETTING")
            # really can read SETTING without a Name/Attribute AST node.
            inert = (self.index or {}).get("@inert_name_ranges", {}).get(rel)
            mentioned = name_reference_lines(text, pat, scopes, inert)
            for ln in sorted(mentioned):
                st = scopes.at(ln)
                if st is None:
                    return False
                node, runtime = st[3], st[4]
                if runtime:
                    if ln in imp and not any(rel == f and scopes.in_func(ln, {fn}) for f, fn in self.HOOKS):
                        return False
                    if DYNAMIC.search(lines[ln - 1]) and ln in imp:
                        return False
                    continue
                if not self._extension_only(node, names):
                    return False
                value = getattr(node, 'value', None)
                targets = assigned_names(node)
                if targets and value is not None and _mentions(value, names):
                    # Copying a table into an unrelated class carries its
                    # runtime effects beyond the original class's MRO. Keep
                    # the normal users/readers of every same-name consumer.
                    # Different-name copies need a larger dependency closure.
                    if not targets <= names:
                        return False
                    key = (rel, id(node))
                    if key not in seen_bindings:
                        seen_bindings.add(key)
                        module = rel[:-3].replace('/', '.').removesuffix('.__init__')
                        extra_why = []
                        users = self.module_level(rel, module, st[5], extra_why, st[0], node)
                        self._literal_extra_users |= users
                        if why is not None:
                            why.extend(extra_why)
                            why.append(f'{rel}:{st[0]} same-name literal dependency: keep {len(users)} consumer tests')
        return True

    def _extension_only(self, node, names):
        """A module or class statement that mentions names only as its own
        assignment target or as **NAME / *NAME unpacked into a display."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # the name sits on a decorator, base or default: evaluated at import
            heads = list(node.decorator_list) + list(getattr(node, "bases", [])) + \
                list(getattr(node, "keywords", []))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                heads += list(node.args.defaults) + [d for d in node.args.kw_defaults if d] + \
                    ([node.returns] if node.returns else [])
                heads += [a.annotation for a in node.args.args + node.args.kwonlyargs if a.annotation]
            return not any(_mentions(h, names) for h in heads)
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            return False
        if not all(isinstance(t, ast.Name) for t in targets):
            return False
        if value is None:
            return True
        # A same-name alias preserves the literal value and cannot fail on a
        # same-type literal edit. Readers of the target are already scanned
        # under the same name; differently named aliases need propagation.
        if _is_ref(value, names) and all(t.id in names for t in targets):
            return True
        ok = []

        def unpacked(n):
            # **Base.NAME in a dict display, *Base.NAME in a list, set or tuple
            if isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if k is None and _is_ref(v, names):
                        ok.append(v)
            elif isinstance(n, (ast.List, ast.Set, ast.Tuple)):
                for e in n.elts:
                    if isinstance(e, ast.Starred) and _is_ref(e.value, names):
                        ok.append(e.value)
        unpacked(value)
        return not _mentions(value, names, skip=ok)

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

    def qualified_consumers(self, cls, node, why, depth=3):
        """Code that reads this class attribute through its class name.

        presto.py binds `TIME_MAPPING = MySQL.TIME_MAPPING` in its class
        body, so a MySQL TIME_MAPPING edit changes Presto, whose tests are not
        MySQL's users (t44x a44l01: TestPresto::test_to_char and
        TestHive::test_time fail). This applies whether or not the edit could
        fail at import. An import-time copy keeps the copying statement's own
        users and is followed again under its new class and name; a runtime
        read keeps the coverage of its function. Widening only."""
        if not cls or not isinstance(node, (ast.Assign, ast.AnnAssign)):
            return set()
        frontier = [(cls, n) for n in sorted(assigned_names(node) or ())]
        seen, out = set(frontier), set()
        reads = (self.index or {}).get("@qualified_reads")
        while frontier and depth > 0:
            depth -= 1
            nxt = []
            sites = {}
            for c, n in frontier:
                if reads is None:  # old or absent index: scan the pinned source
                    pat = re.compile(r"\b" + re.escape(f"{c}.{n}") + r"\b")
                    found = [(rel, text.count("\n", 0, m.start()) + 1)
                             for rel, text in self._all_sources().items() if rel.startswith("sqlglot/")
                             for m in pat.finditer(text)]
                else:
                    found = [(rel, ln) for rel, ln, chain in reads.get(n, ())
                             if chain == c + "." or chain.endswith("." + c + ".")]
                for rel, ln in found:
                    sites.setdefault(rel, set()).add(ln)
            for rel in sorted(sites):
                try:
                    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
                        scopes = self._scopes(rel, f.read())
                except (OSError, SyntaxError):
                    continue
                module = rel[:-3].replace("/", ".").removesuffix(".__init__")
                for ln in sorted(sites[rel]):
                    st = scopes.at(ln)
                    if st is None:
                        continue
                    if st[4]:
                        got = self.cov(rel, range(st[0], st[1] + 1))
                        why.append(f"{rel}:{ln} runtime read of a changed class attribute {len(got)}")
                        out |= got
                        continue
                    got = self.module_level(rel, module, st[5], why, ln, st[3])
                    why.append(f"{rel}:{ln} copies a changed class attribute: keep {len(got)} consumer tests")
                    out |= got
                    if st[5]:
                        for t in sorted(assigned_names(st[3]) or ()):
                            if (st[5], t) not in seen:
                                seen.add((st[5], t))
                                nxt.append((st[5], t))
            frontier = nxt
        return out

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


CMP_OPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot)
CMP_FAMILY = {op: ((0, 1, 6, 7) if op in (0, 1, 6, 7) else (0, 1, 2, 3, 4, 5)) for op in range(8)}


def comparison_swaps(a_list, b_list, lo, hi):
    """The statements overlapping lines lo..hi differ only in the operators
    of single-operator comparisons: return [(old Compare, old op, new op)].
    Positions are ignored, so reformatting around the operator still
    matches. Anything else differing returns None."""
    swaps = []

    def same(a, b):
        if type(a) is not type(b):
            return False
        if isinstance(a, list):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if not isinstance(a, ast.AST):
            return repr(a) == repr(b)
        if isinstance(a, ast.Compare) and len(a.ops) == 1 and len(b.ops) == 1 \
                and type(a.ops[0]) is not type(b.ops[0]):
            if type(a.ops[0]) not in CMP_OPS or type(b.ops[0]) not in CMP_OPS:
                return False
            swaps.append((a, CMP_OPS.index(type(a.ops[0])), CMP_OPS.index(type(b.ops[0]))))
            return same(a.left, b.left) and same(a.comparators, b.comparators)
        return all(same(getattr(a, f, None), getattr(b, f, None)) for f in a._fields)

    if len(a_list) != len(b_list):
        return None
    for a, b in zip(a_list, b_list):
        start = min([getattr(a, "lineno", 0)] + [d.lineno for d in getattr(a, "decorator_list", [])])
        if hasattr(a, "lineno") and (a.end_lineno < lo or start > hi):
            continue
        if not same(a, b):
            return None
    return swaps or None


UNSAFE_FUNCS = {"__new__", "__init_subclass__", "__set_name__", "__class_getitem__"}
DYNAMIC = re.compile(r"getattr\(|__dict__|vars\(")
# A maximal dotted chain such as `tokens.Tokenizer.KEYWORDS.copy`.
QUALIFIED_READ = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")


# This is a closed-source reader audit, invalidated by any change to the
# original source tree. Patches are compared separately and must be one file.
PINNED_STRING_AUDIT = 'fc8e3c215f006385b628ef4612295b1d074b93b42de8c773997de3f40103d090'


def source_fingerprint(sources):
    digest = hashlib.sha256()
    for path, text in sorted(sources.items()):
        digest.update(path.encode() + b'\0' + text.encode() + b'\0')
    return digest.hexdigest()


def string_changes(old_tree, new_tree):
    """All AST fields agree except str constants; return their old ancestors."""
    changes = []

    def same(a, b, chain=()):
        if type(a) is not type(b):
            return False
        if isinstance(a, ast.Constant) and a.value != b.value:
            if type(a.value) is not str or type(b.value) is not str or a.kind != b.kind:
                return False
            changes.append(chain + (a,))
            return True
        if isinstance(a, ast.AST):
            return all(same(getattr(a, field), getattr(b, field), chain + (a,)) for field in a._fields)
        if isinstance(a, list):
            return len(a) == len(b) and all(same(x, y, chain) for x, y in zip(a, b))
        return type(a) is type(b) and a == b

    return changes if same(old_tree, new_tree) and changes else None


def inert_string_changes(old_tree, new_tree):
    changes = string_changes(old_tree, new_tree)
    return bool(changes) and all(len(chain) >= 2 and isinstance(chain[-2], ast.Expr)
                                and chain[-2].value is chain[-1] for chain in changes)


def runtime_lambda_changes(old_tree, new_tree):
    changes = string_changes(old_tree, new_tree)
    if not changes:
        return None
    lambdas = {}
    for chain in changes:
        indices = [i for i, n in enumerate(chain) if isinstance(n, ast.Lambda)]
        if not indices:
            return None
        i = indices[-1]
        node = chain[i]
        # Defaults run at definition time, and an immediate call/factory can
        # invoke a callback at import. Accept only direct stored dict values.
        if chain[i + 1] is not node.body or i < 3 or not isinstance(chain[i - 1], ast.Dict) \
                or not any(v is node for v in chain[i - 1].values):
            return None
        stmt = chain[i - 2]
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)) or stmt.value is not chain[i - 1] \
                or not assigned_names(stmt) or not assigned_names(stmt) <= {'TRANSFORMS', 'AFTER_HAVING_MODIFIER_TRANSFORMS'}:
            return None
        outer = chain[:i - 2]
        if not isinstance(outer[0], ast.Module) or any(not isinstance(c, ast.ClassDef)
                or not c.name.endswith('Generator') or c.decorator_list or c.keywords for c in outer[1:]):
            return None
        lambdas[id(node)] = node
    return list(lambdas.values())


def argparse_help_only(old_tree, new_tree):
    """Only ASCII, percent-free help strings on a stock ArgumentParser change.

    Stock argparse actions store help text without interpreting it during
    add_argument. Percent formatting happens when help is rendered; prohibit
    percent characters in both versions. Prove the parser has not escaped,
    been rebound, registered custom actions, or acquired a custom formatter.
    All other AST fields, including argument names/defaults/actions, agree.
    This only removes an import-failure fallback; ordinary users stay selected.
    """
    imports = [n for n in old_tree.body if isinstance(n, ast.Import)
               for alias in n.names if alias.name == 'argparse' and alias.asname is None]
    if len(imports) != 1:
        return False
    changes = []

    def same(a, b, chain=()):
        if type(a) is not type(b):
            return False
        if isinstance(a, ast.Constant) and a.value != b.value:
            if not (type(a.value) is str and type(b.value) is str
                    and a.value.isascii() and b.value.isascii()
                    and '%' not in a.value and '%' not in b.value
                    and a.kind == b.kind and len(chain) == 4):
                return False
            module, stmt, call, keyword, const = (*chain, a)
            if not (isinstance(module, ast.Module) and isinstance(stmt, ast.Expr)
                    and stmt in module.body and isinstance(call, ast.Call)
                    and stmt.value is call and isinstance(keyword, ast.keyword)
                    and keyword.arg == 'help' and isinstance(call.func, ast.Attribute)
                    and call.func.attr == 'add_argument' and isinstance(call.func.value, ast.Name)):
                return False
            changes.append(call)
            return True
        if isinstance(a, ast.AST):
            return all(same(getattr(a, field), getattr(b, field), chain + (a,)) for field in a._fields)
        if isinstance(a, list):
            return len(a) == len(b) and all(same(x, y, chain) for x, y in zip(a, b))
        return a == b

    if not same(old_tree, new_tree) or not changes:
        return False
    # A constant's ancestors are Module, Expr, Call, keyword (four nodes).
    names = {call.func.value.id for call in changes}
    parents = {id(child): node for node in ast.walk(old_tree) for child in ast.iter_child_nodes(node)}
    stores = {name: [] for name in names | {'argparse'}}
    for node in ast.walk(old_tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in stores:
            stores[node.id].append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in stores:
            return False
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = alias.asname or alias.name.split('.')[0]
                if bound in stores and not (node is imports[0] and bound == 'argparse'):
                    return False
    if stores['argparse']:
        return False
    # Before a changed registration, allow only imports, parser construction
    # and literal argument registrations. No arbitrary helper can replace the
    # stock parser/action registry between construction and the changed call.
    last_change = max(call.lineno for call in changes)
    for stmt in old_tree.body:
        if stmt.lineno > last_change or isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id in names:
            continue  # constructor checked below
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and type(stmt.value.value) is str:
            continue
        if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == 'add_argument'
                and isinstance(stmt.value.func.value, ast.Name) and stmt.value.func.value.id in names):
            return False
        call = stmt.value
        if not all(isinstance(v, ast.Constant) and type(v.value) is str for v in call.args):
            return False
        for keyword in call.keywords:
            if isinstance(keyword.value, ast.Constant):
                continue
            if keyword.arg == 'type' and isinstance(keyword.value, ast.Name) and keyword.value.id == 'str':
                # A source-level replacement of built-in str would be a new
                # callback; reject all bindings other than its implicit one.
                if any(n == 'str' for _, n in bound_names(Scopes(old_tree))):
                    return False
                continue
            return False
    for name in names:
        if len(stores[name]) != 1:
            return False
        assignment = parents[id(stores[name][0])]
        if not (isinstance(assignment, ast.Assign) and assignment in old_tree.body
                and len(assignment.targets) == 1 and isinstance(assignment.value, ast.Call)):
            return False
        ctor = assignment.value
        if not (isinstance(ctor.func, ast.Attribute) and ctor.func.attr == 'ArgumentParser'
                and isinstance(ctor.func.value, ast.Name) and ctor.func.value.id == 'argparse'
                and not ctor.args and all(k.arg in {'description', 'prog'}
                    and isinstance(k.value, ast.Constant) and type(k.value.value) is str for k in ctor.keywords)):
            return False
        if any(assignment.lineno >= call.lineno for call in changes if call.func.value.id == name):
            return False
        for node in ast.walk(old_tree):
            if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
                continue
            if node.id == 'argparse' and node is not ctor.func.value:
                return False
            if node.id != name:
                continue
            attr = parents[id(node)]
            call = parents.get(id(attr))
            if not (isinstance(attr, ast.Attribute) and attr.attr in {'add_argument', 'parse_args'}
                    and isinstance(attr.ctx, ast.Load) and isinstance(call, ast.Call) and call.func is attr):
                return False
            if attr.attr == 'add_argument':
                if any(k.arg is None for k in call.keywords):
                    return False
                actions = [k.value for k in call.keywords if k.arg == 'action']
                if any(not isinstance(v, ast.Constant) or v.value not in
                       {'store', 'store_const', 'store_true', 'store_false', 'append', 'append_const',
                        'count', 'help', 'version', 'extend'} for v in actions):
                    return False
    return True


def inert_name_ranges(text, scopes):
    """Character intervals occupied by comments and inert string statements."""
    import io
    import tokenize

    inert = {(st[3].value.lineno, st[3].value.col_offset)
             for st in scopes.stmts if isinstance(st[3], ast.Expr)
             and isinstance(st[3].value, ast.Constant)
             and isinstance(st[3].value.value, str)}
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    ranges = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT or token.start in inert:
            ranges.append((offsets[token.start[0] - 1] + token.start[1],
                           offsets[token.end[0] - 1] + token.end[1]))
    return ranges


def name_reference_lines(text, pattern, scopes, inert=None):
    """Lexical name mentions minus comments and inert string statements.

    Executable string expressions remain possible dynamic name reads.
    The image indexes inert intervals at build time; old or absent indexes
    compute the identical intervals here. No patch code is evaluated.
    """
    if inert is None:
        inert = inert_name_ranges(text, scopes)
    lines, pos = set(), 0
    for match in pattern.finditer(text):
        while pos < len(inert) and inert[pos][1] <= match.start():
            pos += 1
        if pos < len(inert) and inert[pos][0] <= match.start() and match.end() <= inert[pos][1]:
            continue
        lines.add(text.count("\n", 0, match.start()) + 1)
    return lines


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
    """Import-time class bindings whose literal structure became unsafe.

    Class construction also indexes entries inside tables: IDENTIFIERS can
    remain a nonempty list while an entry becomes an empty or one-item pair.
    Keep ordinary same-type leaf edits on the existing reader selection.
    """
    def values(sc):
        out = {}
        for start, end, header_end, node, runtime, cls in sc.stmts:
            if runtime or not cls or not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            names = assigned_names(node)
            if names and len(names) == 1 and node.value is not None:
                out[(cls, next(iter(names)))] = node.value
        return out
    old, new = values(old_scopes), values(new_scopes)
    out = set()
    for key, value in old.items():
        if key in new and literal_structure_changed(value, new[key]):
            out.add(key)
    return out


def literal_structure_changed(before, after):
    """A literal or one of its entries changed type, emptied, or lost arity.

    Unknown computed old values carry no literal contract. Dictionary values
    are matched by key, so adding/removing ordinary keys stays with the
    existing import-time lookup rule rather than widening unrelated entries.
    """
    old, new = _shape(before), _shape(after)
    if old is None:
        return False
    if new is None or old[0] != new[0] or (old[1] and not new[1]):
        return True
    if isinstance(before, (ast.List, ast.Tuple)):
        if isinstance(before, ast.Tuple) and len(before.elts) != len(after.elts):
            return True
        return any(literal_structure_changed(a, b) for a, b in zip(before.elts, after.elts))
    if isinstance(before, ast.Dict):
        kinds = {shape[0] for k in before.keys if (shape := _shape(k)) is not None}
        if kinds and any(shape[0] not in kinds for k in after.keys
                         if (shape := _shape(k)) is not None):
            return True
        previous = {_dump(k): v for k, v in zip(before.keys, before.values) if k is not None}
        return any(_dump(k) in previous and literal_structure_changed(previous[_dump(k)], v)
                   for k, v in zip(after.keys, after.values) if k is not None)
    return False

def changed_test_state(old_tree, new_tree, touched):
    """An edited test/helper can leave imported or module state for later tests.

    Runtime coverage credits the writer, not tests that observe its state.
    Inspect the whole enclosing function: changing a saved original value can
    corrupt a later restoration even when the changed statement is a read.
    Local objects and self/cls attributes keep ordinary coverage selection.
    """
    mutators = {"add", "append", "clear", "discard", "extend", "insert", "pop", "popitem",
                "remove", "reverse", "set", "setdefault", "sort", "update", "clear_cache",
                "clear_column_cache"}
    for tree in (old_tree, new_tree):
        bindings, imports = set(), {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    name = a.asname or a.name.split(".")[0]
                    bindings.add(name); imports[name] = a.name if a.asname else a.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    name = a.asname or a.name
                    bindings.add(name); imports[name] = (node.module or "") + "." + a.name
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bindings.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                bindings.update(assigned_names(node) or ())

        def root(node):
            while isinstance(node, (ast.Attribute, ast.Subscript)):
                node = node.value
            return node.id if isinstance(node, ast.Name) else None

        def imported_ref(node, refs):
            if isinstance(node, ast.Name): return refs.get(node.id, "")
            if isinstance(node, ast.Attribute):
                parent = imported_ref(node.value, refs)
                return parent + "." + node.attr if parent else ""
            return ""

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    or not any(fn.lineno <= line <= fn.end_lineno for line in touched):
                continue
            params = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
            params |= {a.arg for a in (fn.args.vararg, fn.args.kwarg) if a is not None}
            external = bindings - params - {"self", "cls"}
            refs = {name:value for name,value in imports.items() if name not in params}
            nodes = list(ast.walk(fn))
            globals_ = {name for n in nodes if isinstance(n, ast.Global) for name in n.names}
            # Track aliases of shared objects, but not fresh constructor/call results.
            for _ in range(len(nodes)):
                previous = len(external)
                for n in nodes:
                    if isinstance(n, ast.ClassDef) and any(root(b) in external for b in n.bases):
                        # A fresh subclass can still inherit shared mutable tables.
                        external.add(n.name)
                    if isinstance(n, (ast.Assign, ast.AnnAssign)) and root(n.value) in external:
                        external.update(assigned_names(n) or ())
                        ref = imported_ref(n.value, refs)
                        if ref:
                            refs.update({name:ref for name in (assigned_names(n) or ())})
                if len(external) == previous: break
            for n in nodes:
                if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
                    targets = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                    if any((isinstance(t, (ast.Attribute, ast.Subscript)) and root(t) in external)
                           or (isinstance(t, ast.Name) and t.id in globals_) for t in targets):
                        return fn.name
                if isinstance(n, ast.Call):
                    if isinstance(n.func, ast.Attribute) and n.func.attr in mutators \
                            and root(n.func.value) in external:
                        return fn.name
                    if isinstance(n.func, ast.Name) and n.func.id in {"setattr", "delattr"} \
                            and n.args and root(n.args[0]) in external:
                        return fn.name
                if isinstance(n, ast.ClassDef):
                    for base in n.bases:
                        imported = imported_ref(base, refs)
                        if imported == "sqlglot.Dialect" or imported.startswith("sqlglot.dialects."):
                            # _Dialect.__new__ registers even a test-local class globally.
                            return fn.name
    return None


def _is_ref(node, names):
    return (isinstance(node, ast.Name) and node.id in names) or \
        (isinstance(node, ast.Attribute) and node.attr in names)


def _mentions(node, names, skip=()):
    """Does node read any of names: a Name, an attribute, or a string that a
    getattr could use? Subtrees in skip are exempt."""
    stack = [node]
    while stack:
        n = stack.pop()
        if any(n is s for s in skip):
            continue
        if _is_ref(n, names) or (isinstance(n, ast.Constant) and n.value in names):
            return True
        stack.extend(ast.iter_child_nodes(n))
    return False


def _key(node, consts):
    """A comparable spelling of a dict key or lookup argument, or None."""
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name) and node.id in consts:
        return repr(consts[node.id])
    if isinstance(node, (ast.Name, ast.Attribute)):
        return ast.unparse(node)
    return None


def _str_consts(tree):
    """Plain NAME = <constant> assignments anywhere at import level in a
    module, so HINT_START: ... keys resolve to "/*+"."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(node, "value", None), ast.Constant):
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, node.value.value)
    return out


def removed_dict_keys(old_tree, new_tree, old_scopes=None, new_scopes=None):
    """{table name: keys} removed or renamed in a dict display assigned at
    import level (a class attribute or module constant)."""
    def tables(tree, sc):
        out = {}
        for start, end, header_end, node, runtime, cls in (sc or Scopes(tree)).stmts:
            if runtime or not isinstance(node, (ast.Assign, ast.AnnAssign)) \
                    or not isinstance(node.value, ast.Dict):
                continue
            names = assigned_names(node)
            if names and len(names) == 1:
                out[(cls, next(iter(names)))] = node
        return out
    old, new = tables(old_tree, old_scopes), tables(new_tree, new_scopes)
    out = {}
    consts = {}
    for key, node in old.items():
        other = new.get(key)
        if other is not None and ast.dump(node.value) == ast.dump(other.value):
            continue
        if not consts:
            consts = {"": None, **_str_consts(old_tree)}
            new_consts = _str_consts(new_tree)
        before = {_key(k, consts) for k in node.value.keys if k is not None} - {None}
        after = {_key(k, new_consts) for k in other.value.keys if k is not None} - {None} if other is not None else set()
        gone = before - after
        if gone:
            out.setdefault(key[1], set()).update(gone)
    return out


def popped_at_import(sources, dropped, scopes_for):
    """(table, file) of an import-time NAME.pop(key), del NAME[key] or
    NAME[key] read whose key was dropped, or None. A pop with a default
    cannot raise."""
    pats = {n: re.compile(r"\b%s\s*(?:\.pop\(|\[)" % re.escape(n)) for n in dropped}
    for rel, text in sources.items():
        names = [n for n, p in pats.items() if p.search(text)]
        if not names:
            continue
        try:
            tree = ast.parse(text)
            scopes = scopes_for(rel, text)
        except SyntaxError:
            continue
        consts = _str_consts(tree)

        def table(node):
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                return node.attr
            return None

        for node in ast.walk(tree):
            target = key = None
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "pop" and len(node.args) == 1 and not node.keywords:
                target, key = table(node.func.value), node.args[0]
            elif isinstance(node, ast.Subscript) and not isinstance(node.ctx, ast.Store):
                target, key = table(node.value), node.slice
            if target not in names or _key(key, consts) not in dropped[target]:
                continue
            st = scopes.at(node.lineno)
            if st is None or not st[4]:
                return target, rel
    return None


def lookup_at_import(node, line, changed):
    """Does a changed line of this import-level statement sit in a pop, del or
    subscript read that runs while the module loads?"""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    lines = set(changed)
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        hit = False
        if isinstance(n, ast.Subscript) and not isinstance(n.ctx, ast.Store):
            hit = True
        elif isinstance(n, ast.Delete):
            hit = True
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "pop" \
                and len(n.args) == 1 and not n.keywords:
            hit = True
        if hit and any(n.lineno <= l <= n.end_lineno for l in lines):
            return True
        if isinstance(n, ast.AnnAssign):
            # Annotations (t.ClassVar[...]) are subscripts that cannot raise here.
            stack.extend(c for c in (n.target, n.value) if c is not None)
            continue
        stack.extend(ast.iter_child_nodes(n))
    return False


PARSE_CALLS = {"maybe_parse", "parse_one", "parse", "from_str", "build", "to_identifier", "column", "table_",
               "Struct", "strptime", "fromhex", "Decimal", "int", "float", "complex", "format", "compile",
               "match", "fullmatch", "search", "sub", "split", "findall", "literal_eval", "loads"}


def _added_lines(fp):
    out = set()
    for (_, lines), (_, new_start, new_count) in zip(fp.hunks, fp.ranges):
        n = new_start if new_count else new_start + 1
        for l in lines:
            if l[:1] == "+":
                out.add(n)
            if l[:1] in (" ", "+"):
                n += 1
    return out


def _import_time_nodes(tree):
    """Expression nodes evaluated while the module loads: module and class
    bodies, decorators and default arguments, but not function or lambda bodies."""
    stack = list(tree.body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(n.decorator_list)
            stack.extend(n.args.defaults + [d for d in n.args.kw_defaults if d is not None])
            continue
        if isinstance(n, ast.Lambda):
            stack.extend(n.args.defaults)
            continue
        yield n
        stack.extend(ast.iter_child_nodes(n))


def _try_eval(n):
    """True if the call/format can be evaluated from literals and succeeds,
    False if it raises, None if it is not evaluable here."""
    import datetime, decimal, struct
    try:
        if isinstance(n, ast.BinOp):
            left, right = ast.literal_eval(n.left), ast.literal_eval(n.right)
            left % right
            return True
        func = n.func
        args = [ast.literal_eval(a) for a in n.args]
        kwargs = {k.arg: ast.literal_eval(k.value) for k in n.keywords if k.arg}
    except Exception:
        return None
    try:
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Constant) and func.attr == "format":
            func.value.value.format(*args, **kwargs); return True
        name = ast.unparse(func)
        table = {"int": int, "float": float, "complex": complex, "Decimal": decimal.Decimal,
                 "decimal.Decimal": decimal.Decimal, "bytes.fromhex": bytes.fromhex,
                 "struct.Struct": struct.Struct, "datetime.strptime": datetime.datetime.strptime,
                 "datetime.datetime.strptime": datetime.datetime.strptime}
        if name in table:
            table[name](*args, **kwargs); return True
        if name.startswith("re.") and name[3:] in RE_CALLS and args:
            re.compile(args[0], args[1] if len(args) > 1 and isinstance(args[1], int) else 0); return True
    except Exception:
        return False
    return None


def changed_call_at_import(new_tree, fp):
    """A changed constant inside an import-time call that parses or validates
    it (PARSE_CALLS), a % format or a literal index can raise while the module
    loads. Selects importers unless the expression evaluates from literals
    without raising. Factory calls such as rename_func("X") cannot raise on a
    constant and keep their selection: selecting importers for every changed
    constant in any call costs about 30% on the samples."""
    added = _added_lines(fp)
    if not added:
        return False
    for n in _import_time_nodes(new_tree):
        cand = None
        if isinstance(n, ast.Call):
            consts = [c for a in list(n.args) + [k.value for k in n.keywords] for c in ast.walk(a)
                      if isinstance(c, ast.Constant) and c.lineno in added]
            if consts:
                name = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                if name in PARSE_CALLS:
                    cand = n
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant) \
                and isinstance(n.left.value, str) and any(c.lineno in added for c in ast.walk(n) if isinstance(c, ast.Constant)):
            cand = n
        elif isinstance(n, ast.Subscript) and isinstance(n.value, (ast.Constant, ast.List, ast.Tuple, ast.Dict)) \
                and any(getattr(c, "lineno", 0) in added for c in ast.walk(n.slice)):
            cand = n
        if cand is None:
            continue
        ok = _try_sub(cand) if isinstance(cand, ast.Subscript) else _try_eval(cand)
        if ok is not True:
            return True
    return False


def _try_sub(n):
    try:
        ast.literal_eval(n.value)[ast.literal_eval(n.slice)]
        return True
    except Exception:
        return False


RE_CALLS = {"compile", "match", "fullmatch", "search", "findall", "finditer", "sub", "subn", "split"}


def bad_regex_at_import(node, line, changed, new_tree, fp):
    """Does an import-level re.compile("...") (or another re call) on a
    changed line now fail to compile? Compiling a literal pattern runs no
    patch code. A pattern that compiles keeps the ordinary selection."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    if not any(l[:1] == "+" for _, ls in fp.hunks for l in ls):
        return False
    new_lines = set()
    for (_, lines), (_, new_start, new_count) in zip(fp.hunks, fp.ranges):
        n = new_start if new_count else new_start + 1
        for l in lines:
            if l[:1] == "+":
                new_lines.add(n)
            if l[:1] in (" ", "+"):
                n += 1
    for n in ast.walk(new_tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in RE_CALLS
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "re" and n.args
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, (str, bytes))):
            continue
        if not any(n.lineno <= l <= n.end_lineno for l in new_lines):
            continue
        flags = 0
        if len(n.args) > 1 and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, int):
            flags = n.args[1].value
        try:
            re.compile(n.args[0].value, flags)
        except (re.error, OverflowError, ValueError, TypeError, RecursionError):
            return True
    return False


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
    # Build-time-only tokenization: a proof must not add a source-wide token
    # scan to every charged commit. Offsets refer to the pinned source only.
    # Build-time-only: every `Class.name` read in sqlglot (presto.py's
    # `MySQL.TIME_MAPPING`), so qualified_consumers needs no source scan.
    qual = {}
    for rel, text in sources.items():
        if rel.startswith("sqlglot/"):
            for m in QUALIFIED_READ.finditer(text):
                parts, ln = m.group(0).split("."), text.count("\n", 0, m.start()) + 1
                for i in range(1, len(parts)):
                    # every owner.attr prefix: `MySQL.TIME_MAPPING.items`
                    # records TIME_MAPPING under owner `MySQL.`
                    if parts[i - 1][:1].isupper() or parts[i - 1][:1] == "_":
                        qual.setdefault(parts[i], []).append([rel, ln, ".".join(parts[:i]) + "."])
    index["@qualified_reads"] = qual
    index['@pinned_string_audit'] = source_fingerprint(sources) == PINNED_STRING_AUDIT
    index['@generator_string_calls'] = [
        [rel, n.body[0].lineno, n.end_lineno]
        for rel, text in sources.items()
        if rel in {'sqlglot/generator.py', 'sqlglot/transforms.py'}
        for n in ast.walk(ast.parse(text))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in {'sql', 'json_path_part', 'query_modifiers', '_to_sql'}]
    index["@inert_name_ranges"] = {
        rel: inert_name_ranges(sources[rel], sc)
        for rel, sc in parsed.items() if rel.startswith("sqlglot/")}
    with gzip.open(out_path, "wt") as f:
        json.dump(index, f, separators=(",", ":"))
    log(f"index: {len(cands)} names; test imports and shared setup scopes")


IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
KEYWORDS = set(__import__("keyword").kwlist)


RISKY_WORDS = {"import", "while", "for", "raise", "assert", "del", "with", "try",
               "yield", "await", "return", "global", "nonlocal"}
RISKY_OPS = ("/", "%", "**", "<<", ">>")


def could_raise(fp, old_text=None, new_text=None):
    """Conservatively flag new import effects, without executing patch code.
    With both file versions, comments and string contents are read as data:
    a '/' in a comment or 'return' in a help string is not code. Words in a
    changed string still count as new names (a renamed key can fail a
    lookup at import). The token reading can only clear a lexical flag."""
    if not _lexical_could_raise(fp):
        return False
    if old_text is not None and new_text is not None:
        got = _token_could_raise(fp, old_text, new_text)
        if got is not None:
            return got
    return True


def _lexical_could_raise(fp):
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
    if after & RISKY_WORDS:
        return True
    if any(op in added_text for op in RISKY_OPS):
        return True
    after -= KEYWORDS
    return bool(after - before)


def _changed_tokens(text, lines):
    """Tokens of text that touch any of the given 1-based lines, or None if
    the text does not tokenize."""
    import io
    import tokenize

    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if any(tok.start[0] <= l <= tok.end[0] for l in lines):
                out.append(tok)
    except (tokenize.TokenError, SyntaxError, ValueError):
        return None
    return out


def _token_could_raise(fp, old_text, new_text):
    import tokenize

    removed, added = set(), set()
    for (start, lines), (old_count, new_start, _) in zip(fp.hunks, fp.ranges):
        o = start if old_count else start + 1
        n = new_start
        for l in lines:
            if l[:1] == " ":
                o += 1
                n += 1
            elif l[:1] == "-":
                removed.add(o)
                o += 1
            elif l[:1] == "+":
                added.add(n)
                n += 1
    old_toks = _changed_tokens(old_text, removed) if removed else []
    new_toks = _changed_tokens(new_text, added) if added else []
    if old_toks is None or new_toks is None:
        return None
    strings = {tokenize.STRING} | {getattr(tokenize, k) for k in ("FSTRING_MIDDLE", "TSTRING_MIDDLE")
                                   if hasattr(tokenize, k)}

    def words(toks):
        code, data = set(), set()
        for t in toks:
            if t.type == tokenize.NAME:
                code.add(t.string)
            elif t.type in strings:
                data |= set(IDENT.findall(t.string))
            elif t.type == tokenize.OP and any(op in t.string for op in RISKY_OPS):
                code.add("<op>")
            elif t.type == tokenize.ERRORTOKEN:
                code.add("<op>")  # unknown: treat as risky
        return code, data

    before_code, before_data = words(old_toks)
    after_code, after_data = words(new_toks)
    if after_code & (RISKY_WORDS | {"<op>"}):
        return True
    # A string's words count even when they spell a keyword ("in", "or").
    after = (after_code - KEYWORDS - {"<op>"}) | after_data
    return bool(after - before_code - before_data)


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


def read_patch(patch_path):
    # O_NONBLOCK: opening a FIFO for reading waits for a writer forever, and
    # this runs in the parent (prepare_batch), which has no time limit.
    import stat
    with os.fdopen(os.open(patch_path, os.O_RDONLY | os.O_NONBLOCK), "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError("patch is not a regular file")
        raw = f.read(MAX_PATCH_BYTES + 1)
    if len(raw) > MAX_PATCH_BYTES:
        raise ValueError("patch exceeds size limit")
    text = raw.decode("utf-8")
    files = parse_patch(text)
    if not files and text.strip():
        raise RuntimeError("no files in patch")
    return files


def _vm_size():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


# Below this many commits, loading the comparison profile in every child that
# needs it (about 8% of proxy commits) costs less CPU than loading it once.
CMP_PRELOAD_COMMITS = 16
# Hunk lines prepare_batch may keep for the children (about 60 bytes each in
# memory: 2,000,000 is about 120 MB). 2,000 proxy commits hold 24,000.
MAX_CACHED_PATCH_LINES = 2_000_000


def prepare_batch(sel, paths, deadline):
    """Work done once in the parent before forking: parse each patch (which
    also compiles its regular expressions once for every child) and load the
    comparison profile. Returns an estimated analysis cost per patch path (bytes of Python
    to parse), so the cheapest commits can go first. A patch that fails here
    is left for its own child, which fails it the same way."""
    sel.vm_base = _vm_size()
    cost, size = {}, {}
    # The cache lives in the parent for the whole batch, and the OOM killer
    # takes the parent once it is the only large process: about 700 patches
    # of 49,000 short lines (105 MB on disk) filled 2 GB. Past this many
    # cached hunk lines (about 60 bytes each), children re-read their patch.
    lines_left = MAX_CACHED_PATCH_LINES
    for path in paths:
        cost[path] = 1 << 40
        if time.monotonic() >= deadline:
            continue
        try:
            files = read_patch(path)
        except Exception:
            continue
        c, n = 1, 0
        for fp in files:
            if fp.old is not None and fp.old.endswith(".py"):
                if fp.old not in size:
                    try:
                        size[fp.old] = os.path.getsize(os.path.join(SRC, fp.old))
                    except OSError:
                        size[fp.old] = 0
                c += size[fp.old]
            for _, ls in fp.hunks:
                n += len(ls)
                c += sum(len(l) for l in ls)
        cost[path] = c
        if n <= lines_left:
            lines_left -= n
            sel.patches[path] = files
        del files
    if len(paths) >= CMP_PRELOAD_COMMITS:
        sel.cmp_profile()
    return cost


def select_patch(patch_path, sel, tests, deadline):
    """Analyze one commit. Any exception is handled by the parent process."""
    if time.monotonic() >= deadline:
        raise RuntimeError("batch analysis deadline reached")
    files = getattr(sel, "patches", {}).get(patch_path)
    if files is None:
        files = read_patch(patch_path)
    sel._single_file_patch = len(files) == 1
    chosen, why = set(), []
    sel.pending_shared = set()
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
        # Keep the same headroom over what the parent's caches added.
        base, now = getattr(sel, "vm_base", None), _vm_size()
        if base is not None and now is not None and now > base:
            limit += now - base
        if soft != resource.RLIM_INFINITY:
            limit = min(limit, soft)
        resource.setrlimit(resource.RLIMIT_AS, (limit, hard))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # If two children together exhaust the container's memory, the kernel
        # must kill a child, never the parent that writes the output.
        try:
            with open("/proc/self/oom_score_adj", "w") as f:
                f.write("1000")
        except OSError:
            pass
        # SIGXCPU ends the child after MAX_COMMIT_SECONDS of its own CPU time
        # (a forked child starts from zero); SIGKILL one second later.
        cpu_soft, cpu_hard = resource.getrlimit(resource.RLIMIT_CPU)
        cpu = max(1, int(MAX_COMMIT_SECONDS))
        if cpu_hard != resource.RLIM_INFINITY:
            cpu = min(cpu, cpu_hard)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1 if cpu_hard == resource.RLIM_INFINITY else cpu_hard))
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


def cpu_slots():
    """How many analysis children to run at once: the CPUs this container may
    use (its cgroup quota, else its affinity mask), at most 4. Each child is
    still one process at a time on one CPU, so the CPU charge is unchanged."""
    override = os.environ.get("BLAST_WORKERS")
    if override:
        try:
            return max(1, min(4, int(override)))
        except ValueError:
            pass
    try:
        n = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        n = os.cpu_count() or 1
    try:
        with open("/sys/fs/cgroup/cpu.max") as f:
            quota, period = f.read().split()[:2]
        if quota != "max":
            n = min(n, max(1, int(quota) // int(period)))
    except (OSError, ValueError):
        pass
    return max(1, min(4, n))


def _reap(process):
    if process.pid is not None:
        process.join(0.01)
        if process.is_alive():
            process.terminate()
            process.join(0.1)
        if process.is_alive():
            process.kill()
            process.join()
        process.close()


def analyze_batch(context, patch_paths, sel, tests, deadline, emit, slots=1):
    """Analyze commits in the given order with up to `slots` children at once
    and call emit(patch_path, chosen, why) once per commit, in completion
    order. Each child has the per-commit CPU limit and its own wall backstop;
    once the batch deadline passes, the remaining commits select everything."""
    from multiprocessing.connection import wait

    pending = list(reversed(patch_paths))
    running = {}  # receiver -> (process, patch_path, wall limit)
    while pending or running:
        while pending and len(running) < slots:
            path = pending.pop()
            now = time.monotonic()
            budget = min(MAX_COMMIT_WALL_SECONDS, deadline - now)
            if budget <= 0:
                emit(path, set(tests), ["batch analysis deadline reached: everything"])
                continue
            receiver = sender = process = None
            try:
                # Inside the try: os.pipe fails with EMFILE once failed forks
                # have leaked descriptors (CPython's Popen_fork leaks 4 per
                # failed fork), and that must cost one commit, not the run.
                receiver, sender = context.Pipe(duplex=False)
                process = context.Process(target=_analyze_child,
                                          args=(sender, path, sel, tests, deadline))
                process.start()
            except Exception as e:
                if receiver is not None:
                    receiver.close()
                if process is not None:
                    _reap(process)
                emit(path, set(tests), [f"analysis process failed {type(e).__name__}: everything"])
                continue
            finally:
                if sender is not None:
                    sender.close()
            running[receiver] = (process, path, now + budget)
        if not running:
            continue
        timeout = max(0.0, min(limit for _, _, limit in running.values()) - time.monotonic())
        ready = wait(list(running), timeout)
        now = time.monotonic()
        for receiver in list(running):
            process, path, limit = running[receiver]
            if receiver in ready:
                try:
                    result = receiver.recv()
                except EOFError:
                    result = (set(tests), ["commit analysis stopped by a resource limit: everything"])
                except Exception as e:
                    result = (set(tests), [f"analysis process failed {type(e).__name__}: everything"])
            elif now >= limit:
                result = (set(tests), ["commit analysis timed out: everything"])
            else:
                continue
            del running[receiver]
            receiver.close()
            _reap(process)
            emit(path, *result)


def analyze_patch(context, patch_path, sel, tests, deadline):
    """A broken/slow commit cannot reject the rest of the batch."""
    budget = min(MAX_COMMIT_WALL_SECONDS, deadline - time.monotonic())
    if budget <= 0:
        return set(tests), ["batch analysis deadline reached: everything"]
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_analyze_child,
                              args=(sender, patch_path, sel, tests, deadline))
    try:
        process.start()
        sender.close()
        if receiver.poll(budget):
            try:
                return receiver.recv()
            except EOFError:
                # Killed without a reply: CPU limit, memory, or a signal.
                return set(tests), ["commit analysis stopped by a resource limit: everything"]
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
    everything = set(tests)
    paths = [os.path.join(cdir, name) for name in sorted(os.listdir(cdir)) if name.endswith(".patch")]

    emitted = set()

    def emit(path, chosen, why):
        if path in emitted:  # one line per commit, whatever happens
            return
        cid = os.path.basename(path)[: -len(".patch")]
        workers = fallback_workers if chosen == everything else pack(chosen, tests)
        log(cid, len(chosen), "tests;", "; ".join(why))
        sys.stdout.write(json.dumps({"commit": cid, "workers": workers}) + "\n")
        emitted.add(path)

    try:
        if sel is None:
            for path in paths:
                emit(path, everything, ["map unavailable: everything"])
        else:
            cost = {}
            try:
                cost = prepare_batch(sel, paths, deadline)
            except Exception as e:  # caches are an optimisation only
                log("batch preparation failed:", repr(e))
                sel.patches = {}
            # Cheapest first: if the deadline comes, the fewest commits fall back
            # to every test. Output order is free.
            paths.sort(key=lambda p: (cost.get(p, 1 << 40), p))
            # Children never free the parent's objects. Without this, a child's
            # first collection walks every inherited object (the maps, the cached
            # trees), copying their pages and spending CPU on each commit.
            import gc
            gc.collect()
            gc.freeze()
            analyze_batch(context, paths, sel, tests, deadline, emit, cpu_slots())
    except Exception as e:  # a missing line rejects the run: fall back for the rest
        log("batch failed:", repr(e))
        for path in paths:
            emit(path, everything, ["batch failed: everything"])
    sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--index":
        build_index(sys.argv[2])
    else:
        main()
