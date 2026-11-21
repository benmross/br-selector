# Handoff

Model: gpt-6.1-sol. Baseline be28115d6b491536992e294aff9ae9b1d2a27dee.
All 83 mutants are labeled. Five baseline misses are fixed by two rules that
only widen. Original nine measurement sets retain identical selections/costs.
The t30 simulated total improves from 3344.690 s to 2153.452 s, five misses to
zero. 161 selector tests and 22 tools tests pass. Sources restored by checksum.

Legion label container exited 0, no running label job. CPUs 8–9, 1 GiB. Scope
limits (1490, DuckDB query 88, selected OOM case 44, smoke controls) are explicit
in mutants/t30/manifest.json and label_quality.json. No tainted OOM label used.

The candidate is the final tip of w/t30. The exact hash, final gate PASS line,
image CPU and push status are recorded in the authoritative result file:
/home/benmross/herald/projects/buildathon/tasks/t30-blast-newkinds3.result.md

Exact next command: read that result, then review w/t30. This worker never
submits, writes buildathon/queue/, or pushes to main.
