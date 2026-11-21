"""Ground-truth failure collection for the validation harness only."""
import glob
import json
import re


def failure_numbers(nodeids, tests):
    failing = set()
    for nid in nodeids:
        base = nid.split("[", 1)[0]
        if base in tests:
            nid = base
        if nid in tests:
            failing.add(tests[nid])
        else:
            # Collection can fail for an entire file or class.
            failing.update(n for tid, n in tests.items() if tid.startswith(nid + "::"))
    return failing


def report_failures(prefix, tests):
    paths = glob.glob(prefix + ".*.json")
    if not paths:
        raise RuntimeError("pytest produced no structured failure reports: " + prefix)
    ids = set()
    for path in paths:
        with open(path) as f:
            ids.update(json.load(f)["failed"])
    return failure_numbers(ids, tests)


def summary_failures(text, tests):
    """Recover saved pytest 9 summaries, including multiline SQL subtest tags."""
    summary = text.rsplit("short test summary info", 1)[-1]
    pattern = r"^(?:FAILED|ERROR|SUBFAILED)(?:[\[(][\s\S]*?[\])])?\s+(tests/\S+)"
    return failure_numbers(re.findall(pattern, summary, re.MULTILINE), tests)
