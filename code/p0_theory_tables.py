#!/usr/bin/env python3
"""Topic 43 / P0 / T02: exact tables for Theorems 1-2 and Proposition 4, checked by Monte Carlo (5 seeds).

(a) PPV ceiling  PPV*(pi, u) = pi / (pi + (1 - pi) u)            pi in {0.2, 0.5, 1, 2} %, u in {0.5, 1, 1.5, 3, 5} %
(b) P(false flag) = P(Bin(n, u) >= k)                             n in {20, 50, 100, 150, 300}, k in {1, 2, 3}
(c) k*(n, u, alpha) = min{k : P(Bin(n, u) >= k) <= alpha}         alpha in {1, 5} %
(d) Monte Carlo: seeds seed..seed+4; (a) with s = 1 on M references, (b) on P papers per cell.
Headlines use (pi, u) from theory/params_from_lit.csv.

Outputs: results/p0_theory_tables.csv, results/p0_theory_tables.png, results/p0_theory_headlines.json
Usage: python p0_theory_tables.py --seed 42 [--limit N]   (--limit caps MC sample sizes, for quick runs)
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
PIS = [0.002, 0.005, 0.01, 0.02]
US = [0.005, 0.01, 0.015, 0.03, 0.05]
NS = [20, 50, 100, 150, 300]
KS = [1, 2, 3]
ALPHAS = [0.01, 0.05]
NS_K = [10, 20, 30, 50, 75, 100, 150, 200, 300, 500]


def ppv_ceiling(pi, u):
    return pi / (pi + (1 - pi) * u)


def p_false_flag(n, k, u):
    return float(binom.sf(k - 1, n, u))


def k_star(n, u, alpha):
    for k in range(1, n + 2):
        if p_false_flag(n, k, u) <= alpha:
            return k
    return n + 1


def lit_params():
    """Pick headline (pi, u) values from params_from_lit.csv; every value keeps its source + page."""
    df = pd.read_csv(ROOT / "theory" / "params_from_lit.csv")

    def get(src, sym, contains):
        m = df[(df.source_key == src) & (df.symbol == sym) & df.quantity.str.contains(contains, regex=False)]
        if m.empty:
            raise KeyError(f"{src}/{sym}/{contains}")
        r = m.iloc[0]
        return r

    out = {}
    r = get("zhao2026wild", "pi", "arXiv")
    out["pi_zhao_arxiv_aug2025"] = (float(r.value), f"{r.source_key} {r.page_or_section}: {r.quantity}")
    r = get("zhao2026wild", "u_stage3", "refined title")
    out["u_zhao_stage3"] = (float(r.value), f"{r.source_key} {r.page_or_section}: {r.quantity} "
                                            "(pooled 2020-2025, NOT a pre-LLM baseline; upper proxy for u)")
    # Russinovich et al.: ICLR 2023 (submissions Sept 2022, pre-ChatGPT) share of papers with >= 1 flag,
    # accepted 0.160 (n=1566) / rejected 0.169 (n=2208); mean refs/paper from ICLR 2025 (221281 refs / 3703 papers).
    r = get("russinovich2026phantom", "flag_rate_paper", "ICLR 2023")
    acc, rej = 0.160, 0.169
    n_acc, n_rej = 1566, 2208
    share = (acc * n_acc + rej * n_rej) / (n_acc + n_rej)
    nbar = 221281 / 3703
    u_impl = 1 - (1 - share) ** (1 / nbar)
    out["u_phantom_iclr2023_implied"] = (u_impl, f"derived (ours) from {r.source_key} {r.page_or_section}: pooled "
                                                 f">=1-flag share {share:.4f} of ICLR 2023 papers, mean n={nbar:.1f} "
                                                 "(ICLR 2025 refs/paper), k=1 binomial inversion; "
                                                 "biased low by Jensen (n varies)")
    r = get("russinovich2026phantom", "flag_rate_ref", "2025 (all refs)")
    iclr25 = float(str(r.value).split("/")[0])
    out["pi_phantom_iclr2025_excess"] = (max(iclr25 - u_impl, 0.0),
                                         f"derived (ours): ICLR 2025 flagged-ref rate {iclr25} ({r.source_key} "
                                         f"{r.page_or_section}) minus implied pre-LLM u")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="cap MC sizes (0 = full: 2e6 refs, 2e4 papers per cell)")
    ap.add_argument("--u0-json", default=str(RES / "p0_groundtruth.json"),
                    help="ground-truth JSON with measured u0 (def1 title-only, def2 title+author); skipped if absent")
    args = ap.parse_args()
    seeds = [args.seed + i for i in range(5)]
    M = 2_000_000 if not args.limit else min(args.limit, 2_000_000)
    P = 20_000 if not args.limit else min(args.limit, 20_000)
    RES.mkdir(exist_ok=True)
    rows = []

    # (a) + MC
    for pi in PIS:
        for u in US:
            exact = ppv_ceiling(pi, u)
            mc = []
            for sd in seeds:
                rng = np.random.default_rng([sd, int(pi * 1e5), int(u * 1e5), 1])
                fab = rng.random(M) < pi
                z = np.where(fab, True, rng.random(M) < u)  # s = 1
                mc.append(fab[z].mean())
            rows.append(dict(table="ppv_ceiling", pi=pi, u=u, n=None, k=None, alpha=None, exact=exact,
                             mc_mean=np.mean(mc), mc_sd=np.std(mc, ddof=1), mc_n=M, mc_seeds=len(seeds)))
    # (b) + MC
    for n in NS:
        for k in KS:
            for u in US:
                exact = p_false_flag(n, k, u)
                mc = []
                for sd in seeds:
                    rng = np.random.default_rng([sd, n, k, int(u * 1e5), 2])
                    z = rng.random((P, n)) < u if n * P <= 6e7 else None
                    if z is None:  # memory guard: draw counts in chunks
                        cnt = np.concatenate([(rng.random((P // 4, n)) < u).sum(1) for _ in range(4)])
                    else:
                        cnt = z.sum(1)
                    mc.append((cnt >= k).mean())
                rows.append(dict(table="p_false_flag", pi=0.0, u=u, n=n, k=k, alpha=None, exact=exact,
                                 mc_mean=np.mean(mc), mc_sd=np.std(mc, ddof=1), mc_n=len(cnt), mc_seeds=len(seeds),
                                 poisson=float(1 - sum(math.exp(-n * u) * (n * u) ** j / math.factorial(j)
                                                       for j in range(k))),
                                 lecam_bound=n * u * u))
    # (c)
    for alpha in ALPHAS:
        for u in US:
            for n in NS_K:
                ks = k_star(n, u, alpha)
                rows.append(dict(table="k_alpha", pi=None, u=u, n=n, k=ks, alpha=alpha,
                                 exact=p_false_flag(n, ks, u)))
    df = pd.DataFrame(rows)
    df["abs_err_mc"] = (df.mc_mean - df.exact).abs()
    df.to_csv(RES / "p0_theory_tables.csv", index=False, float_format="%.6g")

    # MC check: |mc - exact| within 4 binomial SE of the pooled estimate
    chk = df[df.table != "k_alpha"].copy()
    n_eff = np.where(chk.table == "ppv_ceiling",
                     chk.mc_n * (chk.pi + (1 - chk.pi) * chk.u),  # PPV is a proportion among flagged refs
                     chk.mc_n) * 5
    se = np.sqrt(chk.exact * (1 - chk.exact) / n_eff).clip(lower=1e-9)
    worst = float((chk.abs_err_mc / se).max())

    # headlines
    lp = lit_params()
    pi_z, src_pi = lp["pi_zhao_arxiv_aug2025"]
    heads = {"seed": args.seed, "mc_seeds": seeds, "mc_max_abs_err_over_se": round(worst, 2), "params": {
        k: {"value": v, "source": s} for k, (v, s) in lp.items()}, "headlines": []}
    for ukey in ["u_zhao_stage3", "u_phantom_iclr2023_implied"]:
        u, _ = lp[ukey]
        heads["headlines"].append({
            "name": f"PPV ceiling, pi = Zhao arXiv Aug-2025, u = {ukey}", "pi": pi_z, "u": u,
            "ppv_ceiling": ppv_ceiling(pi_z, u)})
        heads["headlines"].append({
            "name": f"P(false flag) survey n=150, k=2, u = {ukey}", "n": 150, "k": 2, "u": u,
            "p_false_flag": p_false_flag(150, 2, u)})
    pi_p, _ = lp["pi_phantom_iclr2025_excess"]
    u_p, _ = lp["u_phantom_iclr2023_implied"]
    heads["headlines"].append({"name": "PPV ceiling, Phantom ICLR (derived pi, implied u)", "pi": pi_p, "u": u_p,
                               "ppv_ceiling": ppv_ceiling(pi_p, u_p) if pi_p > 0 else 0.0})
    heads["headlines"].append({"name": "PLAN illustration pi=0.5%, u=1.5%", "pi": 0.005, "u": 0.015,
                               "ppv_ceiling": ppv_ceiling(0.005, 0.015),
                               "p_ff_n50_k1": p_false_flag(50, 1, 0.015), "p_ff_n50_k2": p_false_flag(50, 2, 0.015),
                               "p_ff_n150_k2": p_false_flag(150, 2, 0.015)})
    # P0B: headlines with OUR measured pre-LLM u0 (both definitions), pi scenarios Zhao arXiv 0.39 % and Phantom 0.5 %
    u0p = Path(args.u0_json)
    if u0p.exists():
        gt = json.loads(u0p.read_text(encoding="utf-8"))
        heads["u0_source"] = {"file": u0p.name, "smoke_test": gt.get("smoke_test"), "seed": gt.get("seed")}
        for dkey in ["def1_title_only", "def2_title_author"]:
            d = gt.get("u0", {}).get(dkey)
            if not d or not d.get("n"):
                continue
            for u_name, u in [("point", d["u0"]), ("wilson_lo", d["wilson95"][0]), ("wilson_hi", d["wilson95"][1])]:
                for pi_name, pi in [("zhao_arxiv_0.39%", pi_z), ("phantom_0.5%", 0.005)]:
                    heads["headlines"].append({
                        "name": f"MEASURED u0 {dkey} ({u_name}), pi {pi_name}", "u0_def": dkey, "u_variant": u_name,
                        "u": u, "u0_n_refs": d["n"], "u0_n_papers": d.get("n_papers"), "pi": pi,
                        "ppv_ceiling": ppv_ceiling(pi, u) if u > 0 else 1.0,
                        "p_ff_n50_k1": p_false_flag(50, 1, u), "p_ff_n50_k2": p_false_flag(50, 2, u),
                        "p_ff_n150_k2": p_false_flag(150, 2, u),
                        "k_alpha_n150_a0.05": k_star(150, u, 0.05) if u > 0 else 1,
                        "k_alpha_n150_a0.01": k_star(150, u, 0.01) if u > 0 else 1})
    (RES / "p0_theory_headlines.json").write_text(json.dumps(heads, indent=2), encoding="utf-8")

    # figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    ug = np.linspace(0.001, 0.05, 200)
    for pi in PIS:
        ax[0].plot(ug * 100, ppv_ceiling(pi, ug) * 100, label=f"π = {pi*100:g} %")
    a = df[df.table == "ppv_ceiling"]
    ax[0].errorbar(a.u * 100, a.mc_mean * 100, yerr=a.mc_sd * 100, fmt="k.", ms=3, label="MC (5 seeds)")
    ax[0].set(xlabel="u = P(unresolved | real) [%]", ylabel="PPV ceiling [%]", title="Thm 1: precision ceiling")
    ax[0].legend(fontsize=7)
    ng = np.arange(5, 401)
    for k in KS:
        ax[1].plot(ng, binom.sf(k - 1, ng, 0.015) * 100, label=f"k = {k}")
    b = df[(df.table == "p_false_flag") & (df.u == 0.015)]
    ax[1].errorbar(b.n, b.mc_mean * 100, yerr=b.mc_sd * 100, fmt="k.", ms=3, label="MC (5 seeds)")
    ax[1].set(xlabel="n references", ylabel="P(legit paper flagged) [%]", title="Thm 2: u = 1.5 %")
    ax[1].legend(fontsize=7)
    for alpha, ls in zip(ALPHAS, ["-", "--"]):
        for u in [0.005, 0.015, 0.05]:
            c = df[(df.table == "k_alpha") & (df.alpha == alpha) & (df.u == u)]
            ax[2].plot(c.n, c.k, ls, marker="o", ms=3, label=f"α={alpha*100:g}%, u={u*100:g}%")
    ax[2].axhline(2, color="grey", lw=0.8)
    ax[2].set(xlabel="n references", ylabel="k*(n, u, α)", title="Prop 4: α-safe threshold")
    ax[2].legend(fontsize=6)
    fig.suptitle(f"Topic 43 P0 theory tables (exact; MC seeds {seeds[0]}–{seeds[-1]})", fontsize=9)
    fig.tight_layout()
    fig.savefig(RES / "p0_theory_tables.png", dpi=150)

    print(f"seed={args.seed} MC seeds={seeds} M={M} refs, P={P} papers per cell; max |MC-exact|/SE = {worst:.2f}")
    for h in heads["headlines"]:
        print(h)


if __name__ == "__main__":
    main()
