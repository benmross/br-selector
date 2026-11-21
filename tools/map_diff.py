"""Compare two maps: lines, classes and fixtures whose test sets grew, and new import lines."""
import gzip, json, sys
from collections import Counter
a = json.load(gzip.open(sys.argv[1], "rt")); b = json.load(gzip.open(sys.argv[2], "rt"))
sa, sb = a["sets"], b["sets"]
grown, added, by_file, extra = 0, 0, Counter(), 0
for f, ls in b["files"].items():
    al = a["files"].get(f, {})
    for k, v in ls.items():
        if k not in al:
            added += 1; by_file[f] += 1
        elif len(sb[v]) > len(sa[al[k]]):
            grown += 1; by_file[f] += 1; extra += len(sb[v]) - len(sa[al[k]])
imp = {f: sorted(set(v) - set(a["import_lines"].get(f, []))) for f, v in b["import_lines"].items()}
imp = {f: v for f, v in imp.items() if v}
def named(key):
    return sum(1 for k, v in b[key].items() if k not in a[key] or len(sb[v]) > len(sa[a[key][k]]))
print(json.dumps({"lines_grown": grown, "lines_added": added, "test_credits_added": extra,
                  "files_touched": len(by_file), "top_files": by_file.most_common(15),
                  "new_import_lines": imp, "classes_grown": named("classes"), "fixtures_grown": named("fixtures")}, indent=1))
