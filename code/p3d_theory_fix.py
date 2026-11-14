#!/usr/bin/env python3
"""Topic 43 / P3D: recompute the theory numbers affected by the erratum (P3D/ERRATUM_43.md, items 1-6; THEORY_43_v4.md).

Same inputs as p2_theory_final.py; no data, hypothesis or verdict changes. This runs after p2_theory_final.py, whose
csv keeps the earlier values as the "before" record, and patches results/numbers.json only where a value changes.

  R2  q_s = sup over mu <= u+_s, rho <= rho+_s of the (1 - alpha/(2|A|)) Beta quantile (mean mu, ICC rho).
      At fixed rho the quantile increases in mu (likelihood-ratio order of Beta(a, b) with a + b fixed), so the sup sits
      at mu = u+_s and is taken over rho in (0, rho+_s] (grid + bounded refinement). A direct box grid checks this.
  R3  V+_i with max over u in [u-_s, u+_s] of u(1 - u) in place of u+_s(1 - u+_s) (1/4 if the interval contains 1/2).
  k*_A(n = 150) with u+ (pooled, and per tier at the corpus mix), next to the earlier point-estimate value.
  Identifier tables: union screen (identifier route then title cascade) and the identifier-only pair, the one that
      carries the TPR >= 1 - eps guarantee of Prop 3.
  One-sided exact binomial p of the R1 cells against nominal alpha.
Backend sets: crossref_only, plus_dblp, full. Monte Carlo as in p2_theory_final.py: 5 seeds x 20,000 papers.

Outputs: results/p3d_theory_fix.csv (long), results/p3d_theory_fix.json; patches results/numbers.json and numbers.tex.
Usage: python p3d_theory_fix.py --seed 42 [--mc 20000]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import binom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_theory_tables as tt  # noqa: E402
import p2_theory_final as p2  # noqa: E402
from ground_truth import ROOT  # noqa: E402

A = ["J", "C", "P"]
ALPHAS = [0.05, 0.01]
SCEN = {"crossref_only": ("crossref", ["crossref"]), "plus_dblp": ("dblp", ["crossref", "arxiv", "dblp"]), "full": ("s2", None)}
RES = ROOT / "results"
RULES = ("R1_CI", "R2_betaq", "R3_cantelli")


def q_sup(u_up, rho_up, level):
    """sup over rho in (0, rho_up] of the Beta quantile at mean u_up; returns (q, argmax rho). rho -> 0 gives u_up."""
    if rho_up <= 1e-6:
        return float(u_up), 0.0
    grid = np.geomspace(1e-5, rho_up, 400)
    vals = np.array([p2.beta_q(u_up, r, level) for r in grid])
    i = int(np.argmax(vals))
    best_q, best_r = float(vals[i]), float(grid[i])
    if 0 < i < len(grid) - 1:  # interior peak: refine
        res = minimize_scalar(lambda r: -p2.beta_q(u_up, r, level), bounds=(grid[i - 1], grid[i + 1]), method="bounded",
                              options={"xatol": 1e-7})
        if -res.fun > best_q:
            best_q, best_r = float(-res.fun), float(res.x)
    if u_up > best_q:
        return float(u_up), 0.0
    return best_q, best_r


def box_check(u_up, rho_up, level, q):
    """Direct grid over the whole box mu <= u_up, rho <= rho_up: returns its max, which must not exceed q."""
    best = 0.0
    for mu in np.linspace(u_up / 40, u_up, 40):
        for r in np.geomspace(1e-5, max(rho_up, 1e-5), 40):
            best = max(best, p2.beta_q(mu, r, level))
    return best


def max_uvar(lo, up):
    return 0.25 if lo <= 0.5 <= up else max(lo * (1 - lo), up * (1 - up))


def rules_v4(counts, lo, up, rho_up, alpha):
    r1 = tt.k_star(counts, [up[s] for s in A], alpha)
    level = 1 - alpha / (2 * len(A))
    q = {s: q_sup(up[s], rho_up[s], level)[0] for s in A}
    r2 = tt.k_star(counts, [q[s] for s in A], alpha / 2)
    lam = sum(n * up[s] for n, s in zip(counts, A))
    v = sum(math.sqrt(n * max_uvar(lo[s], up[s]) * (1 + (n - 1) * rho_up[s])) for n, s in zip(counts, A)) ** 2
    r3 = math.ceil(lam + math.sqrt(v * (1 - alpha) / alpha)) if v > 0 else 1
    return {"R1_CI": r1, "R2_betaq": r2, "R3_cantelli": max(r3, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--mc", type=int, default=20000)
    args = ap.parse_args()
    gt = pd.read_csv(RES / "p1_groundtruth.csv", dtype=str, keep_default_na=False)
    ev = gt[(gt.period == "2019-21") & gt.def1_status.isin(["resolved", "unresolved"])].copy()
    unres = (ev.def1_status == "unresolved").values
    bb = json.loads((RES / "p1_h5_betabinom.json").read_text(encoding="utf-8"))["scenarios"]
    rows, out = [], {"seed": args.seed, "mc_papers": args.mc, "mc_seeds": 5, "scenarios": {}}
    patched = {}
    for sc, (col, backends) in SCEN.items():
        U = tt.rates_from_backend_table("2019-21", col)
        x = unres if backends is None else (unres | ~tt.resolved_by(ev.backends_hit, backends))
        ev["x"] = x.astype(int)
        lo = {s: U[s]["paper_bootstrap95"][0] for s in A}
        up = {s: U[s]["paper_bootstrap95"][1] for s in A}
        tiers = bb[sc]["tiers"]
        rho = {s: tiers[s]["rho_icc"] for s in A}
        rho_up = {s: tiers[s]["rho_boot95"][1] for s in A}
        mu = {s: tiers[s]["mu"] for s in A}
        pa = ev[ev.tier.isin(A)].groupby(["paper_id", "tier"]).agg(n=("x", "size"), k=("x", "sum")).unstack(fill_value=0)
        P = pd.DataFrame({f"n_{s}": pa["n"].get(s, 0) for s in A}).fillna(0).astype(int)
        P["N_A"] = pa["k"].sum(axis=1).astype(int)
        P = P.reindex(ev.paper_id.unique(), fill_value=0)
        P["n_A"] = P[[f"n_{s}" for s in A]].sum(axis=1)
        cnt = P[[f"n_{s}" for s in A]].values
        for s in A:
            old_var, new_var = up[s] * (1 - up[s]), max_uvar(lo[s], up[s])
            rows.append(dict(table="var_bound", scenario=sc, tier=s, u_lo=lo[s], u_up=up[s], rho_up=rho_up[s],
                             value=new_var, old=old_var))
            for alpha in ALPHAS:
                level = 1 - alpha / (2 * len(A))
                q, arg = q_sup(up[s], rho_up[s], level)
                rows.append(dict(table="q_sup", scenario=sc, tier=s, alpha=alpha, u_up=up[s], rho_up=rho_up[s],
                                 value=q, old=p2.beta_q(up[s], rho_up[s], level), rho_argmax=arg,
                                 box_max=box_check(up[s], rho_up[s], level, q)))
        scen_out = {"u_s": {s: U[s]["u"] for s in A}, "u_s_lower": lo, "u_s_upper": up, "rho_s_upper": rho_up}
        for alpha in ALPHAS:
            cache, ks = {}, {r: [] for r in RULES}
            for c in map(tuple, cnt):
                if c not in cache:
                    cache[c] = rules_v4(c, lo, up, rho_up, alpha)
                for r in ks:
                    ks[r].append(cache[c][r])
            for r in ks:
                kk = np.array(ks[r])
                rej = (P.N_A.values >= kk) & (P.n_A.values > 0)
                k_, n_ = int(rej.sum()), len(P)
                wl, wh = tt.wilson(k_, n_)
                mc = []
                for sd in range(args.seed, args.seed + 5):  # same stream as p2_theory_final.py
                    g = np.random.default_rng(sd)
                    idx = g.integers(len(P), size=args.mc)
                    N = np.zeros(args.mc, dtype=int)
                    for j, s in enumerate(A):
                        cc = 1 / max(rho[s], 1e-6) - 1
                        Ui = g.beta(max(mu[s], 1e-9) * cc, max(1 - mu[s], 1e-9) * cc, size=args.mc)
                        N += g.binomial(cnt[idx, j], Ui)
                    mc.append(float(((N >= kk[idx]) & (cnt[idx].sum(axis=1) > 0)).mean()))
                p_one = float(binom.sf(k_ - 1, n_, alpha)) if k_ > 0 else 1.0
                rows.append(dict(table="rule_check", scenario=sc, alpha=alpha, rule=r, k_rejected=k_, n_papers=n_,
                                 value=k_ / n_, lo=wl, hi=wh, mc_mean=float(np.mean(mc)), mc_sd=float(np.std(mc)),
                                 safe_obs=bool(wl <= alpha), safe_mc=bool(np.mean(mc) <= alpha), p_one_sided=p_one))
                rec = {"rejected": k_, "n": n_, "share": k_ / n_, "wilson": [wl, wh], "mc_mean": float(np.mean(mc))}
                scen_out[f"{r}_a{alpha}"] = {**rec, "p_one_sided": p_one}
                patched[(sc, f"{r}_a{alpha}")] = rec
        # 5 typical papers, same selection as p2_theory_final.py
        Pa = P[P.n_A > 0].sort_values(["n_A"]).reset_index()
        for qv in (0.1, 0.25, 0.5, 0.75, 0.9):
            r_ = Pa.iloc[min(int(qv * (len(Pa) - 1)), len(Pa) - 1)]
            c = tuple(int(r_[f"n_{s}"]) for s in A)
            for alpha in ALPHAS:
                for rule, kv in rules_v4(c, lo, up, rho_up, alpha).items():
                    rows.append(dict(table="k_typical", scenario=sc, quantile=qv, paper_id=r_.paper_id, n_J=c[0], n_C=c[1],
                                     n_P=c[2], n_A=sum(c), N_A_obs=int(r_.N_A), alpha=alpha, rule=rule, value=kv))
        # k*_A(n = 150): point estimate (the earlier column, not alpha-safe), pooled u+, per-tier u+ at the corpus mix
        tot = np.maximum(cnt.sum(axis=0), 0)
        w = tot / tot.sum()
        ns = [int(v) for v in np.floor(150 * w)]
        for i in np.argsort(-(150 * w - np.floor(150 * w)))[:150 - sum(ns)]:
            ns[i] += 1
        uA, (_, hiA) = U["A"]["u"], U["A"]["paper_bootstrap95"]
        scen_out["kstar_n150"] = {"mix_J_C_P": ns}
        for alpha in ALPHAS:
            vals = dict(point_pooled=tt.k_star([150], [uA], alpha), upper_pooled=tt.k_star([150], [hiA], alpha),
                        upper_tiered=tt.k_star(ns, [up[s] for s in A], alpha))
            for kind, v in vals.items():
                rows.append(dict(table="kstar_n150", scenario=sc, alpha=alpha, rule=kind, n_J=ns[0], n_C=ns[1], n_P=ns[2],
                                 n_A=150, value=v))
            scen_out["kstar_n150"][f"a{alpha}"] = vals
        out["scenarios"][sc] = scen_out
    # identifier tables: union screen and the identifier-only pair
    sf = pd.read_csv(RES / "p1_screen_fp.csv", dtype=str, keep_default_na=False)
    rho_full_up = {s: bb["full"]["tiers"][s]["rho_boot95"][1] for s in A}
    typ = [r for r in rows if r.get("table") == "k_typical" and r["scenario"] == "full" and r["rule"] == "R1_CI" and r["alpha"] == 0.05]
    out["identifier"] = {}
    for name, backend in (("identifier", "union"), ("identifier_only", "idonly")):
        c = sf[(sf.subset == "certified-real") & (sf.source == "render") & (sf.tier == "all") & (sf["style"] == "IEEEtran_doi")
               & (sf.variant == "orig") & (sf.parser == "grobid") & (sf.backend == backend)].iloc[0]
        u_pt, u_lo, u_hi = float(c.fp), float(c.ci_lo), float(c.ci_hi)
        lo_id, up_id = {s: u_lo for s in A}, {s: u_hi for s in A}
        out["identifier"][name] = {"u": u_pt, "u_lower": u_lo, "u_upper": u_hi, "k": int(c.k_flagged), "n": int(c.n_refs)}
        for s in A:
            for alpha in ALPHAS:
                level = 1 - alpha / (2 * len(A))
                q, arg = q_sup(u_hi, rho_full_up[s], level)
                rows.append(dict(table="q_sup", scenario=name, tier=s, alpha=alpha, u_up=u_hi, rho_up=rho_full_up[s], value=q,
                                 old=p2.beta_q(u_hi, rho_full_up[s], level), rho_argmax=arg,
                                 box_max=box_check(u_hi, rho_full_up[s], level, q)))
        for r_ in typ:
            cn = (r_["n_J"], r_["n_C"], r_["n_P"])
            for alpha in ALPHAS:
                for rule, kv in rules_v4(cn, lo_id, up_id, rho_full_up, alpha).items():
                    rows.append(dict(table="k_identifier", scenario=name, quantile=r_["quantile"], n_A=sum(cn), n_J=cn[0],
                                     n_C=cn[1], n_P=cn[2], alpha=alpha, rule=rule, value=kv))
            p2_pt, p2_up = tt.pb_tail(cn, [u_pt] * 3, 2), tt.pb_tail(cn, [u_hi] * 3, 2)
            lam = sum(cn) * u_hi
            v = sum(math.sqrt(n * max_uvar(u_lo, u_hi) * (1 + (n - 1) * rho_full_up[s])) for n, s in zip(cn, A)) ** 2
            cant = v / (v + (2 - lam) ** 2) if 2 > lam else 1.0
            rows.append(dict(table="p_two_flags_identifier", scenario=name, quantile=r_["quantile"], n_A=sum(cn), value=p2_pt,
                             hi=p2_up, cantelli_k2=cant))
    frame = pd.DataFrame(rows)
    frame["seed"] = args.seed
    frame.to_csv(RES / "p3d_theory_fix.csv", index=False)
    q_t = frame[frame.table == "q_sup"]
    out["q_sup_box_check_max_excess"] = float((q_t.box_max - q_t.value).max())
    out["tables"] = {
        "k_typical": pivot(frame, "k_typical"),
        "k_identifier": pivot(frame, "k_identifier"),
    }
    (RES / "p3d_theory_fix.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    # numbers.json: change only the keys whose definition changed; add the new block at the end
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    changed = []
    for (sc, key), rec in patched.items():
        if sc in nums and key in nums[sc] and nums[sc][key] != rec:
            changed.append((sc, key))
            nums[sc][key] = rec
    nums["p3d_erratum"] = {
        "plus_dblp": {k: v for k, v in out["scenarios"]["plus_dblp"].items()},
        "kstar_n150": {sc: out["scenarios"][sc]["kstar_n150"] for sc in SCEN},
        "r1_p_one_sided": {sc: {f"a{a}": out["scenarios"][sc][f"R1_CI_a{a}"]["p_one_sided"] for a in ALPHAS} for sc in SCEN},
        "identifier": out["identifier"],
        "q_sup_box_check_max_excess": out["q_sup_box_check_max_excess"],
    }
    (RES / "numbers.json").write_text(json.dumps(nums, indent=1, default=float), encoding="utf-8")
    p2.write_tex(nums)
    print("numbers.json keys changed in place:", changed)
    print(frame[frame.table == "rule_check"][["scenario", "alpha", "rule", "k_rejected", "value", "mc_mean", "p_one_sided"]].round(5).to_string())
    print(q_t[["scenario", "tier", "alpha", "u_up", "rho_up", "old", "value", "rho_argmax", "box_max"]].round(5).to_string())
    print(frame[frame.table == "var_bound"][["scenario", "tier", "u_lo", "u_up", "old", "value"]].round(5).to_string())
    print(frame[frame.table == "kstar_n150"][["scenario", "alpha", "rule", "n_J", "n_C", "n_P", "value"]].to_string())
    print(frame[frame.table == "p_two_flags_identifier"][["scenario", "n_A", "value", "hi", "cantelli_k2"]].to_string())


def pivot(frame, table):
    res = {}
    for _, r in frame[frame.table == table].iterrows():
        res.setdefault(r.scenario, {}).setdefault(str(int(r.n_A)), {}).setdefault(str(r.alpha), {})[r.rule.split("_")[0]] = int(r.value)
    return res


if __name__ == "__main__":
    main()
