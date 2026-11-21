#!/bin/sh
# Label t24a's mutants inside python:3.13-slim on the Legion, OOM refused:
# docker run --rm --name br-t24a-label --cpuset-cpus 8,9 --memory 3g --memory-swap 3g \
#   -v ~/br/t24a:/kit:ro -v ~/br/sample:/kit/sample:ro -v ~/br/work/sqlglot:/kit/work/sqlglot:ro \
#   -v ~/br/t24a/mutants/t24a:/muts c0e8df938051 sh /kit/mutants/t24a/run.sh
set -e
mkdir -p /src && cp -r /kit/work/sqlglot/sqlglot /kit/work/sqlglot/tests /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock 2>&1 | grep -v notice | tail -1
LABEL_N=${LABEL_N:-2} python /kit/tools/label.py /muts /src /muts/answers.json
