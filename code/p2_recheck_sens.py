#!/usr/bin/env python3
"""Topic 43 / P2 / T10a: EXPLORATORY sensitivity of the recheck agreement (not part of PREREG_AMENDMENT_4).

The registered PASS rule stays p2_recheck.py kappa (pooled PABAK >= 0.8). This script only re-reports the same
statistics on subsets defined by an objective row property, to show where the disagreement comes from:
  S0  all rows (= registered result, for reference)
  S1  rows whose recheck sheet showed a title (drops .bbl rows with an empty parsed title and no bib entry: the
      rechecker saw only an author surname, while pass 1 had the full .bbl item)
  S2  S1 and rows whose pass-1 or pass-2 note records an (a)+(b)-met / (c)-failed date conflict, which
      manual_protocol.md does not assign to any outcome (drops them; labels are NOT changed)
Also counts exists <-> not-found disagreements (the only kind that would move FP_manual).
Outputs: results/p2_kappa_sens.json, results/p2_kappa_sens.csv
Usage: python p2_recheck_sens.py --seed 42 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_recheck import CATS, KEY, RES, stats  # noqa: E402

DATE_CONFLICT = {"K25", "K29"}  # pass-1 note "(c) fails"; LQD note "REVIEW ... (c)" (P2_LOG 2026-10-24)


def boot(d, seed, B):
    rng = np.random.default_rng(seed)
    papers = d.paper_id.unique()
    bs = {k: [] for k in ("raw", "pabak", "ac1", "kappa")}
    for _ in range(B):
        bd = pd.concat([d[d.paper_id == p] for p in rng.choice(papers, len(papers), replace=True)])
        sb = stats(bd)
        for k in bs:
            bs[k].append(sb[k])
    return {f"{k}_ci": [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in bs.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    rc = pd.read_csv(KEY, dtype=str, keep_default_na=False)
    p2 = pd.concat([pd.read_csv(RES / f, dtype=str, keep_default_na=False)
                    for f in ("p2_recheck_sheet.csv", "p2_recheck_cc.csv")])[["recheck_id", "exists"]]
    m = rc.merge(p2.rename(columns={"exists": "pass2"}), on="recheck_id")
    m = m[m.pass2.isin(CATS)]
    no_title = (m.title.str.strip() == "") & (m.bib_entry.str.strip() == "")
    subsets = {"S0 all": m, "S1 sheet shows a title": m[~no_title],
               "S2 S1 minus (c)-only date conflicts": m[~no_title & ~m.recheck_id.isin(DATE_CONFLICT)]}
    out = {"exploratory": True, "interim": False, "seed": args.seed, "boot": args.boot,
           "note": "not a registered test; the PASS rule is p2_kappa.json",
           "dropped_no_title": sorted(m.recheck_id[no_title]), "dropped_date_conflict": sorted(DATE_CONFLICT),
           "exists_vs_notfound_disagreements": int(((m.pass1 == "exists") & (m.pass2 == "not-found")).sum()
                                                   + ((m.pass1 == "not-found") & (m.pass2 == "exists")).sum()),
           "disagreements": m[m.pass1 != m.pass2][["recheck_id", "rater", "stratum", "pass1", "pass2"]]
           .to_dict("records")}
    rows = []
    for name, d in subsets.items():
        for grp, dd in (("pooled", d), ("inter-rater (LQD)", d[d.rater == "LQD"]), ("intra-rater (CC)", d[d.rater == "CC"])):
            s = stats(dd)
            s.update(boot(dd, args.seed, args.boot))
            out[f"{name} | {grp}"] = s
            rows.append(dict(subset=name, group=grp, **{k: v for k, v in s.items() if k != "table"},
                             exploratory=True))
    (RES / "p2_kappa_sens.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    pd.DataFrame(rows).to_csv(RES / "p2_kappa_sens.csv", index=False)
    print(pd.DataFrame(rows)[["subset", "group", "n", "raw", "pabak", "pabak_ci", "ac1", "kappa"]].to_string())
    print("exists<->not-found disagreements:", out["exists_vs_notfound_disagreements"])


if __name__ == "__main__":
    main()
