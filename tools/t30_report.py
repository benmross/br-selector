"""Build the validation-only per-mutant matrix from real saved labels."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT/'mutants/t30'
manifest = json.load(open(directory/'manifest.json'))['commits']
answers = json.load(open(directory/'answers.json'))['commits']

def selections(variant):
    return {r['commit']:{n for w in r['workers'] for n in w} for r in
            map(json.loads,open(ROOT/f'work/t30-measure/t30.{variant}.jsonl'))}

base, candidate = selections('base'), selections('candidate')
rows = {}; misses = {}; groups = {}
lines = ['# t30 real pytest labels', '',
         'Test 1490 is deselected under the 1 GiB cap; collection failures still count it.',
         'TPC-DS baseline subtest 88 is subtracted by subtest key, preserving other new failures.',
         'A ≥ failure count is a lower bound: an all-selected smoke control, or t30x044 with selected test 1106 omitted after OOM.',
         'All smoke controls select every test on main. Per-mutant exclusions are recorded in manifest.json.', '',
         '| Mutant | Class | Edit | Failing | Main selected | Main missed | Candidate missed |',
         '| --- | --- | --- | ---: | ---: | ---: | ---: |']
for cid, meta in manifest.items():
    if cid not in answers:
        lines.append(f'| {cid} | {meta["kind"]} | {meta["description"]} | pending | {len(base[cid])} | pending | pending |')
        continue
    failing = set(answers[cid]['failing'])
    missed, remaining = failing-base[cid], failing-candidate[cid]
    group = groups.setdefault(meta['kind'],{'mutants':0,'failing_mutants':0,'failing_test_instances':0,
                                          'main_selected_test_instances':0,'main_misses':[], 'candidate_misses':[]})
    group['mutants'] += 1; group['failing_mutants'] += bool(failing)
    group['failing_test_instances'] += len(failing)
    group['main_selected_test_instances'] += len(base[cid])
    if missed: group['main_misses'].append(cid)
    if remaining: group['candidate_misses'].append(cid)
    row = {'class':meta['kind'],'description':meta['description'],'failing':len(failing),
           'label_scope':meta.get('label_scope','full numbered suite except 1490'),
           'main_selected':len(base[cid]),'main_missing':sorted(missed),
           'candidate_selected':len(candidate[cid]),'candidate_missing':sorted(remaining)}
    rows[cid] = row
    if missed: misses[cid] = row
    fail_count = ('≥' if 'tests' in meta or meta.get('deselect') else '') + str(len(failing))
    lines.append(f'| {cid} | {meta["kind"]} | {meta["description"]} | {fail_count} | {len(base[cid])} | {len(missed)} | {len(remaining)} |')
(ROOT/'reviews/t30-matrix.md').write_text('\n'.join(lines)+'\n')
(ROOT/'reviews/t30-label-summary.json').write_text(json.dumps({'labeled':len(answers),'generated':len(manifest),
          'classes':groups,'misses':misses,'rows':rows},indent=2)+'\n')
print(json.dumps({'labeled':len(answers),'classes':groups,'miss_ids':list(misses)},indent=2))
