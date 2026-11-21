#!/bin/sh
# Label t14's mutants inside python:3.13-slim (see run command in reviews/t14-review.md).
set -e
mkdir -p /src && cp -r /kit/work/sqlglot/sqlglot /kit/work/sqlglot/tests /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock 2>&1 | grep -v notice | tail -1
python /kit/tools/label.py /muts /src /muts/answers.json
