#!/bin/sh
# How this set was made and labeled (t20b). Swaps come from tools/cmpgen.py at
# sites the comparison profile (cmp.json.gz at e0584f8) calls equivalent, so
# e0584f8 selects nothing for each. Labels run each mutant's d56d66e selection
# (listed per mutant in manifest.json) with real pytest, not the full suite.
#   python tools/cmpgen.py work/sqlglot cmp.json.gz work/cmpall 2000 21   # then 36 picked
#   docker run --cpus 2 --memory 2g -e LABEL_N=2 ... br-t5-subtests \
#     python /w/tools/label.py /muts /src /muts/answers.json
