"""Write the final external handoff after the exact commit's gate finishes."""
import collections,json,re,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TASKS=Path('/home/benmross/herald/projects/buildathon/tasks');OUT=ROOT/'mutants/t47'
ref=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
rows=json.load(open(OUT/'matrix.json'));costs=json.load(open(ROOT/'reviews/t47-costs.json'));q=json.load(open(OUT/'label_quality.json'))
assert len(rows)==72 and not any(r['candidate_missing'] for r in rows.values())
gate=TASKS.parent/'gates'/f'{ref}.txt';gate_text=gate.read_text() if gate.exists() else 'not yet run'
misses={c:r for c,r in rows.items() if r['missing']};groups=collections.defaultdict(list)
for c,r in rows.items():groups[r['kind']].append(r)
parts=[f'''# t47 — New change kinds, round 4

## Handoff
- Model: GPT-6-based Codex (exact backend identifier not exposed).
- Completed: **72 novel labeled mutants, {len(misses)} main misses, zero candidate misses**, plus one freshly replayed shared-gate control. No push, submission, or main-branch commit.
- Baseline: `59be830bae1042fab164d330ceb7617e49b52a4f`.
- Final candidate: **`{ref}`**, branch `w/t47`, worktree `/home/benmross/herald/projects/blast-radius/work/wt/t47`.
- Standalone widening rule: **`79d448758064d2c5661574357ab7c8f34619ddf2`**. Artifacts and labels are in the rest of the branch. It is ready to review/cherry-pick; no integration with the concurrent narrowing branches is claimed.
- Additional widening: **`e8e33808ec069266854fd6bd6e4a2973a822111d`**, porting t44’s indexed qualified-consumer fix only (no narrowing proofs).
- Gate versus `dc913410055bea94a97ceba751aa59f9f51df972`: **{'PASS' if 'PASS '+ref in gate_text else 'NOT PASS'}**. Record: `{gate}`.
- Started 2026-11-21 11:58:41 UTC; finished {time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())}; elapsed {(time.time()-1795262321)/60:.1f} minutes. Deadline 13:28:41 UTC.
- Recommendation: keep the class-base guard and the qualified-consumer widening when evaluating the final entry; the latter is already available on t44’s branch. It removes real structurally blind misses with no selection/cost changes on the sample, frozen tracked corpus, earlier cohorts, or 600 proxies.
- No t47 label container or handoff watcher remains running. Shared pinned source is pristine; the isolated label overlay was restored.

## Why this widening is needed

A class header executes before test coverage. Removing a base introduces no new lexical name, so `could_raise` does not widen it. The old fallback credits only the module's old runtime/instance users: 224 tests for errors.py and 1,540 for expressions/core.py. Exception matching and inherited protocols affect tests outside those users, including dialect collection/lazy-loading tests.

The rule compares the bases of existing import-time classes by qualified name and AST. A changed base list selects import/implicit protocol users (all tests for sqlglot modules). It leaves body edits, formatting and unchanged bases on their existing paths; local runtime classes retain their existing handling. The same blind spot applies to base swaps and MRO reorders, so the predicate covers semantic base-list changes rather than only lexical deletions. Four focused checks fail before the fix and pass after; a fifth verifies that a body edit does not trigger it. No patched code is executed, and runtime code never reads labels, manifests or outcomes.

## Misses and their rule

All use the single standalone rule commit above. Failure counts below are full numbered-suite observations, with only test 1490 deselected.

| Mutant | Change | Failing | Main selected | Omitted failures | Candidate selected |
| --- | --- | ---: | ---: | ---: | ---: |
''']
for c,r in misses.items():parts.append(f"| {c} | {r['description']} | {len(r['failing'])} | {len(r['main_selected'])} | {len(r['missing'])} | {len(r['candidate_selected'])} |\n")
parts.append('\n## Additional shared-gate miss and separate widening\n\nThe first exact gate, on 7f6b6c3575802a02cdcda8ddc7a95ef1103f9f5c, added 12 t44 labels beyond the frozen 412 plus t47’s 72. It exposed a44l01, a known main-59be830 miss: MySQL TIME_MAPPING `%i` changes from `%M` to `%-M`, adding no new word. Presto copies the table by class name, and the old selector keeps only MySQL users. It fails seven tests and omits 434 (Hive test_time) and 624 (Presto test_to_char).\n\nA fresh rosserver full-suite replay under the same 2 CPU / 2 GiB caps confirms exactly [93, 383, 434, 449, 623, 624, 678] in 106 s, with only 1490 deselected. This control is separate from the 72 new-kind cohort. Its oracle, provenance and compressed reports are in mutants/t47-extra/.\n\nSeparate commit e8e33808ec069266854fd6bd6e4a2973a822111d ports only t44’s widening from aa08ed6/650f87e and regression from ab55fc2. It keeps import-copy and runtime users of a changed qualified class attribute using the pristine build-time index. The new selection is 444 tests and covers all seven failures. Both new regression variants fail before the fix. All 168 selector tests pass afterward.\n\nThe 12-case t44 control set improves from one miss / 587.705 simulated seconds to zero / 287.705 seconds. Execution cost is unchanged at 287.705 seconds. The two-rule candidate is selection-identical to the class-only candidate on all 72 t47 cases and all previously frozen sets. See reviews/t47-rule1-costs.json for the first widening alone and reviews/t47-costs.json for the combined candidate.\n')
parts.append('''
## Fixed-set cost evaluation

Simulated seconds include worker execution and 300 seconds per missed commit. Proxy sets have no failing-test oracle; their figures are execution cost only. The tracked 412 ids were frozen before t47 labels; t14/t15/t24a/t30 are overlapping breakdowns of that set, and t3 is the separate original 20-case cohort. Old oracle quality limits remain those documented by earlier workers. Combined cost measurements use runtime commit e8e33808ec069266854fd6bd6e4a2973a822111d; its selector, map, comparison profile and Dockerfile are identical to the final artifact commit.

| Set | Commits | Baseline s | Candidate s | Misses before → after | Widened / narrowed |
| --- | ---: | ---: | ---: | --- | --- |
''')
for name in ['sample','tracked','t3','t14','t15','t24a','t30','t44','hid','fresha','freshb']:
 r=costs[name];a,b=r['baseline'],r['candidate'];miss='unlabeled' if name in ['hid','fresha','freshb'] else f"{len(a['misses'])} → {len(b['misses'])}"
 parts.append(f"| {name} | {a['commits']} | {a['simulated_seconds']:.3f} | {b['simulated_seconds']:.3f} | {miss} | {len(r['widened'])} / {len(r['narrowed'])} |\n")
t=costs['t47'];parts.append(f"| t47 | 72 | {t['main_simulated_seconds']:.3f} | {t['candidate_simulated_seconds']:.3f} | {t['main_misses']} → {t['candidate_misses']} | see exact per-id matrix |\n")
parts.append(f"\nOn t47, execution cost changes from {t['main_execution_seconds']:.3f} to {t['candidate_execution_seconds']:.3f} seconds while removing {t['main_misses']} missed-commit penalties. Exactly {len(t['widened_ids'])} selections widen and {len(t['narrowed_ids'])} narrow.\n")
parts.append('''
The class-base rule fires on **0 of 600 proxy commits**. The qualified-consumer rule fires on **71 of 600** (14 hid, 24 fresha, 33 freshb), but changes no proxy selection. Each rule adds **0 simulated seconds** on the proxies, samples, frozen 412-case corpus and prior cohorts. A previously unselected commit that triggers full selection costs 36.815 seconds instead of risking a 300-second miss. `reviews/t47-costs.json` records per-set CPU, rule firings and selection comparisons; `reviews/t47-eval-ids.json` fixes the ids.

## Class inventory and oracle scope

The initial exploration pool had 79 candidates. Seven redundant expression-MRO reorder variants (015–021) were removed before labeling; `gen.py --all` preserves their stable ids for later exploration. The delivered cohort contains 72 unique patches, including the fully labeled Column reorder representative and the schema reorder. It avoids earlier rounds' generic default edits, decorator removals, dataclass fields, fixture changes, table shapes, file moves and cache pollution. Runtime exception dispatch, descriptor binding replacement, keyword-only/positional-only binding and iteration protocol probes extend the earlier import-fallback/decorator controls with distinct mechanisms.

| Class | Labeled | Breaking | Main misses | Scoped all-selected controls |
| --- | ---: | ---: | ---: | ---: |
''')
for name,rs in sorted(groups.items()):parts.append(f"| {name} | {len(rs)} | {sum(bool(r['failing']) for r in rs)} | {sum(bool(r['missing']) for r in rs)} | {sum('tests' in r for r in rs)} |\n")
parts.append(f'''
Labels ran on rosserver only, in one t47 container at a time with 2 CPU quota and 2 GiB memory/swap caps. First 38 labels used two pytest workers; later labels used one pytest process, cpuset 0–1. Legion was checked, but occupied by another label container when eligible, so it was not used. The image was cached `br-t24b3`, id `{q['image_id']}`, Python 3.13.18, with requirements.lock installed. Pinned source: eb11aec4be8cb2122afe713a4816662c3f0fb2fa.

The pristine full baseline passed: 1619 passed, 1 skipped, 1 deselected, 25440 subtests passed, 119.47 seconds. Test max_nodes (1490) is the only full-suite deselection. There is no baseline failure subtraction. The 37 all-selected controls run targeted suite files; their failure counts are lower bounds, and a selection miss is impossible because main selects all 1,620 tests. The other 35 labels run the full suite. Structured pytest reports preserve failed subtests and collection errors. The labeler rejects an OOM-tainted run; none was accepted. Raw logs and reports remain under mutants/t47/ (ignored); a compressed structured-report archive is committed.

Checks: 168 selector tests and 22 tools tests pass; all 72 patches apply and compile. Final source checksums match pristine. Gate output below reports image CPU and host/image consistency.

## Every labeled mutant

≥ marks the 37 scoped all-selected controls. Exact failing ids and both selected sets are in `mutants/t47/matrix.json`; compact labels are in `answers.json`.

| ID | Class and change | Failing | Main selected | Main miss | Candidate selected | Candidate miss |
| --- | --- | ---: | ---: | --- | ---: | --- |
''')
for c,r in sorted(rows.items()):parts.append(f"| {c} | {r['kind']}: {r['description']} | {'≥' if 'tests' in r else ''}{len(r['failing'])} | {len(r['main_selected'])} | {'MISS '+str(len(r['missing'])) if r['missing'] else 'no'} | {len(r['candidate_selected'])} | {'MISS' if r['candidate_missing'] else 'no'} |\n")
parts.append('\n## Exact final gate record\n\n```text\n'+gate_text.strip()+'\n```\n')
result=TASKS/'t47-blast-newkinds4.result.md';temp=result.with_suffix('.md.tmp');temp.write_text(''.join(parts));temp.replace(result)
print('wrote',result,ref)
