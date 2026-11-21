"""Record every sqlglot line the expensive phase of TestExecutor's TPC tests runs.

Usage (in the labeled image, pristine source at SRC, coverage installed):
    python tools/heavy_cov.py SRC OUT.json.gz [jobs]

Per test (tpcds, tpch):
  setup  one fresh process: TestExecutor.setUpClass (Table construction)
  plans  one fresh process: the cheap phase for every executed query, plans
         and tables pickled to disk
  run i  per query, a fresh process: imports, then (context E) unpickle the
         plan and tables, ensure_tables, PythonExecutor.execute, DataFrame
         build. Caches the phase uses are built inside it. Then, in a second
         fresh process, the cheap phase without measurement followed by the
         same expensive phase measured (caches as warm as in the real worker).
The union of the measured lines is written as {"lines": {name: {file: [line]}}}.
"""
import gzip
import json
import os
import pickle
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def child(src, mode, name, tpch, work, i=None):
    os.chdir(src)
    sys.path.insert(0, src)
    os.environ["SKIP_INTEGRATION"] = "0"
    sys.setrecursionlimit(20000)
    import coverage
    cov = coverage.Coverage(data_file=None, source=[os.path.join(src, "sqlglot")])
    cov.start()
    cov.switch_context("import")
    import numpy as np
    import pandas as pd
    import tests.test_executor as te
    from sqlglot import find_tables, parse_one
    from sqlglot.executor.python import PythonExecutor
    from sqlglot.executor.table import ensure_tables
    from sqlglot.optimizer import optimize
    from sqlglot.planner import Plan
    from sqlglot.schema import ensure_schema
    from tests.helpers import TPCH_SCHEMA, TPCDS_SCHEMA, load_sql_fixture_pairs
    schema_src = TPCH_SCHEMA if tpch else TPCDS_SCHEMA
    fixture = "optimizer/tpc-h/tpc-h.sql" if tpch else "optimizer/tpc-ds/tpc-ds.sql"
    result = None

    def cheap(sql):
        e = pickle.loads(pickle.dumps(parse_one(sql)))
        names = [t.name for t in find_tables(e)]
        schema = ensure_schema(schema_src, dialect=None)
        expression = optimize(e, schema, leave_tables_isolated=True, dialect=None)
        expression.sql(pretty=True)
        return names, Plan(expression)

    def expensive(names, plan, all_tables):
        tables_ = ensure_tables({n: all_tables[n] for n in names}, dialect=None)
        table = PythonExecutor(tables=tables_).execute(plan)
        df = pd.DataFrame(((np.nan if c is None else c for c in r) for r in table.rows), columns=table.columns)
        return df.shape, repr(table.rows[:3])

    if mode == "setup":
        cov.switch_context("E")
        te.TestExecutor.setUpClass()
        tables = te.TestExecutor.tpch_tables if tpch else te.TestExecutor.tpcds_tables
        cov.switch_context("off")
        with open(os.path.join(work, f"{name}.tables.pkl"), "wb") as f:
            pickle.dump(tables, f)
        sqls = list(load_sql_fixture_pairs(fixture))
        plans = {}
        for k, (meta, sql, _) in enumerate(sqls):
            if meta.get("execute"):
                plans[k] = cheap(sql)
        with open(os.path.join(work, f"{name}.plans.pkl"), "wb") as f:
            pickle.dump(plans, f)
        result = sorted(plans)
    elif mode in ("cold", "warm"):
        with open(os.path.join(work, f"{name}.tables.pkl"), "rb") as f:
            tables = pickle.load(f)
        if mode == "cold":
            cov.switch_context("E")
            with open(os.path.join(work, f"{name}.plans.pkl"), "rb") as f:
                names, plan = pickle.load(f)[i]
        else:
            cov.switch_context("off")
            sql = list(load_sql_fixture_pairs(fixture))[i][1]
            names, plan = cheap(sql)
            cov.switch_context("E")
        result = expensive(names, plan, tables)
    cov.stop()
    data = cov.get_data()
    data.set_query_contexts(["E"])
    lines = {}
    for f in data.measured_files():
        ls = data.lines(f) or []
        if ls:
            lines[os.path.relpath(os.path.realpath(f), os.path.realpath(src))] = sorted(ls)
    json.dump({"lines": lines, "result": repr(result)}, sys.stdout)


def run(src, mode, name, tpch, work, i=None):
    cmd = [sys.executable, os.path.abspath(__file__), "--child", src, mode, name, str(int(tpch)), work]
    if i is not None:
        cmd.append(str(i))
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{mode} {name} {i}: {p.stderr[-2000:]}")
    return json.loads(p.stdout)


def main(src, out, jobs):
    work = tempfile.mkdtemp(prefix="heavy-cov-")
    res = {}
    for name, tpch in (("tpcds", False), ("tpch", True)):
        acc = {}

        def add(d):
            for f, ls in d["lines"].items():
                acc.setdefault(f, set()).update(ls)

        s = run(src, "setup", name, tpch, work)
        add(s)
        idx = json.loads(s["result"].replace("'", '"'))
        results = {}
        with ThreadPoolExecutor(jobs) as pool:
            futs = {(m, i): pool.submit(run, src, m, name, tpch, work, i) for i in idx for m in ("cold", "warm")}
            for (m, i), fu in futs.items():
                d = fu.result()
                add(d)
                results[(m, i)] = d["result"]
        same = sum(results[("cold", i)] == results[("warm", i)] for i in idx)
        print(f"{name}: {len(idx)} queries, cold==warm results on {same}", file=sys.stderr)
        res[name] = {f: sorted(ls) for f, ls in sorted(acc.items())}
        print(f"{name}: {sum(len(v) for v in res[name].values())} lines in {len(res[name])} files", file=sys.stderr)
    with gzip.open(out, "wt") as f:
        json.dump({"lines": res}, f, sort_keys=True)


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        a = sys.argv[2:]
        child(a[0], a[1], a[2], a[3] == "1", a[4], int(a[5]) if len(a) > 5 else None)
    else:
        main(os.path.abspath(sys.argv[1]), sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
