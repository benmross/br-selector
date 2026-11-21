"""Measure fixed samples, tracked corpus, task labels and 600 historical proxies."""
import hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPO=Path('/home/benmross/herald/projects/blast-radius'); OUT=ROOT/'work/t47-eval'
sets={'sample':REPO/'sample','tracked':OUT/'tracked','hid':REPO/'work/wt/t9/work/t9/hid','fresha':REPO/'work/wt/t9/work/t9/fresha','freshb':REPO/'work/wt/t9/work/t9/freshb','t47':ROOT/'mutants/t47','t3':REPO/'work/wt/t3/work/t3-recorded','extra':ROOT/'mutants/t47-extra','t44':OUT/'t44'}
ref=sys.argv[1]; variant=sys.argv[2]; script=OUT/(variant+'.py');script.write_bytes(subprocess.check_output(['git','show',ref+':selector.py']))
tests={r['number']:round(r['seconds']*1000) for r in json.load(open(REPO/'sample/tests.json'))['tests']}
summary={}
for name,ds in sets.items():
 if len(sys.argv)>3 and name not in sys.argv[3:]:continue
 if name=='t47':
  # Only completed oracles, so early reports remain valid.
  a=json.load(open(ds/'answers.json'))['commits'];ds=OUT/'t47';(ds/'commits').mkdir(parents=True,exist_ok=True)
  for p in (ds/'commits').glob('*.patch'):p.unlink()
  for c in a:shutil.copy(ROOT/'mutants/t47/commits'/f'{c}.patch',ds/'commits')
  shutil.copy(ROOT/'mutants/t47/answers.json',ds/'answers.json');shutil.copy(REPO/'sample/tests.json',ds/'tests.json')
 answers=json.load(open(ds/'answers.json'))['commits'] if (ds/'answers.json').exists() else {}
 dest=OUT/f'{name}.{variant}.jsonl'; err=OUT/f'{name}.{variant}.why'; u=resource.getrusage(resource.RUSAGE_CHILDREN);start=u.ru_utime+u.ru_stime
 env=dict(os.environ,DATA_DIR=str(ds),SQLGLOT_SRC=str(REPO/'work/sqlglot'),MAP_PATH=str(ROOT/'map.json.gz'),INDEX_PATH=str(ROOT/'index.json.gz'),CMP_PATH=str(ROOT/'cmp.json.gz'),BLAST_WORKERS='1')
 with dest.open('w') as out,err.open('w') as why:subprocess.run([sys.executable,str(script)],env=env,stdout=out,stderr=why,check=True)
 u=resource.getrusage(resource.RUSAGE_CHILDREN); cpu=u.ru_utime+u.ru_stime-start
 rows={};total=0;misses={}
 for r in map(json.loads,dest.read_text().splitlines()):
  c=r['commit'];ws=[w for w in r['workers'] if w];chosen={n for w in ws for n in w};cost=max((sum(tests[n] for n in w) for w in ws),default=0)+2000*len(ws);missing=sorted(set(answers.get(c,{}).get('failing',[]))-chosen)
  if missing:misses[c]=missing
  total+=cost;rows[c]={'selected':sorted(chosen),'cost_ms':cost}
 report={'hash':ref,'commits':len(rows),'labeled':len(answers),'execution_seconds':total/1000,'simulated_seconds':total/1000+300*len(misses),'misses':misses,'cpu_seconds':cpu,'all_selected':sum(len(r['selected'])==1620 for r in rows.values()),'ids_sha256':hashlib.sha256('\n'.join(sorted(rows)).encode()).hexdigest()}
 (OUT/f'{name}.{variant}.summary.json').write_text(json.dumps(report,indent=2)+'\n');summary[name]=report
 print(name,json.dumps(report),flush=True)
(OUT/f'{variant}.summary.json').write_text(json.dumps(summary,indent=2)+'\n')
