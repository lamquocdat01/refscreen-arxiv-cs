#!/usr/bin/env python3
"""Topic 43 / P1 (PREREG §5 H4 + PROMPT_P1 item 8): FP on certified-real vs FP on the hand-checked sample, per tier.

H4 itself is h4_test() of screen_baseline.py (same function, same seed), run here for the three screens
Crossref-only, +DBLP and the full cascade (+S2 = "union"), on the 2019-21 corpus, def 1, bib titles.
Per tier t the selection-bias coefficient is c_t = FP_manual,t / FP_certified,t (and its inverse, the factor that
turns a certified-real FP into a hand-checked one is c_t itself); Wilson 95 % CIs per proportion, and a paper-level
bootstrap CI (B = 1000) of FP_manual,t - FP_certified,t. With k_certified,t = 0 the ratio is undefined ("inf").
Output: results/p1_h4_bias.{csv,json}
Usage:  python p1_h4_bias.py --seed 42 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import wilson  # noqa: E402
from ground_truth_p1 import DERIVED, ROOT  # noqa: E402
from p1_backend_table import first_hit_stage  # noqa: E402
from screen_baseline import _bib_flags, h4_test  # noqa: E402

SCREENS = {"crossref": "Crossref-only", "dblp": "+DBLP", "union": "+S2 (full cascade)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    gt = pd.read_csv(DERIVED / "p1_groundtruth_refs_full.csv", dtype={"arxiv_id": str, "key": str}, low_memory=False)
    man = pd.read_csv(ROOT / "results" / "p1_manual_sample.csv", dtype=str)
    man = man[man.exists == "exists"][["paper_id", "key"]].rename(columns={"paper_id": "arxiv_id"})
    g = gt[gt.period == "2019-21"]
    cert = _bib_flags(g[g.certified_real == 1], first_hit_stage)
    mm = _bib_flags(g.merge(man, on=["arxiv_id", "key"]), first_hit_stage)
    rng = np.random.default_rng(args.seed)
    rows, h4 = [], {}
    for be, label in SCREENS.items():
        h4[be] = h4_test(gt, man, be, args.seed, args.boot)
        h4[be]["label"] = label
        col = f"flag_{be}"
        for t in ["J", "C", "P", "B", "S", "W"]:
            c, m = cert[(cert.tier == t) & cert[col].notna()], mm[(mm.tier == t) & mm[col].notna()]
            kc, nc, km, nm = int(c[col].sum()), len(c), int(m[col].sum()), len(m)
            r = {"screen": label, "tier": t, "k_certified": kc, "n_certified": nc, "k_manual": km, "n_manual": nm,
                 "fp_certified": kc / nc if nc else np.nan, "fp_manual": km / nm if nm else np.nan}
            for nm_, k_, n_ in (("certified", kc, nc), ("manual", km, nm)):
                lo, hi = wilson(k_, n_) if n_ else (np.nan, np.nan)
                r[f"wilson_{nm_}"] = f"{lo:.4f}-{hi:.4f}"
            r["bias_coef_manual_over_cert"] = (r["fp_manual"] / r["fp_certified"] if kc else
                                               (np.inf if km else np.nan))
            papers = sorted(set(c.arxiv_id) | set(m.arxiv_id))
            if nc and nm and len(papers) >= 10:
                pc = c.groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
                pm = m.groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
                idx = rng.integers(0, len(papers), (args.boot, len(papers)))
                with np.errstate(invalid="ignore", divide="ignore"):
                    d = (pm["sum"].values[idx].sum(1) / pm["count"].values[idx].sum(1)
                         - pc["sum"].values[idx].sum(1) / pc["count"].values[idx].sum(1))
                r["diff_boot95"] = f"{np.nanquantile(d, .025):.4f}..{np.nanquantile(d, .975):.4f}"
            rows.append(r)
    tab = pd.DataFrame(rows)
    tab.insert(0, "interim", False)
    out = ROOT / "results"
    tab.to_csv(out / "p1_h4_bias.csv", index=False)
    meta = {"interim": False, "seed": args.seed, "boot": args.boot,
            "spec": "2019-21, def 1, bib titles; manual = pass-1 'exists' refs; H4 = h4_test of screen_baseline.py",
            "H4": h4, "per_tier": rows}
    (out / "p1_h4_bias.json").write_text(json.dumps(meta, indent=1, default=float, ensure_ascii=False),
                                         encoding="utf-8")
    for be, v in h4.items():
        print(f"H4 {v['label']}: FP_manual_w {v['fp_manual_weighted']:.4f} ({v['k_manual']}/{v['n_manual']}) vs "
              f"FP_cert {v['fp_certified']:.4f} ({v['k_certified']}/{v['n_certified']}) diff {v['diff']:+.4f} "
              f"CI {v['diff_ci'][0]:+.4f}..{v['diff_ci'][1]:+.4f} PASS={v['PASS']}")
    print(tab.drop(columns=["interim"]).to_string(index=False))


if __name__ == "__main__":
    main()
