#!/bin/sh
# Runs inside python:3.13-slim with the sqlglot checkout at /src (writable copy).
# One pass records line coverage per test, files each test opens, and sqlglot
# classes each test instantiates. Process pools run inline (tools/inprocess.py).
set -e
cd /src
pip install -q --root-user-action=ignore -r /kit/requirements.lock coverage pytest-cov 2>&1 | grep -v notice | tail -2
export SKIP_INTEGRATION=0 PYTHONPATH=/src:/kit/tools FIXTURE_TRACE_OUT=/out/fixtures CLASS_TRACE_OUT=/out/classes COVERAGE_CORE=ctrace
python -m pytest tests -q -n 4 -p fixture_trace -p class_trace -p no:cacheprovider \
  --cov=.  --cov-context=test --cov-report= \
  -o addopts= 2>&1 | grep -v "^[.u]*\s*\[" | tail -15
cp .coverage /out/coverage.db
