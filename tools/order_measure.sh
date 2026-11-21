#!/bin/sh
# t24a: run selector.py with two maps on each measurement set; print cost and
# any commit whose selection with the new map is not a superset of the base's.
# usage: order_measure.sh BASE_MAP NEW_MAP OUTDIR
set -u
R=$HOME/herald/projects/blast-radius
B=$1; N=$2; O=$3; mkdir -p "$O"
T15=$O/t15set; rm -rf "$T15"; mkdir -p "$T15"; cp -r "$R/work/wt/t24a/mutants/t15/commits" "$T15/" 2>/dev/null || cp -r "$R/mutants/t15/commits" "$T15/"; cp "$R/sample/tests.json" "$T15/"
for s in sample:$R/sample mutset:$R/work/mutset t3:$R/work/wt/t3/work/t3-recorded t14:$R/work/wt/t24a/mutants/t14 t15:$T15 t24a:$R/work/wt/t24a/mutants/t24a hid:$R/work/wt/t9/work/t9/hid; do
  name=${s%%:*}; d=${s#*:}
  for which in base new; do
    m=$B; [ $which = new ] && m=$N
    /usr/bin/time -f "%U %S" -o "$O/$name.$which.time" env DATA_DIR=$d SQLGLOT_SRC=$R/work/sqlglot MAP_PATH=$m INDEX_PATH=$R/work/wt/t24a/index.json.gz CMP_PATH=$R/work/wt/t24a/cmp.json.gz \
      python3 ${SELECTOR:-$R/work/wt/t24a/selector.py} > "$O/$name.$which.jsonl" 2> "$O/$name.$which.why"
  done
  python3 - "$d/tests.json" "$O/$name.base.jsonl" "$O/$name.new.jsonl" "$name" "$O/$name.base.time" "$O/$name.new.time" <<'PY'
import json, sys
tests = {t["number"]: t["seconds"] for t in json.load(open(sys.argv[1]))["tests"]}
def load(p):
    out = {}
    for l in open(p):
        d = json.loads(l); w = [x for x in d["workers"] if x]
        cost = (max(sum(tests[n] for n in x) for x in w) + 2 * len(w)) if w else 0
        out[d["commit"]] = ({n for x in w for n in x}, cost)
    return out
a, b = load(sys.argv[2]), load(sys.argv[3])
nar = sorted(c for c in a if not a[c][0] <= b.get(c, (set(), 0))[0])
wid = sorted(c for c in a if c in b and a[c][0] < b[c][0])
cpu = [sum(map(float, open(p).read().split()[-2:])) for p in sys.argv[5:7]]
print(f"{sys.argv[4]:7s} commits {len(a):4d} base {sum(v[1] for v in a.values()):9.1f} s new {sum(v[1] for v in b.values()):9.1f} s "
      f"widened {len(wid):3d} narrower {len(nar)}{' ' + ','.join(nar) if nar else ''} cpu {cpu[0]:.1f}/{cpu[1]:.1f} s")
PY
done
