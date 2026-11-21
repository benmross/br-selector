#!/bin/sh
# Runs inside python:3.13-slim (same requirements as build_coverage.sh) with
# the pinned sqlglot copied to /src. Records which comparison-operator swaps
# change any result (tools/cmp_profile.py), per test phase, into /out/cmp.*.json.
set -e
rm -rf /src && mkdir -p /src && (cd ${SQLGLOT_DIR:-/kit/work/sqlglot} && tar cf - --exclude=.git --exclude=sqlglot-integration-tests .) | (cd /src && tar xf -)
cd /src
find . -name __pycache__ -prune -exec rm -rf {} +
pip install -q --root-user-action=ignore -r /kit/requirements.lock 2>&1 | grep -v notice | tail -2
export SKIP_INTEGRATION=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/src:/kit/tools/cmpsite:/kit/tools
export CMP_PROFILE_OUT=/out/cmp CMP_PROFILE_ROOT=/src
rm -f /out/cmp.*.json /out/cmp.*.jsonl
start=$(date +%s)
python -m pytest tests -q -n "${CMP_N:-2}" -p cmp_profile -p no:cacheprovider -o addopts= > /tmp/run.log 2>&1 || true
grep -v "^[.usx]*\s*\[" /tmp/run.log | tail -8
# A crashed worker (memory) loses the test it was running: run those alone.
crashed=$(sed -n "s/.*crashed while running '\(.*\)'.*/\1/p" /tmp/run.log | sort -u)
if [ -n "$crashed" ]; then
  echo "rerunning alone: $crashed"
  python -m pytest $crashed -q -p no:xdist -p cmp_profile -p no:cacheprovider -o addopts= 2>&1 | tail -3
fi
echo "profile seconds $(( $(date +%s) - start ))"
