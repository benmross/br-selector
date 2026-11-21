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


def startup_failures(text, returncode, src, tests):
    """A patched shadow module can stop pytest before plugins are imported.

    Only a real Python traceback through the overlay qualifies; argument,
    timeout and infrastructure failures remain errors rather than labels.
    """
    if returncode in (1, 2) and 'Traceback (most recent call last):' in text \
            and re.search(r'File [\"\']' + re.escape(src.rstrip('/') + '/'), text):
        return set(tests.values())
    return None


def summary_failures(text, tests):
    """Recover saved pytest 9 summaries, including multiline SQL subtest tags."""
    summary = text.rsplit("short test summary info", 1)[-1]
    pattern = r"^(?:FAILED|ERROR|SUBFAILED)(?:[\[(][\s\S]*?[\])])?\s+(tests/\S+)"
    return failure_numbers(re.findall(pattern, summary, re.MULTILINE), tests)
