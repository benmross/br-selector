# Inert string statements

All AST fields must agree except str values that are direct Expr.value constants. This covers module/class/function docstrings and later attribute-documentation strings. Assigned strings, returned strings, f-strings, and executable expressions fail the proof. The patch must modify one file, preserve the encoding rules, and pass syntax/compile checks.

The audit is tied to the complete pinned Python source fingerprint. All __doc__/getdoc/doctest/pdoc consumers were inspected: tests/test_docs.py defines unittest.load_tests, which pytest does not invoke and contributes no numbered tests; tests/leakcheck.py reads only its own module doc in main(), which no numbered test executes; Expr.__init_subclass__ reads class documentation, including inherited documentation; expression-class docstrings therefore retain the conservative selection. Inspect-based signature/class readers do not consume documentation. Neither documentation consumer may gain mapped runtime users, numbered tests, or fixture readers. Source-file fixture readers retained by for_file still apply.

No effect reaches a numbered runtime test. Return the empty selection before class/enum import fallback. Changes to an assigned Enum value or other executable string are excluded by AST position.
