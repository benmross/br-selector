# br-selector

Static change-impact analysis for a Python test suite: given a unified diff, choose which tests can be affected and pack them across workers.

`selector.py` reads patches and prints one JSON line per change. `tools/` builds the coverage map and evaluation sets; `tests_selector/` checks the selector against unusual patches.
