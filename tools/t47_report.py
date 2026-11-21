"""Freeze same-set before/after cost and selection comparisons."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'work/t47-eval'
report={}; ids={}
variant=sys.argv[1] if len(sys.argv)>1 else 'combined'
def selections(path):
 return {r['commit']:{n for w in r['workers'] for n in w} for r in map(json.loads,path.read_text().splitlines())}
for name in (['sample','tracked','hid','fresha','freshb','t3','t44'] if variant=='combined' else ['sample','tracked','hid','fresha','freshb','t3']):
 bv='base-t3' if name=='t3' else 'base'
 cv=variant if variant=='combined' else ('rule1-t3' if name=='t3' else 'rule1')
 a=json.load(open(OUT/f'{name}.{bv}.summary.json'));b=json.load(open(OUT/f'{name}.{cv}.summary.json'))
 sa=selections(OUT/f'{name}.{bv}.jsonl');sb=selections(OUT/f'{name}.{cv}.jsonl');assert sa.keys()==sb.keys()
 ids[name]=sorted(sa)
 wide=[c for c in sa if sa[c]<sb[c]];nar=[c for c in sa if not sa[c]<=sb[c]]
 trigger=sum('class bases changed' in line for line in (OUT/f'{name}.{cv}.why').read_text().splitlines())
 report[name]={'baseline':a,'candidate':b,'widened':wide,'narrowed':nar,'rule_trigger_commits':trigger,'qualified_rule_trigger_commits':sum(('copies a changed class attribute' in line or 'runtime read of a changed class attribute' in line) for line in (OUT/f'{name}.{cv}.why').read_text().splitlines())}
# Existing task subsets are all within the frozen tracked corpus; no second selector run needed.
times={r['number']:round(r['seconds']*1000) for r in json.load(open(ROOT/'sample/tests.json'))['tests']}
for task in ['t14','t15','t24a','t30']:
 answers=json.load(open(ROOT/'mutants'/task/'answers.json'))['commits']; ids[task]=sorted(answers);report[task]={}
 for v in ['base',variant]:
  rows={r['commit']:r for r in map(json.loads,(OUT/f'tracked.{v}.jsonl').read_text().splitlines())}
  total=0;miss=[]
  for c,a in answers.items():
   ws=[w for w in rows[c]['workers'] if w];selected={n for w in ws for n in w}
   cost=max((sum(times[n] for n in w) for w in ws),default=0)+2000*len(ws)
   bad=bool(set(a['failing'])-selected);total+=cost+300000*bad
   if bad:miss.append(c)
  report[task]['baseline' if v=='base' else 'candidate']={'commits':len(answers),'simulated_seconds':total/1000,'misses':miss}
 report[task].update(widened=[],narrowed=[],rule_trigger_commits=0)
report['t47']=json.load(open(ROOT/'mutants/t47/cohort_metrics.json'))
(ROOT/'reviews/t47-costs.json').write_text(json.dumps(report,indent=2)+'\n')
(ROOT/'reviews/t47-eval-ids.json').write_text(json.dumps(ids,indent=2)+'\n')
for name,r in report.items():
 if name=='t47':print(name,r);continue
 print(name,r['baseline']['commits'],r['baseline']['simulated_seconds'],r['candidate']['simulated_seconds'],'widened',len(r['widened']),'narrowed',len(r['narrowed']),'fires',r['rule_trigger_commits'])
