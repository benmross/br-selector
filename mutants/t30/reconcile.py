"""Recover new subtest failures hidden by subtracting a failing parent test.

The fresh baseline has one failure, TPC-DS query 88 in parent 1106. A new
query failure or collection error must still count that parent as failing.
The source is pytest's real saved summaries; this is validation data only.
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from label_reports import failure_numbers, startup_failures


def failure_keys(text):
    summary = text.rsplit('short test summary info', 1)[-1]
    pattern = r'^(FAILED|ERROR|SUBFAILED)(?:[\[(]([\s\S]*?)[\])])?\s+(tests/\S+)'
    return {(kind, case or '', nodeid) for kind, case, nodeid in re.findall(pattern, summary, re.MULTILINE)}


def main():
    directory = Path(__file__).resolve().parent
    tests = {t['id']:t['number'] for t in json.load(open(directory/'tests.json'))['tests']}
    logs = Path(sys.argv[1]) if len(sys.argv) > 1 else directory / 'answers.json.logs'
    baseline = failure_keys((logs/'baseline.log').read_text())
    answer_path = directory/'answers.json'
    answers = json.load(open(answer_path))
    manifest = json.load(open(directory/'manifest.json'))['commits']
    added = {}
    for cid, row in answers['commits'].items():
        row['kind'] = manifest[cid]['kind']
        row['label_scope'] = manifest[cid].get('label_scope', 'full numbered suite except 1490')
        if 'tests' in manifest[cid]: row['tests_run'] = manifest[cid]['tests']
        if manifest[cid].get('deselect'): row['additional_deselected'] = manifest[cid]['deselect']
        text = (logs/(cid+'.log')).read_text()
        new = failure_keys(text) - baseline
        failing = failure_numbers({nodeid for _,_,nodeid in new}, tests)
        if 'short test summary info' not in text:
            failing |= startup_failures(text, 1, '/src', tests) or set()
        previous = set(row['failing'])
        if failing-previous:
            added[cid] = sorted(failing-previous)
        row['failing'] = sorted(previous|failing)
    answer_path.write_text(json.dumps(answers)+'\n')
    (directory/'label_quality.json').write_text(json.dumps({
        'baseline_failure_keys':sorted(baseline),'added_after_subtest_reconciliation':added,
        'deselected':[1490], 'reason':'Pinned max_nodes OOMs alone with the required 1 GiB cap',
        'baseline_environment_failure':'TPC-DS 88 exceeds DuckDB reference execution memory (819 MiB); other new subtest failures are counted',
        'broad_numbered_tests':1619,'smoke_failure_counts_are_lower_bounds':True,
        'additional_mutant_exclusions':{c:r['deselect'] for c,r in manifest.items() if r.get('deselect')},
        'container':'python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90',
        'cpuset':'8-9','memory_bytes':1073741824,'pytest_workers':0},indent=2)+'\n')
    print('recovered',added)


if __name__ == '__main__': main()
