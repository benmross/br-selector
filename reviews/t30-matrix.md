# t30 real pytest labels

Test 1490 is deselected under the 1 GiB cap; collection failures still count it.
TPC-DS baseline subtest 88 is subtracted by subtest key, preserving other new failures.
A ≥ failure count is a lower bound: an all-selected smoke control, or t30x044 with selected test 1106 omitted after OOM.
All smoke controls select every test on main. Per-mutant exclusions are recorded in manifest.json.

| Mutant | Class | Edit | Failing | Main selected | Main missed | Candidate missed |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| t30x000 | metaclass | metaclass registry key | 3 | 1620 | 0 | 0 |
| t30x001 | metaclass | metaclass time trie | 3 | 1620 | 0 | 0 |
| t30x002 | metaclass | metaclass string parser lookup | 1175 | 1620 | 0 | 0 |
| t30x003 | metaclass | metaclass inherited generator lookup | 0 | 1620 | 0 | 0 |
| t30x004 | metaclass | metaclass shared transform mutation | 1 | 1620 | 0 | 0 |
| t30x005 | metaclass | metaclass quote endpoint | 0 | 1620 | 0 | 0 |
| t30x006 | metaclass | tokenizer init-subclass quote source | 1020 | 1620 | 0 | 0 |
| t30x007 | metaclass | tokenizer string-name inheritance | 4 | 1620 | 0 | 0 |
| t30x008 | metaclass | expression required-args comprehension | ≥113 | 1620 | 0 | 0 |
| t30x009 | metaclass | quote converter at import | ≥194 | 1620 | 0 | 0 |
| t30x010 | metaclass | hive quote tuple value | 42 | 355 | 0 | 0 |
| t30x011 | metaclass | bigquery quote scalar value | 33 | 294 | 0 | 0 |
| t30x012 | metaclass | generator string-read setting | ≥2 | 1620 | 0 | 0 |
| t30x013 | metaclass | snowflake inverse time map value | ≥0 | 1620 | 0 | 0 |
| t30x014 | cache | dispatch memo stored under base class | 176 | 1347 | 0 | 0 |
| t30x015 | cache | dispatch memo read under base class | 689 | 1347 | 0 | 0 |
| t30x016 | cache | dispatch memo mutates previous cached table | 868 | 1347 | 0 | 0 |
| t30x017 | cache | optimizer lazy global cached wrong name | ≥0 | 1620 | 0 | 0 |
| t30x018 | cache | optimizer lazy global writes extra name | ≥0 | 1620 | 0 | 0 |
| t30x019 | cache | optimizer lazy RULES registry target | ≥0 | 1620 | 0 | 0 |
| t30x020 | cache | optimizer lazy scope registry target | ≥0 | 1620 | 0 | 0 |
| t30x021 | cache | optimizer rule registry swap | ≥13 | 1620 | 0 | 0 |
| t30x022 | cache | scope column-cache reset | 5 | 229 | 0 | 0 |
| t30x023 | cache | resolver cache key loses only-visible | 2 | 225 | 0 | 0 |
| t30x024 | cache | dialect registry reload pollutes base | ≥0 | 1620 | 0 | 0 |
| t30x025 | cache | dialect registry lazy result fallback | 1099 | 1235 | 0 | 0 |
| t30x026 | infrastructure | identity SQL whitespace literal | 2 | 2 | 0 | 0 |
| t30x027 | infrastructure | optimizer fixture metadata | 0 | 1 | 0 | 0 |
| t30x028 | infrastructure | fixture comment becomes statement | 1 | 1 | 0 | 0 |
| t30x029 | infrastructure | test helper fixture separator | 0 | 85 | 0 | 0 |
| t30x030 | infrastructure | test helper comment-filter sense | 2 | 89 | 0 | 0 |
| t30x031 | infrastructure | test infrastructure collection config | ≥0 | 1620 | 0 | 0 |
| t30x032 | infrastructure | public re-export changes bound target | ≥93 | 1620 | 0 | 0 |
| t30x033 | infrastructure | public re-export removed | ≥0 | 1620 | 0 | 0 |
| t30x034 | infrastructure | TYPE_CHECKING made runtime | 0 | 1518 | 0 | 0 |
| t30x035 | infrastructure | Rust import fallback catch narrowed | ≥0 | 1620 | 0 | 0 |
| t30x036 | infrastructure | new module shadows stdlib json | ≥1620 | 1620 | 0 | 0 |
| t30x037 | infrastructure | new Rust module triggers deprecation warning | ≥0 | 1620 | 0 | 0 |
| t30x038 | infrastructure | new conftest fails all setup | ≥247 | 1620 | 0 | 0 |
| t30x039 | infrastructure | deleted test support file | ≥248 | 1620 | 0 | 0 |
| t30x040 | shape | dataclass field becomes ClassVar | ≥50 | 1620 | 0 | 0 |
| t30x041 | shape | dataclass required field becomes InitVar | ≥8 | 1620 | 0 | 0 |
| t30x042 | shape | dataclass decorator argument | 0 | 53 | 0 | 0 |
| t30x043 | shape | dataclass field default factory | ≥50 | 1620 | 0 | 0 |
| t30x044 | shape | default argument references changed runtime expression | ≥68 | 94 | 0 | 0 |
| t30x045 | shape | boolean and-or | 13 | 89 | 0 | 0 |
| t30x046 | shape | membership operator | ≥4 | 1620 | 0 | 0 |
| t30x047 | shape | slice bound | 0 | 94 | 0 | 0 |
| t30x048 | shape | arithmetic operator | 84 | 85 | 0 | 0 |
| t30x049 | shape | multiline string whitespace | 0 | 1 | 0 | 0 |
| t30x050 | shape | pure function move | ≥0 | 1620 | 0 | 0 |
| t30x051 | shape | dataclass field declaration order | ≥0 | 1620 | 0 | 0 |
| t30x052 | shape | two-file lazy registry and rule default | ≥37 | 1620 | 0 | 0 |
| t30x053 | shape | SQL fixture whitespace only | 0 | 2 | 0 | 0 |
| t30x054 | comparison | profile safe 1-test site sqlglot/dialects/clickhouse.py:67 != | 0 | 0 | 0 | 0 |
| t30x055 | comparison | profile safe 1-test site sqlglot/dialects/dialect.py:232 is not | 0 | 0 | 0 | 0 |
| t30x056 | comparison | profile safe 1-test site sqlglot/executor/env.py:128 != | 0 | 0 | 0 | 0 |
| t30x057 | comparison | profile safe 1-test site sqlglot/expressions/builders.py:884 is | 0 | 0 | 0 | 0 |
| t30x058 | comparison | profile safe 1-test site sqlglot/expressions/query.py:683 is not | 0 | 0 | 0 | 0 |
| t30x059 | comparison | profile safe 1-test site sqlglot/generator.py:1817 != | 0 | 0 | 0 | 0 |
| t30x060 | comparison | profile safe 1-test site sqlglot/generators/athena.py:60 is not | 0 | 0 | 0 | 0 |
| t30x061 | comparison | profile safe 1-test site sqlglot/generators/bigquery.py:247 != | 0 | 0 | 0 | 0 |
| t30x062 | comparison | profile safe 1-test site sqlglot/generators/clickhouse.py:37 == | 0 | 0 | 0 | 0 |
| t30x063 | comparison | profile safe 1-test site sqlglot/generators/doris.py:601 is not | 0 | 0 | 0 | 0 |
| t30x064 | metaclass | nested quote pair loses endpoint | 1020 | 355 | 707 | 0 |
| t30x065 | metaclass | nested quote entry becomes empty list | 1031 | 294 | 808 | 0 |
| t30x066 | metaclass | escape item changes type | 305 | 355 | 0 | 0 |
| t30x067 | metaclass | time-map value changes type | 70 | 291 | 0 | 0 |
| t30x068 | comparison | chained lower bound | 1 | 1 | 0 | 0 |
| t30x069 | comparison | chained upper bound | 0 | 3 | 0 | 0 |
| t30x070 | comparison | comparison lambda equality | ≥0 | 1620 | 0 | 0 |
| t30x071 | comparison | comparison lambda mapping read | 9 | 11 | 0 | 0 |
| t30x072 | comparison | comparison in comprehension | 0 | 0 | 0 | 0 |
| t30x073 | comparison | comparison in import-time generator | ≥0 | 1620 | 0 | 0 |
| t30x074 | comparison | comparison operand advances parser | ≥0 | 1620 | 0 | 0 |
| t30x075 | shape | PEP 701 comment in f-string expression | pending | 0 | pending | pending |
| t30x076 | metaclass | time-map key changes type | pending | 291 | pending | pending |
| t30x077 | metaclass | quote tuple arity shrinks | pending | 117 | pending | pending |
| t30x078 | shape | two individually harmless edits fail only together | pending | 1620 | pending | pending |
| t30x079 | cache | test cleanup snapshots wrong shared parser | 106 | 1 | 106 | 0 |
| t30x080 | cache | test cleanup restores wrong shared parser | 106 | 1 | 106 | 0 |
| t30x081 | cache | test cleanup omitted shared parser restoration | 0 | 1 | 0 | 0 |
| t30x082 | metaclass | test-local dialect class overwrites shared registry | 145 | 1 | 145 | 0 |
