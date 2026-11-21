"""pytest plugin: record which keys of class-level callable tables each test probes.

Parser FUNCTIONS and FUNCTION_PARSERS and Generator TRANSFORMS are dicts built
in class bodies at import, so line coverage credits an edit of one entry to no
test, and the selector keeps every user of the class. This records, per test,
every key probed (hits and misses: get, [], in, pop, setdefault, assignment,
deletion) on each class's own table, and whether the test consumed a table
whole (iteration, keys/items/values, copy, len, comparison, splat).

Generator TRANSFORMS is copied into a per-class dispatch dict on first use
(generator._build_dispatch); that copy is followed: probes of the dispatch
dict count as probes of the class's TRANSFORMS, and the copy itself is not a
whole-table read.

For each table it also records, per key, a value-group id: entries that hold
the same object (copied by a subclass splat, a filtered comprehension, or an
alias such as Teradata's TRYCAST) share a group, so an edit of one entry can be
followed to every table that holds it.

Probes outside any test (collection, module-level test code) are recorded
under the context "@global"; the selector keeps today's selection for them.
"""
import json
import os

import pytest

import inprocess  # noqa: F401  (run process pools inline)

TABLES = ("FUNCTIONS", "FUNCTION_PARSERS", "TRANSFORMS")
_current = ["@global"]
_probes = {}  # ctx -> {table: set(keys)}
_whole = {}  # ctx -> set(tables)
_paused = [0]
_ran = set()


def kstr(k):
    if isinstance(k, str):
        return "s:" + k
    if isinstance(k, type):
        return "t:" + k.__name__
    return "r:" + repr(k)


def _probe(table, key):
    if _paused[0]:
        return
    try:
        s = kstr(key)
    except Exception:
        s = "r:?"
    _probes.setdefault(_current[0], {}).setdefault(table, set()).add(s)


def _all(table):
    if not _paused[0]:
        _whole.setdefault(_current[0], set()).add(table)


class RecDict(dict):
    __slots__ = ("_t",)

    def __getitem__(self, k):
        _probe(self._t, k)
        return dict.__getitem__(self, k)

    def get(self, k, d=None):
        _probe(self._t, k)
        return dict.get(self, k, d)

    def __contains__(self, k):
        _probe(self._t, k)
        return dict.__contains__(self, k)

    def pop(self, k, *a):
        _probe(self._t, k)
        return dict.pop(self, k, *a)

    def setdefault(self, k, d=None):
        _probe(self._t, k)
        return dict.setdefault(self, k, d)

    def __setitem__(self, k, v):
        _probe(self._t, k)
        return dict.__setitem__(self, k, v)

    def __delitem__(self, k):
        _probe(self._t, k)
        return dict.__delitem__(self, k)

    def __iter__(self):
        _all(self._t)
        return dict.__iter__(self)

    def keys(self):
        _all(self._t)
        return dict.keys(self)

    def items(self):
        _all(self._t)
        return dict.items(self)

    def values(self):
        _all(self._t)
        return dict.values(self)

    def copy(self):
        _all(self._t)
        return dict.copy(self)

    def __len__(self):
        _all(self._t)
        return dict.__len__(self)

    def __eq__(self, o):
        _all(self._t)
        return dict.__eq__(self, o)

    def __ne__(self, o):
        _all(self._t)
        return dict.__ne__(self, o)

    __hash__ = None

    def __or__(self, o):
        _all(self._t)
        return dict.__or__(self, o)

    def __ror__(self, o):
        _all(self._t)
        return dict.__ror__(self, o)

    def __ior__(self, o):
        _all(self._t)
        return dict.__ior__(self, o)

    def update(self, *a, **k):
        _all(self._t)
        return dict.update(self, *a, **k)

    def popitem(self):
        _all(self._t)
        return dict.popitem(self)

    def clear(self):
        _all(self._t)
        return dict.clear(self)

    def __repr__(self):
        _all(self._t)
        return dict.__repr__(self)

    def __reduce_ex__(self, p):
        _all(self._t)
        return (dict, (dict(dict.items(self)),))


def _rec(table, content):
    r = RecDict(content)
    r._t = table
    return r


_tables = {}  # table name -> (class, attr)
_mro = {}


def pytest_configure(config):
    import class_trace

    classes = class_trace._all_classes()
    groups = {}
    for cls in sorted(classes, key=lambda c: f"{c.__module__}:{c.__qualname__}"):
        for attr in TABLES:
            v = cls.__dict__.get(attr)
            if type(v) is not dict:
                continue
            name = f"{cls.__module__}:{cls.__qualname__}.{attr}"
            _tables[name] = (cls, attr)
            _mro[name] = [f"{c.__module__}:{c.__qualname__}" for c in cls.__mro__ if c.__module__.startswith("sqlglot")]
            gmap = {}
            for k, val in v.items():
                gid = groups.setdefault(id(val), f"{name}|{kstr(k)}")
                gmap[kstr(k)] = gid
            _GROUPS[name] = gmap
            setattr(cls, attr, _rec(name, v))
    import sqlglot.generator as g

    g._DISPATCH_CACHE.clear()
    orig = g._build_dispatch

    def traced_build(cls):
        _paused[0] += 1
        try:
            d = orig(cls)
        finally:
            _paused[0] -= 1
        own = next((c for c in cls.__mro__ if type(c.__dict__.get("TRANSFORMS")) is RecDict), None)
        if own is None:
            _all("@dispatch-unowned")
            return d
        return _rec(f"{own.__module__}:{own.__qualname__}.TRANSFORMS", d)

    g._build_dispatch = traced_build


_GROUPS = {}


def _phase(item, phase):
    _current[0] = item.nodeid if phase == "call" else f"{item.nodeid}|{phase}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    _phase(item, "setup")
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _phase(item, "call")
    _ran.add(item.nodeid)
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    _phase(item, "teardown")
    yield
    _current[0] = "@global"


def pytest_sessionfinish(session):
    out = os.environ.get("KEY_TRACE_OUT")
    if out:
        wid = os.environ.get("PYTEST_XDIST_WORKER", "main")
        with open(f"{out}.{wid}.json", "w") as f:
            json.dump({"probes": {c: {t: sorted(ks) for t, ks in v.items()} for c, v in _probes.items()},
                       "whole": {c: sorted(v) for c, v in _whole.items()},
                       "groups": _GROUPS, "mro": _mro, "ran": sorted(_ran)}, f)
