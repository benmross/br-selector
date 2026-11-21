"""In-container verification of tiny selections.

A commit whose static selection is cheap still pays the 2 s worker charge.
When every selected test passes against the patched code, the commit can
emit no workers at all. This module decides that, and only that: any doubt
keeps the full static selection.

For each commit it builds an overlay of the pristine checkout in /tmp:
symlinks to every pristine file and directory, with real directories only
along the paths the patch touches and the patched files written into them.
A forked child puts the overlay first on sys.path, makes it the working
directory and imports sqlglot and the test modules fresh, so import-time
state (class tables, registries, caches), files read from disk (fixtures,
source files) and spawned process pools all see the patched code. The
parent never imports sqlglot.

The child runs the tests with unittest and reports one verdict: "P" when
every test passed cleanly. Anything else (a failure, an error, a failing
subtest, a skip, an expected failure, a class or module fixture error, an
import error, a missing test, a crash, a timeout or the CPU limit) keeps
the static selection.
"""
import os
import resource
import select
import shutil
import sys
import tempfile
import time

TEST_ID_PARTS = 3  # tests/x.py::Class::method; anything else is not run


def _expand_dirs(paths):
    dirs = {""}
    for p in paths:
        parts = p.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]))
    return dirs


def build_overlay(src, files, root=None):
    """files: {relative path: new text, or None when the patch deletes it}.
    Returns the overlay directory."""
    root = root or tempfile.mkdtemp(prefix="br-ov-")
    expand = _expand_dirs(files)
    stems = {}
    for p in files:
        d, _, base = p.rpartition("/")
        if base.endswith(".py"):
            stems.setdefault(d, set()).add(base[:-3])

    def mirror(d):
        here = os.path.join(src, d) if d else src
        dst = os.path.join(root, d) if d else root
        os.makedirs(dst, exist_ok=True)
        try:
            names = os.listdir(here)
        except FileNotFoundError:
            names = []  # a directory the patch creates
        for name in names:
            rel = f"{d}/{name}" if d else name
            if rel in files:
                continue
            if rel in expand:
                mirror(rel)
            elif name == "__pycache__" and d in stems:
                # keep bytecode of the untouched modules only
                os.makedirs(os.path.join(dst, name), exist_ok=True)
                for pyc in os.listdir(os.path.join(here, name)):
                    if pyc.split(".", 1)[0] not in stems[d]:
                        os.symlink(os.path.join(here, name, pyc), os.path.join(dst, name, pyc))
            else:
                os.symlink(os.path.join(here, name), os.path.join(dst, rel.rsplit("/", 1)[-1]))

    mirror("")
    for p, text in files.items():
        if text is None:
            continue
        path = os.path.join(root, p)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    return root


class InlineExecutor:
    """Stands in for the test modules' ProcessPoolExecutor (t4). A spawn pool
    would start one interpreter per host core, each importing sqlglot, pandas
    and duckdb: seconds of CPU for one fixture test. Workers would import the
    same overlay, so running the calls here differs only in sharing process
    state. Arguments and results still cross a pickle round trip, as they
    would between processes (sqlglot pickles expressions through serde)."""

    def __init__(self, max_workers=None, mp_context=None, initializer=None, initargs=(), **kw):
        import pickle
        self._pickle = pickle
        if initializer is not None:
            initializer(*self._trip(initargs))

    def _trip(self, x):
        return self._pickle.loads(self._pickle.dumps(x))

    def submit(self, fn, *args, **kwargs):
        from concurrent.futures import Future
        f = Future()
        try:
            fn, args, kwargs = self._trip((fn, args, kwargs))
            f.set_result(self._trip(fn(*args, **kwargs)))
        except BaseException as e:  # noqa: B036
            f.set_exception(e)
        return f

    def map(self, fn, *its, timeout=None, chunksize=1):
        return iter([self.submit(fn, *a).result() for a in zip(*its)])

    def shutdown(self, wait=True, *, cancel_futures=False):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.shutdown()
        return False


# Standard modules (and mypy_extensions) that sqlglot and its test modules
# import, from sys.modules after importing sqlglot and several test modules
# in the image.
PRELOAD = (
    "argparse", "ast", "asyncio", "base64", "bisect", "concurrent.futures", "contextlib", "copy",
    "dataclasses", "datetime", "decimal", "difflib", "email", "enum", "fnmatch", "fractions",
    "functools", "glob", "heapq", "importlib.metadata", "importlib.resources", "importlib.util",
    "inspect", "itertools", "json", "keyword", "locale", "logging", "math", "mypy_extensions",
    "numbers", "operator", "pathlib", "pickle", "pkgutil", "pprint", "random", "re", "shutil",
    "string", "struct", "subprocess", "tempfile", "textwrap", "threading", "tokenize", "traceback",
    "typing", "unittest", "unittest.mock", "warnings", "weakref", "zipfile",
)

# Third-party modules some test files import at module level. Importing them
# once in the parent, before any fork, saves each child about 0.7 s of CPU.
# They never import sqlglot, so the children still load all of sqlglot fresh.
SHARED_MODULES = ("numpy", "pandas", "pandas.testing", "duckdb")


def _child(root, src, test_ids, wfd, cpu_s):
    """Runs in the forked child; never returns."""
    out = os.fdopen(wfd, "w", buffering=1)
    try:
        os.setpgid(0, 0)  # the parent kills pool workers with the child
    except OSError:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(cpu_s + 0.999)), resource.RLIM_INFINITY))
    except (ValueError, OSError):
        pass
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    debug = os.environ.get("BR_V_DEBUG")
    if not debug:
        os.dup2(devnull, 2)
    verdict = "F"
    try:
        sys.dont_write_bytecode = True
        os.environ["SKIP_INTEGRATION"] = "0"  # as the labels were made
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        src_abs = os.path.abspath(src)
        sys.path[:] = [root] + [p for p in sys.path if p and os.path.abspath(p) != src_abs
                                and os.path.abspath(p) != os.path.dirname(os.path.abspath(__file__))]
        os.chdir(root)
        for name in list(sys.modules):
            if name == "sqlglot" or name.startswith(("sqlglot.", "tests")):
                del sys.modules[name]
        import importlib
        import unittest
        importlib.invalidate_caches()

        import concurrent.futures
        concurrent.futures.ProcessPoolExecutor = InlineExecutor
        suite = unittest.TestSuite()
        mine = set()
        for module, cls, meth in test_ids:
            mod = importlib.import_module(module)
            for m in list(sys.modules.values()):
                if getattr(m, "__name__", "").startswith("tests") and hasattr(m, "ProcessPoolExecutor"):
                    m.ProcessPoolExecutor = InlineExecutor
            klass = getattr(mod, cls)
            if not (isinstance(klass, type) and issubclass(klass, unittest.TestCase)):
                raise TypeError(f"{module}.{cls} is not a TestCase")
            t = klass(meth)  # ValueError when the method is gone
            mine.add(id(t))
            suite.addTest(t)

        class Result(unittest.TestResult):
            bad = False
            passed = 0

            def _fail(self):
                self.bad = True
                self.stop()

            def startTest(self, test):
                super().startTest(test)
                self._ok = False

            def addSubTest(self, test, subtest, err):
                super().addSubTest(test, subtest, err)
                if err is not None:
                    self._fail()

            def addSuccess(self, test):
                super().addSuccess(test)
                self._ok = True

            def addError(self, test, err):
                super().addError(test, err)
                if debug:
                    print("verify error:", test, self.errors[-1][1][-1500:], file=sys.stderr)
                self._fail()

            def addFailure(self, test, err):
                super().addFailure(test, err)
                if debug:
                    print("verify failure:", test, self.failures[-1][1][-1500:], file=sys.stderr)
                self._fail()

            def addSkip(self, test, reason):
                super().addSkip(test, reason)
                self._fail()

            def addExpectedFailure(self, test, err):
                super().addExpectedFailure(test, err)
                self._fail()

            def addUnexpectedSuccess(self, test):
                super().addUnexpectedSuccess(test)
                self._fail()

            def stopTest(self, test):
                super().stopTest(test)
                if id(test) in mine and self._ok and not self.bad:
                    self.passed += 1
                else:
                    self._fail()

        r = Result()
        suite.run(r)
        if not r.bad and r.passed == len(test_ids) and r.wasSuccessful() and r.testsRun == len(test_ids):
            verdict = "P"
    except BaseException as e:  # noqa: B036
        if debug:
            import traceback
            print("verify child:", "".join(traceback.format_exception(e))[-1500:], file=sys.stderr)
        verdict = "F"
    try:
        out.write(verdict + "\n")
        out.flush()
    finally:
        os._exit(0)


_TICK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def _cpu_of(pid):
    """User + system CPU seconds of a live process (its own threads)."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            fields = f.read().rsplit(b")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / _TICK
    except (OSError, IndexError, ValueError):
        return 0.0


class Verifier:
    def __init__(self, src, tests):
        self.src = os.path.abspath(src)
        self.tests = tests  # number -> (id, file, ms)
        self.cpu = 0.0
        self.last_cpu = 0.0
        self.shared = False
        self.preload()

    def preload(self):
        """Import, once in the parent, the standard modules every child would
        import with sqlglot and its tests (about 0.1 s of CPU per child).
        None of them imports sqlglot. random and tempfile reseed after fork."""
        import importlib
        for m in PRELOAD:
            try:
                importlib.import_module(m)
            except Exception:
                pass

    def share_modules(self, test_files):
        """Import SHARED_MODULES in the parent when a test file to be run
        imports any of them."""
        if self.shared:
            return
        for tf in test_files:
            try:
                with open(os.path.join(self.src, tf), encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                continue
            if any(f"import {m}" in text or f"from {m}" in text for m in ("pandas", "duckdb", "numpy")):
                break
        else:
            return
        import importlib
        t0 = time.process_time()
        for m in SHARED_MODULES:
            try:
                importlib.import_module(m)
            except Exception:
                pass
        self.shared = True
        self.cpu_shared = time.process_time() - t0

    def test_ids(self, nums):
        """[(module, class, method)] in recorded-time order, or None when a
        test cannot be run this way."""
        ids = []
        for n in sorted(nums, key=lambda n: (self.tests[n][2], self.tests[n][0])):
            parts = self.tests[n][0].split("::")
            if len(parts) != TEST_ID_PARTS or not parts[0].endswith(".py") or "[" in parts[2]:
                return None
            ids.append((parts[0][:-3].replace("/", "."), parts[1], parts[2]))
        return ids

    def run(self, files, nums, wall_s, cpu_s):
        """True only when every test in nums passed against the patched tree."""
        ids = self.test_ids(nums)
        if ids is None:
            return False, "unrunnable test id"
        root = build_overlay(self.src, files)
        r, w = os.pipe()
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(r)
                _child(root, self.src, ids, w, cpu_s)
            finally:
                os._exit(0)
        os.close(w)
        verdict, buf, why = None, b"", "timeout"
        deadline = time.monotonic() + wall_s
        try:
            while verdict is None:
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                ready, _, _ = select.select([r], [], [], min(left, 0.05))
                if not ready:
                    # the CPU cap holds however loaded the machine is
                    if _cpu_of(pid) > cpu_s:
                        why = "cpu limit"
                        break
                    continue
                chunk = os.read(r, 4096)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    verdict = buf.split(b"\n", 1)[0].decode()
        finally:
            os.close(r)
            for kill in (lambda: os.killpg(pid, 9), lambda: os.kill(pid, 9)):
                try:
                    kill()
                except OSError:
                    pass
            _, status, ru = os.wait4(pid, 0)
            self.last_cpu = ru.ru_utime + ru.ru_stime
            self.cpu += self.last_cpu
            shutil.rmtree(root, ignore_errors=True)
        if verdict == "P":
            return True, "passed"
        return False, why if verdict is None else "failed"
