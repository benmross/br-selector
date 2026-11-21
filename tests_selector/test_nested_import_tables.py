"""Nested literal entries can fail while a metaclass builds derived tables."""
import ast
import difflib
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('selector_t30', Path(__file__).resolve().parents[1] / 'selector.py')
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


@pytest.mark.parametrize('before,after', [
    ('["`"]', '[("`",)]'),
    ('["`"]', '[[]]'),
    ('["\\\\"]', '[0]'),
    ('{"%M": "%B"}', '{"%M": 0}'),
    ('{"%M": "%B"}', '{0: "%B"}'),
    ('[("/*", "*/")]', '[("/*",)]'),
    ('["`"]', '[""]'),
])
def test_nested_structure_is_not_a_same_shape_table(before, after):
    def scopes(value):
        return selector.Scopes(ast.parse('class A:\n    SETTINGS = ' + value + '\n'))
    assert selector.reshaped_names(scopes(before), scopes(after)) == {('A', 'SETTINGS')}


@pytest.mark.parametrize('before,after', [
    ('["`"]', '["!"]'),
    ('[("`", "`")]', '[("`", "!")]'),
    ('{"%M": "%B"}', '{"%M": "%Y"}'),
    ('[1, 2]', '[2, 3]'),
    ('[True]', '[False]'),
    ('{"x": 1, "y": 2}', '{"y": 2}'),
])
def test_same_type_values_and_ordinary_key_deletions_keep_reader_selection(before, after):
    assert not selector.literal_structure_changed(ast.parse(before, mode='eval').body,
                                                  ast.parse(after, mode='eval').body)


@pytest.mark.parametrize('replacement,expected', [('[("`",)]', {0, 1, 2}),
                                                  ('[[]]', {0, 1, 2}),
                                                  ('["!"]', {0})])
def test_import_reader_widens_nested_structure_beyond_class_instances(tmp_path, monkeypatch,
                                                                     replacement, expected):
    before = 'class A:\n    SETTINGS = ["`"]\n\ndef build(cls):\n    return cls.SETTINGS[0]\n'
    after = before.replace('["`"]', replacement)
    path = 'sqlglot/core.py'
    source = tmp_path / path
    source.parent.mkdir()
    source.write_text(before)
    monkeypatch.setattr(selector, 'SRC', str(tmp_path))
    mapping = {'sets': [[0]], 'files': {path: {'5': 0}}, 'fixtures': {},
               'classes': {'sqlglot.core:A': 0}, 'import_lines': {path: [5]}}
    tests = {n: (f'tests/test_{n}.py::test_x', f'tests/test_{n}.py', 1) for n in range(3)}
    instance = selector.Selector(tests, mapping)
    instance.index = None
    monkeypatch.setattr(instance, '_all_sources', lambda: {path: before})
    patch = 'diff --git a/' + path + ' b/' + path + '\n' + ''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), 'a/' + path, 'b/' + path))
    why = []
    assert instance.for_file(selector.parse_patch(patch)[0], why) == expected, why
