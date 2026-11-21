"""pytest plugin: run every test in its own forked child after collection.

The parent collects (imports test modules and whatever they import) and never
runs a test, so each child starts from the same post-collection state: a cache
that a test would build when run alone is built, and recorded, by that test.

Each child records the sqlglot and tests lines it runs with sys.monitoring
(one event per line, then disabled), plus the class_trace and fixture_trace
observations, and writes them to $FORK_OUT/<index>.json.gz. The parent records
each child's exit status in $FORK_OUT/status.<shard>.json so a missing or
crashed child is visible when the runs are merged.

FORK_SHARD=i/n runs every n-th item starting at i (two parents share 2 CPUs).
"""
import gzip
import json
import os
import signal
import sys

import pytest
from _pytest.runner import runtestprotocol

_out = os.environ.get("FORK_OUT")
_shard = os.environ.get("FORK_SHARD", "0/1")
_root = os.path.realpath(os.getcwd()) + os.sep
_status = {}
_index = {}


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items):
    i, n = (int(x) for x in _shard.split("/"))
    for k, it in enumerate(items):
        _index[it.nodeid] = k
    keep = [it for k, it in enumerate(items) if k % n == i]
    config.hook.pytest_deselected(items=[it for k, it in enumerate(items) if k % n != i])
    items[:] = keep


def _child(item):
    mon = sys.monitoring
    tool = mon.COVERAGE_ID
    mon.use_tool_id(tool, "t24a-fork")
    lines = {}
    DISABLE = mon.DISABLE
    root = _root

    def on_line(code, lineno):
        f = code.co_filename
        if f.startswith(root):
            s = lines.get(f)
            if s is None:
                s = lines[f] = set()
            s.add(lineno)
        return DISABLE

    mon.register_callback(tool, mon.events.LINE, on_line)
    mon.set_events(tool, mon.events.LINE)
    try:
        reports = runtestprotocol(item, log=False, nextitem=None)
    finally:
        mon.set_events(tool, 0)
    outcome = "passed"
    for r in reports:
        if r.failed:
            outcome = "failed"
    cls, fix = {}, {}
    try:
        import class_trace

        cls = {k: sorted(v) for k, v in class_trace._used.items() if k}
    except Exception:
        pass
    try:
        import fixture_trace

        fix = {k: sorted(v) for k, v in fixture_trace._opens.items() if k}
    except Exception:
        pass
    data = {
        "nodeid": item.nodeid,
        "outcome": outcome,
        "lines": {f[len(root):]: sorted(s) for f, s in lines.items()},
        "classes": cls,
        "fixtures": fix,
    }
    path = os.path.join(_out, f"{_index[item.nodeid]}.json.gz")
    with gzip.open(path + ".tmp", "wt") as fh:
        json.dump(data, fh, separators=(",", ":"))
    os.replace(path + ".tmp", path)


def pytest_runtest_protocol(item, nextitem):
    sys.stdout.flush()
    sys.stderr.flush()
    pid = os.fork()
    if pid == 0:
        code = 0
        try:
            signal.alarm(900)
            _child(item)
        except BaseException:
            import traceback

            traceback.print_exc()
            code = 3
        finally:
            os._exit(code)
    _, st = os.waitpid(pid, 0)
    _status[item.nodeid] = os.waitstatus_to_exitcode(st)
    return True


def pytest_sessionfinish(session):
    if _out:
        with open(os.path.join(_out, f"status.{_shard.replace('/', 'of')}.json"), "w") as f:
            json.dump(_status, f)
