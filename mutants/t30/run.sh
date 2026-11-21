#!/bin/sh
set -eu
cp -a /kit/pinned/. /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock
export LABEL_N=2 LABEL_DIST=load
# This pinned test OOMs even alone in a fresh 1 GiB container. Never accept
# an OOM-tainted label or silently represent this deselection as a full oracle.
export LABEL_DESELECT=tests/test_parser.py::TestParser::test_max_nodes
python /kit/tools/label.py /kit/mutants/t30 /src /kit/mutants/t30/answers.json
