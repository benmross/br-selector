"""Validate and archive the completed real-pytest oracles after source restore."""
import hashlib,json,subprocess,tarfile
from pathlib import Path
from label_reports import report_failures
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'mutants/t47';SRC=ROOT/'work/sqlglot';OVERLAY=ROOT/'work/t47-src'
a=json.load(open(OUT/'answers.json'))['commits'];m=json.load(open(OUT/'manifest.json'))['commits']
assert len(a)==72 and a.keys()==m.keys()
assert json.load(open(OUT/'answers.json.baseline'))==[]
tests={r['id']:r['number'] for r in json.load(open(ROOT/'sample/tests.json'))['tests']}
for c,r in a.items():
 observed=report_failures(str(OUT/'answers.json.reports'/c),tests)
 assert observed==set(r['failing']),c
for p in SRC.rglob('*.py'):
 if '.git' in p.parts:continue
 assert p.read_bytes()==(OVERLAY/p.relative_to(SRC)).read_bytes(),p
archive=OUT/'structured-reports.tar.gz'
with tarfile.open(archive,'w:gz') as tf:
 for directory in ['answers.json.reports','answers.json.logs']:
  for p in sorted((OUT/directory).glob('*')):tf.add(p,arcname=directory+'/'+p.name)
quality={'pinned_source':'eb11aec4be8cb2122afe713a4816662c3f0fb2fa','container_host':'rosserver','cpus':2,'memory_bytes':2147483648,'memory_swap_bytes':2147483648,'first_38_pytest_workers':2,'later_pytest_workers':0,'later_cpuset':'0-1','python':'3.13.18','image_id':subprocess.check_output(['docker','inspect','br-t24b3','--format','{{.Id}}'],text=True).strip(),'baseline_failing':[],'deselected':[1490],'scoped_all_selected_controls':sum('tests' in r for r in m.values()),'full_suite_labels':sum('tests' not in r for r in m.values()),'structured_reports_exactly_match_answers':True,'source_python_content_restored':True,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'oracle_notes':['Failure counts for scoped all-selected controls are lower bounds.','Initial bootstrap lacked the sample mount and produced no labels; corrected before labeling.','The first completed 38-label batch had a shell trailer error after label.py saved all reports and restored source. The structured test reports, rather than the shell exit, determine those labels.','The labeler rejects any cgroup OOM kill during pytest; no OOM-tainted label was accepted.','Seven redundant MRO reorder candidates 015-021 were removed before labeling; gen.py --all restores the exploration pool.']}
(OUT/'label_quality.json').write_text(json.dumps(quality,indent=2)+'\n')
print('audited 72 labels; pristine source restored; archive',archive.stat().st_size,'bytes')
