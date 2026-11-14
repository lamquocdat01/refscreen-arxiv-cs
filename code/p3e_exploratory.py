#!/usr/bin/env python3
"""Topic 43 / P3E (PREREG_AMENDMENT_7 (d)): EXPLORATORY analyses, offline (no request), on the completed ground truth.

Run inside the p3e_recompute.py work copy (THS_DATASETS = its private data root, results/ = recomputed files); the
stored API answers are read from P3E_CACHE_ROOT (the real $THS_DATASETS/_derived/43: cache/ then cache_p3e/).
  d1 tau sweep: u_s at tau in {0.80, 0.85, 0.90, 0.95} for Crossref-only and the full cascade, 2019-21 and 2024-26,
     from the best candidate similarity per backend (ground-truth sim_* columns; for a backend not asked because an
     earlier one resolved, the stored answer if any). A reference with no known similarity >= tau and a backend of
     unknown similarity counts in an interval [lower = resolved, upper = unresolved]. False-match (resolution) rate of
     the generated items of results/p2_fake_items.csv per family at each tau on the same backend sets.
  d2 absent vs present-but-unmatched: J/C certified-real references with a DOI, unresolved by the Crossref title search:
     present-but-unmatched if the DOI resolved in Crossref (id_backend = crossref), absent otherwise; plus the S5 cases
     (D16, D31, D46, D48) and GZ023 (S6).
  d3 PDF-parsed screen on the 60 identifier-free render references (results/p2_manual_sample.csv, pass-1 exists): FP of
     the rendered-string screen (GROBID / anystyle parse; flag_union and flag_crossref of screen_p1/screen_refs.csv)
     next to the .bib-title screen on the same rows with the same backends (Crossref, arXiv, DBLP, S2).
  d4 Bonferroni: one-sided bounds at 1 - eta/m (eta = 0.05; m = 3 for R1, 6 for R2/R3): u_s from a paper bootstrap
     (B = 1000, seed 42), rho_s from a beta-binomial bootstrap (B = 200, seed 42; order statistic), rules R1-R3 re-derived
     (p3d_theory_fix.rules_v4) and checked on the 2019-21 corpus; 5 typical papers.
  d5 empirical thresholds: k_emp(alpha) = min k with share(N_A >= k) <= alpha, legitimate papers, 2019-21 (in sample)
     and 2024-26 (hold-out), all papers and n_A tertiles (2019-21 cut points), Crossref-only and full cascade; Wilson.
  d6 identifier thresholds at rho = 0 and rho = rho+ (Table 10 columns), union and identifier-only routes.
Outputs: results/p3e_exploratory.json, results/p3e_exploratory.csv (long)
Usage: python p3e_exploratory.py --seed 42
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
import p1_theory_tables as tt  # noqa: E402
import p3d_theory_fix as p3d  # noqa: E402
from ground_truth import DATA, ROOT, wilson  # noqa: E402
from p1_h5_betabinom import fit_bb  # noqa: E402

RES = ROOT / "results"
DER = DATA / "_derived" / "43"
CROOT = Path(os.environ.get("P3E_CACHE_ROOT", str(DER)))
CACHES = [CROOT / "cache", CROOT / "cache_p3e"]
TAUS = [0.80, 0.85, 0.90, 0.95]
BACK = ["crossref", "arxiv", "dblp", "openalex", "s2"]
A = ["J", "C", "P"]
ETA = 0.05


def stored(backend, url, params):
    key = hashlib.sha1((url + "?" + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    for c in CACHES:
        f = c / backend / f"{key}.json"
        if f.exists():
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                return d["status"], d["payload"]
            except (ValueError, KeyError, OSError):
                pass
    return None, None


def stored_sim(backend, title):
    """Best similarity from a stored answer; None when nothing is stored."""
    import feedparser
    if backend == "crossref":
        base = {"query.bibliographic": title[:500], "rows": 5, "mailto": rm.MAILTO}
        for sel in ("DOI,title,subtitle,issued", "DOI,title,subtitle,issued,author"):
            st, p = stored("crossref", "https://api.crossref.org/works", dict(base, select=sel))
            if st is not None:
                c = [(it.get("DOI", ""), rm._crossref_titles(it)) for it in (p or {}).get("message", {}).get("items", [])]
                return rm.best_sim(c, title=title)[0] if st == 200 else 0.0
        return None
    if backend == "arxiv":
        st, txt = stored("arxiv", *rm._arxiv_ti_req(title))
        if st is None:
            return None
        es = feedparser.parse(txt).entries if st == 200 and txt else []
        return rm.best_sim([(e.id, [" ".join(e.title.split())]) for e in es if getattr(e, "title", "")], title=title)[0]
    if backend == "dblp":
        st, p = stored("dblp", *rm.dblp_req(title))
        return None if st is None else rm.best_sim([(h.get("key", ""), [h.get("title", "")]) for h in (p or {}).get("hits", [])], title=title)[0]
    if backend == "openalex":
        url, prm = rm._openalex_req(title)
        prm.pop("api_key", None)
        st, p = stored("openalex", url, prm)
        return None if st is None else rm.best_sim([(w.get("id", ""), [w.get("title") or ""]) for w in (p or {}).get("results", [])], title=title)[0]
    if backend == "s2":
        st, p = stored("s2", *rm.s2_match_req(title))
        return None if st is None else rm.best_sim([(d.get("paperId", ""), [d.get("title", "")]) for d in (p or {}).get("data", [])], title=title)[0]
    return None


def fnum(x):
    try:
        v = float(x)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ d1
def d1(gt, rows, out):
    ev = gt[gt.def1_status.isin(["resolved", "unresolved"])].copy()
    applies = (ev.has_arxiv.astype(str) == "1") | (ev.tier == "P")
    sims = {b: ev[f"sim_{b}"].map(fnum) for b in BACK}
    # fill the backends not asked at 0.9 (an earlier one resolved) from stored answers; only references whose best
    # known similarity is below the largest tau can change, so only those are looked up
    known_max = pd.DataFrame(sims).max(axis=1)
    need = (ev.def1_status == "resolved") & (known_max < max(TAUS))
    filled = 0
    for b in BACK[1:]:
        m = need & sims[b].isna() & ((b != "arxiv") | applies)
        for i in ev.index[m]:
            v = stored_sim(b, ev.at[i, "title"])
            if v is not None:
                sims[b].at[i] = v
                filled += 1
    S = pd.DataFrame(sims)
    S.loc[~applies, "arxiv"] = -1.0  # not in this reference's cascade
    out["d1"] = {"filled_from_stored_answers": filled, "cells": []}
    for per in ("2019-21", "2024-26"):
        for strat, msk in [("A", ev.tier.isin(A))] + [(t, ev.tier == t) for t in ["J", "C", "P", "B", "S", "W"]]:
            m = msk & (ev.period == per)
            for tau in TAUS:
                cr = S.loc[m, "crossref"]
                k_cr = int((~(cr >= tau)).sum())
                known = S.loc[m].fillna(-2.0)
                res_known = (known >= tau).any(axis=1)
                unknown = S.loc[m].isna().any(axis=1) & ~res_known
                k_up = int((~res_known).sum())
                k_lo = int((~res_known & ~unknown).sum())
                n = int(m.sum())
                rec = dict(table="tau_sweep", period=per, stratum=strat, tau=tau, n=n, k_crossref=k_cr,
                           u_crossref=k_cr / n if n else None, k_full_upper=k_up, k_full_lower=k_lo,
                           u_full_upper=k_up / n if n else None, u_full_lower=k_lo / n if n else None)
                rows.append(rec)
                out["d1"]["cells"].append(rec)
    fk = pd.read_csv(RES / "p2_fake_items.csv", dtype=str, keep_default_na=False)
    fapp = (fk.has_arxiv.astype(str) == "1") | (fk.tier == "P")
    F = pd.DataFrame({b: fk[f"sim_{b}"].map(fnum) for b in BACK})
    F.loc[~fapp, "arxiv"] = np.nan
    out["d1"]["false_match"] = []
    for fam in ["gen_a", "gen_b", "gen_c", "badalova", "gptzero"]:
        m = fk.set == fam
        for tau in TAUS:
            cr = int((F.loc[m, "crossref"] >= tau).sum())
            full = int((F.loc[m].fillna(-1) >= tau).any(axis=1).sum())
            n = int(m.sum())
            rec = dict(table="tau_false_match", family=fam, tau=tau, n=n, k_crossref=cr, rate_crossref=cr / n,
                       k_full=full, rate_full=full / n)
            rows.append(rec)
            out["d1"]["false_match"].append(rec)


# ------------------------------------------------------------------------------------------------ d2
def d2(gt, rows, out):
    c = gt[(gt.certified_real.astype(str) == "1") & gt.tier.isin(["J", "C"]) & (gt.has_doi.astype(str) == "1")
           & gt.def1_status.isin(["resolved", "unresolved"])].copy()
    c["cr_resolved"] = c.backends_hit.str.split(";").map(lambda h: "crossref" in h)
    u = c[~c.cr_resolved]
    out["d2"] = {}
    for per in ("2019-21", "2024-26"):
        for t in ("J", "C", "J+C"):
            m = (u.period == per) & (u.tier.isin(["J", "C"]) if t == "J+C" else u.tier == t)
            mc = (c.period == per) & (c.tier.isin(["J", "C"]) if t == "J+C" else c.tier == t)
            x = u[m]
            present = int((x.id_backend == "crossref").sum())
            rec = dict(table="absent_present", period=per, tier=t, n_certified_doi=int(mc.sum()),
                       unresolved_crossref_title=int(len(x)), present_but_unmatched=present,
                       absent_from_crossref=int(len(x) - present),
                       present_share=present / len(x) if len(x) else None,
                       present_sim_median=float(x[x.id_backend == "crossref"].sim_crossref.map(fnum).median())
                       if present else None)
            rows.append(rec)
            out["d2"][f"{per}/{t}"] = rec
    dg = pd.read_csv(RES / "p1_diag_unresolved_jc60.csv", dtype=str, keep_default_na=False)
    cases = dg[dg.diag_id.isin(["D16", "D31", "D46", "D48"])]
    g2 = gt.set_index(["arxiv_id", "key"])
    lst = []
    for _, r in cases.iterrows():
        k = (r.arxiv_id, r.key)
        st = g2.loc[[k]].iloc[0] if k in g2.index else None
        lst.append(dict(id=r.diag_id, tier=r.tier, best_backend=r.best_backend, best_sim=fnum(r.best_sim),
                        sim_crossref_now=fnum(st.sim_crossref) if st is not None else None,
                        state_now=st.def1_status if st is not None else None, bib_title=r.bib_title,
                        best_title=r.best_title))
    au = pd.read_csv(RES / "p2_recall_drop_audit.csv", dtype=str, keep_default_na=False)
    gz = au[au.item_id == "GZ023"].iloc[0]
    lst.append(dict(id="GZ023", first_backend=gz.first_backend, similarity=fnum(gz.similarity),
                    cited_title=gz.cited_title, record_title=gz.record_title, audit_label=gz.audit_label))
    out["d2"]["cases"] = lst


# ------------------------------------------------------------------------------------------------ d3
def d3(gt, rows, out):
    ms = pd.read_csv(RES / "p2_manual_sample.csv", dtype=str, keep_default_na=False)
    ms = ms[ms.exists == "exists"]
    sr = pd.read_csv(DER / "screen_p1" / "screen_refs.csv", dtype=str, keep_default_na=False,
                     usecols=["arxiv_id", "style", "variant", "parser", "key", "flag_union", "flag_crossref"])
    j = sr.merge(ms[["paper_id", "key", "tier"]].rename(columns={"paper_id": "arxiv_id"}), on=["arxiv_id", "key"])
    g = gt.drop_duplicates(["arxiv_id", "key"]).set_index(["arxiv_id", "key"])
    bib = []
    for _, r in ms.iterrows():
        k = (r.paper_id, r.key)
        if k in g.index:
            x = g.loc[k]
            hit = set(str(x.backends_hit).split(";")) & {"crossref", "arxiv", "dblp", "s2"}
            bib.append(dict(tier=r.tier, state=x.def1_status, flag_union=int(x.def1_status == "unresolved" or
                                                                              (x.def1_status == "resolved" and not hit)),
                            flag_crossref=int("crossref" not in str(x.backends_hit).split(";"))))
    b = pd.DataFrame(bib)
    b = b[b.state.isin(["resolved", "unresolved"])]
    out["d3"] = {"n_rows": int(len(ms)), "bib_title": {}, "rendered": []}
    for fc in ("flag_union", "flag_crossref"):
        k, n = int(b[fc].sum()), len(b)
        out["d3"]["bib_title"][fc] = dict(k=k, n=n, fp=k / n, wilson=list(wilson(k, n)))
        rows.append(dict(table="pdf_screen", source="bib-title", screen=fc, k=k, n=n, fp=k / n))
    for (st, var, par), x in j.groupby(["style", "variant", "parser"]):
        for fc in ("flag_union", "flag_crossref"):
            v = pd.to_numeric(x[fc], errors="coerce")
            k, n = int(v.sum()), int(v.notna().sum())
            rec = dict(table="pdf_screen", source="rendered", style=st, variant=var, parser=par, screen=fc, k=k, n=n,
                       n_missing=int(v.isna().sum()), fp=k / n if n else None,
                       wilson=list(wilson(k, n)) if n else None)
            rows.append({kk: vv for kk, vv in rec.items() if kk != "wilson"})
            out["d3"]["rendered"].append(rec)


# ------------------------------------------------------------------------------------------------ d4, d5, d6
def paper_frame(ev, x):
    ev = ev.assign(x=x.astype(int))
    pa = ev[ev.tier.isin(A)].groupby(["paper_id", "tier"]).agg(n=("x", "size"), k=("x", "sum")).unstack(fill_value=0)
    P = pd.DataFrame({f"n_{s}": pa["n"].get(s, 0) for s in A}).fillna(0).astype(int)
    for s in A:
        P[f"k_{s}"] = pa["k"].get(s, 0)
    P = P.reindex(ev.paper_id.unique(), fill_value=0).fillna(0).astype(int)
    P["N_A"] = P[[f"k_{s}" for s in A]].sum(axis=1)
    P["n_A"] = P[[f"n_{s}" for s in A]].sum(axis=1)
    return P


def scen_x(ev, sc):
    unres = (ev.def1_status == "unresolved").values
    col, backends = p3d.SCEN[sc]
    return unres if backends is None else (unres | ~tt.resolved_by(ev.backends_hit, backends))


def d4(gt1, rows, out, seed):
    ev = gt1[(gt1.period == "2019-21") & gt1.def1_status.isin(["resolved", "unresolved"])].copy()
    out["d4"] = {}
    for sc in ("crossref_only", "full"):
        P = paper_frame(ev, scen_x(ev, sc))
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, len(P), (1000, len(P)))
        ub = {s: (P[f"k_{s}"].values[idx].sum(1) / np.maximum(P[f"n_{s}"].values[idx].sum(1), 1)) for s in A}
        rng2 = np.random.default_rng(seed)
        rb = {}
        for s in A:
            keep = P[f"n_{s}"].values > 0
            kk, nn = P[f"k_{s}"].values[keep], P[f"n_{s}"].values[keep]
            f0 = fit_bb(kk, nn)
            draws = []
            for _ in range(200):
                i = rng2.integers(0, len(kk), len(kk))
                draws.append(fit_bb(kk[i], nn[i], f0.get("x"))["rho"])
            rb[s] = np.array(draws)
        res = {"bounds": {}}
        for rule, m in (("R1_CI", 3), ("R2_betaq", 6), ("R3_cantelli", 6)):
            lv = 1 - ETA / m
            up = {s: float(np.quantile(ub[s], lv)) for s in A}
            lo = {s: float(np.quantile(ub[s], 1 - lv)) for s in A}
            rho_up = {s: float(np.quantile(rb[s], lv)) for s in A}
            res["bounds"][rule] = dict(level=lv, m=m, u_up=up, u_lo=lo, rho_up=rho_up)
            for alpha in (0.05, 0.01):
                cache, ks = {}, []
                for c in map(tuple, P[[f"n_{s}" for s in A]].values):
                    if c not in cache:
                        cache[c] = p3d.rules_v4(c, lo, up, rho_up, alpha)[rule]
                    ks.append(cache[c])
                ks = np.array(ks)
                rej = (P.N_A.values >= ks) & (P.n_A.values > 0)
                k_, n_ = int(rej.sum()), len(P)
                wl, wh = wilson(k_, n_)
                rec = dict(table="bonferroni_rule_check", scenario=sc, rule=rule, alpha=alpha, level=lv,
                           k_rejected=k_, n_papers=n_, share=k_ / n_, wilson_lo=wl, wilson_hi=wh,
                           alpha_safe_obs=bool(wl <= alpha))
                rows.append(rec)
                res[f"{rule}_a{alpha}"] = rec
                Pa = P[P.n_A > 0].sort_values("n_A").reset_index()
                for qv in (0.1, 0.25, 0.5, 0.75, 0.9):
                    r_ = Pa.iloc[min(int(qv * (len(Pa) - 1)), len(Pa) - 1)]
                    c = tuple(int(r_[f"n_{s}"]) for s in A)
                    kv = p3d.rules_v4(c, lo, up, rho_up, alpha)[rule]
                    rows.append(dict(table="bonferroni_k_typical", scenario=sc, rule=rule, alpha=alpha, quantile=qv,
                                     n_A=sum(c), n_J=c[0], n_C=c[1], n_P=c[2], value=kv))
                    res.setdefault("k_typical", {}).setdefault(f"{rule}_a{alpha}", {})[str(sum(c))] = int(kv)
        out["d4"][sc] = res


def d5(gt1, rows, out):
    out["d5"] = {}
    ev_all = gt1[gt1.def1_status.isin(["resolved", "unresolved"])].copy()
    pre_papers = ev_all[ev_all.period == "2019-21"]
    for sc in ("crossref_only", "full"):
        frames = {}
        for per in ("2019-21", "2024-26"):
            ev = ev_all[ev_all.period == per]
            frames[per] = paper_frame(ev, scen_x(ev, sc))
        cuts = np.quantile(frames["2019-21"].n_A, [1 / 3, 2 / 3])
        res = {"tertile_cuts_nA": [float(c) for c in cuts]}
        for per, P in frames.items():
            bins = {"all": np.ones(len(P), bool), "T1": P.n_A.values <= cuts[0],
                    "T2": (P.n_A.values > cuts[0]) & (P.n_A.values <= cuts[1]), "T3": P.n_A.values > cuts[1]}
            for b, m in bins.items():
                N = P.N_A.values[m]
                n = int(m.sum())
                kmax = max(int(N.max()) + 2, 12) if n else 12
                sh = {k: int((N >= k).sum()) for k in range(1, kmax)}
                for alpha in (0.05, 0.01):
                    kk = next((k for k in range(1, kmax) if sh[k] / n <= alpha), None) if n else None
                    wl, wh = wilson(sh[kk], n) if kk else (None, None)
                    rec = dict(table="empirical_threshold", scenario=sc, period=per, bin=b, alpha=alpha, n_papers=n,
                               k_emp=kk, share_at_k=sh[kk] / n if kk else None, wilson_lo=wl, wilson_hi=wh,
                               share_at_k_minus_1=sh[kk - 1] / n if kk and kk > 1 else None,
                               nA_median=float(np.median(P.n_A.values[m])) if n else None)
                    rows.append(rec)
                    res[f"{per}/{b}/a{alpha}"] = rec
                res[f"{per}/{b}/shares"] = {str(k): sh[k] / n for k in range(1, 11)} if n else {}
        out["d5"][sc] = res
    _ = pre_papers


def d6(rows, out):
    bb = json.loads((RES / "p1_h5_betabinom.json").read_text(encoding="utf-8"))["scenarios"]
    rho_up = {s: bb["full"]["tiers"][s]["rho_boot95"][1] for s in A}
    fx = json.loads((RES / "p3d_theory_fix.json").read_text(encoding="utf-8"))
    typ = pd.read_csv(RES / "p3d_theory_fix.csv", dtype=str, keep_default_na=False)
    typ = typ[(typ.table == "k_typical") & (typ.scenario == "full") & (typ.rule == "R1_CI") & (typ.alpha == "0.05")]
    out["d6"] = {}
    for name in ("identifier", "identifier_only"):
        x = fx["identifier"][name]
        lo, up = {s: x["u_lower"] for s in A}, {s: x["u_upper"] for s in A}
        for _, r_ in typ.iterrows():
            cn = (int(float(r_.n_J)), int(float(r_.n_C)), int(float(r_.n_P)))
            for alpha in (0.05, 0.01):
                for rl, rh in (("rho0", {s: 0.0 for s in A}), ("rho_up", rho_up)):
                    for rule, kv in p3d.rules_v4(cn, lo, up, rh, alpha).items():
                        rows.append(dict(table="k_identifier_rho", scenario=name, rho=rl, n_A=sum(cn), alpha=alpha,
                                         rule=rule, value=kv))
                        out["d6"].setdefault(name, {}).setdefault(str(sum(cn)), {}).setdefault(f"a{alpha}", {}) \
                            .setdefault(rl, {})[rule.split("_")[0]] = int(kv)


def d7(gt, rows, out):
    """H1 under the cascade without DBLP (the registered backends; R2 Q8): a reference resolves if Crossref, arXiv,
    OpenAlex or S2 matches at 0.9. For references that DBLP resolved first, the later backends were not asked; their
    stored answers are used where they exist, otherwise the reference counts in an interval."""
    ev = gt[(gt.period == "2019-21") & gt.tier.isin(A) & gt.def1_status.isin(["resolved", "unresolved"])].copy()
    applies = (ev.has_arxiv.astype(str) == "1") | (ev.tier == "P")
    hit = ev.backends_hit.str.split(";")
    res_other = hit.map(lambda h: bool(set(h) & {"crossref", "arxiv", "openalex", "s2"}))
    dblp_only = hit.map(lambda h: "dblp" in h) & ~res_other
    known_res, unknown, looked = 0, 0, 0
    for i in ev.index[dblp_only]:
        t = ev.at[i, "title"]
        vals = []
        for b in ("openalex", "s2") + (("arxiv",) if applies.at[i] else ()):
            v = fnum(ev.at[i, f"sim_{b}"])
            v = stored_sim(b, t) if v is None else v
            vals.append(v)
        looked += 1
        if any(v is not None and v >= 0.9 for v in vals):
            known_res += 1
        elif any(v is None for v in vals):
            unknown += 1
    n = len(ev)
    k_unres_full = int((ev.def1_status == "unresolved").sum())
    k_up = k_unres_full + int(dblp_only.sum()) - known_res
    k_lo = k_up - unknown
    rec = dict(table="h1_without_dblp", n=n, k_full=k_unres_full, u_full=k_unres_full / n, dblp_first=int(dblp_only.sum()),
               dblp_first_resolved_elsewhere_stored=known_res, dblp_first_unknown=unknown, k_upper=k_up, k_lower=k_lo,
               u_upper=k_up / n, u_lower=k_lo / n,
               h1_window=[0.005, 0.05], h1_upper_in_window=bool(0.005 <= k_up / n <= 0.05),
               h1_lower_in_window=bool(0.005 <= k_lo / n <= 0.05))
    rows.append(rec)
    out["d7"] = rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    gt = pd.read_csv(DER / "p2_groundtruth_refs_full.csv", dtype=str, keep_default_na=False, low_memory=False)
    gt1 = pd.read_csv(RES / "p1_groundtruth.csv", dtype=str, keep_default_na=False)
    rows, out = [], {"label": "EXPLORATORY (PREREG_AMENDMENT_7 (d)); offline; completed ground truth", "seed": args.seed}
    d1(gt, rows, out)
    d2(gt, rows, out)
    d3(gt, rows, out)
    d4(gt1, rows, out, args.seed)
    d5(gt1, rows, out)
    d6(rows, out)
    d7(gt, rows, out)
    pd.DataFrame(rows).to_csv(RES / "p3e_exploratory.csv", index=False)
    (RES / "p3e_exploratory.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k in ("d2", "d3")}, indent=1, default=float)[:3000])


if __name__ == "__main__":
    main()
