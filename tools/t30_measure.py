"""Run baseline/candidate sequentially on the task's fixed measurement sets."""
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = Path('/home/benmross/herald/projects/blast-radius')
OUT = Path(os.environ.get('T30_OUT',str(ROOT / 'work/t30-measure')))
OUT.mkdir(parents=True, exist_ok=True)
frozen = ROOT/'work/t30-gate238'
if not frozen.exists():
    ids = json.load(open(ROOT/'reviews/t30-gate238-ids.json'))
    original = REPO/'work/mutset'
    answers = json.load(open(original/'answers.json'))['commits']
    (frozen/'commits').mkdir(parents=True)
    for cid in ids: shutil.copy(original/'commits'/(cid+'.patch'),frozen/'commits'/(cid+'.patch'))
    shutil.copy(REPO/'sample/tests.json',frozen/'tests.json')
    (frozen/'answers.json').write_text(json.dumps({'commits':{c:answers[c] for c in ids}}))
sets = {
    'sample': REPO / 'sample',
    'gate238': ROOT / 'work/t30-gate238',
    't3': REPO / 'work/wt/t3/work/t3-recorded',
    't14': ROOT / 'mutants/t14',
    't15': ROOT / 'mutants/t15',
    't24a': ROOT / 'mutants/t24a',
    'hid': REPO / 'work/wt/t9/work/t9/hid',
    'fresha': REPO / 'work/wt/t9/work/t9/fresha',
    'freshb': REPO / 'work/wt/t9/work/t9/freshb',
    't30': ROOT / 'mutants/t30',
}
tests = {t['number']: round(t['seconds']*1000) for t in json.load(open(REPO/'sample/tests.json'))['tests']}
baseline = OUT / 'baseline.py'
base_ref = os.environ.get('T30_BASELINE_COMMIT','be28115d6b491536992e294aff9ae9b1d2a27dee')
baseline.write_bytes(subprocess.check_output(['git','show',base_ref+':selector.py'],cwd=ROOT))

def usage():
    u = resource.getrusage(resource.RUSAGE_CHILDREN)
    return u.ru_utime + u.ru_stime

def load(path, answers):
    rows = {}
    for line in path.read_text().splitlines():
        r = json.loads(line); ws = [w for w in r['workers'] if w]
        chosen = {n for w in ws for n in w}
        cost = max((sum(tests[n] for n in w) for w in ws), default=0) + 2000*len(ws)
        fail = set(answers.get(r['commit'],{}).get('failing',[]))
        missing = sorted(fail-chosen)
        rows[r['commit']] = {'selected':len(chosen),'chosen':chosen,'execution_ms':cost,'missing':missing}
    return rows

summary = {}
for name, original in sets.items():
    if len(sys.argv)>1 and name not in sys.argv[1:]: continue
    dataset = OUT / ('data-'+name)
    if not dataset.exists():
        dataset.mkdir()
        (dataset/'commits').mkdir()
        shutil.copy(REPO/'sample/tests.json',dataset/'tests.json')
    current = {p.name for p in (original/'commits').glob('*.patch')}
    for path in (dataset/'commits').glob('*.patch'):
        if path.name not in current: path.unlink()
    for path in (original/'commits').glob('*.patch'): shutil.copy(path,dataset/'commits'/path.name)
    if (original/'answers.json').exists(): shutil.copy(original/'answers.json',dataset/'answers.json')
    answers = json.load(open(dataset/'answers.json'))['commits'] if (dataset/'answers.json').exists() else {}
    variants = {}; cpus = {}
    for variant, script in [('base',baseline),('candidate',ROOT/'selector.py')]:
        result = OUT / f'{name}.{variant}.jsonl'
        env = dict(os.environ, DATA_DIR=str(dataset), SQLGLOT_SRC=str(REPO/'work/sqlglot'),
                   MAP_PATH=str(ROOT/'map.json.gz'), INDEX_PATH=str(ROOT/'index.json.gz'),
                   CMP_PATH=str(ROOT/'cmp.json.gz'))
        start = usage()
        with open(result,'w') as out, open(OUT/f'{name}.{variant}.why','w') as err:
            subprocess.run([sys.executable,str(script)],env=env,cwd=ROOT,stdout=out,stderr=err,check=True)
        cpus[variant] = round(usage()-start,4)
        variants[variant] = load(result,answers)
    a,b = variants['base'],variants['candidate']
    assert a.keys()==b.keys(),name
    nar = [cid for cid in a if not a[cid]['chosen'] <= b[cid]['chosen']]
    wide = [cid for cid in a if a[cid]['chosen'] < b[cid]['chosen']]
    row = {'commits':len(a),'labeled':len(answers),'narrowed':nar,'widened':wide,'cpu_seconds':cpus}
    for variant,rows in variants.items():
        misses = {c:r['missing'] for c,r in rows.items() if r['missing']}
        execution = sum(r['execution_ms'] for r in rows.values())/1000
        row[variant] = {'misses':misses,'execution_seconds':execution,
                        'simulated_seconds':execution+300*len(misses)}
    summary[name]=row
    (OUT/f'{name}.summary.json').write_text(json.dumps(row,indent=2)+'\n')
    print(name,json.dumps({'commits':len(a),'base':row['base']['simulated_seconds'],
          'candidate':row['candidate']['simulated_seconds'],
          'misses':[len(row[v]['misses']) for v in ('base','candidate')],
          'widened':wide,'narrowed':nar,'cpu_seconds':cpus}),flush=True)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
