"""Real pytest proof of a later test passing alone and failing after a primer."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path[:0] = ['/kit','/kit/tools']
from selector import apply, parse_patch
from label_reports import report_failures

root = Path('/kit')
source = root/'cache-order-src'
if source.exists(): shutil.rmtree(source)
shutil.copytree(root/'pinned', source, ignore=shutil.ignore_patterns('.git','__pycache__'))
out = root/'cache-order'
out.mkdir(exist_ok=True)
tests = {t['id']:t['number'] for t in json.load(open(root/'sample/tests.json'))['tests']}
primer = 'tests/test_generator.py::TestGenerator::test_identify'
later = 'tests/dialects/test_bigquery.py::TestBigQuery::test_string_agg'
results = {}

def run(name, targets):
    prefix = str(out/name)
    env = dict(os.environ, PYTHONPATH=str(source)+':/kit/tools',
               PYTHONDONTWRITEBYTECODE='1',LABEL_REPORT_PREFIX=prefix)
    r = subprocess.run([sys.executable,'-m','pytest',*targets,'-q','-n','0',
                        '-o','addopts=','--tb=short','-p','no:cacheprovider','-p','label_trace'],
                       cwd=source,env=env,capture_output=True,text=True)
    (out/(name+'.log')).write_text(r.stdout+'\nSTDERR\n'+r.stderr)
    results[name] = {'returncode':r.returncode,'targets':targets,
                     'failing':sorted(report_failures(prefix,tests))}

run('baseline-heavy',['tests/test_executor.py::TestExecutor::test_execute_tpcds'])
run('baseline-pair',[primer,later])
fp, = parse_patch((root/'mutants/t30/commits/t30x016.patch').read_text())
path = source/fp.old
before = path.read_text()
try:
    path.write_text(apply(before,fp)[0])
    run('mutant-alone',[later])
    run('mutant-pair',[primer,later])
finally:
    path.write_text(before)
results['order_dependence_confirmed'] = (not results['baseline-pair']['failing']
    and not results['mutant-alone']['failing'] and tests[later] in results['mutant-pair']['failing'])
(out/'result.json').write_text(json.dumps(results,indent=2)+'\n')
print('cache order proof',json.dumps(results),flush=True)
