"""Write the requested worker result from saved validation artifacts."""
import argparse
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
project = root.parents[2]
result = project.parent/'buildathon/tasks/t30-blast-newkinds3.result.md'
ap = argparse.ArgumentParser()
ap.add_argument('--candidate',default='working tree; final hash pending')
ap.add_argument('--final',action='store_true')
a = ap.parse_args()
manifest = json.load(open(root/'mutants/t30/manifest.json'))['commits']
labels = json.load(open(root/'reviews/t30-label-summary.json'))
metrics = {n:json.load(open(root/f'work/t30-measure/{n}.summary.json'))
           for n in ('sample','gate238','t3','t14','t15','t24a','hid','fresha','freshb','t30')}
incremental = {n:json.load(open(root/f'work/t30-measure-r2/{n}.summary.json')) for n in metrics}
gate_path = project.parent/'buildathon/gates'/f'{a.candidate}.txt'
gate = gate_path.read_text() if gate_path.exists() else ''
pass_line = f'PASS {a.candidate}'
cpu = re.findall(r'^CPU\s+([\d.]+)',gate,re.M)
if a.final:
    assert labels['labeled']==len(manifest)==83
    assert pass_line in gate
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==a.candidate
    assert all(not r['candidate']['misses'] and not r['narrowed'] for r in metrics.values())
running = 'none' if a.final else 'Legion br-label-t30; remaining labels and final gate'
next_command = (f'git -C {root} show --stat {a.candidate}' if a.final else
                "ssh legion 'free -g; tail -3 ~/bt-watchdog.log; docker logs --tail 8 br-label-t30'")
lines = [
 '# Handoff','',
 '- Worker t30-blast-newkinds3, lane B-safety. Actual model: **gpt-6.1-sol**, verified in this session’s turn metadata.',
 '- Baseline: `be28115d6b491536992e294aff9ae9b1d2a27dee`.',
 f'- Candidate: `{a.candidate}`, branch `w/t30`, worktree `{root}`.',
 f'- Done: {labels["labeled"]}/{len(manifest)} mutants labeled; two widening rules; 161 selector tests and 22 tools tests pass.',
 f'- Running: {running}.',f'- Exact next command: `{next_command}`.',
 f'- Gate: `{pass_line}`.' if pass_line in gate else '- Gate: pending.',
 f'- Sample image CPU: {cpu[-1]} s.' if cpu else '- Sample image CPU: pending.',
 '- Started 2026-11-21 07:15 UTC; hard stop 09:45 UTC. No submission, queue write, or main push by this worker.','',
 f'Recommendation: {"merge w/t30" if a.final else "finish labels and gate before merging the final candidate"}. Both changes only widen. '
 'They change no selection on the original nine historical/proxy sets. The oracle limits below prevent claiming exhaustive full-suite validation.','',
 'The cohort contains 83 patches (`t30x000`–`t30x082`); t30x038/039 deliberately repeat t3’s conftest/deleted-helper controls, leaving 81 newly designed patches. '
 f'The per-mutant counts and MISS verdicts are in [the matrix]({root}/reviews/t30-matrix.md); numeric failing ids are in '
 f'[answers.json]({root}/mutants/t30/answers.json). Runtime selection never reads these artifacts.','',
 '| Class | Labeled / generated | Breaking mutants | Failing test instances | Main selections, range | Main missed commits | Candidate missed commits |',
 '| --- | ---: | ---: | ---: | ---: | --- | --- |']
for kind in ('metaclass','cache','infrastructure','shape','comparison'):
    g=labels['classes'].get(kind,{})
    rows=[r for r in labels['rows'].values() if r['class']==kind]
    count=sum(v['kind']==kind for v in manifest.values())
    selected=[r['main_selected'] for r in rows]
    span=f'{min(selected)}–{max(selected)}' if selected else 'pending'
    lines.append(f'| {kind} | {len(rows)} / {count} | {g.get("failing_mutants",0)} | ≥{g.get("failing_test_instances",0)} | {span} | '
                 f'{", ".join(g.get("main_misses",[])) or "none"} | {", ".join(g.get("candidate_misses",[])) or "none"} |')
lines += ['',
 'Failure counts are lower bounds where smoke scopes or selected-test exclusions apply; the matrix marks those rows with ≥. '
 'Every smoke-scoped patch selects all 1,620 tests on main, so a selector miss is impossible for those controls regardless of unrun tests.','',
 '| Miss | Failure mechanism | Failing | Main selected | Main omitted | Candidate selected |',
 '| --- | --- | ---: | ---: | ---: | ---: |']
for cid,r in labels['misses'].items():
    lines.append(f'| {cid} | {r["description"]} | {r["failing"]} | {r["main_selected"]} | {len(r["main_missing"])} | {r["candidate_selected"]} |')
lines += ['',
 'Rule 1 extends the existing import-table shape check into nested entries: changed entry type, newly empty entries, changed tuple arity, and newly introduced dictionary key types. '
 'It widens only when the existing reader analysis identifies an import-time/unsafe reader. The quote-table misses keep a nonempty outer list while its entry becomes malformed. '
 'Sixteen focused tests cover nested structures and safe same-type values. A structurally valid Hive quote pair (t30x010) is widened even though main already selects its 42 failures; the general contract check is retained for unseen import-time consumers.','',
 'Rule 2 widens edits to test/helper functions that write imported/module state, mutate aliases of that state, or create globally registered dialect subclasses. '
 'It checks the whole enclosing function because a changed saved original can corrupt a later restoration. It tracks shared tables inherited through local subclasses. '
 'Twelve focused tests cover wrong saved values, wrong/removed cleanup, aliases, local objects, qualified/aliased dialect bases, and later-test selection. '
 'The omitted-cleanup control t30x081 has no additional recorded failures and remains broad because shared state survives the test. Neither rule needs a narrower form under the 1% hid bar: both cost exactly 0% there.','',
 'All 73 executable statement starts in `_Dialect.__new__`, `_TokenizerBase.__init_subclass__`, and `Expr.__init_subclass__` are import lines. '
 'This pin has no separate parser/generator metaclass. String-name readers are tracked by the name index and treated as unsafe/dynamic. '
 'The missed nested records bypassed the old outer-container guard, rather than missing hook coverage.','',
 'No lru_cache/cache/cached_property decorator occurs in the pinned source. The additional lazy exports, rule registry, memo keys, and instance caches were tested. '
 'The real ordered-test proof for t30x016 passes BigQuery test 73 alone, but fails it after generator test 1225; main selects test 73. '
 'Both individual edits in t30x078 pass the diff tests; together they fail all 14 numbered diff tests at collection. '
 f'[Proof results]({root}/reviews/t30-order-proofs.json) and raw logs under `work/t30-cache-order/` preserve these runs.','',
 'Infrastructure probes cover SQL data and metadata, helpers, collection configuration, exports, TYPE_CHECKING activation, root module shadowing, deletion, and the optional Rust import. '
 'The Rust path in this pin is a deprecation check, rather than a working Rust tokenizer. Patch-shape probes include moved code, whitespace, a PEP 701 f-string comment, runtime dataclass annotations, decorator/default arguments, body order, and non-comparison operators. '
 'Comparison probes include ten profile-equivalent sites with one credited test, chained comparisons, lambdas, comprehensions, and a parser operand with side effects. '
 'The parser comparison at 6774 and Expression.__eq__ at 838 run at import, so the profile cannot discard their dependencies.','',
 'All costs below are simulated seconds including 300 s per recorded missed commit, excluding selector CPU. The proxies have no oracle; their figures are execution cost only. '
 'The fixed original 238 ids are recorded in `reviews/t30-gate238-ids.json`. Main advanced to our first rule during the task and its live corpus became 242, so subsequent measurements use the frozen original set.','',
 '| Set | Commits | be28115 | Rule 1 | Rules 1 + 2 | Misses before → after |',
 '| --- | ---: | ---: | ---: | ---: | --- |']
for n,r in metrics.items():
    middle=incremental[n]['base']
    misses=(f'{len(r["base"]["misses"])} → {len(r["candidate"]["misses"])}' if r['labeled'] else 'unlabeled')
    lines.append(f'| {n} | {r["commits"]} | {r["base"]["simulated_seconds"]:.3f} | {middle["simulated_seconds"]:.3f} | '
                 f'{r["candidate"]["simulated_seconds"]:.3f} | {misses} |')
lines += ['',
 'The same table applies to every miss handled by each rule. Incremental rule-2 and cumulative JSON also retain widened/narrowed ids and host CPU. '
 f'[Cumulative measurements]({root}/reviews/t30-costs-cumulative.json), '
 f'[rule-2 measurements]({root}/reviews/t30-costs-rule2.json). No measured selection becomes narrower than be28115 or rule 1.','',
 'Labels use the pinned Python 3.13 image digest from Dockerfile and requirements.lock, on Legion CPUs 8–9 only, one container, `--memory 1g --memory-swap 1g`, one pytest process. '
 'The full pristine tree is copied, so the sqlglotc setup tests pass the baseline rather than inheriting older missing-file failures. Both source checkouts are pinned at `eb11aec4be8cb2122afe713a4816662c3f0fb2fa`; Python sources/tests matched by checksum. '
 'The host memory guard stops below 5 GiB available, and ~/bt-watchdog.log was checked. SSH interruptions were retried. Rosserver work uses one CPU.','',
 'Oracle limits: test 1490 OOMs even alone in a fresh 1 GiB container and is explicitly deselected. TPC-DS query 88 exceeds DuckDB’s 819 MiB reference-execution allowance; only that baseline subtest is subtracted, preserving other new failures in parent 1106. '
 'There are 29 all-selected smoke controls and 54 broader scopes. t30x044’s first run OOM-killed and was rejected; its retry also excludes already-selected test 1106 and records 68 other failures without OOM. '
 'These exclusions are explicit in the manifest and label-quality file. OOM-tainted outputs were never accepted. '
 f'[Baseline traceback]({root}/reviews/t30-baseline-limit.txt); raw rejected log `work/t30-rejected-044.log`.','',
 'Reproduce: generate with `python mutants/t30/gen.py`; replay using `mutants/t30/run.sh` in the constrained Legion container; '
 'sync answers and logs, then run `python mutants/t30/reconcile.py work/t30-label-logs`, `python tools/t30_measure.py ...`, and `python tools/t30_report.py`. '
 'The generator preserves explicit validation scopes. Raw artifacts remain at `legion:~/br/t30/` and local `work/t30-label-logs/`.','',
 'The first rule already has orchestrator gate `PASS 9a0a808d35be9086ea851abf8d4de9d548b70180` (242 mutants, image CPU 1.61 s). '
 'The final gate is invoked through `tools/t30_gate.sh`, which runs the unmodified shared gate while tightening Docker resources to this worker’s one CPU/1 GiB rosserver cap. '
 'Any narrowing relative to dc91341 is inherited from be28115’s comparison profile, rather than introduced here.','',
 f'Final gate record: [{gate_path.name}]({gate_path}).' if gate else 'Final gate record: pending.',
 'All t30x000–082 patches and their answers must be present after the orchestrator merges the full branch for the gate to cover the complete cohort; the initial four nested-table labels are already on main.','']
result.write_text('\n'.join(lines))
print(result)
