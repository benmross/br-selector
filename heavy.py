"""Drop TestExecutor's TPC executor tests when the patch provably cannot change them.

test_execute_tpcds (21.5 s) and test_execute_tpch (3.9 s) run every TPC query
twice: DuckDB on sqlglot's DuckDB transpilation (the expected frame), and
sqlglot's Python executor on sqlglot's plan (the actual frame). For one query
the work splits into

  cheap:     parse_one in the test process, the pickle trip to the pool
             worker, find_tables, execute()'s optimize, its eager
             expression.sql(pretty=True) and Plan, and transpile(write="duckdb")
  expensive: DuckDB running that SQL over fixtures, and
             PythonExecutor(tables).execute(plan) plus the DataFrame build.

The expensive phase is a function of its inputs: the plan, the DuckDB SQL, the
table names, the fixture files, the code it runs, and module state it reads.
tools/heavy_cov.py records, on the pristine source in fresh processes, every
sqlglot line the expensive phase runs (once with the plan unpickled first, so
every cache it uses is built inside the phase, and once in process after the
cheap phase) plus the Table construction in setUpClass. heavy_lines.json.gz
holds those lines.

A test is dropped from a commit's selection only when
  1. every changed file is an existing sqlglot/*.py file other than
     sqlglot/executor/__init__.py (execute() itself), and no changed or
     neighbouring line is in the recorded lines, and
  2. in the patched overlay, two fresh processes (the "parent" parses,
     pickles and transpiles; the "worker" unpickles, optimizes and plans)
     give, for every executed query, the same deep fingerprint of plan,
     optimized expression, table names, schema table args and DuckDB SQL as
     the pristine source, and the same fingerprint of every sqlglot module's
     state (class tables, registries, caches, function defaults) at the end.
Any difference, error, crash, timeout or CPU overrun keeps the test.
"""
import hashlib
import json
import os
import pickle
import sys
import types

HEAVY = {
    # test number -> (name, tpch?)
    1106: ("tpcds", False),
    1107: ("tpch", True),
}
FORCED = ("sqlglot/executor/__init__.py",)


# ---------------------------------------------------------------- fingerprints

class Doubt(Exception):
    pass


def _norm(s, roots):
    for r in roots:
        if r:
            s = s.replace(r, "<ROOT>")
    return s


class Deep:
    """Structural digest of plans and expressions: every attribute, except the
    upward links (Expr.parent, Step.dependents) and Expr._hash (derived)."""

    SKIP = {"parent", "_hash", "dependents"}

    def __init__(self, roots):
        self.roots = roots
        self.memo = {}
        self.stack = set()

    _slots = {}

    def attrs(self, o):
        t = type(o)
        names = self._slots.get(t)
        if names is None:
            names = []
            for k in t.__mro__:
                sl = getattr(k, "__slots__", ()) or ()
                for s in ((sl,) if isinstance(sl, str) else sl):
                    if s not in names and s not in self.SKIP and not s.startswith("__"):
                        names.append(s)
            self._slots[t] = names = tuple(names)
        out = [(n, getattr(o, n, "<unset>")) for n in names]
        d = getattr(o, "__dict__", None)
        if d:
            out.extend((k, v) for k, v in d.items() if k not in names and k not in self.SKIP and not k.startswith("__"))
        return out

    def __call__(self, o):
        t = type(o)
        if o is None or t in (bool, int, float, complex, bytes):
            return t.__name__ + ":" + repr(o)
        if t is str:
            return "s:" + _norm(o, self.roots)
        key = id(o)
        if key in self.memo:
            return self.memo[key][1]
        if key in self.stack:
            raise Doubt("cycle")
        self.stack.add(key)
        try:
            if t in (list, tuple):
                body = t.__name__ + "[" + ",".join(self(x) for x in o) + "]"
            elif t in (set, frozenset):
                body = "set[" + ",".join(sorted(self(x) for x in o)) + "]"
            elif t is dict:
                body = "dict{" + ",".join(self(k) + "=" + self(v) for k, v in o.items()) + "}"
            elif isinstance(o, type):
                body = "cls:" + o.__module__ + "." + o.__qualname__
            elif isinstance(o, (types.FunctionType, types.BuiltinFunctionType, types.MethodType)):
                body = "fn:" + getattr(o, "__module__", "?") + "." + getattr(o, "__qualname__", "?")
            elif hasattr(o, "__dict__") or getattr(t, "__slots__", None):
                body = "obj:" + t.__module__ + "." + t.__qualname__ + "(" + ",".join(
                    n + "=" + self(v) for n, v in self.attrs(o)) + ")"
            else:
                body = "rep:" + t.__qualname__ + ":" + _norm(repr(o), self.roots)
        finally:
            self.stack.discard(key)
        h = hashlib.sha1(body.encode("utf-8", "surrogatepass")).hexdigest()
        self.memo[key] = (o, h)  # keep o alive so its id is not reused
        return h


_STATE_DUMP = {} if os.environ.get("BR_HEAVY_STATE_DUMP") else None


class State:
    """Digest of every loaded sqlglot module's state: module and class
    attributes, containers, enum members, function defaults and decorator
    wrappers. Function bodies are identified by name only (their lines are
    the recorded-lines rule's job); everything import-time code or a cache
    leaves behind is compared by value."""

    def __init__(self, roots, deep):
        self.roots = roots
        self.deep = deep
        self.stack = set()

    def fn(self, f):
        code = getattr(f, "__code__", None)
        extra = ""
        if code is not None:
            extra = "|d=" + self.v(f.__defaults__, 0) + "|k=" + self.v(f.__kwdefaults__, 0)
            if f.__closure__:
                cells = []
                for c in f.__closure__:
                    try:
                        cells.append(self.v(c.cell_contents, 1))
                    except ValueError:
                        cells.append("empty")
                extra += "|c=" + ",".join(cells)
        w = getattr(f, "__wrapped__", None)
        if w is not None and w is not f:
            extra += "|w=" + self.fn(w)
        return "fn:" + str(getattr(f, "__module__", "?")) + "." + str(getattr(f, "__qualname__", "?")) + extra

    def v(self, o, depth):
        t = type(o)
        if o is None or t in (bool, int, float, complex, bytes):
            return repr(o)
        if t is str:
            return "s:" + _norm(o, self.roots)
        if depth > 8:
            return "deep:" + t.__qualname__
        key = id(o)
        if key in self.stack:
            return "cycle"
        self.stack.add(key)
        try:
            if t in (list, tuple):
                parts = [self.v(x, depth + 1) for x in o]
                if o and all(isinstance(x, type) for x in o):
                    # class tuples for isinstance, built from sets in id()
                    # order (canonicalize._CANONICALIZE_TYPES): order varies
                    parts.sort()
                return t.__name__ + "[" + ",".join(parts) + "]"
            if t in (set, frozenset):
                return "set[" + ",".join(sorted(self.v(x, depth + 1) for x in o)) + "]"
            if isinstance(o, dict):
                # sorted: several import-time tables are filled in id() order
                # (iteration over sets of classes), which changes from run to run
                return t.__qualname__ + "{" + ",".join(sorted(
                    self.v(k, depth + 1) + "=" + self.v(x, depth + 1) for k, x in o.items())) + "}"
            if isinstance(o, types.ModuleType):
                return "mod:" + o.__name__
            if isinstance(o, type):
                return "cls:" + o.__module__ + "." + o.__qualname__
            if isinstance(o, (staticmethod, classmethod)):
                return t.__name__ + "(" + self.fn(o.__func__) + ")"
            if isinstance(o, property):
                return "prop(" + ",".join(self.fn(f) if f else "-" for f in (o.fget, o.fset, o.fdel)) + ")"
            if callable(o) and hasattr(o, "__qualname__") and not hasattr(o, "args"):
                return self.fn(o)
            mod = getattr(t, "__module__", "") or ""
            if hasattr(o, "name") and hasattr(o, "value") and hasattr(t, "__members__"):
                return "enum:" + t.__qualname__ + "." + str(o.name)
            if mod.startswith("sqlglot"):
                if hasattr(o, "args") and hasattr(o, "arg_key"):
                    return "expr:" + self.deep(o)
                d = getattr(o, "__dict__", None)
                if d is not None:
                    return "obj:" + t.__qualname__ + "{" + ",".join(
                        k + "=" + self.v(x, depth + 1) for k, x in sorted(d.items())) + "}"
            if mod in ("re",) or t.__name__ == "Pattern":
                return "re:" + repr(getattr(o, "pattern", "")) + str(getattr(o, "flags", ""))
            return "other:" + mod + "." + t.__qualname__
        finally:
            self.stack.discard(key)

    def cls(self, c):
        parts = ["bases=" + ",".join(b.__module__ + "." + b.__qualname__ for b in c.__bases__),
                 "meta=" + type(c).__module__ + "." + type(c).__qualname__]
        for k, x in sorted(vars(c).items()):
            if k in ("__dict__", "__weakref__", "__doc__", "__module__", "__qualname__"):
                continue
            parts.append(k + "=" + self.v(x, 1))
        return "class{" + ";".join(parts) + "}"

    def modules(self):
        h = hashlib.sha1()
        for name in sorted(n for n in sys.modules if n == "sqlglot" or n.startswith("sqlglot.")):
            m = sys.modules[name]
            if m is None:
                h.update(f"{name}:none\n".encode())
                continue
            h.update(f"module {name}\n".encode())
            for k, x in sorted(vars(m).items()):
                if k in ("__builtins__", "__cached__", "__loader__", "__spec__", "__file__", "__path__", "__doc__"):
                    continue
                if isinstance(x, type) and x.__module__ == name:
                    s = self.cls(x)
                else:
                    s = self.v(x, 0)
                h.update(f"{k}={s}\n".encode("utf-8", "surrogatepass"))
                if _STATE_DUMP is not None:
                    _STATE_DUMP[f"{name}.{k}"] = s
        if _STATE_DUMP is not None and os.environ.get("BR_HEAVY_STATE_DUMP"):
            with open(os.environ["BR_HEAVY_STATE_DUMP"] + f".{os.getpid()}", "w") as f:
                json.dump(_STATE_DUMP, f)
        return h.hexdigest()


# ------------------------------------------------------------- cheap phase

def _fixture(tpch):
    return "optimizer/tpc-h/tpc-h.sql" if tpch else "optimizer/tpc-ds/tpc-ds.sql"


def _test_module_imports():
    """The sqlglot and test-helper imports of tests/test_executor.py, in its
    order (both the test process and the spawned workers import that module).
    numpy, pandas and duckdb are left out: they never import sqlglot."""
    import sqlglot  # noqa: F401
    from sqlglot import exp, find_tables, parse_one, transpile  # noqa: F401
    from sqlglot.errors import ExecuteError  # noqa: F401
    from sqlglot.executor import env, execute  # noqa: F401
    from sqlglot.executor.python import Python, PythonExecutor  # noqa: F401
    from sqlglot.executor.table import Table, ensure_tables  # noqa: F401
    from sqlglot.optimizer import optimize  # noqa: F401
    from sqlglot.planner import Plan  # noqa: F401
    import tests.helpers  # noqa: F401


def parent_side(tpch, roots):
    """What the test process does with sqlglot: parse_one every query (the
    pool submit pickles it) and transpile each executed query for DuckDB."""
    _test_module_imports()
    from sqlglot import parse_one, transpile
    from tests.helpers import load_sql_fixture_pairs
    sqls = list(load_sql_fixture_pairs(_fixture(tpch)))
    exprs = [parse_one(sql) for _, sql, _ in sqls]
    blobs = [pickle.dumps(e) for e in exprs]
    deep = Deep(roots)
    duck = []
    for (meta, sql, _), e in zip(sqls, exprs):
        if not meta.get("execute"):
            duck.append(None)
            continue
        duck.append(transpile(sql, write="duckdb")[0])
    meta = [bool(m.get("execute")) for m, _, _ in sqls]
    return blobs, duck, meta, State(roots, deep).modules()


def worker_side(tpch, blobs, meta, roots, expect=None):
    """What a pool worker does before PythonExecutor runs: mp_execute's
    find_tables and execute()'s schema, optimize, eager sql() and Plan."""
    _test_module_imports()
    from sqlglot import find_tables
    from sqlglot.optimizer import optimize
    from sqlglot.planner import Plan
    from sqlglot.schema import ensure_schema
    from tests.helpers import TPCH_SCHEMA, TPCDS_SCHEMA
    schema_src = pickle.loads(pickle.dumps(TPCH_SCHEMA if tpch else TPCDS_SCHEMA))
    deep = Deep(roots)
    out = []
    for blob, run in zip(blobs, meta):
        e = pickle.loads(blob)  # the pool unpickles every submitted expression
        if not run:
            out.append(None)
            continue
        names = [t.name for t in find_tables(e)]
        schema = ensure_schema(schema_src, dialect=None)
        expression = optimize(e, schema, leave_tables_isolated=True, dialect=None)
        expression.sql(pretty=True)
        plan = Plan(expression)
        out.append(deep([names, schema.supported_table_args, plan, expression]))
        if expect is not None and (len(expect) != len(blobs) or out[-1][:16] != expect[len(out) - 1]):
            raise Doubt(f"plan of query {len(out)} differs")
    return out, State(roots, deep).modules()


def _enter(root, src):
    sys.dont_write_bytecode = True
    os.environ["SKIP_INTEGRATION"] = "0"
    src_abs = os.path.abspath(src)
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [root] + [p for p in sys.path if p and os.path.abspath(p) not in (src_abs, here)]
    os.chdir(root)
    for name in list(sys.modules):
        if name == "sqlglot" or name.startswith(("sqlglot.", "tests")):
            del sys.modules[name]
    import importlib
    importlib.invalidate_caches()
    sys.setrecursionlimit(20000)


def _send(fd, obj):
    data = pickle.dumps(obj)
    with os.fdopen(fd, "wb") as f:
        f.write(len(data).to_bytes(8, "big") + data)


def _recv(fd):
    with os.fdopen(fd, "rb") as f:
        n = int.from_bytes(f.read(8) or b"\0" * 8, "big")
        data = f.read(n)
    if n == 0 or len(data) != n:
        raise Doubt("short read")
    return pickle.loads(data)


def fingerprint(root, src, tpch, expect=None):
    """Runs in a forked child that has not imported sqlglot. Forks a second
    fresh process for the worker side. Returns one digest for the test."""
    roots = [os.path.abspath(root), os.path.abspath(src)]
    r1, w1 = os.pipe()   # parent side -> worker side
    r2, w2 = os.pipe()   # worker side -> here
    pid = os.fork()
    if pid == 0:
        try:
            os.close(w1)
            os.close(r2)
            res = ("err",)
            try:
                blobs, meta = _recv(r1)
                _enter(root, src)
                res = ("ok",) + worker_side(tpch, blobs, meta, roots, expect and expect.get("q"))
            except BaseException as e:  # noqa: B036
                res = ("err", repr(e)[:300])
            _send(w2, res)
        finally:
            os._exit(0)
    os.close(r1)
    os.close(w2)
    try:
        _enter(root, src)
        blobs, duck, meta, st_parent = parent_side(tpch, roots)
        if expect is not None and hashlib.sha1(json.dumps([duck, meta]).encode()).hexdigest()[:16] != expect["duck"]:
            raise Doubt("duckdb sql differs")
        if expect is not None and st_parent[:16] != expect["sp"]:
            raise Doubt("parent module state differs")
        _send(w1, (blobs, meta))
        res = _recv(r2)
    finally:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
        os.waitpid(pid, 0)
    if res[0] != "ok":
        raise Doubt("worker: " + "".join(res[1:]))
    per_query, st_worker = res[1], res[2]
    dump = os.environ.get("BR_HEAVY_DUMP")
    if dump:
        with open(dump, "w") as f:
            json.dump([duck, meta, per_query, st_parent, st_worker], f)
    return json.dumps({"duck": hashlib.sha1(json.dumps([duck, meta]).encode()).hexdigest()[:16],
                       "q": [q[:16] if q else None for q in per_query], "sp": st_parent[:16], "sw": st_worker[:16]},
                      separators=(",", ":"))


def compare(a, b):
    """'' when two digests are equal, else which parts differ."""
    try:
        a, b = json.loads(a), json.loads(b)
    except (TypeError, ValueError):
        return "unreadable"
    out = []
    if a["duck"] != b["duck"]:
        out.append("duckdb sql")
    nq = sum(x != y for x, y in zip(a["q"], b["q"])) + abs(len(a["q"]) - len(b["q"]))
    if nq:
        out.append(f"plan of {nq} queries")
    if a["sp"] != b["sp"]:
        out.append("parent module state")
    if a["sw"] != b["sw"]:
        out.append("worker module state")
    return ", ".join(out)


# ------------------------------------------------------------- selector side

def load_lines(path):
    import gzip
    with gzip.open(path, "rt") as f:
        d = json.load(f)
    return {name: {fp: set(ls) for fp, ls in files.items()} for name, files in d["lines"].items()}


def static_ok(name, lines, changes):
    """changes: {path: set of old-side line numbers touched}, where an
    insertion counts as touching both neighbours. True when no changed line
    is one the expensive phase runs."""
    rec = lines.get(name)
    if rec is None:
        return False
    for path, touched in changes.items():
        if not (path.startswith("sqlglot/") and path.endswith(".py")) or path in FORCED:
            return False
        ran = rec.get(path, ())
        if any(n in ran for n in touched):
            return False
    return True


def _fp_main(root, src, tpch, cpu_s, expect_path=None):
    """Entry of the fresh interpreter (PYTHONHASHSEED=0): prints D<digest> or E."""
    import resource
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(cpu_s + 0.999)), resource.RLIM_INFINITY))
    except (ValueError, OSError):
        pass
    out = os.fdopen(os.dup(1), "w", buffering=1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    if not os.environ.get("BR_V_DEBUG"):
        os.dup2(devnull, 2)
    msg = "E"
    try:
        expect = None
        if expect_path:
            with open(expect_path) as f:
                expect = json.loads(f.read())
        msg = "D" + fingerprint(root, src, tpch, expect)
    except Doubt as e:
        msg = "X" + str(e).replace("\n", " ")[:200]
    except BaseException as e:  # noqa: B036
        if os.environ.get("BR_V_DEBUG"):
            import traceback
            print("heavy child:", "".join(traceback.format_exception(e))[-2000:], file=sys.stderr)
    out.write(msg + "\n")
    out.flush()
    os._exit(0)


def run_fingerprint(src, files, tpch, wall_s, cpu_s, acc=None, expect=None):
    """Digest of the cheap phase on src patched with files, or None. The
    child is a fresh interpreter with a fixed hash seed, so set and dict
    orders, and therefore the digest, repeat from run to run."""
    import select
    import shutil
    import subprocess
    import time
    from verify import build_overlay, _cpu_of
    src = os.path.abspath(src)
    root = build_overlay(src, files)
    argv = [sys.executable, os.path.abspath(__file__), "--fp", root, src, str(int(tpch)), str(cpu_s)]
    if expect is not None:
        # the pristine digest: the child stops at the first part that differs
        ep = os.path.join(root, ".heavy-expect.json")
        with open(ep, "w") as f:
            f.write(expect)
        argv.append(ep)
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", SKIP_INTEGRATION="0")
    p = subprocess.Popen(argv,
                         stdout=subprocess.PIPE, stderr=None if os.environ.get("BR_V_DEBUG") else subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, env=env, cwd=root, start_new_session=True)
    r = p.stdout.fileno()
    buf, msg = b"", None
    deadline = time.monotonic() + wall_s
    try:
        while msg is None:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            ready, _, _ = select.select([r], [], [], min(left, 0.05))
            if not ready:
                if _cpu_of(p.pid) > cpu_s:
                    break
                continue
            chunk = os.read(r, 4096)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                msg = buf.split(b"\n", 1)[0].decode()
    finally:
        for kill in (lambda: os.killpg(p.pid, 9), lambda: os.kill(p.pid, 9)):
            try:
                kill()
            except OSError:
                pass
        _, _, ru = os.wait4(p.pid, 0)
        p.returncode = 0
        p.stdout.close()
        cpu = ru.ru_utime + ru.ru_stime
        shutil.rmtree(root, ignore_errors=True)
    if acc is not None:
        acc.last_cpu = cpu
        acc.cpu += cpu
        acc.last_reason = msg[1:] if msg and msg[0] == "X" else ("failed" if not msg or msg[0] != "D" else "")
    if msg and msg.startswith("D"):
        return msg[1:]
    return None


def record(src, out, wall_s=600.0, cpu_s=600.0):
    """Pristine digests, written at image build time (not charged)."""
    res = {}
    for num, (name, tpch) in HEAVY.items():
        a = run_fingerprint(src, {}, tpch, wall_s, cpu_s)
        b = run_fingerprint(src, {}, tpch, wall_s, cpu_s)
        # a digest that differs between two pristine runs is useless: leave it out
        if a is not None and a == b:
            res[str(num)] = a
    with open(out, "w") as f:
        json.dump(res, f)
    return res


if __name__ == "__main__":
    if len(sys.argv) in (6, 7) and sys.argv[1] == "--fp":
        _fp_main(sys.argv[2], sys.argv[3], sys.argv[4] == "1", float(sys.argv[5]),
                 sys.argv[6] if len(sys.argv) == 7 else None)
    if len(sys.argv) >= 3 and sys.argv[1] == "--record":
        print(record(os.environ.get("SQLGLOT_SRC", "/opt/sqlglot"), sys.argv[2]))


# ------------------------------------------------------------- statements

def touched_ranges(old_text, changed, inserts):
    """For every changed old line and both neighbours of every insertion, the
    line range of the innermost statement containing it (decorators count as
    part of their def or class). Lines in no statement (comments, blanks)
    give nothing. A file that does not parse gives None (doubt)."""
    import ast
    try:
        tree = ast.parse(old_text)
    except (SyntaxError, ValueError):
        return None
    spans, funcs = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            start = node.lineno
            for d in getattr(node, "decorator_list", ()) or ():
                start = min(start, d.lineno)
            spans.append((start, node.end_lineno or node.lineno))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(spans[-1])
    lines = set(changed)
    out = []
    for p in inserts:
        lines.update((p, p + 1))
        # an inserted line may run at the end of a block whose last statement
        # never ran: count the whole innermost function it lands in
        best = None
        for s, e in funcs:
            if s <= p <= e and (best is None or e - s < best[1] - best[0]):
                best = (s, e)
        if best is not None:
            out.append(best)
    for n in sorted(lines):
        best = None
        for s, e in spans:
            if s <= n <= e and (best is None or e - s < best[1] - best[0]):
                best = (s, e)
        if best is not None:
            out.append(best)
    return out


def drop_heavy(results, tests, src, lines_path, record_path, overlay_files, parse_patch, apply,
               log, t_start, wall_budget, cpu_cap, allowed=None):
    """results: [cid, chosen set, why list, patch path]. Removes a heavy test
    from chosen when the static rule and the overlay fingerprint both pass."""
    import time
    nums = {}
    for num, (name, tpch) in HEAVY.items():
        if num in tests and tests[num][0] == f"tests/test_executor.py::TestExecutor::test_execute_{name}" \
                and (allowed is None or num in allowed):
            nums[num] = (name, tpch)
    if not nums:
        return
    jobs = []
    for r in results:
        chosen = r[1]
        mine = [n for n in nums if n in chosen]
        if not mine or len(chosen) == len(tests):
            continue
        jobs.append((r, mine))
    if not jobs:
        return
    try:
        lines = load_lines(lines_path)
        with open(record_path) as f:
            rec = json.load(f)
    except Exception as e:  # noqa: BLE001
        log("heavy: data unavailable:", repr(e))
        return
    for r, mine in jobs:
        try:
            with open(r[3], encoding="utf-8") as f:
                fps = parse_patch(f.read())
            changes = {}
            ok = True
            for fp in fps:
                if fp.binary or fp.old is None or fp.new != fp.old:
                    ok = False
                    break
                with open(os.path.join(src, fp.old), encoding="utf-8", newline="") as f:
                    old_text = f.read()
                _, changed, inserts = apply(old_text, fp)
                rng = touched_ranges(old_text, changed, inserts) if fp.old.endswith(".py") else None
                if rng is None:
                    ok = False
                    break
                changes[fp.old] = {n for s, e in rng for n in range(s, e + 1)}
        except Exception as e:  # noqa: BLE001
            r[2].append(f"heavy: patch not analysed ({type(e).__name__})")
            continue
        if not ok:
            r[2].append("heavy: patch adds, deletes, renames or edits a non-Python file")
            continue
        cand = [n for n in mine if str(n) in rec and static_ok(nums[n][0], lines, changes)]
        if not cand:
            r[2].append("heavy: a changed statement runs in the executing phase")
            continue
        files = overlay_files(r[3])
        if not files:
            continue
        for n in sorted(cand, key=lambda n: -tests[n][2]):
            left = wall_budget - (time.monotonic() - t_start)
            if left < 3 * cpu_cap:
                r[2].append("heavy: out of time")
                break
            d = run_fingerprint(src, files, nums[n][1], min(left, 4 * cpu_cap), cpu_cap, _CPU, rec[str(n)])
            diff = compare(d, rec[str(n)]) if d is not None else _CPU.last_reason
            same = d is not None and diff == "" and d == rec[str(n)]
            r[2].append(f"heavy: {nums[n][0]} fingerprint {'same' if same else 'differs: ' + diff},"
                        f" child CPU {_CPU.last_cpu:.2f} s")
            if same:
                r[1] = set(r[1]) - {n}
    log(f"heavy: {len(jobs)} commits, child CPU {_CPU.cpu:.2f} s")


class _Acc:
    cpu = 0.0
    last_cpu = 0.0
    last_reason = ""


_CPU = _Acc()
