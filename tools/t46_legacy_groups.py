"""Explain every narrower selection than the exact dc91341 comparator."""
import collections,gzip,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];w=root/'work/t46';out=root/'reviews/t46'
old={r['commit']:{n for q in r['workers'] for n in q} for r in map(json.loads,open(w/'dc-combined.jsonl'))}
new=json.load(open(w/'sem-final3-combined.rows.json'))
why={l.split()[0]:l.rstrip() for l in open(w/'sem-final3-combined.why')}
assert old.keys()==new.keys()
groups=collections.defaultdict(list);changes=[]
for c in sorted(old):
 chosen=set(new[c]['chosen'])
 if not old[c]-chosen:continue
 reason=why[c]
 if 'comparison swap changes no result' in reason:group='Existing observed comparison-result profile'
 elif 'stock argparse' in reason:group='Existing unused stock argparse help proof'
 elif 'lambda-body strings' in reason:group='Audited stored lambda body coverage'
 elif 'inert string statements' in reason:group='Audited documentation and code-constant readers'
 elif 'rename_func closure' in reason:group='Pure stored rename_func argument'
 elif 'type spellings' in reason:group='Audited type spellings and direct cast readers'
 elif 'dialect keyword strings' in reason:group='Audited dialect keyword consumers'
 else:group='Other (review exact reason)'
 groups[group].append(c);changes.append({'commit':c,'group':group,'old_count':len(old[c]),'new_count':len(chosen),'removed':sorted(old[c]-chosen),'added':sorted(chosen-old[c]),'reason':reason})
with gzip.open(out/'legacy-narrowed.json.gz','wt') as f:json.dump(changes,f)
lines=['# Every narrower mutant than dc91341','',f'{len(changes)} of {len(new)} inputs are narrower. Both exact selections are archived; this corpus is the final 611-input union prepared for the gate. The final gate list must be reconciled before claiming PASS.','']
for group,ids in groups.items():
 lines.extend(['## '+group,'',', '.join(ids),''])
 lines.extend(['| Patch | dc91341 | Candidate | Reason |','|---|---:|---:|---|'])
 for r in changes:
  if r['group']==group:lines.append(f"| {r['commit']} | {r['old_count']} | {r['new_count']} | {r['reason'].replace('|','/')} |")
 lines.append('')
(out/'legacy-narrowing.md').write_text('\n'.join(lines))
json.dump(dict(groups),open(out/'legacy-groups.json','w'),indent=2)
print('narrower',len(changes),'of',len(new),{k:len(v) for k,v in groups.items()})
