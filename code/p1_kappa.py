#!/usr/bin/env python3
"""Topic 43 / P1: test-retest agreement of the manual existence check (manual_protocol.md, "Recheck and agreement").

Pass 1 = results/p1_manual_sample.csv (checker CC, 18-10-2026); pass 2 = the blinded recheck of the 40 rows of
results/p1_manual_recheck.csv, done >= 48 h later by the same checker (intra-rater). Pass 2 is written into the empty
columns of p1_manual_recheck.csv (pass 1 is never overwritten).
Reports Cohen's kappa on the 3 outcomes (exists / not-found / ambiguous), raw agreement, the 3 x 3 table and the
binary kappa (exists vs not exists). CI: bootstrap over references (B = 1000), plus the asymptotic SE.
Output: results/p1_kappa.json, results/p1_kappa_table.csv
Usage:  python p1_kappa.py --pass2 <recheck_pass2.csv> --seed 42 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import wilson  # noqa: E402
from ground_truth_p1 import ROOT  # noqa: E402

CATS = ["exists", "not-found", "ambiguous"]


def kappa(a, b, cats):
    t = pd.crosstab(pd.Categorical(a, cats), pd.Categorical(b, cats), dropna=False).values.astype(float)
    n = t.sum()
    po = np.trace(t) / n
    pe = (t.sum(0) * t.sum(1)).sum() / n ** 2
    k = (po - pe) / (1 - pe) if pe < 1 else np.nan
    se = np.sqrt(po * (1 - po) / (n * (1 - pe) ** 2)) if pe < 1 else np.nan
    return k, po, pe, se, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass2", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    res = ROOT / "results"
    p1 = pd.read_csv(res / "p1_manual_sample.csv", dtype=str)
    rc = pd.read_csv(res / "p1_manual_recheck.csv", dtype=str)
    p2 = pd.read_csv(args.pass2, dtype=str)
    assert set(p2.sample_id) == set(rc.sample_id) and len(p2) == len(rc), "pass 2 must cover the 40 recheck rows"
    assert rc.exists.isna().all(), "p1_manual_recheck.csv already filled"
    cols = ["exists", "evidence_url", "evidence_note", "checker", "checked_at"]
    rc = rc.drop(columns=cols).merge(p2[["sample_id"] + cols], on="sample_id", how="left")
    rc.to_csv(res / "p1_manual_recheck.csv", index=False)
    m = rc[["sample_id", "tier", "exists", "checked_at"]].merge(
        p1[["sample_id", "exists", "checked_at"]], on="sample_id", suffixes=("_2", "_1"))
    a, b = m.exists_1.str.strip().values, m.exists_2.str.strip().values
    k3, po, pe, se, t = kappa(a, b, CATS)
    k2, po2, _, se2, _ = kappa(np.where(a == "exists", "exists", "other"), np.where(b == "exists", "exists", "other"),
                               ["exists", "other"])
    rng = np.random.default_rng(args.seed)
    kb, kb2 = [], []
    for idx in rng.integers(0, len(m), (args.boot, len(m))):
        kb.append(kappa(a[idx], b[idx], CATS)[0])
        kb2.append(kappa(np.where(a[idx] == "exists", "e", "o"), np.where(b[idx] == "exists", "e", "o"), ["e", "o"])[0])
    q = lambda v: [float(np.nanquantile(v, 0.025)), float(np.nanquantile(v, 0.975))]  # noqa: E731
    gap_h = (pd.to_datetime(m.checked_at_2) - pd.to_datetime(m.checked_at_1)).dt.total_seconds() / 3600
    tab = pd.DataFrame(t.astype(int), index=[f"pass1={c}" for c in CATS], columns=[f"pass2={c}" for c in CATS])
    tab.insert(0, "interim", False)
    tab.to_csv(res / "p1_kappa_table.csv")
    dis = m[m.exists_1 != m.exists_2][["sample_id", "tier", "exists_1", "exists_2"]]
    out = {"interim": False, "seed": args.seed, "boot": args.boot, "n": int(len(m)), "rater": "CC (intra-rater)",
           "min_gap_hours": float(gap_h.min()), "kappa3": float(k3), "kappa3_boot95": q(kb),
           "kappa3_asymptotic_se": float(se), "raw_agreement": float(po), "expected_agreement": float(pe),
           "kappa_binary_exists": float(k2), "kappa_binary_boot95": q(kb2), "raw_agreement_binary": float(po2),
           "table_rows_pass1_cols_pass2": {"categories": CATS, "counts": t.astype(int).tolist()},
           "pass1_counts": pd.Series(a).value_counts().to_dict(), "pass2_counts": pd.Series(b).value_counts().to_dict(),
           "disagreements": dis.to_dict("records"), "kappa_ge_0.7": bool(k3 >= 0.7),
           # exploratory: kappa is degenerate when one pass uses a single category (pe = po); PABAK and the
           # Wilson CI of the raw agreement are reported alongside (Byrt, Bishop & Carlin 1993)
           "exploratory_pabak3": float((len(CATS) * po - 1) / (len(CATS) - 1)), "exploratory_pabak_binary": float(2 * po2 - 1),
           "raw_agreement_wilson95": list(wilson(int(round(po * len(m))), len(m)))}
    (res / "p1_kappa.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
