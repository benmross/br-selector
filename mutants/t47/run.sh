#!/bin/sh
set -eu
cp -a /pinned/. /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock
export LABEL_N=0 LABEL_DIST=load
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export LABEL_DESELECT=tests/test_parser.py::TestParser::test_max_nodes
python /kit/tools/t47_label.py /kit/mutants/t47 /src /kit/mutants/t47/answers.json
