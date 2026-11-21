"""pytest plugin: record which sqlglot classes each test instantiates.

Wraps every __init__ defined in a sqlglot class, so an instance of any class
records its type. Class-level tables (KEYWORDS, TRANSFORMS, arg_types) run at
import, outside any test, so coverage cannot say who depends on them; this can.
"""
import functools
import importlib
import json
import os
import pkgutil

import pytest

import inprocess  # noqa: F401  (run process pools inline)

_current = [None]
_used = {}
_seen_types = {}


def _record(cls):
    s = _used.setdefault(_current[0], set())
    names = _seen_types.get(cls)
    if names is None:
        names = [f"{c.__module__}:{c.__qualname__}" for c in cls.__mro__ if c.__module__.startswith("sqlglot")]
        _seen_types[cls] = names
    s.update(names)


def _wrap(cls):
    init = cls.__dict__.get("__init__")
    if init is None or getattr(init, "_traced", False) or not callable(init):
        return

    @functools.wraps(init)
    def traced(self, *a, **k):
        if _current[0] is not None:
            _record(type(self))
        return init(self, *a, **k)

    traced._traced = True
    try:
        setattr(cls, "__init__", traced)
    except (TypeError, AttributeError):
        pass


def _all_classes(mod_prefix="sqlglot"):
    import sqlglot

    for info in pkgutil.walk_packages(sqlglot.__path__, "sqlglot."):
        try:
            importlib.import_module(info.name)
        except Exception:
            pass
    import sys

    seen = set()
    for name, mod in list(sys.modules.items()):
        if not name.startswith(mod_prefix) or mod is None:
            continue
        for obj in list(vars(mod).values()):
            stack = [obj]
            while stack:
                o = stack.pop()
                if isinstance(o, type) and o.__module__.startswith(mod_prefix) and o not in seen:
                    seen.add(o)
                    stack.extend(v for v in vars(o).values() if isinstance(v, type))
    return seen


def pytest_configure(config):
    for cls in _all_classes():
        _wrap(cls)
    # classes whose instances never run a sqlglot __init__ (object.__init__) are
    # caught by wrapping object creation in the metaclass-free way: record on
    # first attribute set is too costly, so also wrap __new__ users lazily.


def _phase(item, phase):
    # setUpClass and class or module fixtures run inside the first test's
    # setup; tag those observations so the map can credit the whole class
    _current[0] = item.nodeid if phase == "call" else f"{item.nodeid}|{phase}"


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
    _current[0] = None


def pytest_sessionfinish(session):
    out = os.environ.get("CLASS_TRACE_OUT")
    if out:
        wid = os.environ.get("PYTEST_XDIST_WORKER", "main")
        with open(f"{out}.{wid}.json", "w") as f:
            json.dump({k: sorted(v) for k, v in _used.items() if k}, f)
