#!/bin/sh
# t52 labels on the Legion (t47's labeler, t30/t44 container recipe):
# docker run -d --name br-label-t52 --cpuset-cpus 10-11 --memory 2g --memory-swap 2g \
#   -v ~/br/t52:/kit -v ~/br/t52/src:/src python:3.13-slim sh /kit/mutants/t52/run.sh
set -eu
rm -rf /src/* /src/.[!.]* 2>/dev/null || true
cp -a /kit/pinned/. /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock
export LABEL_N=0 LABEL_DIST=load
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export LABEL_DESELECT=tests/test_parser.py::TestParser::test_max_nodes
python /kit/tools/t47_label.py /kit/mutants/t52 /src /kit/mutants/t52/answers.json
