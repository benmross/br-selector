# Handoff

- Done: old/main attribution on 838 inputs; 11 lineage checkpoints; 85 real audit labels; proof implementation and 191 selector tests plus 20 tools tests. Branch `w/t32` is pushed. Actual model: **gpt-6.1-sol**.
- Candidate: `cba67182cecd413f7f8bacb25c488a564b768f4e`; baseline: `be28115d6b491536992e294aff9ae9b1d2a27dee`; comparator: `dc913410055bea94a97ceba751aa59f9f51df972`.
- Done: repeated all required before/after sets after integrating current-main safeguards; fresh 30/30 and audit 85/85 have zero observed misses. Running: gate PID 599282, work/t32/final-integrated-gate.log. Host and image both have zero misses on 412 mutants and match all 412 plus two edge patches; sample image CPU 1.24 s. Only dc91341 comparison is still running. Do not claim final PASS until its record says PASS. Next: HOLD for t41 answers and ordered m1x022 reconciliation. No submission, queue write, or main push. Deadline 09:51:33 UTC (04:51 EST).
- Exact immediate next command: `tail -20 ../buildathon/gates/cba67182cecd413f7f8bacb25c488a564b768f4e.txt`; gate PID 599282 continues its old-selector comparison. Keep the one-gate lock discipline.
- Exact next command after t41 answers exist: `taskset -c 3 python3 tools/t32_measure.py . ../t41/mutants/t41 work/t32/t41` followed by `python3 tools/report.py ../t41/mutants/t41 work/t32/t41.jsonl`. Merge current main and gate that exact hash only after zero misses.
- Exact review command: `git show cba67182cecd413f7f8bacb25c488a564b768f4e:reviews/t32/narrowed.md`; final gate record: `../buildathon/gates/cba67182cecd413f7f8bacb25c488a564b768f4e.txt`.

## Outcome and limits

The candidate proves narrower import handling for inert name mentions, same-type literal table edits with audited consumers, and unused stock argparse help metadata. It preserves runtime readers and propagates users through same-name aliases. Proxy selection savings are **367.644 s net** across 600 commits. This is not a hidden-score prediction. Census 2 and the 4:44 EST coordination update, reread before finishing, identifies both hidden full-suite selections as could_raise. The property-comprehension case remains conservative because a sufficient static proof is not implemented.

The branch retains be28115 ancestry. Current main advanced to 59be830 during this run; its selector changes are incorporated by patch rather than a history rebase. In response to coordination, every selector production change from e782551 is now ported: t30 nested-table guards and the three t31 process/cache safeguards. The subsequently published t30 shared-test-state guard is also ported. This is patch integration rather than a history rebase; the final exact source is gated below.

## Old versus robust main

One host Python process per dataset, CPU 3, 1 GiB address-space cap; separate worktrees, maps and indices. Old import-probe subprocess CPU is counted separately. Cost below is selection cost under SCORING.md, including packed worker overhead; miss penalties are separated. Freshb contains 50 patches, giving 600 proxies and 838 total inputs.

| Set | n | dc91341 selection s | main selection s | Delta s |
|---|---:|---:|---:|---:|
| hid | 400 | 3501.803 | 3491.011 | -10.792 |
| fresha | 150 | 1784.348 | 4551.398 | 2767.050 |
| freshb | 50 | 457.419 | 556.021 | 98.602 |
| gate | 238 | 2229.783 | 2989.116 | 759.333 |

dc91341 misses 19 gate commits; its penalty-inclusive score is 7929.783 s. Main misses zero. Never use dc91341 as the final selector.

| Set | Old wall / CPU s | Main wall / CPU s | Candidate wall / CPU s |
|---|---:|---:|---:|
| hid | 4.288 / 4.286 | 9.490 / 8.831 | 14.959 / 7.388 |
| fresha | 39.904 / 31.072 | 26.234 / 23.651 | 39.489 / 19.356 |
| freshb | 0.467 / 0.467 | 4.980 / 4.857 | 9.007 / 4.457 |
| gate238 | 14.560 / 12.799 | 16.813 / 15.999 | 28.169 / 13.943 |

Exact extra/removed test numbers, per-commit simulated seconds, and main’s logged reason are in `reviews/t32/all-diff.json.gz` and the four dataset diff archives. Attribution uses the first independently sufficient widening: an overlapping final could_raise flag does not steal an earlier rule’s cost.

| Main rule | Commits | Added s | Share of gross added cost |
|---|---:|---:|---:|
| could_raise | 120 | 3226.599 | 81.5% |
| at_import | 7 | 232.134 | 5.9% |
| strict_patch_application | 3 | 104.178 | 2.6% |
| inserted_import_code | 2 | 73.634 | 1.9% |
| uninstantiated_class | 2 | 71.619 | 1.8% |
| parse_at_import | 2 | 68.892 | 1.7% |
| coverage_map | 4 | 53.935 | 1.4% |
| protocol_attribute | 1 | 36.817 | 0.9% |
| lookup_at_import | 2 | 35.132 | 0.9% |
| definition_header | 2 | 27.557 | 0.7% |
| reshaped | 1 | 23.658 | 0.6% |
| fixture_readers | 1 | 2.024 | 0.1% |
| removed_name_readers | 1 | 1.945 | 0.0% |
| class_map | 2 | 0.000 | 0.0% |
| removed_key | 3 | 0.000 | 0.0% |

Reverse direction: comparison_profile alone makes main narrower on 40 commits, saving 343.931 s (100% of reverse savings). There are 153 widening commits and no mixed-direction old/main changes. These totals overlap datasets only where their inputs actually repeat.

## Commit-by-commit lineage

| Commit | hid s | fresha s | freshb s | gate selection s | Gate misses | Host CPU s, four sets |
|---|---:|---:|---:|---:|---:|---:|
| old | 3501.803 | 1784.348 | 457.419 | 2229.783 | 19 | 48.624 |
| 88d61b2 | 3702.724 | 5522.550 | 1840.850 | 3107.543 | 18 | 19.959 |
| d1ff7ff | 3702.724 | 5522.550 | 1840.850 | 3107.646 | 18 | 20.849 |
| 42ec341 | 3702.724 | 5522.550 | 1840.850 | 3109.591 | 18 | 20.985 |
| 30013ce | 3702.724 | 5522.550 | 1840.850 | 3285.503 | 14 | 21.558 |
| 443edff | 3702.724 | 5522.550 | 1840.850 | 3309.161 | 13 | 21.106 |
| 525dcf5 | 3567.680 | 4551.398 | 556.021 | 2998.283 | 13 | 30.588 |
| ca971d8 | 3567.680 | 4551.398 | 556.021 | 3042.778 | 6 | 58.310 |
| e0584f8 | 3491.011 | 4551.398 | 556.021 | 2775.516 | 6 | 53.479 |
| e752021 | 3491.011 | 4551.398 | 556.021 | 2809.602 | 5 | 49.392 |
| 1d3e47a | 3491.011 | 4551.398 | 556.021 | 2844.408 | 4 | 47.565 |
| 4bcf1cf | 3491.011 | 4551.398 | 556.021 | 2954.310 | 1 | 45.341 |
| main | 3491.011 | 4551.398 | 556.021 | 2989.116 | 0 | 53.338 |

88d61b2 introduces broad static import-failure protection: the largest cost increase. d1ff7ff adds setup-phase, import graph, definition/protocol readers; 42ec341 covers removed import-level names. 30013ce and 443edff close import/reshape holes. 525dcf5 recovers 2391.025 proxy seconds and 310.878 gate seconds through proved literal handling. ca971d8 closes seven labeled misses. e0584f8’s comparison profile saves 76.669 hid and 267.262 gate seconds. e752021 and 1d3e47a add import-time regex/parse safety (34.086 and 34.806 gate seconds). The 4bcf1cf sibling attributes cached run-once execution to every isolated test; be28115 merges the final safeguards/map, reaching zero misses, +144.708 gate seconds versus 1d3e47a and no proxy delta. Raw selections and reasons for each checkpoint are archived beside lineage-summary.json.

## Real pytest audit

All bulk labels use pinned SQLGlot eb11aec4be8cb2122afe713a4816662c3f0fb2fa and br-t5-map Python 3.13.18. Legion only, cpuset 10-11, one container, memory/swap 1 GiB. At least 15 applicable cases per leading import class, 38 for could_raise. Strict patch application is numerically third but its three malformed/non-applicable patches have no source to execute; retain fallback. The next applicable class, inserted import code, has 15 real cases including 13 new import failures.

| Class | Labeled | Have failures | dc missed commits | Main missed | Candidate missed |
|---|---:|---:|---:|---:|---:|
| at_import | 15 | 10 | 5 | 0 | 0 |
| could_raise | 38 | 25 | 0 | 0 | 0 |
| coverage_or_other | 8 | 4 | 3 | 0 | 0 |
| inserted_import_code | 15 | 15 | 2 | 0 | 0 |
| narrowed_TIME_MAPPING_regression | 1 | 0 | 0 | 0 | 0 |
| protocol_attribute | 1 | 0 | 0 | 0 | 0 |
| read_at_import | 4 | 2 | 0 | 0 | 0 |
| syntax_error | 2 | 2 | 0 | 0 | 0 |
| uninstantiated_class | 1 | 1 | 1 | 0 | 0 |

The top could_raise sample has zero dc misses, but that observation alone is not a safety proof. At-import and inserted-import samples demonstrate necessary widening. The full-suite m1x022 audit records two failures outside old selection, conflicting with the historical empty label. A fresh isolated canonical_time_format_vocabulary baseline and patched run both pass, so this is not an independently reproduced isolated failure; ordered-suite reproduction remains open. Both raw labels are retained and candidate keeps everything. No proof is relaxed on this evidence.

All 15 hid full-suite cases were labeled. Explicit-importer restriction is diagnostic only: it misses five failures on h7x031 and one on h7x172; adding coverage repairs h7x172, still misses h7x031. Thus a blanket importer narrowing is rejected.

| hid commit | Real failures | Old misses (tests) | Importer misses | Importer + coverage misses |
|---|---:|---:|---:|---:|
| h7x031 | 5 | 0 | 5 | 5 |
| h7x035 | 1 | 0 | 0 | 0 |
| h7x079 | 1020 | 0 | 0 | 0 |
| h7x109 | 109 | 0 | 0 | 0 |
| h7x110 | 0 | 0 | 0 | 0 |
| h7x112 | 0 | 0 | 0 | 0 |
| h7x148 | 0 | 0 | 0 | 0 |
| h7x172 | 1 | 0 | 1 | 0 |
| h7x195 | 1020 | 0 | 0 | 0 |
| h7x263 | 0 | 0 | 0 | 0 |
| h7x265 | 0 | 0 | 0 | 0 |
| h7x314 | 3 | 0 | 0 | 0 |
| h7x360 | 13 | 0 | 0 | 0 |
| h7x373 | 1 | 0 | 0 | 0 |
| h7x377 | 1600 | 0 | 0 | 0 |

## Proof implemented

Only a single-file patch can use either new shortcut; another modified file could introduce unseen readers. Token comments and standalone constant-string expression statements are inert name mentions. Assigned strings, executable strings, getattr names and f-strings retain conservatism. Same-name aliases can carry literal values, but their complete mapped class/MRO/module users are included. Different-name copies fail the proof. A regression discovered fa911x023 copying STRING_TYPE_MAPPING into TYPE_MAPPING: it now selects all, adding 24.131 s versus main. This negative saving is included in the net totals.

Literal display changes retain existing same-type/shape and import-reader checks; changed leaves cannot introduce calls or descriptors. Import hooks must match the audited AST patterns, and normal runtime users are retained. argparse proof compares the complete old/new module AST, permits only stock add_argument help-string changes, rejects escaped/shadowed parser objects and custom actions/formatters, enforces a strict constructor/setup prefix, and requires map evidence that help metadata has no runtime/data users or import read. Registration may run at import; its stored metadata is never consumed there. No patched code is executed to establish these proofs.

The t30 nested-table shape guard is included: empty/nested/type/key-shape changes remain conservative. t30x064 and t30x065 are caught (main misses both). Tests cover consumer propagation, comments/docstrings versus executable mentions, parser shadowing/customization, and multi-file invalidation.

Every narrowed commit is listed with its proof and cost in `reviews/t32/narrowed.md`; exact removed IDs are in candidate-narrowed.json.gz. Every added selection is in candidate-widened.json. Unit validation: 191 selector tests and 20 tools tests passed.

## Before / after

| Set | Inputs | Labels | Main selection s | Candidate selection s | Main misses | Candidate misses | Narrow / wide |
|---|---:|---:|---:|---:|---:|---:|---:|
| sample | 30 | 30 | 116.857 | 116.857 | 0 | 0 | 0 / 0 |
| t3 | 20 | 20 | 394.149 | 370.470 | 0 | 0 | 1 / 0 |
| t14 | 17 | 17 | 422.387 | 422.387 | 0 | 0 | 0 / 0 |
| t15 | 25 | 25 | 647.799 | 647.799 | 0 | 0 | 0 / 0 |
| t24a | 6 | 6 | 193.275 | 193.275 | 0 | 0 | 0 / 0 |
| hid | 400 | 0 | 3491.011 | 3454.194 | unlabeled | unlabeled | 1 / 0 |
| fresha | 150 | 0 | 4551.398 | 4220.571 | unlabeled | unlabeled | 15 / 1 |
| freshb | 50 | 0 | 556.021 | 556.021 | unlabeled | unlabeled | 0 / 0 |
| gate238 | 238 | 238 | 2989.116 | 2929.369 | 0 | 0 | 2 / 0 |
| t32 | 30 | 30 | 1104.510 | 196.155 | 0 | 0 | 30 / 0 |
| audit | 85 | 85 | 2982.282 | 2505.653 | 0 | 0 | 19 / 0 |
| t30compat | 2 | 2 | 25.845 | 73.634 | 2 | 0 | 0 / 2 |

Rows report selection cost; each missed commit adds 300 s in the score. Proxies have no complete failure oracle, so absolute zero misses on all 600 cannot honestly be asserted. Every original proxy commit made narrower was relabeled in the 85-case audit, with zero candidate misses. Unchanged/wider selections introduce no selection misses relative to main. Audit rows repeat some original inputs; do not sum them as independent workload.

Fresh t32 has 30 distinct generated patches: 15 nonempty unique TIME_MAPPING keys with full runtime suites; one help control with a full suite; fourteen help controls with full test collection plus a targeted runtime smoke (TestTime/test_format_time), explicitly scoped in manifest. Their zero-runtime-reachability proof supports the narrowing; these fourteen are not full-suite labels.

All full runtime runs explicitly deselect five resource-sensitive cases: test_execute_tpcds, test_max_nodes and three SQLGlotC build/installation tests. No runtime evidence is claimed for those five. Original frozen labels are preserved by union when publishing duplicate IDs; current raw audit labels remain separately archived. Two two-worker attempts OOMed on supplemental cache/table checks; their tainted/incomplete results were discarded, five optional cache probes remain unlabelled, and work resumed with one pytest worker and an OOM monitor. No OOM-derived labels are accepted.

## Gate

The initial gate failed from a Docker CLI Go virtual-address limit, not a selector miss. Gate 8b43b84 passed its 238 mutants before later consumer-propagation/shape safeguards; it is not the final candidate. Expanded-corpus gate b1eb10f failed on three newly published t30 shared-state mutants (t30x079, t30x080, t30x082). Their existing upstream guard was integrated, along with t31 process fixes; the failed gate is preserved in reviews/t32/failed-expanded-gate.txt. Final exact-candidate record follows (the late t41 condition is still pending and this run does not satisfy it):

```
Simulated: 116.857 s
Misses:    0 (0.000 s of the simulated time)
CPU:       not measured here. The simulated seconds above are exact. The board adds the CPU seconds your container used and takes the middle of 3 runs.
mutants: 412 commits, 0 misses; total 7054.7 s   floor about 3601.4 s
Simulated: 116.857 s
Misses:    0 (0.000 s of the simulated time)
CPU 1.24
image differs from host on 0 of 412 mutants
image differs from host on 0 of 2 edge patches
```

Final gate comparison explanations are in `reviews/t32/gate-narrowing.md` when the run completes. Inherited c21 comparison-profile cases use the existing observed operand-pair union and a zero profile bit for the replacement operator; they retain import guards and all original failing labels. New help controls use the stock unused-help proof above.

## Resources and recommendation

Valid final single-worker label epoch: {
  "wall": 2120.8519806609984,
  "cpu": 2465.53227,
  "exitstatus": 0
}

First successful label container CPU lower bound: 4289.415 s (last cgroup snapshot before clean exit); final image CPU is in the gate record. CPU/memory snapshots are archived under reviews/t32 when copied. Host available memory remained above 5 GiB. Successful first/final cgroup snapshots total at least 6757.834 CPU s; discarded OOM epochs add at least 1761.912 CPU s. Raw per-epoch snapshots preserve their cost. Final subprocess descendant CPU is 2465.532 s over 2120.852 wall s; cgroup CPU includes bootstrap/monitor overhead. Full pytest output and per-mutant reports are archived in label-evidence.tar.gz.

Recommendation: HOLD for the newly required t41 batch and the ordered m1x022 label reconciliation, even if the technical gate below passes. At the final check, t41 has generated commits and a manifest but no answers yet; its required 70-plus independent labels cannot be claimed. Review this exact candidate with its scope limits, merge current-main ancestry, and gate that exact merged hash after t41 records zero misses. No tok-str proof was tuned using t41 patches. Do not roll back the robust safeguards. This reduces a large provable proxy could_raise component, but no hidden gain is established. The next useful proof target is h7x031’s property-parser comprehension: it costs 26.794 extra seconds while old’s narrower 219-test selection covers all five failures. A closed initialization/typed-table proof is still missing, so this candidate keeps the fallback. The hidden gap is 27.947 s, but identifying that hidden patch with h7x031 would be speculation.

Coordination read through the 4:44 EST update, including pending census 4 and the required t41 batch, checked again before stopping. Final handoff prepared before 09:51:33 UTC, the 150-minute deadline. Source candidate and later evidence-only branch HEAD have identical selector/map/cmp/Docker inputs; only the exact source candidate named above has the recorded gate.
