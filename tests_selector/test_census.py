"""The census packer hits each target cost to the millisecond."""
import importlib.util
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_selector():
    spec = importlib.util.spec_from_file_location("census_selector", ROOT / "selector.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def suite():
    rnd = random.Random(7)
    ms = [28817, 21454, 6686, 3863] + [0] * 94 + [1] * 408 + [rnd.randint(2, 73) for _ in range(1112)]
    return {n: (f"tests/t.py::test_{n}", "tests/t.py", v) for n, v in enumerate(ms)}


@pytest.mark.parametrize("seconds", [0, 1, 7, 12, 49, 60])
def test_census_packer_hits_target(seconds):
    selector = load_selector()
    tests = suite()
    workers = selector.census_workers(tests, seconds * 1000)
    assert workers is not None
    assert len(workers) == 4 and all(workers)
    assert sorted(n for w in workers for n in w) == sorted(tests)
    loads = [sum(tests[n][2] for n in w) for w in workers]
    assert max(loads) + 2000 * len(workers) == 28817 + 8000 + seconds * 1000
    assert sorted(loads)[-2] < max(loads)


def test_census_x_rules():
    selector = load_selector()
    tests = {0: ("a", "f", 1), 1: (selector.CENSUS_TPCDS, "f", 1), 2: (selector.CENSUS_MAX_NODES, "f", 1)}
    everything = set(tests)
    assert selector.census_x(1, everything, ["x.py: syntax error, importers"], tests) == 1000
    assert selector.census_x(1, everything, ["commit analysis timed out: everything"], tests) == 0
    assert selector.census_x(1, {0}, [], tests) == 0
    assert selector.census_x(2, everything, ["p.py:3 also runs at import, everything"], tests) == 1000
    assert selector.census_x(2, everything, ["p.py:3 module constant read at import, everything"], tests) == 7000
    assert selector.census_x(2, everything, ["p.py: possible import failure, everything"], tests) == 49000
    assert selector.census_x(2, everything, ["p.py: syntax error, importers"], tests) == 0
    assert selector.census_x(3, {1}, [], tests) == 1000
    assert selector.census_x(3, {1, 2}, [], tests) == 12000
    assert selector.census_x(3, {0}, [], tests) == 0
    assert selector.census_x(3, everything, [], tests) == 0


def test_census_x_mode4_trigger_classes():
    selector = load_selector()
    tests = {0: ("a", "f", 1), 1: ("b", "f", 1)}
    everything = set(tests)
    fell = "p.py: possible import failure, everything"
    assert selector.census_x(4, everything, ["p.py: could_raise trigger tok-str", fell], tests) == 1000
    assert selector.census_x(4, everything, ["p.py: could_raise trigger tok-word", fell], tests) == 7000
    for other in ("tok-op", "tok-name", "lex-word", "lex-op", "lex-name"):
        assert selector.census_x(4, everything, [f"p.py: could_raise trigger {other}", fell], tests) == 49000
    assert selector.census_x(4, everything, ["p.py:3 also runs at import, everything"], tests) == 0
    assert selector.census_x(4, everything, ["commit analysis timed out: everything"], tests) == 0
    assert selector.census_x(4, {0}, [], tests) == 0


def _fp(selector, old, new):
    import difflib
    diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), "a/p.py", "b/p.py"))
    text = "diff --git a/p.py b/p.py\n" + diff
    return selector.parse_patch(text)[0]


def test_could_raise_trigger_branches_match_could_raise():
    selector = load_selector()
    cases = [
        ('X = {"a": 1}\n', 'X = {"b": 1}\n', "tok-str"),
        ("X = 1\n", "X = [i for i in Y]\n", "tok-word"),
        ("X = 4\n", "X = 4 / 2\n", "tok-op"),
        ("X = A\n", "X = B\n", "tok-name"),
        ("X = 1\n", "X = 1  # see foo/bar\n", None),
        ('X = "a b"\n', 'X = "b a"\n', None),
    ]
    for old, new, want in cases:
        fp = _fp(selector, old, new)
        got = selector.could_raise_trigger(fp, old, new)
        assert got == want, (old, new, got)
        assert bool(got) == selector.could_raise(fp, old, new)
