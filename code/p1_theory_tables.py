#!/usr/bin/env python3
"""Topic 43 / P1 / T09: stratified theory tables (THEORY_43_v2.md) with the measured per-tier rates.

Inputs : results/p1_backend_table.json (def 1: u_s per tier x period, cumulative backends, paper-bootstrap CIs)
         results/p1_groundtruth.json (def 2), results/p1_groundtruth.csv (per reference: tier, status, backends_hit)
Backend scenarios (def 1): full = final cascade state (+S2 column of the backend table), crossref_only
(a reference counts as resolved only if Crossref resolved it) and plus_dblp (resolved by Crossref, arXiv or DBLP:
the +DBLP column). def 2 has the full scenario only.
Outputs: results/p1_theory_tables.csv     (long table: every cell, exact + MC where applicable)
         results/p1_theory_headlines.json (headlines from the academic tier only, with n and paper-level CIs)
         results/p1_h5.csv, results/p1_alpha_rules.csv (PREREG §7 lines 3 and 5), results/p1_theory.png
Rates u_s are taken from the 2019-2021 set (pi ~ 0) unless --period says otherwise; pi in {0.39 %, 0.5 %}.
Usage: python p1_theory_tables.py --seed 42 [--def def1] [--limit N] [--resume] [--interim]
       --interim: inputs and outputs in results/interim/ ("interim": true); scenarios crossref_only and plus_dblp
       only (full needs the final S2 state)
       (--limit caps MC sizes; --resume is a documented no-op: the script is deterministic and fast)
"""
import argparse
import json
import math
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import binom

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
TIERS = ["J", "C", "P", "B", "S", "W"]
ACAD = ["J", "C", "P"]
PIS = {"zhao_arxiv_0.39%": 0.0039, "phantom_0.5%": 0.005}
FIELDS3 = ["cs.CV", "cs.NI", "cs.CL"]


def pb_tail(counts, rates, k):
    """Exact P(sum_s Bin(n_s, u_s) >= k) by convolution of the per-tier pmfs."""
    pmf = np.array([1.0])
    for n, u in zip(counts, rates):
        n = int(round(n))
        if n <= 0:
            continue
        pmf = np.convolve(pmf, binom.pmf(np.arange(n + 1), n, u))
    return float(pmf[k:].sum()) if k < len(pmf) else 0.0


def k_star(counts, rates, alpha):
    pmf = np.array([1.0])
    for n, u in zip(counts, rates):
        n = int(round(n))
        if n > 0:
            pmf = np.convolve(pmf, binom.pmf(np.arange(n + 1), n, u))
    tail = pmf[::-1].cumsum()[::-1]  # tail[k] = P(N >= k)
    for k in range(1, len(tail)):
        if tail[k] <= alpha:
            return k
    return len(tail)


def ppv_star(pi, u):
    return pi / (pi + (1 - pi) * u)


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def resolved_by(bh, backends):
    """True if one of `backends` resolved the reference (the cascade stops at the first hit, so a hit at or before
    the last of them is in this set)."""
    return pd.Series(bh).fillna("").astype(str).str.split(";").map(lambda xs: bool(set(xs) & set(backends))).values


def rates_from_backend_table(period, col):
    bt = json.loads((RES / "p1_backend_table.json").read_text(encoding="utf-8"))
    U = {}
    for r in bt["rows"]:
        if r["period"] != period:
            continue
        lo, hi = (float(v) for v in r[f"boot_{col}"].split("-")) if r.get(f"boot_{col}") else (np.nan, np.nan)
        U[r["stratum"]] = {"u": r[f"u_{col}"], "k": r[f"k_{col}"], "n": r["n"], "n_papers": r["n_papers"],
                           "paper_bootstrap95": [lo, hi]}
    return U


def scenario_tables(sc, U, ev, args, seeds, M):
    """All theory tables for one backend scenario. ev.x = 1 if unresolved under this scenario."""
    u = {t: (U[t]["u"] if t in U and U[t]["u"] is not None else np.nan) for t in TIERS}
    u_hi = {t: (U[t]["paper_bootstrap95"][1] if t in U and U[t]["paper_bootstrap95"][1] == U[t]["paper_bootstrap95"][1]
                else u[t]) for t in TIERS}
    u_A = U["A"]["u"]
    rows = []
    # 1. PPV ceiling as a function of the web/software share w_W (Thm 1' / Cor 1'.1), academic mix held fixed
    uW = (U["W"]["k"] + U["S"]["k"]) / max(1, U["W"]["n"] + U["S"]["n"])
    for pn, pi in PIS.items():
        for wW in np.round(np.arange(0, 0.31, 0.02), 2):
            ub = (1 - wW) * u_A + wW * uW
            rows.append(dict(table="ppv_vs_wW", pi_name=pn, pi=pi, w_W=wW, u_A=u_A, u_WS=uW, u_bar=ub,
                             ppv_ceiling=ppv_star(pi, ub)))
    # 2. P(false flag) vs n for three measured field mixes (2024-26 mixes; u_s from --period), k = 1, 2; MC check
    mixes = {}
    for f in FIELDS3:
        g = ev[(ev.period == "2024-26") & (ev.field == f)]
        sh = g.tier.value_counts(normalize=True)
        mixes[f] = {t: float(sh.get(t, 0.0)) for t in TIERS}
    rates = [0.0 if np.isnan(u[t]) else u[t] for t in TIERS]
    for f, w in mixes.items():
        for n in [20, 30, 50, 75, 100, 150, 200, 300]:
            counts = [n * w[t] for t in TIERS]
            lam = sum(c * r for c, r in zip(counts, rates))
            for k in [1, 2]:
                exact = pb_tail(counts, rates, k)
                mc = []
                if n in (50, 150):
                    for sd in seeds:
                        rng = np.random.default_rng(sd)
                        N = sum(rng.binomial(int(round(c)), r, M) for c, r in zip(counts, rates))
                        mc.append(float((N >= k).mean()))
                rows.append(dict(table="pff_vs_n", field=f, n=n, k=k, exact=exact,
                                 poisson=float(1 - sum(math.exp(-lam) * lam ** j / math.factorial(j)
                                                       for j in range(k))),
                                 mc_mean=np.mean(mc) if mc else np.nan, mc_sd=np.std(mc, ddof=1) if mc else np.nan,
                                 mc_papers=M if mc else 0, **{f"w_{t}": w[t] for t in TIERS}))
    # 3. H5 (PREREG §5): observed share of 2019-21 papers with >= 2 unresolved refs vs leave-one-paper-out prediction
    pre = ev[ev.period == "2019-21"]
    tot = pre.groupby("tier").x.agg(["sum", "count"])
    per = pre.groupby(["paper_id", "tier"]).x.agg(["sum", "count"]).unstack(fill_value=0)
    h5 = []
    for pid in per.index:
        counts = [int(per.loc[pid, ("count", t)]) if ("count", t) in per.columns else 0 for t in TIERS]
        ks = [int(per.loc[pid, ("sum", t)]) if ("sum", t) in per.columns else 0 for t in TIERS]
        loo = []
        for t, c, kk in zip(TIERS, counts, ks):
            s_, n_ = (tot.loc[t, "sum"] - kk, tot.loc[t, "count"] - c) if t in tot.index else (0, 0)
            loo.append(s_ / n_ if n_ > 0 else 0.0)
        h5.append(dict(paper_id=pid, n=sum(counts), N=sum(ks), pred=pb_tail(counts, loo, 2)))
    h5 = pd.DataFrame(h5)
    h5_out, h5_res = {}, pd.DataFrame()
    if len(h5) >= 3:
        h5["tertile"] = pd.qcut(h5.n.rank(method="first"), 3, labels=["T1", "T2", "T3"])
        res = []
        for t, g in h5.groupby("tertile", observed=True):
            k, n = int((g.N >= 2).sum()), len(g)
            lo, hi = wilson(k, n)
            res.append(dict(scenario=sc, tertile=str(t), n_papers=n, n_refs_median=float(g.n.median()),
                            k_flagged2=k, obs=k / n, wilson_lo=lo, wilson_hi=hi, pred_mean=float(g.pred.mean()),
                            pred_in_ci=bool(lo <= g.pred.mean() <= hi)))
        h5_res = pd.DataFrame(res)
        mono = bool(all(np.diff(h5_res.obs.values) >= 0))
        h5_out = {"monotone": mono, "all_pred_in_ci": bool(h5_res.pred_in_ci.all()),
                  "PASS": mono and bool(h5_res.pred_in_ci.all()), "tertiles": h5_res.to_dict("records"),
                  "definition": args.defn, "seed": args.seed}
    # 4. alpha-safe rules (Prop 4', PREREG §7 line 5): legitimate (2019-21) papers flagged per rule, by field
    rules = []
    uA_hi = [u_hi[t] for t in ACAD]
    for (pid, f), g in pre.groupby(["paper_id", "field"]):
        nA = [int((g.tier == t).sum()) for t in ACAD]
        NA = int(g[g.tier.isin(ACAD)].x.sum())
        Nall = int(g.x.sum())
        r = dict(scenario=sc, paper_id=pid, field=f, n=len(g), n_A=sum(nA), N_all=Nall, N_A=NA,
                 flag_k1=int(Nall >= 1), flag_k2=int(Nall >= 2))
        for a in (0.05, 0.01):
            ks = k_star(nA, uA_hi, a)
            r[f"kstarA_{a}"] = ks
            r[f"flag_kstarA_{a}"] = int(NA >= ks)
        rules.append(r)
    rules = pd.DataFrame(rules)
    agg = []
    if len(rules):
        for f, g in list(rules.groupby("field")) + [("all", rules)]:
            d = dict(scenario=sc, field=f, n_papers=len(g))
            for c in ["flag_k1", "flag_k2", "flag_kstarA_0.05", "flag_kstarA_0.01"]:
                k_, n_ = int(g[c].sum()), len(g)
                lo, hi = wilson(k_, n_)
                d.update({f"{c}_k": k_, f"{c}_share": k_ / n_, f"{c}_wilson": [round(lo, 4), round(hi, 4)]})
            agg.append(d)
    # 5. headlines: academic tier only (PREREG), with n and paper-level CI ends
    heads = []
    cA = U["A"]
    wA = float(ev[ev.period == "2024-26"].tier.isin(ACAD).mean()) if len(ev) else np.nan
    for pn, pi in PIS.items():
        for var, ua in [("point", cA["u"]), ("ci_lo", cA["paper_bootstrap95"][0]),
                        ("ci_hi", cA["paper_bootstrap95"][1])]:
            heads.append(dict(scenario=sc, name=f"academic tier ({args.defn}, {args.period}, {sc}) {var}, pi {pn}",
                              u_A=ua, pi=pi, n_refs=cA["n"], n_papers=cA["n_papers"],
                              ppv_ceiling_A_pooled_pi=ppv_star(pi, ua),
                              ppv_ceiling_A_under_FA=ppv_star(min(1, pi / wA), ua) if wA == wA and wA > 0 else None,
                              w_A_2024_26=wA,
                              p_ff_n50_k1=float(binom.sf(0, 50, ua)), p_ff_n50_k2=float(binom.sf(1, 50, ua)),
                              p_ff_n150_k1=float(binom.sf(0, 150, ua)), p_ff_n150_k2=float(binom.sf(1, 150, ua)),
                              **{"kstar_n150_a0.05": k_star([150], [ua], 0.05),
                                 "kstar_n150_a0.01": k_star([150], [ua], 0.01)}))
    df = pd.DataFrame(rows)
    df["scenario"] = sc
    out = {"u_by_tier": {t: U.get(t) for t in TIERS + ["A", "all"]}, "field_mixes_2024_26": mixes,
           "headlines_academic": heads, "H5": h5_out,
           "alpha_rules_all_fields": next((a for a in agg if a["field"] == "all"), None)}
    return df, h5_res, pd.DataFrame(agg), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--def", dest="defn", default="def1", choices=["def1", "def2"])
    ap.add_argument("--period", default="2019-21")
    ap.add_argument("--limit", type=int, default=0, help="cap MC papers per cell (0 = 20,000)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--interim", action="store_true")
    args = ap.parse_args()
    global RES
    if args.interim:
        RES = RES / "interim"
    seeds = [args.seed + i for i in range(5)]
    M = args.limit or 20000
    gt = pd.read_csv(RES / "p1_groundtruth.csv", dtype={"paper_id": str, "key": str}, low_memory=False)
    st = f"{args.defn}_status"
    ev = gt[gt[st].isin(["resolved", "unresolved"])].copy()
    if args.defn == "def1":
        unres = (ev[st] == "unresolved").values
        scen = {} if args.interim else {"full": (rates_from_backend_table(args.period, "s2"), unres.astype(int))}
        scen["crossref_only"] = (rates_from_backend_table(args.period, "crossref"),
                                 (unres | ~resolved_by(ev.backends_hit, ["crossref"])).astype(int))
        scen["plus_dblp"] = (rates_from_backend_table(args.period, "dblp"),
                             (unres | ~resolved_by(ev.backends_hit, ["crossref", "arxiv", "dblp"])).astype(int))
    else:
        gj = json.loads((RES / "p1_groundtruth.json").read_text(encoding="utf-8"))
        scen = {"full": (gj["u"]["all"][args.period][args.defn], (ev[st] == "unresolved").values.astype(int))}
    tabs, h5s, aggs, outs = [], {}, [], {}
    for sc, (U, x) in scen.items():
        ev["x"] = x
        df, h5s[sc], agg, outs[sc] = scenario_tables(sc, U, ev, args, seeds, M)
        tabs.append(df)
        aggs.append(agg)
    df = pd.concat(tabs, ignore_index=True)
    df["seed"] = args.seed
    df.to_csv(RES / "p1_theory_tables.csv", index=False)
    pd.concat(h5s.values(), ignore_index=True).to_csv(RES / "p1_h5.csv", index=False)
    pd.concat(aggs, ignore_index=True).to_csv(RES / "p1_alpha_rules.csv", index=False)
    chk = df[(df.table == "pff_vs_n") & df.mc_mean.notna()]
    se = np.sqrt(chk.exact * (1 - chk.exact) / M)
    worst = float(((chk.mc_mean - chk.exact).abs() / se.replace(0, np.nan)).max()) if len(chk) else None
    out = {"seed": args.seed, "mc_seeds": seeds, "mc_papers_per_cell": M, "mc_max_abs_err_over_se": worst,
           "definition": args.defn, "period_for_u": args.period, "scenarios": outs}
    if args.interim:
        gj = json.loads((RES / "p1_groundtruth.json").read_text(encoding="utf-8"))
        out.update(interim=True, s2_pending=gj.get("s2_pending"),
                   interim_note="INTERIM: scenarios crossref_only and plus_dblp (exact before S2); full pending")
    (RES / "p1_theory_headlines.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for j, (sc, ls) in enumerate([("full", "-"), ("crossref_only", ":"), ("plus_dblp", "--")]):
        if sc not in scen:
            continue
        for pn in PIS:
            a = df[(df.table == "ppv_vs_wW") & (df.pi_name == pn) & (df.scenario == sc)]
            ax[0].plot(a.w_W * 100, a.ppv_ceiling * 100, ls, marker="o", ms=3,
                       label=f"{sc}, pi = {PIS[pn] * 100:.2f} % (u_A = {a.u_A.iloc[0] * 100:.2f} %)")
        for f in FIELDS3:
            b = df[(df.table == "pff_vs_n") & (df.field == f) & (df.k == 2) & (df.scenario == sc)]
            ax[1].plot(b.n, b.exact * 100, ls, label=f"{f}, k=2, {sc}")
        h = h5s[sc]
        if len(h):
            x = np.arange(len(h)) + 0.1 * (j - 1)
            ax[2].errorbar(x, h.obs * 100, yerr=[np.clip(h.obs - h.wilson_lo, 0, None) * 100,  # float rounding at k=0
                                                 np.clip(h.wilson_hi - h.obs, 0, None) * 100],
                           fmt="o", capsize=3, label=f"observed, {sc}")
            ax[2].plot(x, h.pred_mean * 100, "x", ms=9, label=f"Thm 2' (LOO), {sc}")
    ax[0].set_xlabel("share of web/software references w_W+S (%)")
    ax[0].set_ylabel("PPV ceiling (%)")
    ax[0].set_title(f"Thm 1': ceiling vs tier mix (u_s {args.period}, {args.defn})", fontsize=9)
    ax[0].legend(fontsize=6)
    ax[1].set_xlabel("bibliography length n")
    ax[1].set_ylabel("P(false flag | pi = 0), k = 2 (%)")
    ax[1].set_title("Thm 2': measured field mixes (2024-26)", fontsize=9)
    ax[1].legend(fontsize=6)
    ax[2].set_xticks(range(3), ["T1 (short)", "T2", "T3 (long)"])
    ax[2].set_ylabel("papers with >= 2 unresolved refs (%)")
    ax[2].set_title("H5: Thm 2' vs observed, 2019-21 (pi = 0), Wilson 95 %", fontsize=9)
    ax[2].legend(fontsize=6)
    fig.suptitle(("INTERIM (S2 pending) — " if args.interim else "") + f"seed {args.seed}; MC {len(seeds)} seeds x {M} papers; max |MC - exact| / se = "
                 f"{worst if worst is None else round(worst, 2)}", fontsize=8)
    fig.tight_layout()
    fig.savefig(RES / "p1_theory.png", dpi=150)
    print(json.dumps({"mc_max_abs_err_over_se": worst, "H5": {k: v["H5"] for k, v in outs.items()}}, indent=1,
                     default=float)[:3000])


if __name__ == "__main__":
    main()
