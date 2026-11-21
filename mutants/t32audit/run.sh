#!/bin/sh
set -eu
cp -a /kit/pinned/. /src/
export LABEL_N=0 LABEL_DIST=load
export T32_DESELECT='["tests/test_executor.py::TestExecutor::test_execute_tpcds", "tests/test_parser.py::TestParser::test_max_nodes", "tests/test_sqlglotc.py::TestSQLGlotC::test_build_removes_obsolete_extensions", "tests/test_sqlglotc.py::TestSQLGlotC::test_dry_run_preserves_obsolete_extensions", "tests/test_sqlglotc.py::TestSQLGlotC::test_editable_install_removes_obsolete_extensions"]'
python -u /kit/tools/t32_label.py /kit/mutants/t32audit /src /kit/mutants/t32audit/answers.json
