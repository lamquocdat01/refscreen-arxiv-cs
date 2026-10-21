#!/usr/bin/env python3
"""Topic 43 / P1 — EXPLORATORY H5 diagnosis (not preregistered, no amendment). Independent re-implementation of the
H5 prediction (Thm 2′) to rule out an aggregation or bookkeeping error.

1. Per-paper prediction: P_i(>= k) = 1 - P(PoissonBinomial_i < k), with paper i's own tier counts n_is and the tier
   rates u_s; mean P_i per n-tertile vs the observed share of flagged papers. For contrast, the "bin-averaged mix"
   prediction (mean w per tertile, median n) is also reported; the registered H5 does NOT use it.
2. Set consistency: u_s and "paper flagged" are computed on the same reference set (def 1 resolved/unresolved,
   rate-limited and no-title excluded, same backend column). n on both sides is printed and checked against the
   backend table.
3. Leave-one-paper-out u_s (paper i's refs removed when predicting paper i); the full-sample u_s is shown alongside.
Scenarios: crossref_only, plus_dblp (+ full, non-interim). Period 2019-21 (pi = 0).
Input:  results/[interim/]p1_groundtruth.csv, p1_backend_table.json
Output: results/[interim/]p1_h5_diag.{json,csv}
Usage:  python p1_h5_diag.py --seed 42 [--limit N] [--resume] [--interim]
        (deterministic; --seed is recorded only; --limit caps papers for smoke tests)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binom

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_theory_tables import TIERS, resolved_by, wilson  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KS = [1, 2, 3]
BT_COL = {"full": "s2", "crossref_only": "crossref", "plus_dblp": "dblp"}


def pb_tail(counts, rates, ks):
    pmf = np.array([1.0])
    for n, u in zip(counts, rates):
        n = int(round(n))
        if n > 0:
            pmf = np.convolve(pmf, binom.pmf(np.arange(n + 1), n, u))
    return {k: float(pmf[k:].sum()) if k < len(pmf) else 0.0 for k in ks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--interim", action="store_true")
    args = ap.parse_args()
    res_dir = ROOT / "results" / "interim" if args.interim else ROOT / "results"
    out_json = res_dir / "p1_h5_diag.json"
    if args.resume and out_json.exists():
        print("resume: output exists")
        return
    gt = pd.read_csv(res_dir / "p1_groundtruth.csv", dtype={"paper_id": str, "key": str}, low_memory=False)
    bt = json.loads((res_dir / "p1_backend_table.json").read_text(encoding="utf-8"))
    bt_n = {r["stratum"]: r["n"] for r in bt["rows"] if r["period"] == "2019-21"}
    ev = gt[gt.def1_status.isin(["resolved", "unresolved"])].copy()
    excluded = gt[(gt.period == "2019-21") & ~gt.def1_status.isin(["resolved", "unresolved"])].def1_status.value_counts()
    unres = (ev.def1_status == "unresolved").values
    scen = {} if args.interim else {"full": unres.astype(int)}
    scen["crossref_only"] = (unres | ~resolved_by(ev.backends_hit, ["crossref"])).astype(int)
    scen["plus_dblp"] = (unres | ~resolved_by(ev.backends_hit, ["crossref", "arxiv", "dblp"])).astype(int)
    out = dict(label="EXPLORATORY H5 diagnosis — does not replace H5 (PREREG §5)", seed=args.seed, period="2019-21",
               definition="def 1", interim=args.interim, excluded_2019_21=excluded.to_dict(), scenarios={})
    tabs = []
    for sc, x in scen.items():
        ev["x"] = x
        pre = ev[ev.period == "2019-21"]
        K = pre.pivot_table(index="paper_id", columns="tier", values="x", aggfunc="sum", fill_value=0)
        N = pre.pivot_table(index="paper_id", columns="tier", values="x", aggfunc="count", fill_value=0)
        K, N = K.reindex(columns=TIERS, fill_value=0), N.reindex(columns=TIERS, fill_value=0)
        tk, tn = K.sum(), N.sum()
        u_full = (tk / tn.where(tn > 0)).fillna(0.0)
        # 2. set consistency: the rate side and the flag side use the same refs
        n_rate_side = {t: int(tn[t]) for t in TIERS}
        n_flag_side = {t: int(N[t].sum()) for t in TIERS}
        consist = dict(n_refs_rate_side=int(tn.sum()), n_refs_flag_side=int(N.values.sum()),
                       n_papers_flag_side=int(len(K)), per_tier_rate_side=n_rate_side,
                       per_tier_backend_table={t: bt_n.get(t) for t in TIERS},
                       same_set=n_rate_side == n_flag_side,
                       matches_backend_table=all(bt_n.get(t) == n_rate_side[t] for t in TIERS if t in bt_n),
                       u_s_full={t: float(u_full[t]) for t in TIERS})
        rows = []
        for i, pid in enumerate(K.index):
            c, k = N.loc[pid].values, K.loc[pid].values
            loo = [(tk[t] - k[j]) / (tn[t] - c[j]) if tn[t] - c[j] > 0 else 0.0 for j, t in enumerate(TIERS)]
            p_loo, p_full = pb_tail(c, loo, KS), pb_tail(c, u_full.values, KS)
            rows.append(dict(scenario=sc, paper_id=pid, n=int(c.sum()), N=int(k.sum()),
                             **{f"n_{t}": int(v) for t, v in zip(TIERS, c)},
                             **{f"p_loo_k{q}": p_loo[q] for q in KS}, **{f"p_full_k{q}": p_full[q] for q in KS}))
            if args.limit and i + 1 >= args.limit:
                break
        h = pd.DataFrame(rows)
        h["tertile"] = pd.qcut(h.n.rank(method="first"), 3, labels=["T1", "T2", "T3"]).astype(str)
        res = []
        for q in KS:
            for t, g in h.groupby("tertile"):
                kk, nn = int((g.N >= q).sum()), len(g)
                lo, hi = wilson(kk, nn)
                w = g[[f"n_{s}" for s in TIERS]].sum() / g.n.sum()  # bin-averaged mix (contrast only)
                p_bin = pb_tail([g.n.median() * w[f"n_{s}"] for s in TIERS], u_full.values, [q])[q]
                pl, pf = float(g[f"p_loo_k{q}"].mean()), float(g[f"p_full_k{q}"].mean())
                res.append(dict(scenario=sc, k=q, tertile=t, n_papers=nn, n_refs_sum=int(g.n.sum()),
                                n_refs_median=float(g.n.median()), k_flagged=kk, obs=kk / nn, wilson_lo=lo,
                                wilson_hi=hi, pred_per_paper_loo=pl, pred_per_paper_full=pf,
                                pred_binavg_mix=p_bin, loo_in_ci=bool(lo <= pl <= hi),
                                excess_loo=pl - kk / nn, mean_lambda=float((g[[f"n_{s}" for s in TIERS]].values
                                                                            * u_full.values).sum(1).mean()),
                                mean_N=float(g.N.mean())))
        res = pd.DataFrame(res)
        r2 = res[res.k == 2].sort_values("tertile")
        verdict = dict(monotone=bool(all(np.diff(r2.obs.values) >= 0)), all_in_ci_k2=bool(r2.loo_in_ci.all()),
                       matches_registered_h5="see p1_h5.csv pred_mean (same estimator)")
        out["scenarios"][sc] = dict(consistency=consist, verdict_k2=verdict, tertiles=res.to_dict("records"))
        tabs.append(res)
        print(sc, json.dumps({k: v for k, v in consist.items() if k != "u_s_full"}), flush=True)
        print(r2[["tertile", "n_papers", "n_refs_sum", "k_flagged", "obs", "wilson_lo", "wilson_hi",
                  "pred_per_paper_loo", "pred_per_paper_full", "pred_binavg_mix", "mean_lambda", "mean_N"]]
              .round(3).to_string(index=False), flush=True)
    pd.concat(tabs).to_csv(res_dir / "p1_h5_diag.csv", index=False)
    out_json.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
