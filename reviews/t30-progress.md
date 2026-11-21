# t30 handoff

Model gpt-6.1-sol. Baseline be28115d6b491536992e294aff9ae9b1d2a27dee.
Branch w/t30. Started 07:15 UTC, hard stop 09:45 UTC.

76 mutants generated. Legion br-label-t30 on CPUs 8–9, 1 GiB memory and swap,
2 pytest workers. Parser max_nodes (1490) explicitly deselected: it OOMs alone
in a fresh 1 GiB container; OOM attempts were discarded. All other 1619 numbered
tests included. Structured labels pending; no proven miss claimed yet.

Draft rule extends the existing shape guard into literal container entries.
All 148 selector tests pass. Identical selections on samples, 238 gate mutants,
t3, t14, t15, t24a and all 600 proxies; no narrowing, no historical misses.
Measurement artifacts: work/t30-measure/ and tools/t30_measure.py.

Next command:
ssh legion 'free -g; tail -3 ~/bt-watchdog.log; docker logs --tail 12 br-label-t30'
