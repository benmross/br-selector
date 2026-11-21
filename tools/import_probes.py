"""Function names the parser looks up while sqlglot itself imports.

Some modules parse SQL at import (templates, type strings), probing
FUNCTIONS and FUNCTION_PARSERS before tools/key_trace.py wraps them. Their
results outlive the import, so an edit of such a key keeps today's
selection. Prints JSON {"FUNCTIONS": [...], "FUNCTION_PARSERS": [...]}.
usage: PYTHONPATH=<sqlglot src> python3 tools/import_probes.py"""
import importlib, json, pkgutil, sys

seen = {"FUNCTIONS": set(), "FUNCTION_PARSERS": set(), "NO_PAREN": set(), "calls": 0}


def tracer(frame, event, arg):
    co = frame.f_code
    if co.co_name == "_parse_function_call" and co.co_filename.endswith("sqlglot/parser.py"):
        seen["calls"] += 1

        def local(f, e, a):
            up = f.f_locals.get("upper")
            if isinstance(up, str):
                seen["FUNCTIONS"].add(up)
                seen["FUNCTION_PARSERS"].add(up)
            return local
        return local
    return None


sys.settrace(tracer)
import sqlglot  # noqa: E402

for info in pkgutil.walk_packages(sqlglot.__path__, "sqlglot."):
    try:
        importlib.import_module(info.name)
    except Exception:
        pass
sys.settrace(None)
print(json.dumps({k: sorted(v) if isinstance(v, set) else v for k, v in seen.items()}))
