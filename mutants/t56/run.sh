#!/bin/sh
# t56 labels on the Legion (t52's kit and t47's labeler):
# docker run -d --name br-label-t56 --cpuset-cpus 8,9 --memory 2g --memory-swap 2g \
#   -v ~/br/t56:/kit -v ~/br/t56/src:/src python:3.13-slim sh /kit/mutants/t56/run.sh
set -eu
rm -rf /src/* /src/.[!.]* 2>/dev/null || true
cp -a /kit/pinned/. /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock
export LABEL_N=0 LABEL_DIST=load
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export LABEL_DESELECT=tests/test_parser.py::TestParser::test_max_nodes
python /kit/tools/t47_label.py /kit/mutants/t56 /src /kit/mutants/t56/answers.json
