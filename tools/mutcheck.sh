#!/bin/sh
# Pull labeled mutants from Legion, run the selector on them, report misses.
cd "$(dirname "$0")/.."
rsync -az legion:br/work/mut/ work/mut/ 2>/dev/null
python3 - <<'PY'
import glob, json, os, shutil
ans = {}
for f in glob.glob("work/mut/answers.*.json"):
    try: ans.update(json.load(open(f))["commits"])
    except Exception: pass
d = "work/mutset"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d + "/commits")
shutil.copy("sample/tests.json", d)
for cid in ans:
    shutil.copy(f"work/mut/commits/{cid}.patch", f"{d}/commits/")
json.dump({"commits": ans}, open(f"{d}/answers.json", "w"))
print(len(ans), "labeled,", sum(1 for v in ans.values() if v["failing"]), "break something")
PY
DATA_DIR=work/mutset SQLGLOT_SRC=work/sqlglot MAP_PATH=map.json.gz INDEX_PATH=index.json.gz python3 selector.py > work/mutout.jsonl 2> work/mutwhy.log
python3 tools/report.py work/mutset work/mutout.jsonl | grep -E "MISS|total"
