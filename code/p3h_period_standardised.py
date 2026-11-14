#!/usr/bin/env python3
"""Topic 43 / P3H (closure check N4 and N7; CP3e questions 4 and 1; POST HOC, offline).

(1) Two periods by branch: U/N and R/N of academic references (J, C, P), full cascade, for each branch (.bib, .bbl)
    and period; the within-branch differences (2024-26 minus 2019-21); and the 2024-26 rate directly standardised to
    the 2019-21 branch mix (share of academic references by branch in 2019-21), minus the 2019-21 pooled rate.
    95% CIs by paper bootstrap within period (B = 1000, seed 42); the 2019-21 weights are recomputed in every draw.
(2) Dispersion ratio by branch and period with a paper-bootstrap 95% CI (B = 1000, seed 42), as p3g_branch_split
    (sum (N_A - lambda)^2 / sum V0, the branch's own tier rates), plus the pooled ratio.
(3) Category (cs.*) mix of papers by branch, 2019-21 (N6).
Outputs: results/p3h_period_standardised.{csv,json}
Usage: python code/p3h_period_standardised.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3g_branch_split as bs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
A = ["J", "C", "P"]
B, SEED = 1000, 42
PER = ("2019-21", "2024-26")
BR = ("bib", "bbl")


def paper_table(d, per):
    """per paper of the period: branch, N (academic refs), U, R."""
    g = d[(d.period == per) & d.tier.isin(A)]
    t = g.assign(n1=1).groupby("arxiv_id").agg(n=("n1", "sum"), u=("u", "sum"), r=("r", "sum"),
                                                 br=("paper_branch", "first"))
    return t


def rates(t):
    out = {}
    for b in BR:
        s = t[t.br == b]
        n = s.n.sum()
        out[b] = dict(N=int(n), U=int(s.u.sum()), R=int(s.r.sum()), uN=s.u.sum() / n, rN=s.r.sum() / n)
    n = t.n.sum()
    out["pooled"] = dict(N=int(n), U=int(t.u.sum()), R=int(t.r.sum()), uN=t.u.sum() / n, rN=t.r.sum() / n)
    out["w_bbl"] = out["bbl"]["N"] / n
    return out


def stats(t0, t1):
    r0, r1 = rates(t0), rates(t1)
    w = {b: r0[b]["N"] / r0["pooled"]["N"] for b in BR}
    s = {}
    for m in ("uN", "rN"):
        for b in BR:
            s[f"{m}_{b}_diff"] = r1[b][m] - r0[b][m]
        s[f"{m}_pooled_diff"] = r1["pooled"][m] - r0["pooled"][m]
        s[f"{m}_std_2024"] = sum(w[b] * r1[b][m] for b in BR)
        s[f"{m}_std_diff"] = s[f"{m}_std_2024"] - r0["pooled"][m]
    return r0, r1, s


def boot(t0, t1):
    rng = np.random.default_rng(SEED)
    keys = None
    acc = []
    for _ in range(B):
        b0 = t0.iloc[rng.integers(0, len(t0), len(t0))]
        b1 = t1.iloc[rng.integers(0, len(t1), len(t1))]
        _, _, s = stats(b0, b1)
        keys = keys or list(s)
        acc.append([s[k] for k in keys])
    a = np.array(acc)
    return {k: np.quantile(a[:, i], [.025, .975]).tolist() for i, k in enumerate(keys)}


def dispersion_ci(d, per, branch):
    g = d[d.period == per]
    if branch != "pooled":
        g = g[g.paper_branch == branch]
    P = bs.paper_counts(g)
    point = bs.dispersion(P)["ratio"]
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(B):
        Pb = P.iloc[rng.integers(0, len(P), len(P))]
        vals.append(bs.dispersion(Pb.reset_index(drop=True))["ratio"])
    vals = np.array([v for v in vals if v is not None and np.isfinite(v)])
    return dict(papers=len(P), point=point, ci=np.quantile(vals, [.025, .975]).tolist())


def main():
    d = bs.base()
    t0, t1 = paper_table(d, PER[0]), paper_table(d, PER[1])
    mixed = {p: int((paper_table(d, p).br == "mixed").sum()) for p in PER}
    r0, r1, s = stats(t0, t1)
    ci = boot(t0, t1)
    out = dict(note="POST HOC (closure check N4); academic J/C/P, full cascade; R = r of the deep search frame "
                    "(not found + unanswered); paper bootstrap B=1000 seed 42; std = 2024-26 rates weighted by the "
                    "2019-21 branch mix", mixed_papers=mixed, rates={PER[0]: r0, PER[1]: r1},
               diffs={k: dict(point=v, ci=ci[k]) for k, v in s.items()})
    # dispersion (N7): the ratio uses the branch's own tier rates (bs.dispersion)
    out["dispersion"] = {f"{p}|{b}": dispersion_ci(d, p, b) for p in PER for b in ("pooled",) + BR}
    # category mix by branch (N6), 2019-21 papers
    g = d[d.period == PER[0]].groupby("arxiv_id").agg(field=("field", "first"), br=("paper_branch", "first"))
    out["field_mix_2019_21"] = {b: g[g.br == b].field.value_counts().to_dict() for b in BR}
    rows = []
    for k, v in out["diffs"].items():
        rows.append(dict(kind="diff", key=k, point=v["point"], lo=v["ci"][0], hi=v["ci"][1]))
    for k, v in out["dispersion"].items():
        rows.append(dict(kind="dispersion", key=k, point=v["point"], lo=v["ci"][0], hi=v["ci"][1]))
    pd.DataFrame(rows).to_csv(RES / "p3h_period_standardised.csv", index=False)
    (RES / "p3h_period_standardised.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    for r in rows:
        print(f"{r['kind']:10s} {r['key']:22s} {r['point']:.4f} [{r['lo']:.4f}, {r['hi']:.4f}]")
    print("mixed papers:", mixed, "| field mix:", out["field_mix_2019_21"])


if __name__ == "__main__":
    main()
