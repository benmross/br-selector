#!/bin/sh
# Label t41's string-literal mutants on the Legion (t30's container recipe):
# docker run -d --name br-label-t41 --cpuset-cpus 8,9 --memory 2g --memory-swap 2g \
#   -v ~/br/t41:/kit -v ~/br/t41/src:/src python:3.13-slim sh /kit/mutants/t41/run.sh
set -eu
python - <<'PY'
from pathlib import Path
import shutil
for path in Path('/src').iterdir():
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
PY
cp -a /kit/pinned/. /src/
pip install -q --root-user-action=ignore -r /kit/requirements.lock
export LABEL_N=${LABEL_N:-2} LABEL_DIST=load
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# Same deselection as t30: this pinned test OOMs even alone in 1 GiB.
export LABEL_DESELECT=tests/test_parser.py::TestParser::test_max_nodes
python /kit/tools/label.py /kit/mutants/t41 /src /kit/mutants/t41/answers.json
