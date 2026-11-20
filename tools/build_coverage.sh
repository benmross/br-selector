#!/bin/sh
# Runs inside python:3.13-slim with the sqlglot checkout at /src (writable copy).
set -e
cd /src
pip install -q -r /kit/requirements.lock coverage pytest-cov 2>&1 | tail -2
export SKIP_INTEGRATION=0 PYTHONPATH=/src:/kit/tools FIXTURE_TRACE_OUT=/out/fixtures COVERAGE_CORE=ctrace
python -m pytest tests -q -n 4 -p fixture_trace -p no:cacheprovider \
  --cov=sqlglot --cov=tests --cov-context=test --cov-report= \
  -o addopts= 2>&1 | tail -15
cp .coverage /out/coverage.db 2>/dev/null || python -m coverage combine && cp .coverage /out/coverage.db
