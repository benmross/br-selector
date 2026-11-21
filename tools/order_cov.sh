#!/bin/sh
# t24a order passes, inside python:3.13-slim with the map build's requirements.
# usage: order_cov.sh seq|rev|fork   (output under /out/<pass>)
# seq/rev: one process, per-test coverage contexts, class and fixture traces,
#          default or reversed order (same flags as tools/build_coverage.sh minus -n 4).
# fork:    two parents, each runs its share of items in forked children (tools/fork_each.py).
set -e
mode=$1
mkdir -p /src && cp -r /kit/work/sqlglot/sqlglot /kit/work/sqlglot/tests /src/
cd /src
pip install -q --root-user-action=ignore -r /kit/requirements.lock coverage pytest-cov 2>&1 | grep -v notice | tail -2
o=/out/$mode; mkdir -p $o
export SKIP_INTEGRATION=0 PYTHONPATH=/src:/kit/tools FIXTURE_TRACE_OUT=$o/fixtures CLASS_TRACE_OUT=$o/classes COVERAGE_CORE=ctrace
case $mode in
seq|rev)
  extra=""; [ $mode = rev ] && extra="-p order_reverse"
  python -m pytest tests -q -p fixture_trace -p class_trace $extra -p no:cacheprovider \
    --cov=. --cov-context=test --cov-report= -o addopts= 2>&1 | grep -v "^[.usFEx]*\s*\[" | tail -8
  cp .coverage $o/coverage.db ;;
fork)
  unset FIXTURE_TRACE_OUT CLASS_TRACE_OUT
  mkdir -p $o/items
  for i in 0 1; do
    FORK_OUT=$o/items FORK_SHARD=$i/2 python -m pytest tests -q -p fixture_trace -p class_trace -p fork_each \
      -p no:cacheprovider -o addopts= > $o/log.$i 2>&1 &
  done
  wait
  tail -n 3 $o/log.0 $o/log.1 || true ;;
esac
