#!/usr/bin/env python3
"""Topic 43 / P2 / T10a: pairwise and three-rater agreement on the Amendment-4 recheck sample (LQD 24-10-2026).

Raters (one label per row, outcomes exists / not-found / ambiguous):
  R1  CC pass 1 (all 40 rows; from the key)
  R2  CC blind recheck (40 rows): K01-K20 results/p2_recheck_cc.csv, K21-K40 results/p2_recheck_cc_r2b.csv
      (fresh sub-agent without session context: the main session had seen R1/R3 labels of K21-K40)
  R3  Cowork blind, each row approved by LQD (K21-K40): results/p2_recheck_sheet.csv
Pairs: R1-R3 (main criterion, inter-rater, PABAK >= 0.8), R1-R2 (intra-rater), R2-R3; Gwet's AC1 for the three
raters on the rows all three rated (Gwet 2008, multi-rater form). Statistics and bootstrap (citing papers, B = 1000)
as in p2_recheck.py. Also lists every disagreement row of R1-R3.
Outputs: results/p2_kappa_pairs.json, results/p2_kappa_pairs.csv
Usage: python p2_recheck_pairs.py --seed 42 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_recheck import CATS, KEY, RES, stats  # noqa: E402


def ac1_multi(lab):
    """lab: DataFrame rows = items, columns = raters (labels in CATS)."""
    r = np.stack([(lab == c).sum(axis=1).to_numpy() for c in CATS], axis=1).astype(float)
    ri = r.sum(1)
    pa = np.mean((r * (r - 1)).sum(1) / (ri * (ri - 1)))
    pi = (r / ri[:, None]).mean(0)
    pe = (pi * (1 - pi)).sum() / (len(CATS) - 1)
    return float((pa - pe) / (1 - pe))


def boot(d, fn, seed, B):
    rng = np.random.default_rng(seed)
    papers = d.paper_id.unique()
    vals = []
    for _ in range(B):
        bd = pd.concat([d[d.paper_id == p] for p in rng.choice(papers, len(papers), replace=True)])
        vals.append(fn(bd))
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    rc = pd.read_csv(KEY, dtype=str, keep_default_na=False)
    rd = lambda f: pd.read_csv(RES / f, dtype=str, keep_default_na=False)[["recheck_id", "exists"]]  # noqa: E731
    r2 = pd.concat([rd("p2_recheck_cc.csv"), rd("p2_recheck_cc_r2b.csv")]).rename(columns={"exists": "R2"})
    r3 = rd("p2_recheck_sheet.csv").rename(columns={"exists": "R3"})
    m = rc.rename(columns={"pass1": "R1"}).merge(r2, on="recheck_id", how="left").merge(r3, on="recheck_id", how="left")
    out = {"seed": args.seed, "boot": args.boot, "criterion": "PABAK(R1, R3) >= 0.8 (LQD 24-10-2026)"}
    rows = []
    for a, b, role in (("R1", "R3", "main, inter-rater"), ("R1", "R2", "intra-rater"), ("R2", "R3", "inter-rater")):
        d = m[m[a].isin(CATS) & m[b].isin(CATS)].assign(pass1=lambda x: x[a], pass2=lambda x: x[b])
        s = stats(d)
        bs = boot(d, stats, args.seed, args.boot)
        for k in ("raw", "pabak", "ac1", "kappa"):
            s[f"{k}_ci"] = [float(np.nanpercentile([x[k] for x in bs], q)) for q in (2.5, 97.5)]
        s.update(n_papers=int(d.paper_id.nunique()), role=role,
                 disagreements=d[d[a] != d[b]][["recheck_id", a, b]].to_dict("records"))
        out[f"{a}-{b}"] = s
        rows.append(dict(pair=f"{a}-{b}", role=role, **{k: v for k, v in s.items()
                                                         if k not in ("table", "disagreements", "role")}))
    d3 = m[m.R1.isin(CATS) & m.R2.isin(CATS) & m.R3.isin(CATS)]
    f3 = lambda x: ac1_multi(x[["R1", "R2", "R3"]])  # noqa: E731
    bs = boot(d3, f3, args.seed, args.boot)
    out["AC1 three raters"] = {"n": len(d3), "ac1": f3(d3),
                               "ac1_ci": [float(np.nanpercentile(bs, q)) for q in (2.5, 97.5)],
                               "unanimous": int((d3.R1.eq(d3.R2) & d3.R2.eq(d3.R3)).sum())}
    rows.append(dict(pair="R1-R2-R3", role="three-rater AC1", n=len(d3), ac1=out["AC1 three raters"]["ac1"],
                     ac1_ci=out["AC1 three raters"]["ac1_ci"]))
    out["PASS"] = bool(out["R1-R3"]["pabak"] >= 0.8)
    out["rows"] = m[["recheck_id", "stratum", "R1", "R2", "R3"]].to_dict("records")
    (RES / "p2_kappa_pairs.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    pd.DataFrame(rows).to_csv(RES / "p2_kappa_pairs.csv", index=False)
    print(pd.DataFrame(rows).to_string())
    for p in ("R1-R3", "R1-R2", "R2-R3"):
        print(p, out[p]["table"], out[p]["disagreements"])
    print("3-rater", out["AC1 three raters"], "PASS", out["PASS"])


if __name__ == "__main__":
    main()
