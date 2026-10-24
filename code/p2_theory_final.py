#!/usr/bin/env python3
"""Topic 43 / P2 / T10d: final theory numbers (THEORY_43_v3.md) from measured inputs.

Inputs (all P1 main, interim=false): results/p1_groundtruth.csv (2019-21, def 1), results/p1_backend_table.json
(u_s and paper-bootstrap 95 % CI per tier x cumulative backend), results/p1_h5_betabinom.json (per-tier mean mu_s
and ICC rho_s with bootstrap 95 % CI; exploratory fit of Thm 2'').
Backend scenarios: crossref_only and full (+S2), the two headline columns.

1. Thm 1' headline: PPV*_A at pi in {0.39 %, 0.5 %} with the u_A CI of each scenario.
2. Prop 2''' (dispersion): per paper, lambda_i = sum_s n_is u_s, V0_i = sum_s n_is u_s (1 - u_s) (Poisson-binomial)
   and V_i = (sum_s sqrt(n_is u_s (1 - u_s) (1 + (n_is - 1) rho_s)))^2 (beta-binomial tiers, any cross-tier
   correlation; Cauchy-Schwarz). Observed dispersion: sum_i (N_i - lambda_i)^2 against sum V0_i and sum V_i.
3. Rules on the academic tier A = J, C, P, per paper (Prop 4''), alpha in {0.05, 0.01}:
   R1 "CI"       k_i = min{k : P(PoiBin(n_is, u+_s) >= k) <= alpha},   u+_s = upper paper-bootstrap 95 % bound
   R2 "beta-q"   k_i = min{k : P(PoiBin(n_is, q_s) >= k) <= alpha/2},  q_s = (1 - alpha/(2|A|)) quantile of
                 Beta(mean u+_s, ICC rho+_s): P(reject | legit) <= alpha/2 + sum_s P(U_is > q_s) = alpha
   R3 "Cantelli" k_i = ceil(lambda+_i + sqrt(V+_i (1 - alpha) / alpha)), lambda+, V+ with u+_s and rho+_s:
                 P(N >= lambda + t) <= V / (V + t^2) needs only the mean and the variance.
   Checks: share of the 299 legitimate papers rejected (Wilson), and MC (5 seeds x 20,000 papers resampled
   from the 299 tier-count vectors, U_is ~ Beta(mu_s, rho_s), N_is ~ Bin(n_is, U_is)) per rule.
4. k_i for 5 typical papers (n_A at the 10/25/50/75/90 % quantiles) x 2 scenarios x 3 rules.
5. Identifier scenario (Thm 3 / Prop 3.1 consequence; decision LQD 21-10): every academic reference prints a
   resolvable identifier, so its unresolved rate is the certified-real FP of the render experiment with identifiers
   printed (union = identifier route then title cascade, GROBID, IEEEtran-DOI orig: k/n and paper-bootstrap upper
   bound from results/p1_screen_fp.csv; P3 correction of 24-10, P2 used the stripped IEEEtran cell). Same 5 papers,
   same rules with u_s = that FP for every tier (u+ = its upper bound) and rho+_s of the full cascade (conservative;
   no ICC is measurable from so few flags), plus P(N >= 2) for the "2 flags" rule.
Outputs: results/p2_theory_final.csv (long), results/numbers.json, results/numbers.tex (\\newcommand macros; C6)
Usage: python p2_theory_final.py --seed 42 [--mc 20000]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_theory_tables as tt  # noqa: E402
from ground_truth import ROOT  # noqa: E402

A = ["J", "C", "P"]
ALPHAS = [0.05, 0.01]
PIS = {"0.39%": 0.0039, "0.5%": 0.005}
SCEN = {"crossref_only": "crossref", "full": "s2"}
RES = ROOT / "results"


def beta_q(mu, rho, p):
    mu = min(max(mu, 1e-9), 1 - 1e-9)
    if rho <= 1e-6:
        return mu
    c = 1 / rho - 1
    return float(beta_dist.ppf(p, mu * c, (1 - mu) * c))


def var_bb(n, u, rho):
    return n * u * (1 - u) * (1 + (n - 1) * rho)


def rules_for(counts, up, rho_up, alpha):
    r1 = tt.k_star(counts, [up[s] for s in A], alpha)
    q = {s: beta_q(up[s], rho_up[s], 1 - alpha / (2 * len(A))) for s in A}
    r2 = tt.k_star(counts, [q[s] for s in A], alpha / 2)
    lam = sum(n * up[s] for n, s in zip(counts, A))
    v = sum(math.sqrt(var_bb(n, up[s], rho_up[s])) for n, s in zip(counts, A)) ** 2
    r3 = math.ceil(lam + math.sqrt(v * (1 - alpha) / alpha)) if v > 0 else 1
    return {"R1_CI": r1, "R2_betaq": r2, "R3_cantelli": max(r3, 1)}, q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--mc", type=int, default=20000)
    args = ap.parse_args()
    gt = pd.read_csv(RES / "p1_groundtruth.csv", dtype=str, keep_default_na=False)
    ev = gt[(gt.period == "2019-21") & gt.def1_status.isin(["resolved", "unresolved"])].copy()
    unres = (ev.def1_status == "unresolved").values
    bb = json.loads((RES / "p1_h5_betabinom.json").read_text(encoding="utf-8"))["scenarios"]
    rows, nums = [], {"seed": args.seed, "interim": False, "period": "2019-21", "definition": "def 1"}
    for sc, col in SCEN.items():
        U = tt.rates_from_backend_table("2019-21", col)
        x = unres if sc == "full" else (unres | ~tt.resolved_by(ev.backends_hit, ["crossref"]))
        ev["x"] = x.astype(int)
        u = {s: U[s]["u"] for s in A}
        up = {s: U[s]["paper_bootstrap95"][1] for s in A}
        tiers = bb[sc]["tiers"]
        rho = {s: tiers[s]["rho_icc"] for s in A}
        rho_up = {s: tiers[s]["rho_boot95"][1] for s in A}
        mu = {s: tiers[s]["mu"] for s in A}
        uA, (loA, hiA) = U["A"]["u"], U["A"]["paper_bootstrap95"]
        nums[sc] = {"u_A": uA, "u_A_ci": [loA, hiA], "u_s": u, "u_s_upper": up, "rho_s": rho, "rho_s_upper": rho_up}
        for pn, pi in PIS.items():
            nums[sc][f"ppv_A_pi{pn}"] = tt.ppv_star(pi, uA)
            nums[sc][f"ppv_A_pi{pn}_ci"] = [tt.ppv_star(pi, hiA), tt.ppv_star(pi, loA)]
            rows.append(dict(table="ppv_headline", scenario=sc, pi=pn, value=tt.ppv_star(pi, uA),
                             lo=tt.ppv_star(pi, hiA), hi=tt.ppv_star(pi, loA)))
        # per-paper A counts
        pa = ev[ev.tier.isin(A)].groupby(["paper_id", "tier"]).agg(n=("x", "size"), k=("x", "sum")).unstack(fill_value=0)
        P = pd.DataFrame({f"n_{s}": pa["n"].get(s, 0) for s in A}).fillna(0).astype(int)
        P["N_A"] = pa["k"].sum(axis=1).astype(int)
        all_papers = ev.paper_id.unique()
        P = P.reindex(all_papers, fill_value=0)
        P["n_A"] = P[[f"n_{s}" for s in A]].sum(axis=1)
        # Prop 2''' dispersion
        lam = sum(P[f"n_{s}"] * u[s] for s in A)
        v0 = sum(P[f"n_{s}"] * u[s] * (1 - u[s]) for s in A)
        vbb = sum(np.sqrt(var_bb(P[f"n_{s}"], u[s], rho[s])) for s in A) ** 2
        ss = float(((P.N_A - lam) ** 2).sum())
        nums[sc]["dispersion"] = {"sum_sq_dev": ss, "sum_V0_poibin": float(v0.sum()), "sum_V_bb_cs": float(vbb.sum()),
                                  "ratio_obs_to_poibin": ss / float(v0.sum()), "ratio_obs_to_bb_cs": ss / float(vbb.sum()),
                                  "n_papers": len(P)}
        rows.append(dict(table="dispersion", scenario=sc, value=ss / float(v0.sum()), lo=np.nan, hi=np.nan,
                         note="sum (N-lambda)^2 / sum V0 (Poisson-binomial)"))
        rows.append(dict(table="dispersion", scenario=sc, value=ss / float(vbb.sum()), lo=np.nan, hi=np.nan,
                         note="sum (N-lambda)^2 / sum V (beta-binomial, Cauchy-Schwarz)"))
        # rules on the 299 papers + MC under the fitted beta-binomial model
        rng = np.random.default_rng(args.seed)
        cnt = P[[f"n_{s}" for s in A]].values
        for alpha in ALPHAS:
            cache = {}
            ks = {r: [] for r in ("R1_CI", "R2_betaq", "R3_cantelli")}
            for c in map(tuple, cnt):
                if c not in cache:
                    cache[c] = rules_for(c, up, rho_up, alpha)[0]
                for r in ks:
                    ks[r].append(cache[c][r])
            for r in ks:
                kk = np.array(ks[r])
                rej = (P.N_A.values >= kk) & (P.n_A.values > 0)
                k_, n_ = int(rej.sum()), len(P)
                lo, hi = tt.wilson(k_, n_)
                mc = []
                for sd in range(args.seed, args.seed + 5):
                    g = np.random.default_rng(sd)
                    idx = g.integers(len(P), size=args.mc)
                    N = np.zeros(args.mc, dtype=int)
                    for j, s in enumerate(A):
                        n = cnt[idx, j]
                        cc = 1 / max(rho[s], 1e-6) - 1
                        Ui = g.beta(max(mu[s], 1e-9) * cc, max(1 - mu[s], 1e-9) * cc, size=args.mc)
                        N += g.binomial(n, Ui)
                    mc.append(float(((N >= kk[idx]) & (cnt[idx].sum(axis=1) > 0)).mean()))
                rows.append(dict(table="rule_check", scenario=sc, alpha=alpha, rule=r, k_rejected=k_, n_papers=n_,
                                 value=k_ / n_, lo=lo, hi=hi, mc_mean=float(np.mean(mc)), mc_sd=float(np.std(mc)),
                                 safe_obs=bool(lo <= alpha), safe_mc=bool(np.mean(mc) <= alpha)))
                nums[sc][f"{r}_a{alpha}"] = {"rejected": k_, "n": n_, "share": k_ / n_, "wilson": [lo, hi],
                                             "mc_mean": float(np.mean(mc))}
        # 5 typical papers
        qs = [0.1, 0.25, 0.5, 0.75, 0.9]
        Pa = P[P.n_A > 0].sort_values(["n_A"]).reset_index()
        for qv in qs:
            r_ = Pa.iloc[min(int(qv * (len(Pa) - 1)), len(Pa) - 1)]
            c = tuple(int(r_[f"n_{s}"]) for s in A)
            for alpha in ALPHAS:
                kr, q = rules_for(c, up, rho_up, alpha)
                for rule, kv in kr.items():
                    rows.append(dict(table="k_typical", scenario=sc, quantile=qv, paper_id=r_.paper_id, n_J=c[0],
                                     n_C=c[1], n_P=c[2], n_A=sum(c), N_A_obs=int(r_.N_A), alpha=alpha, rule=rule,
                                     value=kv))
    # 5. identifier scenario
    sf = pd.read_csv(RES / "p1_screen_fp.csv", dtype=str, keep_default_na=False)
    # P3 correction (hostile read 24-10): the rate of a screen on references that PRINT identifiers is the union FP of
    # the DOI-printing style with identifiers kept (identifier route first, title cascade as fallback). P2 used the
    # IEEEtran strip cell, which has no printed identifier (backup %TEMP%/p2_theory_final.py.bak_20261024_uid).
    c = sf[(sf.subset == "certified-real") & (sf.source == "render") & (sf.tier == "all") & (sf["style"] == "IEEEtran_doi")
           & (sf.variant == "orig") & (sf.parser == "grobid") & (sf.backend == "union")].iloc[0]
    u_id, u_id_up = float(c.fp), float(c.ci_hi)
    up_id = {s: u_id_up for s in A}
    rho_full_up = {s: bb["full"]["tiers"][s]["rho_boot95"][1] for s in A}
    nums["identifier_scenario"] = {"u_id": u_id, "u_id_upper": u_id_up, "k": int(c.k_flagged), "n": int(c.n_refs),
                                   "source": "certified-real, render, union, GROBID, IEEEtran-DOI orig"}
    typ = [r for r in rows if r.get("table") == "k_typical" and r["scenario"] == "full" and r["rule"] == "R1_CI"
           and r["alpha"] == 0.05]
    for r_ in typ:
        cnt = (r_["n_J"], r_["n_C"], r_["n_P"])
        for alpha in ALPHAS:
            kr, _ = rules_for(cnt, up_id, rho_full_up, alpha)
            for rule, kv in kr.items():
                rows.append(dict(table="k_identifier", scenario="identifier", quantile=r_["quantile"], n_A=sum(cnt),
                                 alpha=alpha, rule=rule, value=kv))
        p2_pt = tt.pb_tail(cnt, [u_id] * 3, 2)
        p2_up = tt.pb_tail(cnt, [u_id_up] * 3, 2)
        lam = sum(cnt) * u_id_up
        v = sum(math.sqrt(var_bb(n, u_id_up, rho_full_up[s])) for n, s in zip(cnt, A)) ** 2
        cant = v / (v + (2 - lam) ** 2) if 2 > lam else 1.0
        rows.append(dict(table="p_two_flags_identifier", scenario="identifier", quantile=r_["quantile"],
                         n_A=sum(cnt), value=p2_pt, lo=np.nan, hi=p2_up,
                         note=f"P(N>=2): PoiBin at u_id (value) / at u_id upper (hi); Cantelli bound {cant:.4f}"))
        nums["identifier_scenario"][f"nA{sum(cnt)}"] = {"p_two_flags": p2_pt, "p_two_flags_upper": p2_up,
                                                        "cantelli_two_flags": cant}
    f3 = RES / "p3_recheck_stats.json"  # post-hoc recheck (p3_recheck.py stats), carried into numbers.json/.tex
    if f3.exists():
        nums["recheck_posthoc"] = {k.removeprefix("recheck_posthoc_"): v for k, v in
                                   json.loads(f3.read_text(encoding="utf-8"))["flat"].items()}
    out = pd.DataFrame(rows)
    out["seed"], out["interim"] = args.seed, False
    out.to_csv(RES / "p2_theory_final.csv", index=False)
    (RES / "numbers.json").write_text(json.dumps(nums, indent=1, default=float), encoding="utf-8")
    write_tex(nums)
    rc = out[out.table == "rule_check"][["scenario", "alpha", "rule", "k_rejected", "n_papers", "value", "lo", "hi",
                                         "mc_mean"]]
    print(rc.round(4).to_string())
    kt = out[out.table == "k_typical"].pivot_table(index=["scenario", "quantile", "n_A"], columns=["alpha", "rule"],
                                                    values="value")
    print(kt.to_string())
    for sc in SCEN:
        print(sc, json.dumps(nums[sc]["dispersion"]))
    ki = out[out.table == "k_identifier"].pivot_table(index=["n_A"], columns=["alpha", "rule"], values="value")
    print("identifier scenario u =", nums["identifier_scenario"]["u_id"], "upper", nums["identifier_scenario"]["u_id_upper"])
    print(ki.to_string())
    print(out[out.table == "p_two_flags_identifier"][["n_A", "value", "hi", "note"]].to_string())


def write_tex(nums):
    def tag(s):
        return "".join(w.capitalize() for w in s.replace("_", " ").replace(".", " ").split())

    def flat(d, pre=""):
        for k, v in d.items():
            name = pre + tag(str(k).replace("%", "pc").replace("0.", "p"))
            if isinstance(v, dict):
                yield from flat(v, name)
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    if isinstance(x, (int, float)):
                        yield name + "LoHi"[2 * i:2 * i + 2], x
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                yield name, v
    lines = ["% generated by code/p2_theory_final.py from results/numbers.json; do not edit"]
    for name, v in flat(nums):
        words = "Zero One Two Three Four Five Six Seven Eight Nine".split()
        name = "".join(words[int(ch)] if ch.isdigit() else ch for ch in name if ch.isalnum())
        val = f"{v:.4g}" if isinstance(v, float) else str(v)
        lines.append(f"\\newcommand{{\\n{name}}}{{{val}}}")
    seen, out = set(), []
    for ln in lines:
        key = ln.split("}")[0]
        if key not in seen:
            seen.add(key)
            out.append(ln)
    (RES / "numbers.tex").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
