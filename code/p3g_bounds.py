#!/usr/bin/env python3
"""Topic 43 / P3G (POSTHOC_NOTE_P3G.md P4-P8, P10, P12; POST HOC): bounds, decoys and two periods, offline.

P4  decoys: construction counts (from the build log, P3F_LOG 2026-11-08T09:13:06Z) and f / f_hi with the 4
    unanswered D-splice decoys in the denominator (as not found: 0/200; worst case, as found: 4/200) and the lower end.
P5  the GT-3 match rule (sim >= 0.80 + surname + year +-1; 0.90 title-only without surnames or year) on every candidate
    stored for the cascade's title requests of the generated and real-world fabricated items (results/p2_fake_items.csv)
    in cache/, cache_p3e/, cache_p3f/; f per family with Clopper-Pearson; coverage (items with a stored answer, and with
    a stored candidate that carries authors).
P6  found S/W references of 2019-21 by kind of URL answer (HTTP 2xx, HTTP 3xx not followed, Wayback capture).
P7  R/N by tier J/C/P, both periods, difference with a paper bootstrap CI (B = 1000, seed 42); U/N of P without
    identifier both periods; approximate power for +0.39 points (two-sided 0.05, bootstrap SE); the registered and the
    not-found-only differences side by side with three decimals.
P8  not-found academic 2019-21 references split by the best stored deep-search candidate: (b) a candidate at or above the
    rule's similarity that fails the surname or year condition; (a) none at or above it, with best sim in [0.60, 0.80)
    or below 0.60; rows and by branch.
P10 tier rule, binary academic / non-academic agreement and precision of each side (confusion of Amendment 8 (I)).
P12 H4-auto numbers as a table (from results/p3f_gt3_summary.json), with the lower-end effect size.
Outputs: results/p3g_bounds.json, results/p3g_fake_gt3rule.csv, results/p3g_notfound_split.csv
Usage: python code/p3g_bounds.py
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm as N01

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3f_bounds as fb  # noqa: E402
import p3f_deep_search as ds  # noqa: E402
import p3g_branch_split as bs  # noqa: E402
import refmatch as rm  # noqa: E402
from p3c_validity import cp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
A = ["J", "C", "P"]
B, SEED = 1000, 42
CACHES = [ds.OLD_CACHE, ds.P3E_CACHE, ds.CACHE]


def stored_any(backend, url, params):
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


def cascade_cands(title):
    """Candidates of every stored cascade title request for `title`, per backend; None = nothing stored."""
    out = {}
    base = {"query.bibliographic": title[:500], "rows": 5, "mailto": rm.MAILTO}
    got = None
    for sel in ("DOI,title,subtitle,issued,author", "DOI,title,subtitle,issued"):
        st, p = stored_any("crossref", "https://api.crossref.org/works", dict(base, select=sel))
        if st is not None:
            got = ds.cands_crossref(p) if st == 200 else []
            break
    out["crossref"] = got
    st, txt = stored_any("arxiv", *rm._arxiv_ti_req(title))
    out["arxiv"] = None if st is None else (ds.cands_arxiv(txt) if st == 200 else [])
    st, p = stored_any("dblp", *rm.dblp_req(title))
    out["dblp"] = None if st is None else (ds.cands_dblp(p) if st == 200 else [])
    url, prm = rm._openalex_req(title)
    prm.pop("api_key", None)
    st, p = stored_any("openalex", url, prm)
    out["openalex"] = None if st is None else (ds.cands_openalex(p) if st == 200 else [])
    st, p = stored_any("s2", *rm.s2_match_req(title))
    out["s2"] = None if st is None else (ds.cands_s2(p) if st == 200 else [])
    return out


def p5():
    fk = fb.rd(RES / "p2_fake_items.csv")
    rows = []
    for r in fk.to_dict("records"):
        y = ds.int_year(r["year"])
        ref = {"title": r["title"], "surnames": rm.bib_surnames(r["author"]), "year": y}
        cc = cascade_cands(r["title"])
        answered = [b for b, v in cc.items() if v is not None]
        with_auth = [b for b, v in cc.items() if v and any(c["authors"] for c in v)]
        hit = None
        for b, v in cc.items():
            m = ds.best_match(ref, v or [])
            if m and (hit is None or m["sim"] > hit["sim"]):
                hit = dict(m, source=b)
        rows.append(dict(item_id=r["item_id"], family=r["set"], label=r["label"], n_answered=len(answered),
                         answered=";".join(answered), with_authors=";".join(with_auth), found=int(hit is not None),
                         source=hit["source"] if hit else "", sim=hit["sim"] if hit else "",
                         no_surname_or_year=int(not ref["surnames"] or y is None)))
    x = pd.DataFrame(rows)
    x.to_csv(RES / "p3g_fake_gt3rule.csv", index=False)
    fam = {}
    for (f, lab), g in x.groupby(["family", "label"]):
        f = f if f != "badalova" else f"badalova_{lab}"
        ok = g[g.n_answered > 0]
        k, n = int(ok.found.sum()), len(ok)
        fam[f] = dict(n_items=len(g), n_with_stored_answer=n, n_with_author_candidates=int((g.with_authors != "").sum()),
                      found=k, f=k / n if n else None, cp95=cp(k, n) if n else None,
                      by_source=ok[ok.found == 1].source.value_counts().to_dict(),
                      no_surname_or_year=int(g.no_surname_or_year.sum()))
    return fam


def p4(gs):
    fm = gs["false_match"]
    c = gs["cells"]["2019-21|A"]
    ds_ = fm["D-splice"]
    k, n, nu = ds_["k"], ds_["n"], ds_["n_unanswered"]
    out = dict(build={"pool": 9508, "skipped": {"same_paper": 2, "A_no_surname_or_year": 2, "sim_ge_080": 0}, "n_dsplice": 200,
                      "source": "P3F/P3F_LOG.md 2026-11-08T09:13:06Z (build log)"},
               note="every kept decoy has sim < 0.80 with both source titles by construction; the only record sharing its "
                    "surnames and year is source A, which the rule cannot match")
    for lab, kk in (("unanswered_as_not_found", k), ("unanswered_as_found", k + nu)):
        fh = cp(kk, n + nu)[1]
        lo = max(0.0, c["U"] - c["R"] / (1 - fh)) / c["N"]
        out[lab] = dict(k=kk, n=n + nu, f=kk / (n + nu), f_hi=fh, fp_lower_A=lo)
    return out


def p6(d):
    x = fb.rd(RES / "p3f_deep_search.csv")
    y = x[(x.set == "nonacad1921") & (x.state == "found")]
    kind = np.where(y.source == "wayback", "wayback",
                    np.where(y.record_type.str.match(r"http 2\d\d"), "2xx", np.where(y.record_type.str.match(r"http 3\d\d"), "3xx", "title source")))
    m = dict(zip(y.ref_id, kind))
    g = d[(d.period == "2019-21") & d.tier.isin(["B", "S", "W"]) & (d.f == 1)]
    g = g.assign(kind=g.ref_id.map(m))
    out = {t: g[g.tier == t].kind.value_counts().to_dict() for t in ("B", "S", "W")}
    out["codes_3xx"] = y[y.record_type.str.match(r"http 3\d\d")].record_type.value_counts().to_dict()
    out["unit"] = "rows"
    return out


def boot_diff(d, keep, col):
    a = d[(d.period == "2019-21") & keep].assign(n1=1).groupby("arxiv_id")[[col, "n1"]].sum().values
    b = d[(d.period == "2024-26") & keep].assign(n1=1).groupby("arxiv_id")[[col, "n1"]].sum().values
    rng = np.random.default_rng(SEED)
    sa = a[rng.integers(0, len(a), (B, len(a)))].sum(1)
    sb = b[rng.integers(0, len(b), (B, len(b)))].sum(1)
    dd = sb[:, 0] / sb[:, 1] - sa[:, 0] / sa[:, 1]
    ra, rb = a[:, 0].sum() / a[:, 1].sum(), b[:, 0].sum() / b[:, 1].sum()
    return dict(pre=ra, post=rb, k_pre=int(a[:, 0].sum()), n_pre=int(a[:, 1].sum()), k_post=int(b[:, 0].sum()),
                n_post=int(b[:, 1].sum()), diff=rb - ra, ci=np.quantile(dd, [.025, .975]).tolist(), se=float(dd.std(ddof=1)))


def p7(d):
    out = {}
    for t in A + ["A"]:
        keep = d.tier.isin(A) if t == "A" else (d.tier == t)
        out[f"rn|{t}"] = boot_diff(d, keep, "r")
        out[f"fu_counts|{t}"] = {per: dict(F=int(d[(d.period == per) & keep].f.sum()), U=int(d[(d.period == per) & keep].u.sum()))
                                 for per in ("2019-21", "2024-26")}
    noid = (d.tier == "P") & (d.has_doi == "0") & (d.has_arxiv == "0")
    out["un|P_noid"] = boot_diff(d, noid, "u")
    out["rn|P_noid"] = boot_diff(d, noid, "r")
    se = out["rn|A"]["se"]
    delta = 0.0039
    out["power_rn_A_039"] = dict(se=se, delta=delta, power=float(N01.cdf(delta / se - 1.96) + N01.cdf(-delta / se - 1.96)))
    out["rn_notfound_only|A"] = boot_diff(d, d.tier.isin(A), "r_notfound")
    out["why_same_ci"] = ("both use the same bootstrap draws (seed 42, same papers); the two numerators differ only by the "
                          "5 and 18 unanswered rows, so the quantiles differ in the third decimal")
    return out


def p8():
    d = ds.load_gt()
    rows = ds.set_rows(d, "acad1921").to_dict("records")
    st = fb.rd(RES / "p3f_deep_search.csv").set_index("ref_id").state
    ds.rm.CACHE = ds.CACHE
    res = []
    for r in rows:
        ref = ds.make_ref(r, "acad1921")
        if st.get(ref["ref_id"], "") != "not found":
            continue
        need = 0.90 if (not ref["surnames"] or ref["year"] is None) else 0.80
        best, fail_ay = 0.0, False
        for s in ds.SOURCES:
            c = ds.stored(s, ref) or []
            for cand in c:
                sim = max([rm.title_sim(ref["title"], t) for t in cand["titles"] if t] or [0.0])
                best = max(best, sim)
                if sim >= need:
                    fail_ay = True  # stored as not found, so any candidate at or above the threshold failed surname/year
        grp = "b_candidate_fails_author_year" if fail_ay else ("a_best_060_080" if best >= 0.60 else "a_best_below_060")
        res.append(dict(ref_id=ref["ref_id"], branch=ref["ref_source"], best_sim=round(best, 4), need=need, group=grp))
    x = pd.DataFrame(res)
    x.to_csv(RES / "p3g_notfound_split.csv", index=False)
    g = fb.frame()
    g = g[(g.period == "2019-21") & g.tier.isin(A) & (g.u == 1)]
    m = dict(zip(x.ref_id, x.group))
    g = g.assign(group=g.ref_id.map(m))
    g = g[g.group.notna()]
    return dict(unit_rows=g.group.value_counts().to_dict(), by_branch_rows=g.groupby(["ref_source", "group"]).size().unstack(fill_value=0).to_dict("index"),
                distinct=x.group.value_counts().to_dict(), n_rows=len(g), n_distinct=len(x))


def p10():
    t = json.loads((RES / "p3f_tier_validation.json").read_text(encoding="utf-8"))
    M = np.array(t["confusion_machine_rows_record_cols"])
    lab = t["labels"]
    ia = [lab.index(s) for s in A]
    io = [lab.index(s) for s in ("B", "S", "W")]
    aa, ao = M[np.ix_(ia, ia)].sum(), M[np.ix_(ia, io)].sum()
    oa, oo = M[np.ix_(io, ia)].sum(), M[np.ix_(io, io)].sum()
    n = M.sum()
    w = lab.index("W")
    return dict(n=int(n), binary_agreement=float((aa + oo) / n), precision_academic=float(aa / (aa + ao)),
                precision_nonacademic=float(oo / (oa + oo)), rule_academic_record_nonacademic=int(ao),
                rule_nonacademic_record_academic=int(oa), rule_W=int(M[w].sum()), rule_W_record_JCP=int(M[w][ia].sum()),
                rule_W_record_JCP_share=float(M[w][ia].sum() / M[w].sum()), scope="resolved references only; record type of the matched registry record")


def p12(gs):
    h = gs["h4_auto"]
    return dict(h, effect_lower_end_points=(h["fp_nonid_lower"] - h["fp_certified"]) * 100,
                effect_upper_end_points=(h["fp_nonid_upper"] - h["fp_certified"]) * 100)


def main():
    gs = json.loads((RES / "p3f_gt3_summary.json").read_text(encoding="utf-8"))
    d = bs.base()
    out = {"label": "POST HOC (POSTHOC_NOTE_P3G.md P4-P8, P10, P12); offline", "seed": SEED, "B": B}
    out["P4_decoys"] = p4(gs)
    out["P6_url"] = p6(d)
    out["P7_periods"] = p7(d)
    out["P10_tier_binary"] = p10()
    out["P12_h4_auto"] = p12(gs)
    out["P8_notfound_split"] = p8()
    out["P5_fake_families"] = p5()
    (RES / "p3g_bounds.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps(out, indent=1, default=float)[:9000])


if __name__ == "__main__":
    main()
