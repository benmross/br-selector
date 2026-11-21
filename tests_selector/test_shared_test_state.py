"""A passing test can poison imported state observed by later tests."""
import ast
import difflib
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('selector_test_state',Path(__file__).resolve().parents[1]/'selector.py')
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


def changed(before,after,line):
    return selector.changed_test_state(ast.parse(before),ast.parse(after),{line})


BASE = '''from sqlglot.dialects import Snowflake
from sqlglot import Dialect
def test_patch():
    original = Snowflake.parser_class
    try:
        Snowflake.parser_class = object
        assert True
    finally:
        Snowflake.parser_class = original
'''


@pytest.mark.parametrize('old,new,line',[
    ('original = Snowflake.parser_class','original = Dialect.parser_class',4),
    ('Snowflake.parser_class = original','Snowflake.parser_class = Dialect.parser_class',9),
    ('Snowflake.parser_class = original','pass',9),
])
def test_bad_cleanup_and_bad_saved_original_are_shared(old,new,line):
    assert changed(BASE,BASE.replace(old,new),line)=='test_patch'


def test_imported_registry_alias_mutation_is_shared():
    before='from sqlglot import Parser\ndef test_x():\n    state = Parser.FUNCTIONS\n    state.clear()\n'
    assert changed(before,before.replace('clear()','pop("X")'),4)=='test_x'


def test_inherited_table_alias_is_still_shared():
    before='from sqlglot import Tokenizer\ndef test_x():\n    class Parent(Tokenizer):\n        pass\n    state = Parent.KEYWORDS\n    state.clear()\n'
    assert changed(before,before.replace('clear()','pop("SELECT")'),6)=='test_x'


def test_runtime_dialect_class_creation_registers_shared_state():
    before='from sqlglot import Dialect\ndef test_x():\n    class Custom(Dialect):\n        pass\n'
    assert changed(before,before.replace('Custom','Snowflake'),3)=='test_x'


def test_global_binding_write_is_shared():
    before='state = {}\ndef test_x():\n    global state\n    state = {}\n'
    assert changed(before,before.replace('    state = {}','    state = None'),4)=='test_x'


@pytest.mark.parametrize('before',[
    'import sqlglot as sg\ndef test_x():\n    class Custom(sg.Dialect):\n        pass\n',
    'from sqlglot import Dialect\ndef test_x():\n    Base = Dialect\n    class Custom(Base):\n        pass\n',
])
def test_qualified_and_aliased_dialect_registration_is_shared(before):
    after=before.replace('Custom','Snowflake')
    line=next(i for i,l in enumerate(before.splitlines(),1) if 'class Custom' in l)
    assert changed(before,after,line)=='test_x'


def test_local_and_instance_mutation_do_not_widen():
    before='from sqlglot import Parser\ndef test_x(self):\n    state = {}\n    state["x"] = 1\n    self.flag = True\n'
    assert changed(before,before.replace('= 1','= 2'),4) is None


def test_parameter_shadowing_import_does_not_widen():
    before='from sqlglot import Parser\ndef helper(Parser):\n    Parser.flag = True\n'
    assert changed(before,before.replace('True','False'),3) is None


def test_cleanup_edit_selects_later_tests(tmp_path,monkeypatch):
    path='tests/test_producer.py'; source=tmp_path/path;source.parent.mkdir();source.write_text(BASE)
    monkeypatch.setattr(selector,'SRC',str(tmp_path))
    tests={n:(f'tests/test_{n}.py::test_x',f'tests/test_{n}.py',1) for n in range(3)}
    mapping={'sets':[[0]],'files':{path:{str(i):0 for i in range(1,10)}},'fixtures':{},
             'classes':{},'import_lines':{}}
    instance=selector.Selector(tests,mapping); instance.index=None
    after=BASE.replace('original = Snowflake.parser_class','original = Dialect.parser_class')
    patch='diff --git a/'+path+' b/'+path+'\n'+''.join(difflib.unified_diff(
        BASE.splitlines(True),after.splitlines(True),'a/'+path,'b/'+path))
    why=[]
    assert instance.for_file(selector.parse_patch(patch)[0],why)=={0,1,2},why
