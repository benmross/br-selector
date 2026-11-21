"""Summarize exact per-commit costs and narrowed test IDs from t46 measurements."""
import collections,gzip,json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
work=root/'work/t46'
base=sys.argv[1];cand=sys.argv[2]
a=json.load(open(work/f'{base}-summary.json'));b=json.load(open(work/f'{cand}-summary.json'))
rows=[]
for name in a.keys() & b.keys():
 x=json.load(open(work/f'{base}-{name}.rows.json'));y=json.load(open(work/f'{cand}-{name}.rows.json'))
 why={l.split()[0]:l.rstrip() for l in open(work/f'{cand}-{name}.why')}
 assert x.keys()==y.keys(),name
 narrow=[];wide=[]
 for c in x:
  p,q=set(x[c]['chosen']),set(y[c]['chosen'])
  if p!=q:
   row={'set':name,'commit':c,'removed':sorted(p-q),'added':sorted(q-p),'saved_ms':x[c]['cost_ms']-y[c]['cost_ms'],'reason':why.get(c,''),'missed':y[c]['missed']}
   rows.append(row)
   if p-q:narrow.append(c)
   if q-p:wide.append(c)
 print(name,a[name]['n'],a[name]['labeled'],a[name]['selection_s'],b[name]['selection_s'],len(a[name]['misses']),len(b[name]['misses']),'narrow',len(narrow),'wide',len(wide),'fallback',a[name]['fallbacks'],b[name]['fallbacks'])
with gzip.open(root/f'reviews/t46/{cand}-diff.json.gz','wt') as f:json.dump(rows,f)
