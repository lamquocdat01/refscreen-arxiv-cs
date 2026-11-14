#!/usr/bin/env python3
"""Topic 43 / P3G (POSTHOC_NOTE_P3G.md, P1 and P1-rule; POST HOC): split by reference branch, offline.

Branch = ref_source of the completed ground truth: bib (the authors' .bib) or bbl (a .bbl item parsed by GROBID).
For each branch and period, full cascade:
  papers, N, U, u_A with a paper bootstrap 95% CI (B = 1000, seed 42); F, R, F/U (deep search, academic);
  shares of papers with >= k unresolved academic references (k = 1..5, Wilson); k_emp at alpha 0.05/0.01;
  dispersion ratio sum (N_A - lambda)^2 / sum V0 with the branch's own tier rates (Poisson-binomial, as p2_theory_final).
A paper's branch is the branch of its references ("mixed" if both occur).
Also: the .bbl unresolved academic references of 2019-21 lacking surnames or a year in the deep-search reference.
P1-rule (fixed in the note before this ran): .bib is the main branch if |u_A(bib) - u_A(bbl)| > 0.5 points or the
dispersion ratios differ by more than 20% of the .bib ratio (2019-21); otherwise the pooled numbers stay main.
Outputs: results/p3g_branch_split.csv (long), results/p3g_branch_split.json
Usage: python code/p3g_branch_split.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3f_bounds as fb  # noqa: E402
from ground_truth import wilson  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
A = ["J", "C", "P"]
B, SEED = 1000, 42


def base():
    x = fb.rd(RES / "p3f_deep_search.csv")
    d = fb.attach(fb.frame(), x)
    br = d.groupby("arxiv_id").ref_source.agg(lambda s: s.iloc[0] if s.nunique() == 1 else "mixed")
    d["paper_branch"] = d.arxiv_id.map(br)
    return d


def ua_ci(g):
    a = g[g.tier.isin(A)].assign(n1=1).groupby("arxiv_id")[["u", "n1"]].sum().values
    rng = np.random.default_rng(SEED)
    s = a[rng.integers(0, len(a), (B, len(a)))].sum(1)
    return np.quantile(s[:, 0] / s[:, 1], [.025, .975]).tolist()


def paper_counts(g, col="u"):
    """per paper: N_A (flags among academic references), n_s per tier; every paper of g (resolved/unresolved refs)."""
    papers = g.arxiv_id.unique()
    ac = g[g.tier.isin(A)]
    P = pd.DataFrame(index=papers)
    for s in A:
        t = ac[ac.tier == s].groupby("arxiv_id")
        P[f"n_{s}"] = t.size().reindex(papers).fillna(0).astype(int)
        P[f"k_{s}"] = t[col].sum().reindex(papers).fillna(0).astype(int)
    P["N_A"] = P[[f"k_{s}" for s in A]].sum(1)
    P["n_A"] = P[[f"n_{s}" for s in A]].sum(1)
    return P


def shares(P, kmax=5):
    n = len(P)
    out = {}
    for k in range(1, kmax + 1):
        c = int((P.N_A >= k).sum())
        out[str(k)] = dict(papers=c, n=n, share=c / n if n else None, wilson=list(wilson(c, n)) if n else None)
    return out


def k_emp(P):
    n, N = len(P), P.N_A.values
    res = {}
    for a in (0.05, 0.01):
        kk = next((k for k in range(1, 60) if (N >= k).sum() / n <= a), None) if n else None
        kw = next((k for k in range(1, 60) if wilson(int((N >= k).sum()), n)[1] <= a), None) if n else None
        res[f"a{a}"] = dict(k_emp=kk, share_at_k=((N >= kk).sum() / n) if kk else None,
                            wilson_at_k=list(wilson(int((N >= kk).sum()), n)) if kk else None, k_wilson_upper=kw)
    return res


def dispersion(P):
    u = {s: P[f"k_{s}"].sum() / P[f"n_{s}"].sum() if P[f"n_{s}"].sum() else 0.0 for s in A}
    lam = sum(P[f"n_{s}"] * u[s] for s in A)
    v0 = sum(P[f"n_{s}"] * u[s] * (1 - u[s]) for s in A)
    ss = float(((P.N_A - lam) ** 2).sum())
    return dict(ratio=ss / float(v0.sum()) if v0.sum() else None, sum_sq_dev=ss, sum_v0=float(v0.sum()), u_s=u)


def by_backend(g):
    """u_A under the cumulative backend sets (P1-rule: the headline, Crossref-only to full cascade, by branch)."""
    import p1_theory_tables as tt
    ac = g[g.tier.isin(A)]
    out = {}
    for name, bset in (("crossref", ["crossref"]), ("arxiv", ["crossref", "arxiv"]), ("dblp", ["crossref", "arxiv", "dblp"]),
                       ("openalex", ["crossref", "arxiv", "dblp", "openalex"])):
        x = ((ac.u == 1).values | ~tt.resolved_by(ac.backends_hit, bset)).astype(int)
        h = ac.assign(u=x)
        out[name] = dict(u_A=float(x.mean()) if len(x) else None, u_A_ci=ua_ci(h) if len(x) else None)
    return out


def cell(d, per, branch):
    g = d[d.period == per]
    if branch != "pooled":
        g = g[g.ref_source == branch]
    ac = g[g.tier.isin(A)]
    N, U = len(ac), int(ac.u.sum())
    F, R = int(ac.f.sum()), int(ac.r.sum())
    out = dict(period=per, branch=branch, refs_all=len(g), papers_with_refs=int(g.arxiv_id.nunique()), N=N, U=U,
               u_A=U / N if N else None, u_A_ci=ua_ci(g) if N else None, F=F, R=R, F_over_U=F / U if U else None,
               R_not_found=int(ac.r_notfound.sum()), R_unanswered=int(ac.r_unans.sum()))
    # paper-level analyses on papers of this branch (paper_branch); pooled = all papers
    gp = d[d.period == per] if branch == "pooled" else d[(d.period == per) & (d.paper_branch == branch)]
    P = paper_counts(gp)
    out.update(paper_level_papers=len(P), flags=shares(P), k_emp=k_emp(P), dispersion=dispersion(P), by_backend=by_backend(g))
    return out


def bbl_missing():
    import p3f_deep_search as ds
    d = ds.load_gt()
    rows = ds.set_rows(d, "acad1921")
    rows = rows[rows.ref_source == "bbl"].to_dict("records")
    refs = [ds.make_ref(r, "acad1921") for r in rows]
    st = fb.rd(RES / "p3f_deep_search.csv").set_index("ref_id").state
    no_s = [r for r in refs if not r["surnames"]]
    no_y = [r for r in refs if r["year"] is None]
    either = [r for r in refs if not r["surnames"] or r["year"] is None]
    return dict(unit="distinct (paper, key)", n_bbl_unresolved_academic=len(refs), no_surnames=len(no_s), no_year=len(no_y),
                no_surnames_or_year=len(either),
                state_of_those=pd.Series([st.get(r["ref_id"], "") for r in either]).value_counts().to_dict(),
                state_all_bbl=pd.Series([st.get(r["ref_id"], "") for r in refs]).value_counts().to_dict(),
                n_bib_unresolved_academic=int((ds.set_rows(d, "acad1921").ref_source == "bib").sum()))


def main():
    d = base()
    out = {"label": "POST HOC (POSTHOC_NOTE_P3G.md P1); offline; full cascade; unit = rows of the ground truth",
           "seed": SEED, "B": B, "paper_branch_counts": {}}
    rows = []
    for per in ("2019-21", "2024-26"):
        out["paper_branch_counts"][per] = d[d.period == per].groupby("arxiv_id").paper_branch.first().value_counts().to_dict()
        for br in ("bib", "bbl", "pooled"):
            c = cell(d, per, br)
            out[f"{per}|{br}"] = c
            rows.append({k: v for k, v in c.items() if not isinstance(v, (dict, list))} |
                        {"u_A_lo": c["u_A_ci"][0] if c["u_A_ci"] else None, "u_A_hi": c["u_A_ci"][1] if c["u_A_ci"] else None,
                         "ge1": c["flags"]["1"]["share"], "ge2": c["flags"]["2"]["share"], "ge3": c["flags"]["3"]["share"],
                         "k_emp_05": c["k_emp"]["a0.05"]["k_emp"], "k_emp_01": c["k_emp"]["a0.01"]["k_emp"],
                         "dispersion": c["dispersion"]["ratio"]})
    out["bbl_missing_author_year"] = bbl_missing()
    b, l = out["2019-21|bib"], out["2019-21|bbl"]
    du = abs(b["u_A"] - l["u_A"]) * 100
    dr = abs(b["dispersion"]["ratio"] - l["dispersion"]["ratio"]) / b["dispersion"]["ratio"]
    main_branch = "bib" if (du > 0.5 or dr > 0.20) else "pooled"
    out["rule"] = dict(diff_uA_points=du, rel_diff_dispersion=dr, threshold_points=0.5, threshold_rel=0.20, main=main_branch)
    pd.DataFrame(rows).to_csv(RES / "p3g_branch_split.csv", index=False)
    (RES / "p3g_branch_split.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps(out["rule"], indent=1))
    print(pd.DataFrame(rows).to_string())
    print(json.dumps(out["bbl_missing_author_year"], indent=1))
    print(out["paper_branch_counts"])


if __name__ == "__main__":
    main()
