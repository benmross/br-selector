"""End-to-end patch regressions, with a small deterministic coverage map.

Run: SQLGLOT_SRC=work/sqlglot DATA_DIR=$(mktemp -d) python -m pytest tests_selector
The subprocesses use isolated data/source trees so these tests never modify the
real sqlglot checkout, maps, or caller's DATA_DIR.
"""
import difflib
import gzip
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
ALL = set(range(6))
CORE = "def first():\n    return 1\n\n\ndef last():\n    return 2\n"


def diff(path, before=CORE, after=None, destination=None):
    if after is None:
        after = before.replace("return 1", "return 9")
    destination = destination or path
    return (f"diff --git a/{path} b/{destination}\n" + "".join(
        difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                             fromfile=f"a/{path}", tofile=f"b/{destination}")))


@pytest.fixture
def sandbox(tmp_path):
    src = tmp_path / "src"
    sources = {
        "sqlglot/__init__.py": "",
        "sqlglot/core.py": CORE,
        "sqlglot/other.py": "def other():\n    return 3\n",
        "sqlglot/café.py": CORE,
        "sqlglot/has space.py": CORE,
        "sqlglot/noeol.py": "def first():\n    return 1",
        "sqlglot/decorated.py": "@staticmethod\ndef first():\n    return 1\n",
        "sqlglot/encoded.py": "def first():\n    return 'café'\n",
        "tests/test_core.py": "def test_first():\n    assert True\n",
        "tests/conftest.py": CORE,
        "tests/helper.py": CORE,
        "tests/fixtures/data.sql": "SELECT 1;\n",
        "tests/fixtures/destination.sql": "SELECT 2;\n",
        "data/root.sql": "SELECT 1;\n",
    }
    for path, text in sources.items():
        p = src / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    data = tmp_path / "data"
    (data / "commits").mkdir(parents=True)
    tests = [{"number": n, "id": f"{file}::test_{n}", "file": file,
              "seconds": 0.01 * (n + 1)} for n, file in enumerate([
                  "tests/test_core.py", "tests/test_last.py", "tests/test_fixture.py",
                  "tests/test_other.py", "tests/test_misc.py", "tests/test_helper.py"])]
    (data / "tests.json").write_text(json.dumps({"tests": tests}))
    files = {"sqlglot/core.py": {"1": 0, "2": 0, "5": 1, "6": 1},
             "sqlglot/other.py": {"1": 3, "2": 3},
             "tests/test_core.py": {"1": 0, "2": 0},
             "tests/helper.py": {"1": 5, "2": 5}}
    for path in ("sqlglot/café.py", "sqlglot/has space.py", "sqlglot/noeol.py",
                 "sqlglot/decorated.py"):
        files[path] = {"1": 0, "2": 0, "3": 0, "5": 1, "6": 1}
    fixtures = {"tests/fixtures/data.sql": 2,
                "tests/fixtures/destination.sql": 3, "data/root.sql": 4}
    fixtures.update({f"tests/fixtures/file{i}.sql": i % 6 for i in range(50)})
    mapping = {"tests": {t["id"]: t["number"] for t in tests},
               "sets": [[n] for n in range(6)], "files": files,
               "fixtures": fixtures, "classes": {}, "import_lines": {}}
    map_path = tmp_path / "map.json.gz"
    with gzip.open(map_path, "wt") as f:
        json.dump(mapping, f)
    env = {**os.environ, "DATA_DIR": str(data), "SQLGLOT_SRC": str(src),
           "MAP_PATH": str(map_path), "INDEX_PATH": str(tmp_path / "missing-index.gz"),
           "CMP_PATH": str(tmp_path / "cmp.json.gz"), "PYTHONDONTWRITEBYTECODE": "1"}

    def run(patches, timeout=10):
        for p in (data / "commits").iterdir():
            p.unlink()
        for name, patch in patches.items():
            (data / "commits" / f"{name}.patch").write_bytes(
                patch.encode("utf-8") if isinstance(patch, str) else patch)
        started = time.monotonic()
        result = subprocess.run([sys.executable, str(ROOT / "selector.py")],
                                env=env, capture_output=True, timeout=timeout)
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        lines = result.stdout.decode("utf-8").splitlines()
        assert len(lines) == len(patches), result.stdout
        answers = {}
        for line in lines:
            answer = json.loads(line)
            assert set(answer) == {"commit", "workers"}
            assert answer["commit"] in patches
            assert answer["commit"] not in answers
            workers = answer["workers"]
            assert isinstance(workers, list) and len(workers) <= 8
            assert all(isinstance(w, list) for w in workers)
            numbers = [n for worker in workers for n in worker]
            assert all(type(n) is int and n in ALL for n in numbers)
            assert len(numbers) == len(set(numbers))
            answers[answer["commit"]] = set(numbers)
        return answers, result.stderr.decode("utf-8", "replace"), time.monotonic() - started

    run.env = env
    return run, src


NORMAL = diff("sqlglot/core.py")
RENAME = ("diff --git a/sqlglot/core.py b/sqlglot/renamed.py\n"
          "similarity index 100%\nrename from sqlglot/core.py\nrename to sqlglot/renamed.py\n")
FIXTURE_RENAME = ("diff --git a/tests/fixtures/data.sql b/tests/fixtures/destination.sql\n"
                  "similarity index 100%\nrename from tests/fixtures/data.sql\n"
                  "rename to tests/fixtures/destination.sql\n")


CASES = [
    ("normal", NORMAL, {0}, {0}),
    ("crlf", NORMAL.replace("\n", "\r\n"), {0}, {0}),
    ("no-patch-final-newline", NORMAL.rstrip("\n"), {0}, None),
    ("no-source-final-newline", "diff --git a/sqlglot/noeol.py b/sqlglot/noeol.py\n"
     "--- a/sqlglot/noeol.py\n+++ b/sqlglot/noeol.py\n@@ -2 +2 @@\n"
     "-    return 1\n\\ No newline at end of file\n+    return 9\n"
     "\\ No newline at end of file\n", {0}, {0}),
    ("binary-python", "diff --git a/sqlglot/core.py b/sqlglot/core.py\n"
     "Binary files a/sqlglot/core.py and b/sqlglot/core.py differ\n", ALL, None),
    ("git-binary-python", "diff --git a/sqlglot/core.py b/sqlglot/core.py\n"
     "GIT binary patch\nliteral 3\nKcmZQzU|?Vb0000\n", ALL, None),
    ("binary-fixture", "diff --git a/tests/fixtures/data.sql b/tests/fixtures/data.sql\n"
     "Binary files a/tests/fixtures/data.sql and b/tests/fixtures/data.sql differ\n", {2}, None),
    ("rename-only-python", RENAME, ALL, None),
    ("copy-python", RENAME.replace("rename from", "copy from").replace("rename to", "copy to"), ALL, None),
    ("rename-edited-python", RENAME.replace("similarity index 100%", "similarity index 80%") +
     "\n".join(diff("sqlglot/core.py", destination="sqlglot/renamed.py").split("\n")[1:]), ALL, None),
    ("rename-fixture", FIXTURE_RENAME, {2, 3}, None),
    ("rename-edited-fixture", FIXTURE_RENAME +
     "--- a/tests/fixtures/data.sql\n+++ b/tests/fixtures/destination.sql\n"
     "@@ -1 +1 @@\n-SELECT 1;\n+SELECT 9;\n", {2, 3}, None),
    ("copy-fixture", FIXTURE_RENAME.replace("rename from", "copy from").replace("rename to", "copy to"), {2, 3}, None),
    ("new-python", "diff --git a/sqlglot/new.py b/sqlglot/new.py\nnew file mode 100644\n"
     "--- /dev/null\n+++ b/sqlglot/new.py\n@@ -0,0 +1 @@\n+VALUE = 1\n", ALL, None),
    ("new-test-helper", "diff --git a/tests/new_helper.py b/tests/new_helper.py\n"
     "new file mode 100644\n--- /dev/null\n+++ b/tests/new_helper.py\n"
     "@@ -0,0 +1 @@\n+VALUE = 1\n", ALL, None),
    ("deleted-python", "diff --git a/sqlglot/core.py b/sqlglot/core.py\n"
     "deleted file mode 100644\n", ALL, None),
    ("deleted-fixture", "diff --git a/tests/fixtures/data.sql b/tests/fixtures/data.sql\n"
     "deleted file mode 100644\n", {2}, None),
    ("executable-mode-only", "diff --git a/sqlglot/core.py b/sqlglot/core.py\n"
     "old mode 100644\nnew mode 100755\n", set(), set()),
    ("symlink-mode", "diff --git a/sqlglot/core.py b/sqlglot/core.py\n"
     "old mode 100644\nnew mode 120000\n", ALL, None),
    ("script-mode", "diff --git a/tools/run.sh b/tools/run.sh\n"
     "old mode 100755\nnew mode 100644\n", ALL, None),
    ("outside-doc", diff("README.md", "hello\n", "world\n"), set(), set()),
    ("outside-config", diff("pyproject.toml", "hello\n", "world\n"), ALL, None),
    ("outside-python", diff("plugin.py"), ALL, None),
    ("outside-dependency", diff("requirements.lock", "old==1\n", "old==2\n"), ALL, None),
    ("outside-fixture", diff("data/root.sql", "SELECT 1;\n", "SELECT 2;\n"), {4}, None),
    ("conftest", diff("tests/conftest.py"), ALL, None),
    ("multiple-hunks", "diff --git a/sqlglot/core.py b/sqlglot/core.py\n"
     "--- a/sqlglot/core.py\n+++ b/sqlglot/core.py\n"
     "@@ -2 +2 @@\n-    return 1\n+    return 9\n"
     "@@ -6 +6 @@\n-    return 2\n+    return 8\n", {0, 1}, {0, 1}),
    ("line-one", diff("sqlglot/core.py", after=CORE.replace("first", "broken")), {0}, None),
    ("end-of-file", diff("sqlglot/core.py", after=CORE.replace("return 2", "return 9")), {1}, {1}),
    ("append-at-import", diff("sqlglot/core.py", after=CORE + "raise RuntimeError('oops')\n"), ALL, None),
    ("empty", "", set(), set()),
    ("non-utf8", NORMAL.encode().replace(b"return 9", b"return '\xff'"), ALL, None),
    ("unicode-path", diff("sqlglot/café.py"), {0}, {0}),
    ("git-quoted-unicode-path", diff("sqlglot/café.py").replace(
        "a/sqlglot/café.py", '"a/sqlglot/caf\\303\\251.py"').replace(
        "b/sqlglot/café.py", '"b/sqlglot/caf\\303\\251.py"'), {0}, None),
    ("space-path", diff("sqlglot/has space.py"), {0}, {0}),
    ("quoted-space-path", diff("sqlglot/has space.py").replace(
        "a/sqlglot/has space.py", '"a/sqlglot/has space.py"').replace(
        "b/sqlglot/has space.py", '"b/sqlglot/has space.py"'), {0}, None),
    ("mismatched-removal", NORMAL.replace("-    return 1", "-    return 987"), ALL, None),
    ("truncated-hunk", NORMAL.rsplit("+    return 9", 1)[0], ALL, None),
    ("invalid-hunk-count", NORMAL.replace("@@ -1,5 +1,5 @@", "@@ -1,99 +1,99 @@"), ALL, None),
    ("decorator", diff("sqlglot/decorated.py", "@staticmethod\ndef first():\n    return 1\n",
                       "@classmethod\ndef first():\n    return 1\n"), {0}, None),
    ("encoding-cookie", diff("sqlglot/café.py", after="# coding: ascii\n# café\n" + CORE), ALL, None),
    ("path-traversal", diff("../outside.py"), ALL, None),
    ("header-only", "diff --git a/sqlglot/core.py b/sqlglot/core.py\n", ALL, None),
    ("unknown-original", diff("sqlglot/unavailable.py"), ALL, None),
    ("plain-unified", "\n".join(NORMAL.split("\n")[1:]), ALL, None),
    ("new-empty-python", "diff --git a/sqlglot/new.py b/sqlglot/new.py\n"
     "new file mode 100644\nindex 0000000..e69de29\n", ALL, None),
    ("non-utf8-path", NORMAL.encode().replace(b"core.py", b"bad\xff.py"), ALL, None),
    ("huge-hunk-position", NORMAL.replace("@@ -1,5 +1,5 @@", "@@ -999999999999,5 +1,5 @@"), ALL, None),
    ("overlapping-hunks", NORMAL + "@@ -2 +2 @@\n-    return 1\n+    return 8\n", ALL, None),
]


@pytest.mark.parametrize("name,patch,required,exact", CASES, ids=[c[0] for c in CASES])
def test_patch(sandbox, name, patch, required, exact):
    run, _ = sandbox
    answers, _, _ = run({name: patch})
    selected = answers[name]
    assert selected >= required
    if exact is not None:
        assert selected == exact


def test_fifty_files(sandbox):
    run, _ = sandbox
    patch = "".join(diff(f"tests/fixtures/file{i}.sql", "SELECT 1;\n", "SELECT 2;\n")
                    for i in range(50))
    answers, _, elapsed = run({"fifty": patch})
    assert answers["fifty"] == ALL
    assert elapsed < 5


def test_large_patch_does_not_starve_following_commits(sandbox):
    run, _ = sandbox
    huge = "diff --git a/sqlglot/core.py b/sqlglot/core.py\n" + ("+x = 1\n" * 900_000)
    answers, _, elapsed = run({"a-large": huge, "z-normal": NORMAL}, timeout=15)
    assert answers["a-large"] == ALL
    assert answers["z-normal"] == {0}
    assert elapsed < 10


def test_batch_isolates_bad_commits(sandbox):
    run, _ = sandbox
    patches = {name: patch for name, patch, _, _ in CASES}
    answers, _, _ = run(patches, timeout=20)
    assert answers["normal"] == {0}
    for name, _, required, exact in CASES:
        assert answers[name] >= required
        if exact is not None:
            assert answers[name] == exact


def load_selector():
    spec = importlib.util.spec_from_file_location("tested_selector", ROOT / "selector.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("before,after", [
    (CORE, CORE.replace("return 1", "return 9")),
    (CORE, "# comment\n" + CORE),
    (CORE, CORE + "# comment\n"),
    (CORE, CORE.replace("\n\n", "\n# comment\n", 1)),
    (CORE, CORE.replace("return 1", "return 9").replace("return 2", "return 8")),
])
def test_apply_preserves_exact_content(before, after):
    selector = load_selector()
    fp, = selector.parse_patch(diff("sqlglot/core.py", before, after))
    actual, _, _ = selector.apply(before, fp)
    assert actual == after


@pytest.mark.parametrize("patch,before,after", [
    ("@@ -0,0 +1 @@\n+# before\n", CORE, "# before\n" + CORE),
    ("@@ -6,0 +7 @@\n+# after\n", CORE, CORE + "# after\n"),
    ("@@ -1 +0,0 @@\n-# before\n", "# before\n" + CORE, CORE),
    ("@@ -7 +6,0 @@\n-# after\n", CORE + "# after\n", CORE),
])
def test_zero_context_boundary_hunks(patch, before, after):
    selector = load_selector()
    fp, = selector.parse_patch("diff --git a/sqlglot/core.py b/sqlglot/core.py\n"
                               "--- a/sqlglot/core.py\n+++ b/sqlglot/core.py\n" + patch)
    actual, _, _ = selector.apply(before, fp)
    assert actual == after


def test_apply_no_newline_markers():
    selector = load_selector()
    patch = next(c[1] for c in CASES if c[0] == "no-source-final-newline")
    fp, = selector.parse_patch(patch)
    actual, _, _ = selector.apply("def first():\n    return 1", fp)
    assert actual == "def first():\n    return 9"


def test_patch_code_is_never_executed(sandbox, tmp_path):
    run, src = sandbox
    marker = tmp_path / "patch-was-executed"
    before = "from pathlib import Path\nVALUE = 1\n"
    after = f"from pathlib import Path\nVALUE = Path({str(marker)!r}).touch()\n"
    (src / "sqlglot/other.py").write_text(before)
    answers, _, elapsed = run({"side-effect": diff("sqlglot/other.py", before, after),
                               "normal": NORMAL})
    assert not marker.exists()
    assert answers["side-effect"] == ALL
    assert answers["normal"] == {0}
    assert elapsed < 5


def test_multiple_hanging_imports_cannot_exhaust_batch(sandbox):
    run, src = sandbox
    before = "VALUE = 1\n"
    (src / "sqlglot/other.py").write_text(before)
    patch = diff("sqlglot/other.py", before, "while True:\n    pass\n")
    answers, _, elapsed = run({**{f"loop{i}": patch for i in range(5)},
                               "normal": NORMAL}, timeout=10)
    assert all(answers[f"loop{i}"] == ALL for i in range(5))
    assert answers["normal"] == {0}
    assert elapsed < 5


def test_encoding_cookie_reinterprets_unpatched_lines(sandbox):
    run, _ = sandbox
    before = "def first():\n    return 'café'\n"
    answers, _, _ = run({"encoding": diff("sqlglot/encoded.py", before,
                                         "# coding: latin1\n" + before)})
    assert answers["encoding"] == ALL


@pytest.mark.parametrize("after", ["VALUE = 1 / 0\n", "while True:\n    pass\n",
                                   "return 1\n", "assert False\n"])
def test_import_errors_without_new_names(sandbox, after):
    run, src = sandbox
    before = "VALUE = 1\n"
    (src / "sqlglot/other.py").write_text(before)
    answers, _, _ = run({"import-error": diff("sqlglot/other.py", before, after)})
    assert answers["import-error"] == ALL


@pytest.mark.parametrize("action", ["exception", "exit", "signal", "timeout", "memory"])
def test_analysis_process_failure_is_contained(tmp_path, action):
    selector = load_selector()
    selector.MAX_COMMIT_SECONDS = 1
    selector.MAX_COMMIT_WALL_SECONDS = 0.5
    patch_path = tmp_path / "bad.patch"
    patch_path.write_text(NORMAL)

    class BrokenSelector:
        all = ALL

        def for_file(self, fp, why):
            if action == "exception":
                raise RuntimeError("failed")
            if action == "exit":
                os._exit(7)
            if action == "signal":
                os.kill(os.getpid(), signal.SIGKILL)
            if action == "memory":
                bytearray(2 * 1024 * 1024 * 1024)
            time.sleep(10)
            return set()

    context = multiprocessing.get_context("fork")
    started = time.monotonic()
    chosen, why = selector.analyze_patch(context, str(patch_path), BrokenSelector(),
                                         {n: None for n in ALL}, started + 5)
    assert chosen == ALL
    assert why
    assert time.monotonic() - started < 2
    assert not multiprocessing.active_children()


class SlowSelector:
    """Stands in for the real selector: burns CPU or sits idle, then picks 1."""
    all = ALL

    def __init__(self, busy=0.0, idle=0.0):
        self.busy, self.idle = busy, idle

    def for_file(self, fp, why):
        end = time.process_time() + self.busy
        while time.process_time() < end:
            pass
        time.sleep(self.idle)
        return {1}

    def expand_shared_setup(self, chosen, why):
        return chosen


def test_cpu_limit_stops_a_busy_child(tmp_path):
    selector = load_selector()
    selector.MAX_COMMIT_SECONDS = 1
    patch_path = tmp_path / "busy.patch"
    patch_path.write_text(NORMAL)
    started = time.monotonic()
    chosen, why = selector.analyze_patch(multiprocessing.get_context("fork"), str(patch_path),
                                         SlowSelector(busy=30), {n: None for n in ALL}, started + 20)
    assert chosen == ALL
    assert "resource limit" in why[0]
    assert time.monotonic() - started < 5
    assert not multiprocessing.active_children()


def test_stalled_child_under_the_cpu_limit_is_not_cut_off(tmp_path):
    """A host stall makes wall time pass without CPU use. Idle time past the
    CPU limit must not turn the commit into a select-everything fallback."""
    selector = load_selector()
    selector.MAX_COMMIT_SECONDS = 1
    patch_path = tmp_path / "stall.patch"
    patch_path.write_text(NORMAL)
    chosen, why = selector.analyze_patch(multiprocessing.get_context("fork"), str(patch_path),
                                         SlowSelector(busy=0.2, idle=2.5), {n: None for n in ALL},
                                         time.monotonic() + 20)
    assert chosen == {1}


def test_wall_backstop_is_capped_by_the_batch_budget(tmp_path):
    selector = load_selector()
    selector.MAX_COMMIT_WALL_SECONDS = 30
    patch_path = tmp_path / "hang.patch"
    patch_path.write_text(NORMAL)
    started = time.monotonic()
    chosen, why = selector.analyze_patch(multiprocessing.get_context("fork"), str(patch_path),
                                         SlowSelector(idle=60), {n: None for n in ALL}, started + 1)
    assert chosen == ALL
    assert "timed out" in why[0]
    assert time.monotonic() - started < 3
    assert not multiprocessing.active_children()


def test_batch_deadline_prevents_more_analysis(tmp_path):
    selector = load_selector()
    chosen, why = selector.analyze_patch(multiprocessing.get_context("fork"),
                                         str(tmp_path / "not-even-opened"), None,
                                         {n: None for n in ALL}, time.monotonic() - 1)
    assert chosen == ALL
    assert "deadline" in why[0]


@pytest.mark.parametrize("expression", [
    "1+" * 100_000 + "1",
    "[" * 10_000 + "0" + "]" * 10_000,
    "not " * 50_000 + "True",
])
def test_pathological_ast_does_not_break_program(sandbox, expression):
    run, _ = sandbox
    patch = diff("sqlglot/core.py", after="def first():\n    return " + expression + "\n")
    answers, _, elapsed = run({"a-ast": patch, "z-normal": NORMAL})
    assert answers["a-ast"] == ALL
    assert answers["z-normal"] == {0}
    assert elapsed < 5


SET_ATTR = 'class Gen:\n    RESERVED = {\n        "between",\n        "full",\n    }\n'
LITERAL_CASES = [
    # narrowed: a new word in a set display that nothing reads at import
    ("display-literal", SET_ATTR, SET_ATTR.replace('"between"', '"betweenx"'), False),
    # narrowed: '/' in a comment or '%' in a string is not code
    ("comment-slash", "FLAG = False  # on / off\n", "FLAG = True  # on / off\n", False),
    ("string-percent", 'FMT = {\n    "0": "%d/%m",\n}\n', 'FMT = {\n    "1": "%d/%m",\n}\n', False),
    # kept broad: real division, keys read at import, calls, dunders, enums, duplicates
    ("code-division", "VALUE = 10 / 2\n", "VALUE = 10 / 0\n", True),
    ("read-at-import", 'TABLE = {\n    "a": 1,\n}\nVALUE = TABLE["a"]\n',
     'TABLE = {\n    "ax": 1,\n}\nVALUE = TABLE["a"]\n', True),
    ("call-argument", 'X = dict(\n    a="foo",\n)\n', 'X = dict(\n    a="foox",\n)\n', True),
    ("dunder", '__all__ = [\n    "first",\n]\n', '__all__ = [\n    "firstx",\n]\n', True),
    ("enum", 'from enum import Enum\nclass E(Enum):\n    A = "a"\n',
     'from enum import Enum\nclass E(Enum):\n    A = "ax"\n', True),
    ("duplicate-key", 'M = {\n    "a": 1,\n    "ax": 2,\n}\n', 'M = {\n    "ax": 1,\n    "ax": 2,\n}\n', True),
    ("empty-string", 'S = [\n    "a",\n    "b",\n]\n', 'S = [\n    "",\n    "bx",\n]\n', True),
    ("comprehension", 'S = [\n    k for k in "ab" if k != "a"\n]\n', 'S = [\n    k for k in "ab" if k == "a"\n]\n', True),
]


@pytest.mark.parametrize("name,before,after,everything", LITERAL_CASES, ids=[c[0] for c in LITERAL_CASES])
def test_import_time_literal_edits(sandbox, name, before, after, everything):
    run, src = sandbox
    (src / "sqlglot/other.py").write_text(before)
    answers, _, _ = run({name: diff("sqlglot/other.py", before, after)})
    assert (answers[name] == ALL) is everything


# ---------------------------------------------------------------- comparison profile

CMP_SRC = (
    "def f(x, y):\n"            # 1
    "    if x is None:\n"       # 2  site 2:7  is
    "        return 1\n"        # 3
    "    if x < y:\n"           # 4  site 4:7  <
    "        return 2\n"        # 5
    "    if x == y:\n"          # 6  site 6:7  == (never profiled)
    "        return 3\n"        # 7
    "    if 0 < x < y:\n"       # 8  chained, never rewritten
    "        return 4\n"        # 9
    "    if y is None:\n"       # 10 site 10:7 is, flipped only outside tests
    "        return 5\n"        # 11
    "    return x != y\n"       # 12 site 12:11 !=, also runs at import
)
# test sets of the map: index -> tests
CMP_SETS = [[0], [1], [2], [3], [4], [5], [1, 2], [0, 3]]
# op indexes: 0 == 1 != 2 < 3 <= 4 > 5 >= 6 is 7 is-not
CMP_PROFILE = {
    "2:7": [6, (1 << 1) | (1 << 7), 0, 7, {"1": 7, "7": 7}],
    "4:7": [2, (1 << 3) | (1 << 0) | (1 << 4) | (1 << 5), 0, 6, {"0": 6, "3": 2, "4": 6, "5": 6}],
    "10:7": [6, (1 << 0) | (1 << 1) | (1 << 7), 1 << 0, 3, {"1": 3, "7": 3}],
    "12:11": [1, 1 << 0, 0, 1, {"0": 1}],
}


@pytest.fixture
def cmp_sandbox(sandbox, tmp_path):
    run, src = sandbox
    (src / "sqlglot/cmp.py").write_text(CMP_SRC)
    map_path = tmp_path / "map.json.gz"
    with gzip.open(map_path, "rt") as f:
        mapping = json.load(f)
    mapping["sets"] = CMP_SETS
    mapping["files"]["sqlglot/cmp.py"] = {"1": 7, "2": 7, "3": 0, "4": 6, "5": 6, "6": 6, "7": 1,
                                          "8": 6, "9": 2, "10": 3, "11": 3, "12": 1}
    mapping["import_lines"]["sqlglot/cmp.py"] = [12]
    with gzip.open(map_path, "wt") as f:
        json.dump(mapping, f)
    profile = {"tests": mapping["tests"], "sets": CMP_SETS, "sites": {"sqlglot/cmp.py": CMP_PROFILE}}
    with gzip.open(tmp_path / "cmp.json.gz", "wt") as f:
        json.dump(profile, f)

    def run_cmp(patches, per_test=False):
        run.env["CMP_PER_TEST"] = "1" if per_test else "0"
        return run(patches)

    return run_cmp, src


def cmp_diff(old, new, path="sqlglot/cmp.py", before=CMP_SRC):
    assert old in before
    return diff(path, before, before.replace(old, new, 1))


CMP_CASES = [
    # name, old text, new text, selection, selection with per-test narrowing
    ("equivalent-swap", "x is None", "x == None", set(), set()),
    ("equivalent-reformatted", "    if x is None:", "    if  x   ==None :", set(), set()),
    ("differing-swap", "x is None", "x is not None", {0, 3}, {0, 3}),
    ("per-test-subset", "x < y", "x <= y", {1, 2}, {2}),
    ("never-profiled-site", "x == y", "x != y", {1, 2}, {1, 2}),
    ("substitute-outside-family", "x < y", "x is y", {1, 2}, {1, 2}),
    ("chained-comparison", "0 < x < y", "0 <= x < y", {1, 2}, {1, 2}),
    ("unattributed-flip", "y is None", "y == None", {3}, {3}),
    ("runs-at-import", "x != y", "x == y", ALL, ALL),
    ("in-operator", "x == y", "x in y", {1, 2}, {1, 2}),
]


@pytest.mark.parametrize("name,old,new,expected,per_test", CMP_CASES, ids=[c[0] for c in CMP_CASES])
def test_comparison_profile(cmp_sandbox, name, old, new, expected, per_test):
    run, _ = cmp_sandbox
    patch = cmp_diff(old, new)
    answers, why, _ = run({name: patch})
    assert answers[name] == expected, why
    answers, why, _ = run({name: patch}, per_test=True)
    assert answers[name] == per_test, why


def test_comparison_swap_mixed_with_other_edit(cmp_sandbox):
    run, _ = cmp_sandbox
    # Same file, separate hunks: the whole file gets normal selection.
    mixed = CMP_SRC.replace("x is None", "x == None").replace("return 5", "return 50")
    # Separate files: the equivalent swap adds nothing, the other edit keeps its tests.
    two_files = cmp_diff("x is None", "x == None") + NORMAL
    answers, why, _ = run({"mixed": diff("sqlglot/cmp.py", CMP_SRC, mixed), "two-files": two_files})
    assert answers["mixed"] == {0, 3}, why
    assert answers["two-files"] == {0}, why


def test_two_swaps_in_one_file(cmp_sandbox):
    run, _ = cmp_sandbox
    after = CMP_SRC.replace("x is None", "x == None", 1)
    # Two swaps that each change no result: together they change none either.
    both = after.replace("    if x < y:", "    if x != y:", 1)
    answers, why, _ = run({"both": diff("sqlglot/cmp.py", CMP_SRC, both)})
    assert answers["both"] == set(), why
    # One swap changes a result: normal selection for the file, which still
    # includes the equivalent swap's line; per-test drops site 4's safe test.
    after = after.replace("    if x < y:", "    if x <= y:", 1)
    answers, why, _ = run({"mixed": diff("sqlglot/cmp.py", CMP_SRC, after)})
    assert answers["mixed"] == {0, 1, 2, 3}, why
    answers, why, _ = run({"mixed": diff("sqlglot/cmp.py", CMP_SRC, after)}, per_test=True)
    assert answers["mixed"] == {0, 2, 3}, why


def test_comparison_without_profile_is_normal(cmp_sandbox, tmp_path):
    run, _ = cmp_sandbox
    (tmp_path / "cmp.json.gz").unlink()
    answers, why, _ = run({"swap": cmp_diff("x is None", "x == None")})
    assert answers["swap"] == {0, 3}, why
