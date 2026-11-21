"""Boundaries of the closed-reader proof for stored callbacks."""
import ast
import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('runtime_selector',Path(__file__).resolve().parents[1]/'selector.py')
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


@pytest.mark.parametrize('before,allowed',[
 ('class XGenerator:\n    TRANSFORMS = {1: lambda s, e: s.sql(e, "this")}\n',True),
 ('class XGenerator:\n    TRANSFORMS = {1: lambda s, e: f"cast({s.sql(e)} as TEXT)"}\n',True),
 ('AFTER_HAVING_MODIFIER_TRANSFORMS = {1: lambda s, e: "this"}\n',True),
 ('class XGenerator:\n    TRANSFORMS = {1: lambda s, e="this": e}\n',False),
 ('class XGenerator:\n    TRANSFORMS = {1: (lambda: "this")()}\n',False),
 ('class XGenerator:\n    TRANSFORMS = {1: factory(lambda: "this")}\n',False),
 ('class XGenerator:\n    TRANSFORMS = {"this": lambda s, e: e}\n',False),
 ('class XGenerator:\n    TRANSFORMS = {1: rename_func("this")}\n',False),
 ('class XGenerator:\n    TYPE_MAPPING = {1: "this"}\n',False),
 ('class X:\n    TRANSFORMS = {1: lambda s, e: "this"}\n',False),
 ('@decorator\nclass XGenerator:\n    TRANSFORMS = {1: lambda s, e: "this"}\n',False),
 ('def register():\n    TRANSFORMS = {1: lambda s, e: "this"}\n',False),
])
def test_stored_lambda_boundary(before,allowed):
    after=before.replace('this','other').replace('TEXT','VARCHAR')
    assert bool(s.runtime_lambda_changes(ast.parse(before),ast.parse(after))) is allowed


def test_second_non_string_effect_invalidates_callback_proof():
    before='class XGenerator:\n    TRANSFORMS = {1: lambda s, e: "old"}\n'
    assert not s.runtime_lambda_changes(ast.parse(before),ast.parse(before.replace('old','new').replace('1:', '2:')))


def test_changed_reader_tree_invalidates_pinned_audit():
    assert s.source_fingerprint({'a.py':'x=1\n'})!=s.source_fingerprint({'a.py':'x=2\n'})


@pytest.mark.parametrize('before,after,allowed',[
 ('"old"\n','"new"\n',True),
 ('class X:\n    "old"\n','class X:\n    "new"\n',True),
 ('class X:\n    VALUE=1\n    "old"\n','class X:\n    VALUE=1\n    "new"\n',True),
 ('def f():\n    "old"\n    return 1\n','def f():\n    "new"\n    return 1\n',True),
 ('VALUE="old"\n','VALUE="new"\n',False),
 ('"old"\nVALUE=1\n','"new"\nVALUE=2\n',False),
 ('"old"\n','f"{new}"\n',False),
])
def test_inert_string_value_is_never_executable(before,after,allowed):
    assert s.inert_string_changes(ast.parse(before),ast.parse(after)) is allowed
