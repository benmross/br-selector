#!/bin/sh
# Fast local loop: run the selector on the sample set without Docker and score it.
cd "$(dirname "$0")/.."
DATA_DIR=sample SQLGLOT_SRC=work/sqlglot MAP_PATH=map.json.gz python3 selector.py > work/out.jsonl 2> work/why.log
python3 score.py sample sample/answers.json work/out.jsonl
