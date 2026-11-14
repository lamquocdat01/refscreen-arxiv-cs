#!/usr/bin/env python3
"""Topic 43 / P3H (PREREG_AMENDMENT_9.md (F)-(G); POST HOC): score the web evidence, offline.

Opens the key (results/p3h_evidence_key.csv after release; else decrypts $THS_DATASETS/_derived/43/keys/
p3h_evidence_key.csv.enc and checks the plaintext sha256 logged before the search), joins sheet, rule check and the
author's file (results/p3h_evidence_author.csv).
  confirmed  = PASS + y, or needs_browser + y (class "author-opened"); NEAR + y reported separately, not confirmed.
(F) planted rows: share confirmed (rule + author) and share PASS (rule alone), Clopper-Pearson 95%;
    real rows: counts by state, C, cross-tab with GT-3 (found / not found / unanswered) and with the AI rater (R_B)
    labels where a row is shared (matched by normalised title + citing paper is not available in the R_B sheet, so by
    title only; reported as descriptive).
(G) .bib branch, 2019-21, new lower end: a flagged reference is real if GT-3 found it or it is confirmed here.
    FP lower bound (f_hi of the decoys for the rest), paper shares >= 1/2/3, k_emp, Wilson k, PPV at the lower end;
    with and without the web evidence. The upper end does not change.
Outputs: results/p3h_evidence_score.{csv,json}, results/p3h_two_ends.{csv,json}, results/p3h_evidence_key.csv (released)
Usage: python code/p3h_evidence_score.py
"""
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import beta

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3f_bounds as fb  # noqa: E402
import p3g_branch_split as bs  # noqa: E402
import refmatch as rm  # noqa: E402
from p1_theory_tables import ppv_star  # noqa: E402
from p3h_evidence_check import CACHE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
KEYDIR = Path(os.environ.get("THS_DATASETS", "D:/Datasets")) / "_derived" / "43" / "keys"
KEY_SHA = "adc8555c9eda287c06faefbddedd401df0939e7eda27b5cf4cc1765a79b57590"
A = ["J", "C", "P"]


def cp(k, n):
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return [lo, hi]


def load_key():
    rel = RES / "p3h_evidence_key.csv"
    if rel.exists():
        plain = rel.read_bytes()
    else:
        from cryptography.fernet import Fernet
        plain = Fernet((KEYDIR / "p3c_fernet.key").read_bytes()).decrypt((KEYDIR / "p3h_evidence_key.csv.enc").read_bytes())
    h = hashlib.sha256(plain).hexdigest()
    if h != KEY_SHA:
        raise SystemExit(f"key sha256 {h} != logged {KEY_SHA}")
    if not rel.exists():
        rel.write_bytes(plain)
    return pd.read_csv(io.BytesIO(plain), dtype=str, keep_default_na=False), h


def paper_block(g, col):
    P = bs.paper_counts(g, col)
    return dict(papers=len(P), flags=bs.shares(P, 3), k_emp=bs.k_emp(P))


def main():
    key, h = load_key()
    sh = pd.read_csv(RES / "p3h_evidence_sheet.csv", dtype=str, keep_default_na=False)
    ck = pd.read_csv(RES / "p3h_evidence_checked.csv", dtype=str, keep_default_na=False)
    au = pd.read_csv(RES / "p3h_evidence_author.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    au["author_check"] = au.author_check.str.strip().str.lower()
    x = sh.merge(key, on="ID").merge(ck, on="ID").merge(au[["ID", "author_check", "note"]], on="ID", how="left").fillna("")
    x["confirmed"] = ((x.state == "PASS") & (x.author_check == "y")) | ((x.state == "needs_browser") & (x.author_check == "y"))
    x["conf_class"] = x.apply(lambda r: ("author-opened" if r.state == "needs_browser" else r.url_class) if r.confirmed else "",
                              axis=1)
    x["near_y"] = (x.state == "NEAR") & (x.author_check == "y")
    out = dict(label="post hoc; web evidence retrieved by an AI agent, checked by rule, confirmed by the author; "
                     "one URL per reference released", key_sha256=h)
    # (F) planted
    pl = x[x.origin == "planted"]
    n = len(pl)
    out["planted"] = dict(n=n, state=pl.state.value_counts().to_dict(),
                          author=pl[pl.author_check != ""].author_check.value_counts().to_dict(),
                          pass_k=int((pl.state == "PASS").sum()), pass_cp=cp(int((pl.state == "PASS").sum()), n),
                          confirmed_k=int(pl.confirmed.sum()), confirmed_cp=cp(int(pl.confirmed.sum()), n),
                          near_y=int(pl.near_y.sum()))
    # P4 (closure2 M1): reason of every needs_browser row, from its capture (robots / bot block / fetch error / PDF)
    def reason(r):
        if r.state != "needs_browser":
            return ""
        cs = (r.capture_status or "").lower()
        if cs.startswith("robots"):
            return "robots.txt"
        if cs.startswith("blocked"):
            return "bot block or refusal"
        cf = CACHE / f"{hashlib.sha1(r.url.encode('utf-8')).hexdigest()}.txt"
        note = cf.read_text(encoding="utf-8") if cf.exists() else ""
        if cs.startswith("no readable") or re.search(r"(?i)pdf.{0,40}(compressed|unreadable|could not be read)|cover page unreadable", note):
            return "unreadable PDF"
        return "fetch error"
    x["nb_reason"] = [reason(r) for r in x.itertuples()]
    # P4 (closure2 M14): audited URL class where the agent's class is off (E064: a copy on a third-party library site;
    # E036: an aggregator page that showed no record)
    x["url_class_audited"] = x.url_class
    x.loc[x.ID == "E064", "url_class_audited"] = "2"
    x.loc[x.ID == "E036", "url_class_audited"] = "--"
    # P4 (closure2 M2): planted rows whose year is after 2021 (no reference of the corpus is)
    yr = pd.to_numeric(x.year, errors="coerce")
    out["planted_late_year"] = int(((x.origin == "planted") & (yr > 2021)).sum())
    out["real_max_year"] = int(yr[x.origin == "real"].max())
    # (F) real
    d = bs.base()
    rr = x[x.origin == "real"].merge(d[["ref_id", "gt3", "arxiv_id", "tier", "f", "u"]], left_on="source_id",
                                       right_on="ref_id", how="left")
    assert rr.gt3.notna().all() and len(rr) == 81
    out["real"] = dict(n=len(rr), state=rr.state.value_counts().to_dict(),
                       author=rr[rr.author_check != ""].author_check.value_counts().to_dict(),
                       confirmed=int(rr.confirmed.sum()), near_y=int(rr.near_y.sum()),
                       conf_class=rr[rr.confirmed].conf_class.value_counts().to_dict(),
                       by_state_author={f"{s}|{a or '-'}": int(v) for (s, a), v in
                                        rr.groupby(["state", "author_check"]).size().items()},
                       cross_gt3={f"{g}|{'confirmed' if c else 'not confirmed'}": int(v)
                                  for (g, c), v in rr.groupby(["gt3", "confirmed"]).size().items()},
                       nb_reason=rr[rr.state == "needs_browser"].nb_reason.value_counts().to_dict(),
                       nb_reason_confirmed=rr[(rr.state == "needs_browser") & rr.confirmed].nb_reason.value_counts().to_dict())
    # R_B (AI rater) on shared rows, by normalised title (descriptive)
    rb = pd.read_csv(RES / "p3e_human_rB.csv", dtype=str, keep_default_na=False)
    rb["nt"] = rb.title.map(rm.norm)
    rr["nt"] = rr.title.map(rm.norm)
    m = rr.merge(rb[["nt", "exists"]], on="nt", how="inner")
    rr = rr.merge(rb[["nt", "exists"]].drop_duplicates("nt"), on="nt", how="left").fillna({"exists": ""})
    # P4 (closure2 M14): web evidence x GT-3 x AI rater, as promised in Amendment 9 (F)
    rr["web"] = rr.apply(lambda r: "confirmed" if r.confirmed else ("NEAR+y" if r.near_y else "not confirmed"), axis=1)
    out["real"]["cross3"] = {f"{w}|{g}|{e or 'not rated'}": int(v)
                             for (w, g, e), v in rr.groupby(["web", "gt3", "exists"]).size().items()}
    out["real"]["cross_rB"] = {f"{e}|{'confirmed' if c else 'not confirmed'}": int(v)
                               for (e, c), v in m.groupby(["exists", "confirmed"]).size().items()}
    out["real"]["n_shared_rB"] = len(m)
    # (G) new lower end, .bib branch, 2019-21
    conf_ids = set(rr[rr.confirmed].source_id)
    pass_ids = set(rr[(rr.state == "PASS") & (rr.author_check == "y")].source_id)  # rule-checked and confirmed
    gs = json.loads((RES / "p3f_gt3_summary.json").read_text(encoding="utf-8"))
    f_hi = gs["false_match"]["f_hi_used"]
    db = d[(d.paper_branch == "bib")].copy()
    ends = {}
    rows = []
    for name, ids in (("without_web", set()), ("with_web", conf_ids), ("rule_only", pass_ids)):
        g = db.copy()
        g["f2"] = ((g.f == 1) | g.ref_id.isin(ids)).astype(int)
        g["f2"] = g.f2 * g.u
        pre = g[g.period == "2019-21"]
        ga = pre[pre.tier.isin(A)].copy()
        ga["f"] = ga.f2
        ga["r"] = ga.u - ga.f2
        ga["r_notfound"] = ga.r
        ga["r_unans"] = 0
        c = fb.cell(ga, f_hi, boot=True)
        pb = paper_block(pre, "f2")
        ppv = {pn: dict(lower_end=ppv_star(pi, c["fp_lower"]),
                        lower_end_ci=[ppv_star(pi, c["fp_lower_ci"][1]), ppv_star(pi, c["fp_lower_ci"][0])])
               for pn, pi in (("0.39%", 0.0039), ("0.5%", 0.005))}
        ends[name] = dict(bounds=c, paper=pb, ppv=ppv, f_zero=c["F"] / c["U"])
        for k, v in pb["flags"].items():
            rows.append(dict(variant=name, what=f"share_ge{k}", value=v["share"], k=v["papers"], n=v["n"],
                             lo=v["wilson"][0], hi=v["wilson"][1]))
        for a, v in pb["k_emp"].items():
            rows.append(dict(variant=name, what=f"k_emp_{a}", value=v["k_emp"], k=v["k_wilson_upper"]))
        rows.append(dict(variant=name, what="fp_lower", value=c["fp_lower"], lo=c["fp_lower_ci"][0], hi=c["fp_lower_ci"][1],
                         k=c["F"], n=c["U"]))
    out["ends"] = ends
    pd.DataFrame(rows).to_csv(RES / "p3h_two_ends.csv", index=False)
    (RES / "p3h_two_ends.json").write_text(json.dumps(ends, indent=1, default=float), encoding="utf-8")
    # rows released (one URL per reference) and keys for the manuscript
    x[["ID", "origin", "source_id", "reference", "url", "url_class", "url_class_audited", "state", "nb_reason", "sim",
       "page_title", "content_sha256", "fetched_utc", "author_check", "confirmed", "conf_class", "near_y"]].to_csv(RES / "p3h_evidence_score.csv",
                                                                                   index=False, encoding="utf-8")
    p, w, wo = out["planted"], ends["with_web"], ends["without_web"]

    def pc(v, dd=1):
        return f"{100 * v:.{dd}f}"
    real = out["real"]
    nv = dict(evN=str(len(x)), evRealN=str(real["n"]), evPlantN=str(n),
              evConf=str(real["confirmed"]), evNearY=str(real["near_y"]),
              evPass=str(real["state"].get("PASS", 0)), evNear=str(real["state"].get("NEAR", 0)),
              evFail=str(real["state"].get("FAIL", 0)), evNone=str(real["state"].get("NONE", 0)),
              evNb=str(real["state"].get("needs_browser", 0)),
              evConfOpened=str(real["conf_class"].get("author-opened", 0)),
              evConfFound=str(real["cross_gt3"].get("found|confirmed", 0)),
              evConfNotFound=str(real["cross_gt3"].get("not found|confirmed", 0) + real["cross_gt3"].get("unanswered|confirmed", 0)),
              evPlantConfK=f"{p['confirmed_k']}/{n}", evPlantConfCi=f"[{pc(p['confirmed_cp'][0])}, {pc(p['confirmed_cp'][1])}]",
              evPlantPassK=f"{p['pass_k']}/{n}", evPlantPassCi=f"[{pc(p['pass_cp'][0])}, {pc(p['pass_cp'][1])}]",
              evNewF=str(w["bounds"]["F"]), evNewFU=pc(w["f_zero"]),
              evLo=pc(w["bounds"]["fp_lower"], 2), evLoCi=f"[{pc(w['bounds']['fp_lower_ci'][0], 2)}, {pc(w['bounds']['fp_lower_ci'][1], 2)}]",
              evPpvLo039=pc(w["ppv"]["0.39%"]["lower_end"], 0))
    fc = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))["bounds_p3g"]["P5_fake_families"]["gen_c"]["f"]
    b = w["bounds"]
    nv["evLoFamc"] = pc(max(0.0, b["U"] - b["R"] / (1 - fc)) / b["N"], 2)
    nv["evPpvLoFive"] = pc(w["ppv"]["0.5%"]["lower_end"], 0)
    ro = ends["rule_only"]
    nv["evRoK"] = str(len(pass_ids))
    nv["evRoF"] = str(ro["bounds"]["F"])
    nv["evRoLo"] = pc(ro["bounds"]["fp_lower"], 2)
    nv["evRoLoCi"] = f"[{pc(ro['bounds']['fp_lower_ci'][0], 2)}, {pc(ro['bounds']['fp_lower_ci'][1], 2)}]"
    nv["evRoPpvLo039"] = pc(ro["ppv"]["0.39%"]["lower_end"], 0)
    for k in ("1", "2", "3"):
        e = ro["paper"]["flags"][k]
        nv[f"evRoGe{k}"] = pc(e["share"])
        nv[f"evRoGe{k}K"] = f"{e['papers']}/{e['n']}"
    for a, at in (("a0.05", "Five"), ("a0.01", "One")):
        nv[f"evRoKemp{at}"] = str(ro["paper"]["k_emp"][a]["k_emp"])
    nv["evRoLoFamc"] = pc(max(0.0, ro["bounds"]["U"] - ro["bounds"]["R"] / (1 - fc)) / ro["bounds"]["N"], 2)
    nbr, nbc = real["nb_reason"], real["nb_reason_confirmed"]
    for k_, t_ in (("robots.txt", "Robots"), ("bot block or refusal", "Block"), ("fetch error", "Err"), ("unreadable PDF", "Pdf")):
        nv[f"evNb{t_}"] = str(nbr.get(k_, 0))
        nv[f"evNbConf{t_}"] = str(nbc.get(k_, 0))
    nv["evPlantLate"] = str(out["planted_late_year"])
    nv["evRealMaxYear"] = str(out["real_max_year"])
    for k in ("1", "2", "3"):
        e = w["paper"]["flags"][k]
        nv[f"evLoGe{k}"] = pc(e["share"])
        nv[f"evLoGe{k}K"] = f"{e['papers']}/{e['n']}"
        nv[f"evLoGe{k}Ci"] = f"[{pc(e['wilson'][0])}, {pc(e['wilson'][1])}]"
    for a, at in (("a0.05", "Five"), ("a0.01", "One")):
        e = w["paper"]["k_emp"][a]
        nv[f"evKemp{at}"] = str(e["k_emp"])
        nv[f"evKemp{at}Share"] = pc(e["share_at_k"]) if e["k_emp"] else "--"
        nv[f"evKW{at}"] = str(e["k_wilson_upper"]) if e["k_wilson_upper"] else "none"
    out["nv"] = nv
    (RES / "p3h_evidence_score.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("planted", "real")}, indent=1, default=float))
    for name, e in ends.items():
        b = e["bounds"]
        print(name, "F", b["F"], "U", b["U"], "lower", round(b["fp_lower"] * 100, 3), [round(v * 100, 3) for v in b["fp_lower_ci"]],
              {k: (v["papers"], round(v["share"] * 100, 1)) for k, v in e["paper"]["flags"].items()},
              {a: (v["k_emp"], v["k_wilson_upper"]) for a, v in e["paper"]["k_emp"].items()},
              "ppv", round(e["ppv"]["0.39%"]["lower_end"] * 100, 1))


if __name__ == "__main__":
    main()
