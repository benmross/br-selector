"""Evaluate held-out real failures against an already-frozen selection."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
work=root/'work/t46'
answers=json.load(open(sys.argv[1] if len(sys.argv)>1 else work/'legion-answers.json'))['commits']
rows=json.load(open(work/'sem-final3-t46.rows.json'))
manifest=json.load(open(root/'mutants/t46/manifest.json'))['commits']
missing={c:sorted(set(v['failing'])-set(rows[c]['chosen'])) for c,v in answers.items() if set(v['failing'])-set(rows[c]['chosen'])}
result={'completed':len(answers),'expected':len(manifest),'breaking':sum(bool(v['failing']) for v in answers.values()),'misses':missing,'remaining':sorted(manifest.keys()-answers.keys())}
json.dump(result,open(work/'fresh-progress.json','w'),indent=2)
print(json.dumps(result))
