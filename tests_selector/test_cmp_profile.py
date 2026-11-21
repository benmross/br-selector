"""The comparison probe (tools/cmp_profile.py): substitutes are only judged
on operands whose comparisons are side-effect-free builtins; everything else
marks the whole family as differing."""
import ast
import enum
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cp():
    spec = importlib.util.spec_from_file_location("cmp_profile_t", ROOT / "tools" / "cmp_profile.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.set_context("t")
    return mod


EQ, NE, LT, LE, GT, GE, IS, ISNOT = range(8)


def mask(cp, op, pairs):
    sid = 0
    for a, b in pairs:
        cp.PROBES[op](sid, a, b)
    return cp._store["t"].get(sid)


def bits(*ops):
    return sum(1 << o for o in ops)


class Color(enum.Enum):
    RED = 1
    BLUE = 2


class StrColor(str, enum.Enum):
    RED = "red"


class CustomEq:
    def __eq__(self, other):
        return True

    __hash__ = object.__hash__


class Plain:
    pass


class NotBool:
    def __lt__(self, other):
        return [1]


def test_is_none_on_plain_values_agrees_with_eq(cp):
    assert mask(cp, IS, [(None, None), (1, None), ("a", None), (Plain(), None)]) == bits(NE, ISNOT)


def test_enum_identity_agrees_with_eq(cp):
    assert mask(cp, IS, [(Color.RED, Color.RED), (Color.RED, Color.BLUE)]) == bits(NE, ISNOT)


def test_str_enum_is_against_str_differs(cp):
    assert mask(cp, IS, [(StrColor.RED, "red")]) & bits(EQ)


def test_order_records_equality(cp):
    assert not mask(cp, LT, [(1, 2), (3, 2)]) & bits(LE)
    assert mask(cp, LT, [(2, 2)]) & bits(LE)


def test_tuple_operands(cp):
    assert mask(cp, LT, [((23, 1), (23, 12))]) == bits(EQ, GT, GE)


def test_custom_eq_marks_family(cp):
    assert mask(cp, IS, [(CustomEq(), None)]) == bits(EQ, NE, ISNOT)


def test_non_bool_result_marks_family(cp):
    assert mask(cp, LT, [(NotBool(), 1)]) == bits(EQ, NE, LE, GT, GE)


def test_exception_in_substitute_marks_family(cp, monkeypatch):
    def boom(a, b):
        raise TypeError("no order")

    cp.FUNCS[LE] = boom  # this module instance is private to the test
    probe = cp._make(LT)
    assert probe(0, 1, 2) is True
    assert cp._store["t"][0] == bits(EQ, NE, LE, GT, GE)


def test_unordered_operands_raise_as_before(cp):
    p = Plain()
    with pytest.raises(TypeError):
        cp.PROBES[LT](0, p, p)
    assert 0 not in cp._store["t"]


def test_rewrite_leaves_chained_and_membership(cp):
    tree = ast.parse("a < b < c\nx in y\nx not in y\na == b\n")
    out = cp._Rewrite("m.py").visit(tree)
    kinds = [type(s.value).__name__ for s in out.body]
    assert kinds == ["Compare", "Compare", "Compare", "Call"]
    assert cp._sites[-1] == ("m.py", 4, 0, EQ)


def test_probe_returns_original_result(cp):
    assert cp.PROBES[LE](0, 2, 2) is True
    assert cp.PROBES[ISNOT](1, None, None) is False


def test_containers_against_none(cp):
    assert mask(cp, IS, [([1], None), ({}, None), (None, None)]) == bits(NE, ISNOT)


def test_containers_against_each_other_are_unsafe(cp):
    assert mask(cp, IS, [([1], [1])]) == bits(EQ, NE, ISNOT)


def test_expr_eq_against_none_only(cp):
    class Expr:
        def __eq__(self, other):
            return self is other or (type(self) is type(other) and hash(self) == hash(other))

        def __ne__(self, other):
            return not self.__eq__(other)

        __hash__ = object.__hash__

    Expr.__eq__.__module__ = Expr.__ne__.__module__ = "sqlglot.expressions.core"
    Expr.__eq__.__qualname__, Expr.__ne__.__qualname__ = "Expr.__eq__", "Expr.__ne__"
    assert mask(cp, IS, [(Expr(), None)]) == bits(NE, ISNOT)
    cp._store["t"].clear()
    assert mask(cp, IS, [(Expr(), Expr())]) == bits(EQ, NE, ISNOT)
