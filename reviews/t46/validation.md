# t46 validation

Source candidate: 67317971128babe6a704cd36f5fa7c6fee3d6207. Baseline: ab55fc225b6e8d773734f67b8da2c072e6583bf3, with requested start a51c3018af09df9eed79918278f8b63ffefee0a9 measured separately. Every stage snapshot was byte-checked against its commit.

| Set | Inputs | Labels | Baseline selection s | Candidate selection s | Candidate misses | Baseline host CPU s | Candidate host CPU s |
|---|---:|---:|---:|---:|---:|---:|---:|
| sample | 30 | 30 | 116.857 | 116.857 | 0 | 0.946 | 0.887 |
| tracked | 424 | 424 | 7161.546 | 6984.938 | 0 | 37.364 | 34.287 |
| t41 | 82 | 82 | 2948.791 | 1721.508 | 0 | 12.265 | 12.149 |
| gate238 | 238 | 238 | 2929.369 | 2874.158 | 0 | 19.816 | 21.159 |
| audit | 85 | 85 | 2505.653 | 2384.256 | 0 | 10.579 | 12.690 |
| hid | 400 | 0 | 3454.194 | 3445.519 | unlabeled | 10.712 | 9.499 |
| fresha | 150 | 0 | 4220.571 | 3358.298 | unlabeled | 26.824 | 26.349 |
| freshb | 50 | 0 | 556.021 | 556.021 | unlabeled | 6.474 | 6.390 |
| t3 | 20 | 20 | 370.470 | 333.653 | 0 | 1.889 | 2.394 |
| t14 | 17 | 17 | 422.387 | 422.387 | 0 | 3.691 | 4.041 |
| t15 | 25 | 25 | 647.799 | 647.799 | 0 | 3.002 | 3.528 |
| t24a | 6 | 6 | 193.275 | 193.275 | 0 | 1.731 | 1.859 |
| t32 | 30 | 30 | 196.155 | 196.155 | 0 | 4.017 | 4.707 |
| t30 | 83 | 83 | 2153.452 | 2153.452 | 0 | 7.670 | 9.333 |
| edge | 2 | 0 | 73.634 | 73.634 | unlabeled | 0.597 | 0.470 |

Costs exclude miss penalties in the selection columns. Each missed commit adds 300 s. Sets overlap; do not sum as independent tests. Serial host measurements use t32_measure.py, one CPU and 1 GiB; production images retain the actual analysis limits. The 600 proxies have no complete failure oracle.

## Image measurements

Exact scorer flags: network none, 2 CPUs, 2048 MiB memory/swap, pids 256, read-only root, 64 MiB tmpfs, uid/gid 65534, no capabilities or privilege escalation. The tested 2 GiB limit is stricter than the board's 4 GiB.

| Set | Baseline image CPU s | Candidate image CPU s | Candidate selection s | Host/image differences |
|---|---:|---:|---:|---:|
| tracked | 66.149341 | 73.518525 | 6984.938 | 0 |
| t41 | 17.271550 | 22.065249 | 1721.508 | 0 |
| hid | 17.734538 | 20.389776 | 3445.519 | 0 |
| fresha | 58.145204 | 58.807158 | 3358.298 | 0 |
| freshb | 13.361378 | 14.096923 | 556.021 | 0 |
| t46 fresh | not measured | 11.358935 | 397.708 | 0 |

Sample baseline CPU: [1.610003, 1.614641, 1.656716], median 1.614641 s. Candidate: [1.656646, 1.723169, 1.666987], median 1.666987 s. All six sample runs select 116.857 s and match host test sets. CPU is selector plus all analysis descendants; instrumentation-parent overhead is excluded, as in the required gate.

## Limits and negative results

- Initial parallel CLI diagnostics oversubscribed rosserver and one batch reached the wall deadline. Those timings/costs were discarded in favor of serial comparisons. Final image outputs match both test sets and packed costs on every measured input; no resource fallback occurred.
- One unchanged wall-time regression failed under host load, then passed separately. The final full check passed 262 tests and 3 subtests; no timeout/test limit was relaxed.
- Only direct stored generator callbacks, direct nonempty type values, dialect-local keyword keys and known pure rename_func constructors qualify. Unknown factories, parser registries, enum values, regexes, format/SQL templates and test skip reasons retain fallback.
- Base keyword keys feed SQL parsed at import. New t46c05 fails 1,447 tests and keeps all 1,620 selected.
- Expression-class docstrings have an import-time __doc__ reader and remain conservative. Typing function doc changes retain TestTyping because it compares co_consts; the complete pinned callable graph excludes outside functions.
- Fresh canonical labels run all tests except test_max_nodes, test_execute_tpcds and the three SQLGlotC build/install checks. No runtime evidence is claimed for those five. No OOM-derived label is accepted. Every other fresh patch is a full-suite run, not a selected-test subset.
- Local exploratory labeling was paused/stopped after discovering t47 was active; the incomplete patch was discarded. Canonical evidence is the Legion run, after t44 exited at 7:20, on CPUs 8-9 with 2 GiB and one pytest worker.
