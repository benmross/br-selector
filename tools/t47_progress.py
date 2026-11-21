"""Write immediately usable label handoff and detailed selected/failing ids."""
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'mutants/t47'
result=Path('/home/benmross/herald/projects/buildathon/tasks/t47-blast-newkinds4.result.md')
m=json.load(open(OUT/'manifest.json'))['commits']
a=json.load(open(OUT/'answers.json'))['commits'] if (OUT/'answers.json').exists() else {}
rows={r['commit']:r for r in map(json.loads,(ROOT/'work/t47-main.jsonl').read_text().splitlines())}
candidate_path=ROOT/'work/t47-rule1.jsonl'
cand={r['commit']:r for r in map(json.loads,candidate_path.read_text().splitlines())} if candidate_path.exists() else rows
times={r['number']:round(r['seconds']*1000) for r in json.load(open(ROOT/'sample/tests.json'))['tests']}
def cost(row):
 ws=[w for w in row['workers'] if w]
 return (max((sum(times[n] for n in w) for w in ws),default=0)+2000*len(ws))/1000
summary={}; table=[]; totals={'main':0,'candidate':0}; misses={'main':0,'candidate':0}
for c,answer in sorted(a.items()):
 chosen=sorted({n for w in rows[c]['workers'] for n in w}); fail=answer['failing']; missing=sorted(set(fail)-set(chosen))
 selected=sorted({n for w in cand[c]['workers'] for n in w}); cmissing=sorted(set(fail)-set(selected))
 summary[c]={**m[c],**answer,'main_selected':chosen,'missing':missing,'candidate_selected':selected,'candidate_missing':cmissing}
 for v,r,err in [('main',rows[c],missing),('candidate',cand[c],cmissing)]:
  misses[v]+=bool(err);totals[v]+=cost(r)+300*bool(err)
 scope='≥' if 'tests' in m[c] else ''
 table.append(f"| {c} | {m[c]['kind']}: {m[c]['description']} | {scope}{len(fail)} | {len(chosen)} | {'MISS '+str(len(missing)) if missing else 'no'} | {len(selected)} | {'MISS '+str(len(cmissing)) if cmissing else 'no'} |")
(OUT/'matrix.json').write_text('{\n'+',\n'.join(json.dumps(c)+': '+json.dumps(r,separators=(',',':')) for c,r in summary.items())+'\n}\n')
(OUT/'cohort_metrics.json').write_text(json.dumps({'labeled':len(a),'main_misses':misses['main'],'candidate_misses':misses['candidate'],'main_simulated_seconds':round(totals['main'],3),'candidate_simulated_seconds':round(totals['candidate'],3),'main_execution_seconds':round(totals['main']-300*misses['main'],3),'candidate_execution_seconds':round(totals['candidate']-300*misses['candidate'],3),'widened_ids':[c for c,r in summary.items() if set(r['main_selected'])<set(r['candidate_selected'])],'narrowed_ids':[c for c,r in summary.items() if not set(r['main_selected'])<=set(r['candidate_selected'])]},indent=2)+'\n')
text=f'''# t47 — New change kinds, round 4

## Handoff
- Status: labeling in progress; {len(a)}/{len(m)} completed, {misses['main']} main misses and {misses['candidate']} candidate misses recorded. Updated {time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())}.
- Model: GPT-6-based Codex (exact backend identifier not exposed).
- Started 2026-11-21 11:58:41 UTC; hard stop 13:28:41 UTC.
- Baseline: `59be830bae1042fab164d330ceb7617e49b52a4f`; branch `w/t47`, worktree `/home/benmross/herald/projects/blast-radius/work/wt/t47`.
- Fix: `79d448758064d2c5661574357ab7c8f34619ddf2`, class base changes select import/implicit protocol users. Four focused regressions fail before the fix; all five focused checks pass after. 166 selector tests and 22 tools tests pass. Selections and cost are identical on samples, the frozen 412-mutant corpus, t3/t14/t15/t24a/t30, and all 600 proxies. The rule fires on 0/600 proxy commits.
- Label container: rosserver `br-label-t47`, `--cpus 2 --memory 2g --memory-swap 2g`, pinned Python 3.13 image via br-t24b3. First 38 labels use two pytest workers; later labels and the full baseline use one pytest process with cpuset 0–1; test_max_nodes / 1490 deselected. Full pristine baseline: 1619 passed, one skipped, one deselected, zero failures, 25440 subtests passed in 119.47 s. No additional baseline subtraction.
- No pushes, submissions or main edits. Source overlay is isolated at `work/t47-src`.
- Artifacts: `mutants/t47/{{commits,manifest.json,answers.json,matrix.json,cohort_metrics.json,answers.json.logs,answers.json.reports}}`; main selections `work/t47-main.jsonl`; candidate selections `work/t47-rule1.jsonl`; runner logs `work/t47-run.log`, `work/t47-run2.log`, `work/t47-run3.log`.
- Labels are written atomically per mutant. ≥ marks scoped all-selected controls: failure counts are lower bounds; selection misses are impossible because main selects all 1,620 tests. Other mutants run the full numbered suite except 1490. Exact failing ids and main/candidate selection ids are in matrix.json.
- Next: finish labels, measure fixed samples/tracked/proxy sets, run final gate versus dc913410055bea94a97ceba751aa59f9f51df972.

## Labels

| ID | Class and change | Failing tests | Main selected | Main miss | Candidate selected | Candidate miss |
| --- | --- | ---: | ---: | --- | ---: | --- |
'''+ '\n'.join(table)+f'''\n
## Evaluation and recommendation

Current labeled cohort: main {misses['main']} misses, {totals['main']:.3f} simulated seconds; candidate {misses['candidate']} misses, {totals['candidate']:.3f} simulated seconds. Includes 300 seconds per missed commit. Frozen existing sets: samples 116.857 s; tracked 412 8439.638 s; t3 394.149 s; t14 422.387 s; t15 647.799 s; t24a 193.275 s; t30 2153.452 s; hid 3491.011 s; fresha 4551.398 s; freshb 556.021 s. All unchanged, zero recorded misses where labeled, no widened or narrowed selections. Proxy sets have no oracles. Exact fixed ids and costs: `reviews/t47-eval-ids.json`, `reviews/t47-costs.json`. Final gate pending.
'''
temporary=result.with_suffix('.md.tmp')
temporary.write_text(text)
temporary.replace(result)
print('labels',len(a),'misses',{c:len(r['missing']) for c,r in summary.items() if r['missing']},'candidate misses',misses['candidate'],flush=True)
