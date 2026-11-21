# Handoff

Model: gpt-6.1-sol. Baseline be28115d6b491536992e294aff9ae9b1d2a27dee.
Branch w/t30; hard stop 09:45 UTC.

Done: initial 18 metaclass labels; main misses two, candidate misses zero.
149 selector and 22 tools tests pass. No selection/cost change on the nine
historical/proxy sets. Detailed matrix: reviews/t30-matrix.md.

Running: br-label-t30 on Legion CPUs 8–9, 1 GiB, one pytest process; cache
class. Test 1490 OOMs alone and is deselected; baseline TPC-DS 88 is reconciled
by subtest. 28 all-selected controls use explicit smoke scopes; other labels
are broad. Host memory guard stops below 5 GiB available.

Exact next command:
ssh legion 'free -g; tail -3 ~/bt-watchdog.log; docker logs --tail 12 br-label-t30'

After t30x025 stops: touch legion:~/br/t30/cache-order.request, clear stop
files, restart the same container and the memory guard. Gate and push pending.
