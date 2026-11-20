"""pytest plugin: record which files under tests/ each test opens."""
import json
import os
import sys

import pytest

_current = [None]
_opens = {}
_root = os.path.realpath(os.getcwd())


def _hook(event, args):
    if event == "open" and _current[0] is not None:
        path = args[0]
        if isinstance(path, (str, bytes, os.PathLike)):
            try:
                p = os.path.realpath(os.fsdecode(path))
            except Exception:
                return
            if p.startswith(_root + os.sep) and not p.endswith((".pyc", ".py")):
                _opens.setdefault(_current[0], set()).add(os.path.relpath(p, _root))
    elif event == "os.listdir" and _current[0] is not None:
        try:
            p = os.path.realpath(os.fsdecode(args[0]))
        except Exception:
            return
        if p.startswith(_root + os.sep):
            _opens.setdefault(_current[0], set()).add(os.path.relpath(p, _root) + "/")


sys.addaudithook(_hook)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    _current[0] = item.nodeid
    yield
    _current[0] = None


def pytest_sessionfinish(session):
    out = os.environ.get("FIXTURE_TRACE_OUT")
    if out:
        wid = os.environ.get("PYTEST_XDIST_WORKER", "main")
        with open(f"{out}.{wid}.json", "w") as f:
            json.dump({k: sorted(v) for k, v in _opens.items()}, f)
