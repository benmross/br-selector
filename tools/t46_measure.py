"""Fixed-dataset measurements with full removed IDs, costs, reasons and labels."""
import json, os, resource, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=Path('/home/benmross/herald/projects/blast-radius')
OUT=ROOT/'work/t46'
sets={'sample':REPO/'sample','combined':OUT/'combined','tracked':OUT/'tracked','edge':REPO/'work/synth',
 't41':OUT/'t41','t44':OUT/'t44','t47':OUT/'t47','t46':ROOT/'mutants/t46','t3':REPO/'work/wt/t3/work/t3-recorded',
 't14':ROOT/'mutants/t14','t15':ROOT/'mutants/t15','t24a':ROOT/'mutants/t24a',
 't32':ROOT/'mutants/t32','t30':ROOT/'mutants/t30',
 'gate238':OUT/'gate238','audit':OUT/'audit',
 'hid':REPO/'work/wt/t9/work/t9/hid','fresha':REPO/'work/wt/t9/work/t9/fresha','freshb':REPO/'work/wt/t9/work/t9/freshb'}
variant=sys.argv[1];script=Path(sys.argv[2]).resolve()
ms={t['number']:round(t['seconds']*1000) for t in json.load(open(REPO/'sample/tests.json'))['tests']}
summary=json.load(open(OUT/f'{variant}-summary.json')) if (OUT/f'{variant}-summary.json').exists() else {}
for name in sys.argv[3:] or sets:
 data=sets[name]
 if not (data/'tests.json').exists():
  private=OUT/('data-'+name);private.mkdir(exist_ok=True)
  (private/'commits').symlink_to(data/'commits') if not (private/'commits').exists() else None
  (private/'tests.json').symlink_to(REPO/'sample/tests.json') if not (private/'tests.json').exists() else None
  data=private
 ansfile=sets[name]/'answers.json';answers=json.load(open(ansfile))['commits'] if ansfile.exists() else {}
 env=dict(os.environ,DATA_DIR=str(data),SQLGLOT_SRC=str(REPO/'work/sqlglot'),MAP_PATH=str(ROOT/'map.json.gz'),INDEX_PATH=str(ROOT/'index.json.gz'),CMP_PATH=str(ROOT/'cmp.json.gz'),BLAST_WORKERS='1')
 prefix=OUT/f'{variant}-{name}'
 start=resource.getrusage(resource.RUSAGE_CHILDREN)
 with open(str(prefix)+'.jsonl','w') as out,open(str(prefix)+'.why','w') as err:
  if os.environ.get('T46_SERIAL') == '1':
   snapshot=OUT/('snapshot-'+variant);snapshot.mkdir(exist_ok=True)
   import shutil
   shutil.copy(script,snapshot/'selector.py')
   for filename in ['map.json.gz','cmp.json.gz','index.json.gz']:
    target=snapshot/filename
    if not target.exists():target.symlink_to(ROOT/filename)
   subprocess.run([sys.executable,str(ROOT/'tools/t32_measure.py'),str(snapshot),str(data),str(prefix)],env=env,stdout=subprocess.DEVNULL,stderr=err,check=True)
  else:
   subprocess.run([sys.executable,str(script)],env=env,stdout=out,stderr=err,check=True)
 stop=resource.getrusage(resource.RUSAGE_CHILDREN)
 rows={}
 for r in map(json.loads,open(str(prefix)+'.jsonl')):
  ws=[w for w in r['workers'] if w];chosen={n for w in ws for n in w}
  cost=max((sum(ms[n] for n in w) for w in ws),default=0)+2000*len(ws)
  rows[r['commit']]={'chosen':sorted(chosen),'cost_ms':cost,'missed':sorted(set(answers.get(r['commit'],{}).get('failing',[]))-chosen)}
 reasons={line.split(' ',1)[0]:line.rstrip() for line in open(str(prefix)+'.why')}
 row={'n':len(rows),'labeled':len(answers),'selection_s':sum(x['cost_ms'] for x in rows.values())/1000,'misses':{c:r['missed'] for c,r in rows.items() if r['missed']},'cpu_s':stop.ru_utime+stop.ru_stime-start.ru_utime-start.ru_stime,'fallbacks':sum('possible import failure, everything' in r for r in reasons.values())}
 summary[name]=row
 json.dump(rows,open(str(prefix)+'.rows.json','w'))
 json.dump(summary,open(OUT/f'{variant}-summary.json','w'),indent=2)
 print(name,json.dumps({**row,'misses':{k:len(v) for k,v in row['misses'].items()}}),flush=True)
