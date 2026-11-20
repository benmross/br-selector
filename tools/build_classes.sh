#!/bin/sh
set -e
cd /src
pip install -q -r /kit/requirements.lock 2>&1 | grep -v notice | tail -2
export SKIP_INTEGRATION=0 PYTHONPATH=/src:/kit/tools CLASS_TRACE_OUT=/out/classes
python -m pytest tests -q -n 4 -p class_trace -p no:cacheprovider -o addopts= 2>&1 | tail -8
