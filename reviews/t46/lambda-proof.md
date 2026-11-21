# Stored generator callbacks

Pinned source: eb11aec4be8cb2122afe713a4816662c3f0fb2fa. Whole-source SHA256 (sorted Python paths and contents, NUL-delimited): fc8e3c215f006385b628ef4612295b1d074b93b42de8c773997de3f40103d090. The build-time index disables this audit if the original source differs.

Generator TRANSFORMS and AFTER_HAVING_MODIFIER_TRANSFORMS dicts store callbacks. Cross-module extensions/comprehensions copy callable objects. The dialect hook only removes unsupported JSONPath callbacks. The dispatch builder copies handlers into a cache without calling them. Calls happen in Generator.sql, Generator.json_path_part, Generator.query_modifiers, or transforms.preprocess._to_sql; none of their bodies ran at import in the map. No tests read or invoke TRANSFORMS at collection. Coverage of the lambda body sees callbacks after arbitrary aliases and subclass copies.

Only str constants can differ, within a direct dict-value lambda's body. Defaults, immediate calls, unknown factories, keys, assignments, decorators, new code and multiple changed files are excluded. A string can make a runtime helper fail, but any test reaching that effect already reaches the enclosing lambda. Retain every such test, plus the baseline class/readers/qualified consumers and shared-setup closure. Do not infer no import execution from the lambda's own line: single-line creation shares that line.
