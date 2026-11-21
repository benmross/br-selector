# t41 blast string labels: result

Worker t41-blast-string-labels in lane B-safety, Kiro engine, model claude-opus-5.5. This worker submitted nothing, did not write to queue/ or push main, and left selector.py unchanged.

## Handoff

- Branch `w/t41` on origin (worktree `blast-radius/work/wt/t41`, from main 59be830). Final commit: see `git ls-remote origin w/t41`.
- 82 string-literal-only patches in `mutants/t41/commits/` (generator `mutants/t41/gen.py`, manifest `mutants/t41/manifest.json`). Each makes main select all 1,620 tests through "possible import failure, everything", and t40's instrumented copy names tok-str for every one.
- Labels: 73 of 82 recorded in `mutants/t41/answers.json` (t30 format) at 6:36 AM, at least 10 in every stratum. The container br-label-t41 is still labeling the last 9 (75 to 90 s each, done near 6:50 AM).
- Collect the rest: `sh tools/t41_sync.sh` from the worktree (pulls answers.json and logs from `legion:~/br/t41/mutants/t41/`, rewrites `reviews/t41-matrix.md`), then commit `mutants/t41/answers.json reviews/t41-matrix.md` and push w/t41. The container stops by itself when the queue is empty; ~/br/t41/watch.sh stops it if Legion falls under 5 GiB available.
- Per-patch matrix: `reviews/t41-matrix.md` (failing tests, main's selection and reason string, dc91341's selection and miss, and main with tok-str cleared).

Recommendation for t32 (step 4): tok-str can be cleared for a changed string in a lambda body, a docstring, a test skip reason, an import-time regex that still compiles, or a key or value in a class-level table, **unless** another module reads that table at import (`TIME_MAPPING = MySQL.TIME_MAPPING` in presto.py). That exception is the only labeled miss for main with tok-str cleared (t41x047). The Dialects enum renames (t41x050-052) are covered only because main's separate "class Dialects never instantiated, module runs at import: everything" rule catches them; dc91341 misses all three.

## Results (73 labeled)

"Main-cleared" is main with could_raise forced to False (`tools/t41_cleared.py`, analysis only). Every t41 patch is tok-str only, so this is exactly what a tok-str narrowing would select. A miss is a labeled failing test outside the selection.

| Stratum | Patches | Labeled | Breaking | Main fallbacks | dc91341 misses | Main-cleared misses |
|---|---:|---:|---:|---:|---:|---:|
| a call-time string (lambda body) | 14 | 11 | 11 | 14 | 0 | 0 |
| b table value | 12 | 11 | 10 | 12 | 0 | 0 |
| c table key | 11 | 11 | 8 | 11 | 0 | 0 |
| d parsed or compiled at import | 10 | 10 | 3 | 10 | 1 | 1 |
| e name for lookup or dispatch | 13 | 10 | 7 | 13 | 3 | 0 |
| f tests/ | 12 | 10 | 5 | 12 | 1 | 0 |
| g docstrings | 10 | 10 | 0 | 10 | 0 | 0 |
| all | 82 | 73 | 44 | 82 | 5 | 1 |

Main selects 1,620 on every patch (reason ends "possible import failure, everything").

The misses:

| Patch | Stratum | Change | Failing | dc91341 selects, misses | Main-cleared selects, misses |
|---|---|---|---:|---|---|
| t41x047 | d | MySQL TIME_MAPPING key `"%i"` to `"%n"` | 7 | 291, misses TestHive::test_time and TestPresto::test_to_char | 291, same 2 |
| t41x050 | e | Dialects enum `TSQL = "tsql"` to `"mssql"` | 1 | 2, misses TestGenerator::test_generator_memory | 1,620, none |
| t41x051 | e | `DORIS = "doris"` to `"apache_doris"` | 2 | 0, misses test_generator_memory and TestTime::test_canonical_time_format_vocabulary | 1,620, none |
| t41x052 | e | `DRILL = "drill"` to `"apache_drill"` | 1 | 0, misses test_generator_memory | 1,620, none |
| t41x065 | f | tests/helpers.py `FIXTURES_DIR` "fixtures" to "test_fixtures" | 90 | 96, misses TestJsonpath::test_cts_file | 1,377, none |

- t41x047: presto.py sets `TIME_MAPPING = MySQL.TIME_MAPPING` in its class body, and Hive's time test transpiles through Presto. Both selectors credit only MySQL's 291 users. t41x048 (key `"%M"` in the same table) has 8 failures, all inside the 291, so a key-versus-value rule would not separate them; the alias reader does.
- t41x050-052: test_generator_memory and test_canonical_time_format_vocabulary iterate `for name in Dialects` and resolve each value by name, so no test reads the attribute itself. These labels support t32's relabel of m1x022 (`TSQL` to `"tsqlx"`, failing both of those tests) over gate238's empty label for it.
- t41x065: test_jsonpath reads the fixtures directory through `tests.helpers`, which dc91341's coverage misses.

Notes on strata:
- (a): a string inside a `def` body never reaches could_raise on main because that scope is runtime. The call-time strings that do reach tok-str are lambda bodies in class tables (TRANSFORMS), so all 14 (a) patches are of that kind.
- (f): fixture files (.sql) are not Python and never reach could_raise, so (f) contains Python test modules only: fixture paths, skip reasons, `dialect = "..."` class names, leakcheck constants.
- (g): no docstring edit broke any test; dc91341 selects 0 on 8 of them.

## Step 4: narrowest supported condition (recommendation only)

Clear tok-str for a file when every changed string literal is one of:
1. inside a lambda body (11 labeled, 0 misses either way);
2. a docstring (10 labeled, 0 failures);
3. a regex literal compiled at import that still compiles (t41x040-046, 0 misses; a regex that stops compiling is already handled by main's bad_regex_at_import rule);
4. a key or value in a class-level or module-level table, provided no other module reads that table at import (b and c: 22 labeled, 0 misses);
5. in a test module: a skip reason, a test class `dialect` name, or a fixture path (0 misses for main-cleared).

Keep tok-str (or add the readers before clearing it) when:
- another module aliases or reads the changed table at import. Contradicting patch: t41x047.
- the string is an Enum member value used as a registry name. main-cleared covers t41x050-052 only through the "class Dialects never instantiated" rule. A narrowing may rely on that rule but must not remove or weaken it.
- the string is a module constant in a test-support module (tests/helpers.py). main-cleared catches t41x065 (1,377 tests); dc91341 does not.

Simpler conditions the labels contradict:
- "Clear every string-only change": t41x047 (main-cleared misses 2).
- "Clear when dc91341 would select the failures": t41x047, t41x050, t41x051, t41x052, t41x065.
- "Clear table keys and values": t41x047 is a table key. Its sibling t41x048 does not miss, so only the import-time alias reader explains the difference.

## Method

- Step 0: worktree work/wt/t41 on w/t41 from 59be830; index built from pristine sqlglot (eb11aec) in 20 s on one CPU.
- Step 1: 84 candidates from `mutants/t41/gen.py`, each one to three lines, changing text inside string literals only and adding a word absent from the removed tokens. Main's selector (`mutants/t41/main-select.why`) and t40's trigger copy (`mutants/t41/trigger.why`) were run on all of them. 82 take tok-str and the two sets are equal. Dropped: t41x019 (exasol STRING_TYPE_MAPPING value, main's literal_only clears it, 45 tests) and t41x074 (leakcheck string in a function body, runtime scope, 0 tests). Four candidate ids (x020, x038, x067, x083) matched their text more than once and were never emitted.
- Step 2: Legion container br-label-t41, `--cpuset-cpus 8,9 --memory 2g --memory-swap 2g`, python:3.13-slim at t30's digest, `tools/label.py` unchanged, pinned source copied from t30's kit (`~/br/t41/pinned`, eb11aec), the same tests.json (md5 checked), and `tests/test_parser.py::TestParser::test_max_nodes` deselected as in t30. Baseline: no failures. Free memory stayed between 7 and 15 GiB, and no OOM occurred (label.py refuses OOM-tainted labels). br-label-t32-rest had already exited and was not touched. CPUs 8 and 9 are SMT siblings of one core, so LABEL_N=2 gave no speedup: 105 s per patch under load early on, 75 s later. The order interleaves strata (`answers.json.order`).
- Step 3: dc91341 selections were made in worktree work/wt/t41-dc with its own index (`mutants/t41/dc91341.jsonl`, `.why`). Main-cleared: `mutants/t41/main-cleared.jsonl`. The report is `tools/t41_report.py`.
