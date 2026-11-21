"""Comparison value profile: which operator swaps would change a result.

Installed before sqlglot is imported (by tools/cmpsite/sitecustomize.py, so
xdist workers and test subprocesses get it too). An import hook rewrites every
single-operator comparison in sqlglot/ (==, !=, <, <=, >, >=, is, is not) into
a probe call. The probe returns the original result unchanged and evaluates
the operator's substitutes on the same operands:

  equality family: == != is is-not
  order family:    < <= > >= == !=

It records, per site (file:line:col of the comparison, which is the start of
its left operand, so an operator swap keeps the key) and per test phase, which
substitutes ever gave a different bool. Substitutes are evaluated only on
operands whose comparisons are builtin C code with no side effects; any other
operand, a non-bool result, or an exception marks every substitute of the
family as differing. Evaluations outside a test (import, collection, a
subprocess) are recorded under an unattributed context.

Also a pytest plugin (-p cmp_profile): tags evaluations with the test phase.
"""
import ast
import atexit
import importlib.abc
import importlib.machinery
import json
import operator
import os
import sys

OPS = [ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot]
FUNCS = [operator.eq, operator.ne, operator.lt, operator.le, operator.gt, operator.ge,
         operator.is_, operator.is_not]
EQ_FAMILY = (0, 1, 6, 7)
ORDER_FAMILY = (0, 1, 2, 3, 4, 5)


def family(op):
    return EQ_FAMILY if op in (0, 1, 6, 7) else ORDER_FAMILY


_sites = []  # id -> (rel, line, col, op)
_store = {}  # context -> {site id: mask of differing substitutes}
_cur = _store.setdefault("@import", {})
_root = None

_BUILTIN = (object, int, str, float, bytes, bool, type, complex)
_NAMES = ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__")
_ATOMS = {type(None), bool, int, float, str, bytes}
_type_safe = {}


def _safe_type(t):
    s = _type_safe.get(t)
    if s is None:
        s = True
        for name in _NAMES:
            m = getattr(t, name, None)
            if not any(m is getattr(b, name) for b in _BUILTIN):
                s = False
                break
        _type_safe[t] = s
    return s


def _safe(x, depth=0):
    t = x.__class__
    if t in _ATOMS:
        return True
    if t is tuple:
        return depth < 3 and len(x) <= 8 and all(_safe(i, depth + 1) for i in x)
    return _safe_type(t)


_CONTAINERS = {list, dict, set, frozenset, tuple}
_expr_eq = {}


def _none_safe(a, b):
    """x == None (either order) where x is a builtin container or a sqlglot
    Expr: the container returns NotImplemented without reading its items, and
    Expr.__eq__ is `self is other or (type(self) is type(other) and ...)`,
    which returns False before hashing. Neither has side effects."""
    if a is None:
        x = b
    elif b is None:
        x = a
    else:
        return False
    t = x.__class__
    if t in _CONTAINERS:
        return True
    s = _expr_eq.get(t)
    if s is None:
        eq, ne = getattr(t, "__eq__", None), getattr(t, "__ne__", None)
        s = (getattr(eq, "__qualname__", "") == "Expr.__eq__"
             and getattr(eq, "__module__", "") == "sqlglot.expressions.core"
             and getattr(ne, "__qualname__", "") == "Expr.__ne__"
             and getattr(ne, "__module__", "") == "sqlglot.expressions.core")
        _expr_eq[t] = s
    return s


def _make(op):
    fam = family(op)
    eq_family = fam is EQ_FAMILY
    full = sum(1 << k for k in fam if k != op)
    alts = [(k, FUNCS[k]) for k in fam if k != op]
    f = FUNCS[op]

    def probe(site, a, b):
        r = f(a, b)
        cur = _cur
        m = cur.get(site, 0)
        if m == full:
            return r
        if r.__class__ is not bool or not ((_safe(a) and _safe(b)) or (eq_family and _none_safe(a, b))):
            cur[site] = full
            return r
        for k, g in alts:
            bit = 1 << k
            if m & bit:
                continue
            try:
                rk = g(a, b)
            except Exception:
                m = full
                break
            if rk.__class__ is not bool:
                m = full
                break
            if rk is not r:
                m |= bit
        cur[site] = m
        return r

    return probe


PROBES = [_make(i) for i in range(len(OPS))]


class _Rewrite(ast.NodeTransformer):
    def __init__(self, rel):
        self.rel = rel

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) != 1 or type(node.ops[0]) not in OPS:
            return node  # chained comparisons and in/not in stay as they are
        op = OPS.index(type(node.ops[0]))
        sid = len(_sites)
        _sites.append((self.rel, node.lineno, node.col_offset, op))
        call = ast.Call(func=ast.Name(id=f"__brc{op}__", ctx=ast.Load()),
                        args=[ast.Constant(sid), node.left, node.comparators[0]], keywords=[])
        return ast.copy_location(call, node)


class _Loader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname):
        path = self.get_filename(fullname)
        source = self.get_data(path)
        tree = ast.parse(source, path)
        rel = os.path.relpath(path, _root)
        tree = ast.fix_missing_locations(_Rewrite(rel).visit(tree))
        return compile(tree, path, "exec", dont_inherit=True)


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name != "sqlglot" and not name.startswith("sqlglot."):
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or not isinstance(spec.loader, importlib.machinery.SourceFileLoader):
            return spec
        origin = os.path.abspath(spec.origin)
        if not origin.startswith(os.path.join(_root, "sqlglot") + os.sep):
            return spec
        spec.loader = _Loader(spec.loader.name, spec.loader.path)
        return spec


def install(root, out):
    global _root, _cur
    import builtins

    _root = os.path.abspath(root)
    for i, p in enumerate(PROBES):
        setattr(builtins, f"__brc{i}__", p)
    sys.meta_path.insert(0, _Finder())
    global _out
    _out = out
    _cur = _store.setdefault("@import", {})
    atexit.register(_dump, out)


def set_context(ctx):
    global _cur
    _cur = _store.setdefault(ctx, {})


_out = None
_flushed = 0


def flush():
    """Append the records since the last flush to <out>.<pid>.jsonl. Called
    after every test, so a crashed worker loses only the test it was running
    (tools/build_cmp_profile.sh reruns those alone)."""
    global _flushed, _store, _cur
    if _out is None:
        return
    rows = {c: [[s, m] for s, m in d.items()] for c, d in _store.items() if d}
    new_sites = _sites[_flushed:]
    if not rows and not new_sites:
        return
    with open(f"{_out}.{os.getpid()}.jsonl", "a") as f:
        f.write(json.dumps({"sites": new_sites, "ctx": rows}, separators=(",", ":")) + "\n")
    _flushed += len(new_sites)
    current = [c for c, d in _store.items() if d is _cur]
    _store = {}
    _cur = _store.setdefault(current[0] if current else "@collect", {})


def _dump(out):
    flush()


# ------------------------------------------------------------ pytest plugin

def _phase(item, phase):
    set_context(item.nodeid if phase == "call" else f"{item.nodeid}|{phase}")


try:
    import pytest
except ImportError:  # subprocesses without pytest only need the hook
    pytest = None

if pytest is not None:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(item):
        _phase(item, "setup")
        yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(item):
        _phase(item, "call")
        yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(item, nextitem):
        _phase(item, "teardown")
        yield
        set_context("@collect")
        flush()
