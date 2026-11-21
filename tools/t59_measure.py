"""t59: selection cost and misses of a selector ref on the samples, the 600
proxies (hid, fresha, freshb) and the t41, t46, t56, t59 labeled sets.
usage: python3 tools/t59_measure.py <git ref> <variant> [set ...]"""
import json, os, resource, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REPO = Path('/home/benmross/herald/projects/blast-radius')
OUT = ROOT / 'work/t59-eval'
OUT.mkdir(parents=True, exist_ok=True)
T9 = REPO / 'work/wt/t9/work/t9'
sets = {'sample': REPO / 'sample', 'hid': T9 / 'hid', 'fresha': T9 / 'fresha', 'freshb': T9 / 'freshb',
        't41': REPO / 'mutants/t41', 't46': ROOT / 'mutants/t46', 't56': REPO / 'work/wt/t56/mutants/t56',
        't59': ROOT / 'mutants/t59', 't59x': ROOT / 'mutants/t59x'}
ref, variant = sys.argv[1], sys.argv[2]
script = OUT / (variant + '.py')
if ref == 'WORKTREE':
    shutil.copy(ROOT / 'selector.py', script)
else:
    script.write_bytes(subprocess.check_output(['git', 'show', ref + ':selector.py'], cwd=ROOT))
tests = {r['number']: round(r['seconds'] * 1000) for r in json.load(open(REPO / 'sample/tests.json'))['tests']}
for name, ds in sets.items():
    if len(sys.argv) > 3 and name not in sys.argv[3:]:
        continue
    if not (ds / 'commits').exists():
        continue
    answers = json.load(open(ds / 'answers.json'))['commits'] if (ds / 'answers.json').exists() else {}
    if not (ds / 'tests.json').exists() or name in ('t56', 't59', 't59x'):  # copy so every patch is priced
        d = OUT / f'{name}-data'; (d / 'commits').mkdir(parents=True, exist_ok=True)
        for p in (d / 'commits').glob('*.patch'): p.unlink()
        for p in (ds / 'commits').glob('*.patch'): shutil.copy(p, d / 'commits')
        shutil.copy(REPO / 'sample/tests.json', d / 'tests.json')
        ds = d
    dest, err = OUT / f'{name}.{variant}.jsonl', OUT / f'{name}.{variant}.why'
    u = resource.getrusage(resource.RUSAGE_CHILDREN); start = u.ru_utime + u.ru_stime
    env = dict(os.environ, DATA_DIR=str(ds), SQLGLOT_SRC=str(REPO / 'work/sqlglot'), MAP_PATH=str(ROOT / 'map.json.gz'),
               INDEX_PATH=str(ROOT / os.environ.get('T59_INDEX', 'index.json.gz')), CMP_PATH=str(ROOT / 'cmp.json.gz'), KEYS_PATH=str(ROOT / os.environ.get('T59_KEYS', 'keys.json.gz')), BLAST_WORKERS='1')
    with dest.open('w') as out, err.open('w') as why:
        subprocess.run([sys.executable, str(script)], env=env, stdout=out, stderr=why, check=True)
    u = resource.getrusage(resource.RUSAGE_CHILDREN); cpu = u.ru_utime + u.ru_stime - start
    total, misses, allsel = 0, {}, 0
    for r in map(json.loads, dest.read_text().splitlines()):
        ws = [w for w in r['workers'] if w]; chosen = {n for w in ws for n in w}
        total += max((sum(tests[n] for n in w) for w in ws), default=0) + 2000 * len(ws)
        allsel += len(chosen) == len(tests)
        missing = sorted(set(answers.get(r['commit'], {}).get('failing', [])) - chosen)
        if missing: misses[r['commit']] = missing
    rep = {'commits': len(dest.read_text().splitlines()), 'labeled': len(answers), 'execution_seconds': round(total / 1000, 3),
           'misses': len(misses), 'simulated_seconds': round(total / 1000 + 300 * len(misses), 3), 'all_selected': allsel,
           'cpu_seconds': round(cpu, 2), 'missed': misses}
    (OUT / f'{name}.{variant}.summary.json').write_text(json.dumps(rep, indent=1) + '\n')
    print(name, variant, json.dumps({k: v for k, v in rep.items() if k != 'missed'}), list(misses)[:5], flush=True)
