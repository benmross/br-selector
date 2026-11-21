#!/bin/sh
set -eu
python -c 'from pathlib import Path; m=dict(x.split(":",1) for x in Path("/proc/meminfo").read_text().splitlines()); assert int(m["MemAvailable"].split()[0]) >= 5*1024*1024, "less than 5 GiB available"'
cp -a /kit/pinned/. /src/
export LABEL_N=0 LABEL_DIST=load T32_REQUIRE_CLEAN_BASELINE=1
export T32_DESELECT='["tests/test_executor.py::TestExecutor::test_execute_tpcds", "tests/test_parser.py::TestParser::test_max_nodes", "tests/test_sqlglotc.py::TestSQLGlotC::test_build_removes_obsolete_extensions", "tests/test_sqlglotc.py::TestSQLGlotC::test_dry_run_preserves_obsolete_extensions", "tests/test_sqlglotc.py::TestSQLGlotC::test_editable_install_removes_obsolete_extensions"]'
if [ ! -f /kit/mutants/t32audit/answers.json.baseline.n0 ]; then
    cp /kit/mutants/t32audit/answers.json.baseline /kit/mutants/t32audit/answers.json.baseline.n0
    rm /kit/mutants/t32audit/answers.json.baseline
fi
python -u /kit/tools/t32_label.py /kit/mutants/t32audit /src /kit/mutants/t32audit/answers.json
python -u /kit/tools/t32_label.py /kit/mutants/t32 /src /kit/mutants/t32/answers.json
