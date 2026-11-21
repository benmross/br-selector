#!/bin/sh
set -eu
cp -a /kit/pinned/. /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock
export LABEL_N=2 LABEL_DIST=load
python /kit/tools/label.py /kit/mutants/t30 /src /kit/mutants/t30/answers.json
