#!/bin/sh
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
export LABEL_N=0 LABEL_DIST=load
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
if [ -f /kit/cache-order.request ]; then
    python /kit/mutants/t30/cache_order.py
    rm -f /kit/cache-order.request
fi
# This pinned test OOMs even alone in a fresh 1 GiB container. Never accept
# an OOM-tainted label or silently represent this deselection as a full oracle.
export LABEL_DESELECT=tests/test_parser.py::TestParser::test_max_nodes
python /kit/tools/label.py /kit/mutants/t30 /src /kit/mutants/t30/answers.json
