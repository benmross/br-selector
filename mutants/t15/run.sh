#!/bin/sh
# Label t15's mutants inside python:3.13-slim, one pytest worker, OOM refused:
# docker run --rm --name br-t15-label --cpus 2 --memory 2g --memory-swap 2g \
#   -v <worktree>:/kit:ro -v <kit>/sample:/kit/sample:ro -v <kit>/work/sqlglot:/kit/work/sqlglot:ro \
#   -v <worktree>/mutants/t15:/muts c0e8df938051 sh /kit/mutants/t15/run.sh
set -e
mkdir -p /src && cp -r /kit/work/sqlglot/sqlglot /kit/work/sqlglot/tests /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock 2>&1 | grep -v notice | tail -1
LABEL_N=1 python /kit/tools/label.py /muts /src /muts/answers.json
