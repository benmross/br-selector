"""Consolidate measurements and real labels without calling unlabelled data clean."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

project = Path(__file__).resolve().parents[1]
repo = Path(subprocess.check_output(['git', '-C', str(project), 'rev-parse',
    '--path-format=absolute', '--git-common-dir'], text=True).strip()).parent
work, out = project / 'work/t32', project / 'reviews/t32'
tests = json.load(open(repo / 'sample/tests.json'))['tests']
ms = {t['number']: round(t['seconds'] * 1000) for t in tests}
datasets = {'sample': repo / 'sample', 't3': project.parent / 't3/work/t3-recorded',
    't14': project / 'mutants/t14', 't15': work / 't15', 't24a': project / 'mutants/t24a',
    'hid': project.parent / 't9/work/t9/hid', 'fresha': project.parent / 't9/work/t9/fresha',
    'freshb': project.parent / 't9/work/t9/freshb', 'gate238': work / 'gate238',
    't32': project / 'mutants/t32', 'audit': project / 'mutants/t32audit',
    't30compat': project / 'mutants/t32compat'}

def read(path):
    return {r['commit']: r for r in map(json.loads, open(path))}

def selected(row):
    return {n for group in row['workers'] for n in group}

def cost(row):
    groups = [group for group in row['workers'] if group]
    return max((sum(ms[n] for n in group) for group in groups), default=0) + 2000 * len(groups)

def archive(path):
    if path.exists():
        (out / (path.name + '.gz')).write_bytes(gzip.compress(path.read_bytes(), mtime=0))

summary, narrowed, widened = [], [], []
for name, dataset in datasets.items():
    versions = {v: read(work / f'{v}-{name}.jsonl') for v in ['main', 'final']
                if (work / f'{v}-{name}.time.json').exists()}
    if len(versions) != 2:
        continue
    base, candidate = versions['main'], versions['final']
    assert base.keys() == candidate.keys(), name
    why = {line.split()[0]: line.strip() for line in open(work / f'final-{name}.why')}
    label_path = dataset / 'answers.raw.json'
    if not label_path.exists():
        label_path = dataset / 'answers.json'
    if name == 'audit' and not label_path.exists():
        label_path = work / 'audit-partial-answers.json'
    labels = json.load(open(label_path))['commits'] if label_path.exists() else {}
    checked = labels.keys() & candidate.keys()
    row = dict(dataset=name, commits=len(base), labelled=len(checked),
               base_selection_seconds=sum(map(cost, base.values()))/1000,
               candidate_selection_seconds=sum(map(cost, candidate.values()))/1000,
               base_misses=None, candidate_misses=None, narrowed=0, widened=0)
    if checked:
        row['observed_base_misses'] = sum(bool(set(labels[c]['failing']) - selected(base[c])) for c in checked)
        row['observed_candidate_misses'] = sum(bool(set(labels[c]['failing']) - selected(candidate[c])) for c in checked)
        if checked == candidate.keys():
            row['base_misses'] = row['observed_base_misses']
            row['candidate_misses'] = row['observed_candidate_misses']
    for cid in candidate:
        a, b = selected(base[cid]), selected(candidate[cid])
        if a == b:
            continue
        record = dict(dataset=name, commit=cid, base_ms=cost(base[cid]), candidate_ms=cost(candidate[cid]),
                      added=sorted(b-a), removed=sorted(a-b), reason=why[cid])
        if b < a:
            narrowed.append(record)
            row['narrowed'] += 1
        elif a < b:
            widened.append(record)
            row['widened'] += 1
        else:
            raise AssertionError((name, cid, 'non-monotone selection'))
    for version in ['old', 'main', 'cand', 'integrated', 'final']:
        for ext in ['jsonl', 'why', 'time.json']:
            archive(work / f'{version}-{name}.{ext}')
    summary.append(row)

json.dump(summary, open(out / 'candidate-summary.json', 'w'), indent=2)
(out / 'candidate-narrowed.json.gz').write_bytes(gzip.compress(json.dumps(narrowed, indent=2).encode(), mtime=0))
json.dump(widened, open(out / 'candidate-widened.json', 'w'), indent=2)
with open(out / 'narrowed.md', 'w') as f:
    f.write('# Every narrowed commit\n\nThe audit repeats some source commits in another dataset; those rows are explicit.\n\n')
    f.write('| Set | Commit | Removed tests | Before s | After s | Proof |\n|---|---|---:|---:|---:|---|\n')
    for r in narrowed:
        proof = 'Stock help stored but never read at import; no runtime/data users' if 'stock argparse' in r['reason'] else 'Same-type display literals; only audited import hooks, inert mentions and same-name aliases'
        f.write(f"| {r['dataset']} | {r['commit']} | {len(r['removed'])} | {r['base_ms']/1000:.3f} | {r['candidate_ms']/1000:.3f} | {proof} |\n")
for path in work.glob('*-diff.json'):
    archive(path)
(out / 'baseline-summary.txt').write_text((work / 'summary.txt').read_text())
json.dump(dict(source_sha256=hashlib.sha256((project / 'selector.py').read_bytes()).hexdigest(),
               map_sha256=hashlib.sha256((project / 'map.json.gz').read_bytes()).hexdigest(),
               cmp_sha256=hashlib.sha256((project / 'cmp.json.gz').read_bytes()).hexdigest()),
          open(out / 'artifact-hashes.json', 'w'), indent=2)
print(json.dumps(summary, indent=2))
