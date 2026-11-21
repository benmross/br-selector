"""Boundaries of the closed-reader proof for stored callbacks."""
import ast
import importlib.util
from pathlib import Path

import pytest
from test_patches import sandbox

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


@pytest.mark.parametrize('before,after,allowed',[
 ('class XGenerator:\n    TYPE_MAPPING={1:"TEXT"}\n','class XGenerator:\n    TYPE_MAPPING={1:"VARCHAR"}\n',True),
 ('class XGenerator:\n    TYPE_MAPPING={1:"TEXT"}\n','class XGenerator:\n    TYPE_MAPPING={1:""}\n',False),
 ('class XGenerator:\n    TYPE_MAPPING={"TEXT":1}\n','class XGenerator:\n    TYPE_MAPPING={"VARCHAR":1}\n',False),
 ('class XGenerator:\n    TYPE_MAPPING={1:parse("TEXT")}\n','class XGenerator:\n    TYPE_MAPPING={1:parse("VARCHAR")}\n',False),
 ('class XGenerator:\n    TRANSFORMS={1:"TEXT"}\n','class XGenerator:\n    TRANSFORMS={1:"VARCHAR"}\n',False),
 ('class X:\n    TYPE_MAPPING={1:"TEXT"}\n','class X:\n    TYPE_MAPPING={1:"VARCHAR"}\n',False),
])
def test_generator_type_values_only(before,after,allowed):
    assert bool(s.generator_table_changes(ast.parse(before),ast.parse(after))) is allowed


@pytest.mark.parametrize('before,after,allowed',[
 ('class X:\n    class Tokenizer:\n        KEYWORDS={"OLD":1}\n','class X:\n    class Tokenizer:\n        KEYWORDS={"NEW":1}\n',True),
 ('class X:\n    class Tokenizer:\n        KEYWORDS={"OLD":1}\n','class X:\n    class Tokenizer:\n        KEYWORDS={"":1}\n',False),
 ('class Tokenizer:\n    KEYWORDS={"OLD":1}\n','class Tokenizer:\n    KEYWORDS={"NEW":1}\n',False),
 ('class X:\n    class Tokenizer:\n        KEYWORDS={"OLD":1,"OTHER":2}\n','class X:\n    class Tokenizer:\n        KEYWORDS={"OTHER":1,"OTHER":2}\n',False),
 ('class X:\n    class Tokenizer:\n        KEYWORDS={1:"OLD"}\n','class X:\n    class Tokenizer:\n        KEYWORDS={1:"NEW"}\n',False),
 ('class X:\n    class Tokenizer:\n        FUNCTIONS={"OLD":1}\n','class X:\n    class Tokenizer:\n        FUNCTIONS={"NEW":1}\n',False),
])
def test_keyword_keys_exclude_base_collisions_and_registries(before,after,allowed):
    assert s.dialect_keyword_changes(ast.parse(before),ast.parse(after)) is allowed


@pytest.mark.parametrize('before,allowed',[
 ('class XGenerator:\n    TRANSFORMS={1:rename_func("OLD")}\n',True),
 ('class XGenerator:\n    TRANSFORMS={1:rename_func("OLD")()}\n',False),
 ('class XGenerator:\n    TRANSFORMS={1:factory("OLD")}\n',False),
 ('class XGenerator:\n    TRANSFORMS={1:rename_func(name="OLD")}\n',False),
 ('class XGenerator:\n    TYPE_MAPPING={1:rename_func("OLD")}\n',False),
 ('class XGenerator:\n    TRANSFORMS={"OLD":rename_func("UNCHANGED")}\n',False),
])
def test_rename_factory_is_only_an_unchanged_closure_constructor(before,allowed):
    assert s.runtime_rename_changes(ast.parse(before),ast.parse(before.replace('OLD','NEW'))) is allowed


@pytest.mark.parametrize('rel,expected',[('sqlglot/typing/local.py',{4}),('sqlglot/other.py',set())])
def test_function_doc_keeps_code_constant_observer(sandbox,rel,expected):
    run, src = sandbox
    mapping = run.env["MAP_PATH"]
    # TestTyping reads the function's code constant without calling it, so
    # its ID has no runtime coverage of the changed function.
    p=src/rel
    p.parent.mkdir(parents=True,exist_ok=True)
    before='def other():\n    "old"\n    return 3\n'
    after=before.replace('old','new')
    p.write_text(before)
    # This sandbox's pinned audit is deliberately absent: exercise the
    # complete AST proof and its separate observer through a direct Selector.
    import gzip,json
    m=json.load(gzip.open(mapping,'rt'))
    tests=json.load(open(Path(run.env['DATA_DIR'])/'tests.json'))['tests']
    nums={t['number']:(t['id'],t['file'],1) for t in tests}
    obj=s.Selector(nums,m)
    obj.index={'@pinned_string_audit':True}
    obj.by_file['tests/test_typing.py']={4}
    obj._single_file_patch=True
    obj.docstrings_unobserved=lambda *args:True
    from test_patches import diff
    s.SRC=str(src)
    why=[]
    assert obj.for_file(s.parse_patch(diff(rel,before,after))[0],why)==expected
