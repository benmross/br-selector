"""pytest plugin: preserve failed subtests and collection errors as node ids."""
import json
import os
from pathlib import Path

_failed = set()
_prefix = None
_worker = None


def pytest_configure(config):
    global _prefix, _worker
    _prefix = os.environ["LABEL_REPORT_PREFIX"]
    _worker = getattr(config, "workerinput", {}).get("workerid", "main")
    Path(_prefix).parent.mkdir(parents=True, exist_ok=True)
    if _worker == "main":
        for path in Path(_prefix).parent.glob(Path(_prefix).name + ".*.json"):
            path.unlink()


def pytest_runtest_logreport(report):
    if report.failed:
        _failed.add(report.nodeid)


def pytest_collectreport(report):
    if report.failed:
        _failed.add(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    path = _prefix + "." + _worker + ".json"
    with open(path + ".tmp", "w") as f:
        json.dump({"failed": sorted(_failed), "exitstatus": int(exitstatus)}, f)
    os.replace(path + ".tmp", path)
    stop_after = os.environ.get("LABEL_STOP_AFTER_FILE")
    stop_request = os.environ.get("LABEL_STOP_REQUEST_FILE")
    if _worker == "main" and stop_after and stop_request:
        target = Path(stop_after)
        if target.exists() and target.read_text().strip() == Path(_prefix).name:
            Path(stop_request).touch()
