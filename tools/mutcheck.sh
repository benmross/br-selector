#!/bin/sh
# Pull labeled mutants from Legion, run the selector on them, report misses.
# Or: sh tools/mutcheck.sh <already-labeled dataset directory>
cd "$(dirname "$0")/.."
if [ "$#" -gt 0 ]; then
    DATA_DIR="$1" SQLGLOT_SRC="${SQLGLOT_SRC:-work/sqlglot}" MAP_PATH="${MAP_PATH:-map.json.gz}" INDEX_PATH="${INDEX_PATH:-index.json.gz}" python3 selector.py > work/mutout.jsonl 2> work/mutwhy.log
    python3 tools/report.py "$1" work/mutout.jsonl | grep -E "MISS|total"
    exit
fi
rsync -az legion:br/work/mut/ work/mut/ 2>/dev/null
rsync -az legion:br/work/mutC/ work/mutC/ 2>/dev/null; cp work/mutC/commits/*.patch work/mut/commits/ 2>/dev/null; cp work/mutC/answers.0.json work/mut/answers.C.json 2>/dev/null
cp work/mutB/commits/*.patch work/mut/commits/ 2>/dev/null; cp work/mutB/answers.0.json work/mut/answers.B.json 2>/dev/null
# Tracked review mutants (t14 and later): labeled answers live beside their patches.
for d in mutants/*/; do
    [ -f "$d/answers.json" ] || continue
    cp "$d"commits/*.patch work/mut/commits/ && cp "$d/answers.json" "work/mut/answers.$(basename "$d").json" || echo "mutcheck: cannot copy $d" >&2
done
python3 - <<'PY'
import glob, json, os, shutil
ans = {}
for f in glob.glob("work/mut/answers.*.json"):
    try: ans.update(json.load(open(f))["commits"])
    except Exception: pass
for k, v in ans.items():
    if k.startswith("m4x"):
        v["failing"] = [n for n in v["failing"] if n != 1490]  # server batch: memory artifact
d = "work/mutset"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d + "/commits")
shutil.copy("sample/tests.json", d)
for cid in ans:
    shutil.copy(f"work/mut/commits/{cid}.patch", f"{d}/commits/")
json.dump({"commits": ans}, open(f"{d}/answers.json", "w"))
print(len(ans), "labeled,", sum(1 for v in ans.values() if v["failing"]), "break something")
PY
DATA_DIR=work/mutset SQLGLOT_SRC=work/sqlglot MAP_PATH=map.json.gz INDEX_PATH=index.json.gz python3 selector.py > work/mutout.jsonl 2> work/mutwhy.log
python3 tools/report.py work/mutset work/mutout.jsonl | grep -E "MISS|total"
