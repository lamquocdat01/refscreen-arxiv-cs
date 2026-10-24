#!/usr/bin/env python3
"""Topic 43 / P2 / CP-B2 option A (LQD 24-10-2026): third-rater recheck of the same 40 rows, same protocol.

sheet  Writes results/p2_recheck_sheet_R3.csv: all 40 rows of the Amendment-4 recheck sample, showing exactly what
       the pass-2 raters saw (citing-paper date, tier, title, author, bib entry; .bbl rows unchanged), outcome columns
       empty, rows in a seed-shuffled order. Pass-1 / pass-2 outcomes, stratum and rater are not shown.
       The R3 rater must not open p2_recheck_sheet*.csv, p2_recheck_cc*.csv, p2_kappa*, p1/p2_manual_sample.csv or the key.
kappa  Reads the filled R3 sheet and reports, with the statistics and bootstrap of p2_recheck.py:
       pass 1 vs R3 (pooled, strata) -- the proposed decision statistic (PABAK >= 0.8, as Amendment 4 (a));
       pass 2 vs R3 (descriptive).
Outputs: results/p2_kappa_r3.json, results/p2_kappa_r3_table.csv
Usage: python p2_recheck_r3.py sheet --seed 42 ;  python p2_recheck_r3.py kappa --seed 42 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_recheck import CATS, FILL, KEY, RES, SHOW, stats  # noqa: E402

SHEET = RES / "p2_recheck_sheet_R3.csv"


def sheet(args):
    if SHEET.exists():
        sys.exit(f"{SHEET} exists; not overwritten")
    rc = pd.read_csv(KEY, dtype=str, keep_default_na=False)
    sh = rc[["recheck_id"] + SHOW[1:]].sample(frac=1, random_state=args.seed + 3).reset_index(drop=True)
    for c in FILL:
        sh[c] = ""
    sh.to_csv(SHEET, index=False)
    print("wrote", SHEET, len(sh), "rows")


def summarize(d, a, b, seed, B):
    d = d.assign(pass1=d[a], pass2=d[b])
    s = stats(d)
    rng = np.random.default_rng(seed)
    papers = d.paper_id.unique()
    bs = {k: [] for k in ("raw", "pabak", "ac1", "kappa")}
    for _ in range(B):
        bd = pd.concat([d[d.paper_id == p] for p in rng.choice(papers, len(papers), replace=True)])
        sb = stats(bd)
        for k in bs:
            bs[k].append(sb[k])
    for k, v in bs.items():
        s[f"{k}_ci"] = [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
    s["n_papers"] = len(papers)
    return s


def kappa(args):
    rc = pd.read_csv(KEY, dtype=str, keep_default_na=False)
    p2 = pd.concat([pd.read_csv(RES / f, dtype=str, keep_default_na=False)
                    for f in ("p2_recheck_sheet.csv", "p2_recheck_cc.csv")])[["recheck_id", "exists"]]
    r3 = pd.read_csv(SHEET, dtype=str, keep_default_na=False)[["recheck_id", "exists", "checker"]]
    m = rc.merge(p2.rename(columns={"exists": "p2"}), on="recheck_id").merge(
        r3.rename(columns={"exists": "r3"}), on="recheck_id")
    m = m[m.r3.isin(CATS)]
    out = {"seed": args.seed, "boot": args.boot, "n_filled": len(m), "n_sample": len(rc),
           "criterion": "proposed: PABAK(pass 1, R3) >= 0.8 pooled (Amendment 4 (a) rule); confirm with LQD",
           "checker": sorted(m.checker.unique())}
    rows = []
    for name, d, a, b in (("pass1 vs R3 | pooled", m, "pass1", "r3"),
                          ("pass1 vs R3 | stratum E", m[m.stratum == "E"], "pass1", "r3"),
                          ("pass1 vs R3 | stratum N", m[m.stratum == "N"], "pass1", "r3"),
                          ("pass2 vs R3 | pooled", m, "p2", "r3")):
        if len(d):
            s = summarize(d, a, b, args.seed, args.boot)
            out[name] = s
            rows.append(dict(group=name, **{k: v for k, v in s.items() if k != "table"}))
    if "pass1 vs R3 | pooled" in out:
        out["PASS_proposed"] = bool(out["pass1 vs R3 | pooled"]["pabak"] >= 0.8)
    (RES / "p2_kappa_r3.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    pd.DataFrame(rows).to_csv(RES / "p2_kappa_r3_table.csv", index=False)
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["sheet", "kappa"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    (sheet if args.stage == "sheet" else kappa)(args)


if __name__ == "__main__":
    main()
