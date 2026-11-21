"""Read-only attribution using t40's unmodified trigger diagnostic."""
import collections,importlib.util,json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import selector
root=Path(__file__).resolve().parents[1];repo=Path('/home/benmross/herald/projects/blast-radius')
spec=importlib.util.spec_from_file_location('census4_diagnostic',repo/'work/wt/t40/selector.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
output={}
for variant in ['sem-base','sem-final3']:
 counts=collections.Counter();details=[]
 for name in ['hid','fresha','freshb']:
  for line in open(root/f'work/t46/{variant}-{name}.why'):
   if 'possible import failure, everything' not in line:continue
   cid=line.split()[0];p=repo/f'work/wt/t9/work/t9/{name}/commits/{cid}.patch';fps=selector.parse_patch(p.read_text())
   triggers=[]
   for fp in fps:
    if not fp.old or not fp.old.endswith('.py'):continue
    old=(repo/'work/sqlglot'/fp.old).read_text();new=selector.apply(old,fp)[0]
    trigger=m.could_raise_trigger(fp,old,new)
    if trigger:triggers.append(trigger)
   counts.update(triggers);details.append({'set':name,'commit':cid,'triggers':triggers})
 output[variant]={'counts':dict(counts),'details':details}
json.dump(output,open(root/'reviews/t46/fallbacks.json','w'),indent=2)
print({v:x['counts'] for v,x in output.items()})
