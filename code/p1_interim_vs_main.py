#!/usr/bin/env python3
"""Topic 43 / P1: cell-by-cell difference between the INTERIM tables (results/interim/) and the main ones (results/).

Tables compared (numeric cells present in both; text cells such as "chưa hoàn tất" count as missing on that side):
backend table (k_, u_ per column), H5 tertiles (p1_h5.csv), beta-binomial tertiles (p1_h5_betabinom.csv) and
u by reference year (p1_u_by_refyear.csv). The INTERIM refyear uses the +DBLP state, the main one +S2: it is listed
but differs by design.
Output: results/p1_interim_vs_main.csv (one row per cell: table, key, field, interim, main, diff, changed)
Usage:  python p1_interim_vs_main.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth_p1 import ROOT  # noqa: E402

RES = ROOT / "results"
TABLES = {"p1_backend_table.csv": ["period", "stratum"], "p1_h5.csv": ["scenario", "tertile"],
          "p1_h5_betabinom.csv": ["scenario", "k", "tertile"], "p1_u_by_refyear.csv": ["period", "lag_years", "ref_year"]}
SKIP = ("interim", "seed")


def main():
    rows = []
    for name, keys in TABLES.items():
        a, b = pd.read_csv(RES / "interim" / name), pd.read_csv(RES / name)
        keys = [k for k in keys if k in a and k in b]
        m = a.merge(b, on=keys, how="outer", suffixes=("_i", "_m"), indicator=True)
        fields = [c for c in a.columns if c in b.columns and c not in keys and c not in SKIP]
        for _, r in m.iterrows():
            key = "/".join(str(r[k]) for k in keys)
            for f in fields:
                vi = pd.to_numeric(r.get(f"{f}_i"), errors="coerce")
                vm = pd.to_numeric(r.get(f"{f}_m"), errors="coerce")
                if pd.isna(vi) and pd.isna(vm):
                    continue
                d = None if pd.isna(vi) or pd.isna(vm) else float(vm - vi)
                rows.append({"table": name, "key": key, "field": f, "interim": vi, "main": vm, "diff": d,
                             "changed": d is None or abs(d) > 1e-9, "presence": r["_merge"]})
    out = pd.DataFrame(rows)
    out.insert(0, "interim_flag", False)
    out.to_csv(RES / "p1_interim_vs_main.csv", index=False)
    s = out.groupby(["table", "field"]).changed.agg(["sum", "count"])
    print(s[s["sum"] > 0].to_string())


if __name__ == "__main__":
    main()
