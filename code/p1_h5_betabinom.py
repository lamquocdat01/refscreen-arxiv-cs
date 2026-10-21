#!/usr/bin/env python3
"""Topic 43 / P1 — EXPLORATORY (not preregistered, no amendment): between-paper overdispersion of unresolved refs
and a beta-binomial re-prediction of the H5 tertile test (THEORY_43_v2 §7, draft Thm 2″).

The preregistered H5 (PREREG §5, p1_theory_tables.py) is untouched; its FAIL stands. This script reports, on the
2019-21 corpus (pi = 0, def 1):
1. per-paper u_i (academic tier A and each tier s), with quantiles;
2. per tier s, the beta-binomial MLE (mu_s, rho_s) of k_is ~ BetaBin(n_is, a_s, b_s) over papers, where
   rho_s = 1 / (a_s + b_s + 1) is the intra-paper correlation (ICC) and phi_s = 1 + (nbar_s - 1) rho_s the variance
   inflation over the binomial at the mean per-paper count nbar_s; LR test of rho_s = 0 (boundary, 50:50 chi-bar^2);
   paper-bootstrap 95 % CI of rho_s;
3. Thm 2″ prediction P(N_i >= k) = P(sum_s BetaBin(n_is, a_s, b_s) >= k), tiers independent given the paper,
   leave-one-paper-out fits (as H5), compared per n-tertile with the observed share and its Wilson 95 % CI;
   a paper-bootstrap band of the mean prediction; PASS rule as H5 (monotone and every prediction inside the CI).
Scenarios as p1_theory_tables.py: crossref_only, plus_dblp (+ full = final cascade, non-interim only).
Input:  results/[interim/]p1_groundtruth.csv
Output: results/[interim/]p1_h5_betabinom.{json,csv}, p1_paper_u.csv
Usage:  python p1_h5_betabinom.py --seed 42 [--boot 200] [--limit N] [--resume] [--interim]
        --limit N caps papers (smoke tests); --resume reuses an existing json for the same arguments.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from scipy.stats import betabinom, binom, chi2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_theory_tables import TIERS, resolved_by, wilson  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KS = [1, 2, 3]  # k = 2 is the H5 threshold; 1 and 3 are reported alongside
RHO_MIN = 1e-6


def nll(theta, k, n):
    mu, rho = expit(theta[0]), np.clip(expit(theta[1]), RHO_MIN, 1 - 1e-9)
    a, b = mu * (1 - rho) / rho, (1 - mu) * (1 - rho) / rho
    return -betabinom.logpmf(k, n, a, b).sum()


def fit_bb(k, n, x0=None):
    """Beta-binomial MLE over papers; returns mu, rho, a, b, loglik. Degenerate tiers (all 0 or all n) fall back to
    the binomial with rho = 0."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    m = n > 0
    k, n = k[m], n[m]
    p = k.sum() / n.sum() if n.sum() else 0.0
    if p <= 0 or p >= 1 or len(n) < 3:
        return dict(mu=p, rho=0.0, a=np.inf, b=np.inf, ll=float(binom.logpmf(k, n, p).sum()) if len(n) else 0.0)
    p = min(max(p, 1e-4), 1 - 1e-4)
    x0 = x0 if x0 is not None else [logit(p), logit(0.05)]
    r = minimize(nll, x0, args=(k, n), method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-8, maxiter=4000))
    mu, rho = float(expit(r.x[0])), float(max(expit(r.x[1]), RHO_MIN))
    return dict(mu=mu, rho=rho, a=mu * (1 - rho) / rho, b=(1 - mu) * (1 - rho) / rho, ll=float(-r.fun), x=r.x)


def tail(counts, pars, ks):
    """P(sum_s BetaBin(n_s, a_s, b_s) >= k) for k in ks; rho = 0 tiers use the binomial."""
    pmf = np.array([1.0])
    for n, f in zip(counts, pars):
        if n <= 0:
            continue
        x = np.arange(n + 1)
        comp = binom.pmf(x, n, f["mu"]) if f["rho"] <= RHO_MIN or not np.isfinite(f["a"]) \
            else betabinom.pmf(x, n, f["a"], f["b"])
        pmf = np.convolve(pmf, comp)
    return {k: float(pmf[k:].sum()) if k < len(pmf) else 0.0 for k in ks}


def binom_tail(counts, rates, ks):
    pmf = np.array([1.0])
    for n, u in zip(counts, rates):
        if n > 0:
            pmf = np.convolve(pmf, binom.pmf(np.arange(n + 1), n, u))
    return {k: float(pmf[k:].sum()) if k < len(pmf) else 0.0 for k in ks}


def run_scenario(sc, pre, args, rng):
    K = pre.pivot_table(index="paper_id", columns="tier", values="x", aggfunc="sum", fill_value=0)
    N = pre.pivot_table(index="paper_id", columns="tier", values="x", aggfunc="count", fill_value=0)
    K, N = K.reindex(columns=TIERS, fill_value=0), N.reindex(columns=TIERS, fill_value=0)
    papers = K.index.values
    # 1. per-paper u_i
    pu = pd.DataFrame({"scenario": sc, "paper_id": papers, "n_A": N[["J", "C", "P"]].sum(1).values,
                       "k_A": K[["J", "C", "P"]].sum(1).values})
    pu["u_A"] = pu.k_A / pu.n_A.where(pu.n_A > 0)
    for t in TIERS:
        pu[f"u_{t}"] = K[t].values / np.where(N[t].values > 0, N[t].values, np.nan)
    q = pu.u_A.dropna().quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(4)
    # 2. beta-binomial per tier
    fits, tiers_out = {}, {}
    for t in TIERS:
        f = fit_bb(K[t].values, N[t].values)
        kk, nn = K[t].values[N[t].values > 0], N[t].values[N[t].values > 0]
        p = kk.sum() / nn.sum() if nn.sum() else 0.0
        ll0 = float(binom.logpmf(kk, nn, p).sum()) if len(nn) else 0.0
        lr = max(0.0, 2 * (f["ll"] - ll0))
        nbar = float(nn.mean()) if len(nn) else 0.0
        boot = []
        for _ in range(args.boot):
            i = rng.integers(0, len(kk), len(kk)) if len(kk) else []
            boot.append(fit_bb(kk[i], nn[i], f.get("x"))["rho"] if len(kk) else 0.0)
        fits[t] = f
        tiers_out[t] = dict(n_papers=int(len(nn)), k=int(kk.sum()), n=int(nn.sum()), u_pooled=p, mu=f["mu"],
                            rho_icc=f["rho"], rho_boot95=[float(v) for v in np.quantile(boot, [0.025, 0.975])],
                            nbar=nbar, phi=1 + (nbar - 1) * f["rho"], lr_stat=lr,
                            p_lr_rho0=float(0.5 * chi2.sf(lr, 1)) if lr > 0 else 0.5)
    # 3. Thm 2″ prediction, leave-one-paper-out (refit without paper i), vs observed per tertile
    tot_k, tot_n = K.sum(), N.sum()
    rows = []
    for i, pid in enumerate(papers):
        counts, ks = N.loc[pid].values.astype(int), K.loc[pid].values.astype(int)
        loo_f, loo_u = [], []
        for j, t in enumerate(TIERS):
            if counts[j] == 0:
                loo_f.append(fits[t]); loo_u.append(0.0)
                continue
            m = papers != pid
            loo_f.append(fit_bb(K[t].values[m], N[t].values[m], fits[t].get("x")))
            nn = tot_n[t] - counts[j]
            loo_u.append((tot_k[t] - ks[j]) / nn if nn > 0 else 0.0)
        pb, pbin = tail(counts, loo_f, KS), binom_tail(counts, loo_u, KS)
        rows.append(dict(scenario=sc, paper_id=pid, n=int(counts.sum()), N=int(ks.sum()),
                         **{f"pred_bb_k{k}": pb[k] for k in KS}, **{f"pred_bin_k{k}": pbin[k] for k in KS}))
        if args.limit and i + 1 >= args.limit:
            break
    h = pd.DataFrame(rows)
    h["tertile"] = pd.qcut(h.n.rank(method="first"), 3, labels=["T1", "T2", "T3"]).astype(str)
    # paper-bootstrap band of the mean prediction per tertile (full-sample refit per draw, no LOO)
    bands = {k: {t: [] for t in ["T1", "T2", "T3"]} for k in KS}
    terc = h.set_index("paper_id").tertile
    for _ in range(args.boot):
        idx = rng.integers(0, len(papers), len(papers))
        fb = [fit_bb(K[t].values[idx], N[t].values[idx], fits[t].get("x")) for t in TIERS]
        pp = {pid: tail(N.loc[pid].values.astype(int), fb, KS) for pid in h.paper_id}
        for k in KS:
            for t in bands[k]:
                ids = terc.index[terc == t]
                bands[k][t].append(np.mean([pp[p][k] for p in ids]))
    res = []
    for k in KS:
        for t, g in h.groupby("tertile"):
            kk, nn = int((g.N >= k).sum()), len(g)
            lo, hi = wilson(kk, nn)
            pb, pbin = float(g[f"pred_bb_k{k}"].mean()), float(g[f"pred_bin_k{k}"].mean())
            res.append(dict(scenario=sc, k=k, tertile=t, n_papers=nn, n_refs_median=float(g.n.median()),
                            k_flagged=kk, obs=kk / nn, wilson_lo=lo, wilson_hi=hi, pred_binomial=pbin,
                            pred_betabinom=pb, pred_bb_boot95=[float(v) for v in np.quantile(bands[k][t], [.025, .975])],
                            bin_in_ci=bool(lo <= pbin <= hi), bb_in_ci=bool(lo <= pb <= hi)))
    res = pd.DataFrame(res)
    verdict = {}
    for k in KS:
        r = res[res.k == k].sort_values("tertile")
        mono = bool(all(np.diff(r.obs.values) >= 0))
        verdict[f"k{k}"] = dict(monotone=mono, bb_all_in_ci=bool(r.bb_in_ci.all()),
                                PASS_exploratory=mono and bool(r.bb_in_ci.all()),
                                binomial_all_in_ci=bool(r.bin_in_ci.all()))
    out = dict(per_paper_u_A_quantiles={str(k): float(v) for k, v in q.items()},
               n_papers=int(len(papers)), tiers=tiers_out, tertiles=res.to_dict("records"), verdict=verdict)
    return out, res, pu


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--interim", action="store_true")
    args = ap.parse_args()
    res_dir = ROOT / "results" / "interim" if args.interim else ROOT / "results"
    out_json = res_dir / "p1_h5_betabinom.json"
    if args.resume and out_json.exists():
        old = json.loads(out_json.read_text(encoding="utf-8"))
        if (old.get("seed"), old.get("boot"), old.get("limit")) == (args.seed, args.boot, args.limit):
            print("resume: output exists for these arguments")
            return
    gt = pd.read_csv(res_dir / "p1_groundtruth.csv", dtype={"paper_id": str, "key": str}, low_memory=False)
    ev = gt[gt.def1_status.isin(["resolved", "unresolved"])].copy()
    unres = (ev.def1_status == "unresolved").values
    scen = {} if args.interim else {"full": unres.astype(int)}
    scen["crossref_only"] = (unres | ~resolved_by(ev.backends_hit, ["crossref"])).astype(int)
    scen["plus_dblp"] = (unres | ~resolved_by(ev.backends_hit, ["crossref", "arxiv", "dblp"])).astype(int)
    out = dict(label="EXPLORATORY — not preregistered, does not replace H5 (PREREG §5)", seed=args.seed,
               boot=args.boot, limit=args.limit, period="2019-21", definition="def 1", interim=args.interim,
               model="Thm 2″ draft (THEORY_43_v2 §7): tiers independent given the paper, BetaBin per tier",
               scenarios={})
    tabs, pus = [], []
    for sc, x in scen.items():
        ev["x"] = x
        rng = np.random.default_rng(args.seed)
        o, r, pu = run_scenario(sc, ev[ev.period == "2019-21"], args, rng)
        out["scenarios"][sc] = o
        tabs.append(r)
        pus.append(pu)
        print(sc, json.dumps({t: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()
                                  if k in ("u_pooled", "rho_icc", "rho_boot95", "phi", "p_lr_rho0")}
                              for t, d in o["tiers"].items()}), json.dumps(o["verdict"]), flush=True)
    res_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(tabs).to_csv(res_dir / "p1_h5_betabinom.csv", index=False)
    pd.concat(pus).to_csv(res_dir / "p1_paper_u.csv", index=False)
    out_json.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
