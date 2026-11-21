Run the robustness suite from the repository root with pytest installed:

```sh
SQLGLOT_SRC=work/sqlglot DATA_DIR="$(mktemp -d)" python -m pytest tests_selector -q
sh tools/eval.sh
```

The tests create isolated temporary source trees, test inventories, coverage
maps, and patch batches. Subprocess environment overrides protect the real
checkout and caller's data. Every end-to-end case checks exit status, UTF-8 JSON
lines, commit completeness, worker limits, unique test numbers, and required
test selections. Ordinary edits and harmless changes also check exact selections.

Coverage includes CRLF, missing final newlines and their markers, binary diffs,
renames and copies, additions/deletions, executable/symlink modes, configuration
and files outside the package, separated hunks and boundary insertions, empty
patches, invalid bytes, quoted Unicode and space-containing paths, malformed
hunks, large patches, and a 50-file patch. Additional checks exercise import-time
side effects and loops, pathological ASTs, child exceptions/exits/signals,
memory limits, per-commit timeouts, and the batch deadline.

The production selector and process-isolation tests target Linux, matching the
scoring container. They use Python's standard-library fork context and resource
limits; no additional runtime dependencies are required.
