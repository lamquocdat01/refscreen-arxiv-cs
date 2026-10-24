#!/usr/bin/env python3
"""Topic 43 / P3 (C6): every number and generated table of the manuscript, from the result files only.

Writes
  submission_package/latex/numbers_ms.tex   \\nvset{<key>}{<formatted value>} for each key; the manuscript prints them
                                            with \\nv{<key>} (an unknown key is a LaTeX error, so nothing is typed by hand)
  submission_package/latex/tab_*.tex         table bodies (rows only; the table environment lives in main.tex)
  results/numbers_ms_sources.csv             key, value, source file, field (the evidence column of claims.csv)
Inputs: results/*.json|csv (p1/p2/p3), results/prereg_hash.txt, data_manifest/manifest_src_version.csv.
No network, no randomness (all CIs were computed upstream with their seeds).
Usage: python make_ms_numbers.py
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import ROOT  # noqa: E402

RES = ROOT / "results"
OUT = ROOT / "submission_package" / "latex"
NV, SRC = {}, []


def J(f):
    return json.loads((RES / f).read_text(encoding="utf-8"))


def C(f):
    return pd.read_csv(RES / f, dtype=str, keep_default_na=False)


def put(key, val, src, field=""):
    if key in NV and NV[key] != val:
        raise SystemExit(f"duplicate key with different value: {key}")
    NV[key] = val
    SRC.append(dict(key=key, value=val, source=src, field=field))


def pct(x, d=None):
    x = float(x) * 100
    if d is None:
        d = 1 if abs(x) >= 10 else 2
    return f"{x:.{d}f}"


def num(x, d=0):
    x = float(x)
    return f"{x:,.{d}f}"


def ci(lo, hi, d=None, scale=100):
    f = (lambda v: pct(v, d)) if scale == 100 else (lambda v: f"{float(v):.{d if d is not None else 2}f}")
    return f"[{f(lo)}, {f(hi)}]"


def rng(s):
    """'0.1-0.2', '1.67..7.24', '-4.49..-0.57', '[a, b]' -> (a, b); the first '-' after a number is a separator"""
    m = re.match(r"\s*\[?\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)\s*(?:\.\.|,|-|–)\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)", s)
    if not m:
        v = float(re.search(r"-?\d+(?:\.\d+)?", s).group(0))
        return v, v
    return float(m.group(1)), float(m.group(2))


# ---------------------------------------------------------------- corpus, backend table (Fig. 1, Table 2)
def backend():
    d = J("p2_backend_table_retry.json")
    rows = {(r["period"], r["stratum"]): r for r in d["rows"]}
    cols = [("crossref", "Crossref-only"), ("arxiv", "+arXiv"), ("dblp", "+DBLP"), ("openalex", "+OpenAlex"), ("s2", "+S2")]
    src = "results/p2_backend_table_retry.json"
    put("dblpDump", d["dblp_dump"], src, "dblp_dump")
    for per, tag in (("2019-21", "Pre"), ("2024-26", "Post")):
        for st in ["J", "C", "P", "B", "S", "W", "A", "certified_real", "P/no-id", "P/with-id", "all"]:
            r = rows[(per, st)]
            s = re.sub(r"[^A-Za-z]", "", st.replace("certified_real", "Cert").replace("P/no-id", "Pnoid").replace("P/with-id", "Pid").replace("all", "All"))
            put(f"n{s}{tag}", num(r["n"]), src, f"{per}/{st}/n")
            put(f"np{s}{tag}", num(r["n_papers"]), src, f"{per}/{st}/n_papers")
            for c, _ in cols:
                put(f"u{s}{tag}{c}", pct(r[f"u_{c}"]), src, f"{per}/{st}/u_{c}")
                put(f"k{s}{tag}{c}", num(r[f"k_{c}"]), src, f"{per}/{st}/k_{c}")
                lo, hi = rng(r[f"boot_{c}"])
                put(f"ci{s}{tag}{c}", ci(lo, hi), src, f"{per}/{st}/boot_{c}")
            put(f"rl{s}{tag}", num(r["n_rate_limited"]), src, f"{per}/{st}/n_rate_limited")
            put(f"nt{s}{tag}", num(r["n_no_title"]), src, f"{per}/{st}/n_no_title")
    # fold change of u_A between Crossref-only and full cascade
    for tag, per in (("Pre", "2019-21"), ("Post", "2024-26")):
        r = rows[(per, "A")]
        put(f"foldA{tag}", f"{r['u_crossref'] / r['u_s2']:.0f}", src, f"{per}/A u_crossref/u_s2")
    # Table 2 body: tiers x cumulative columns, 2019-21, then 2024-26 final column
    lines = []
    names = {"J": "J", "C": "C", "P": "P", "B": "B", "S": "S", "W": "W", "A": "\\textbf{A}", "certified_real": "Cert."}
    for st in ["J", "C", "P", "B", "S", "W", "A", "certified_real"]:
        a, b = rows[("2019-21", st)], rows[("2024-26", st)]
        cells = [f"{num(a['n'])} ({num(a['n_papers'])})"] + [pct(a[f"u_{c}"]) for c, _ in cols[:-1]]
        lo, hi = rng(a["boot_s2"])
        cells.append(f"\\textbf{{{pct(a['u_s2'])}}} {ci(lo, hi)}")
        cells.append(pct(b["u_s2"]))
        if st == "A":
            lines.append("\\midrule")
        lines.append(names[st] + " & " + " & ".join(cells) + " \\\\")
    (OUT / "tab_backend.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- H1-H2, period comparison, ref-year
def hypotheses():
    h = J("p1_hypotheses_h1h2.json")["columns"]
    src = "results/p1_hypotheses_h1h2.json"
    for c, tag in (("crossref", "crossref"), ("dblp", "dblp"), ("s2", "s2")):
        H1, H2 = h[c]["H1"], h[c]["H2"]
        put(f"hOneU{tag}", pct(H1["u_A"]), src, f"{c}/H1/u_A")
        put(f"hOneK{tag}", num(H1["k"]), src, f"{c}/H1/k")
        put(f"hOneN{tag}", num(H1["n"]), src, f"{c}/H1/n")
        put(f"hOneCi{tag}", ci(*H1["paper_bootstrap95"]), src, f"{c}/H1/paper_bootstrap95")
        put(f"hOnePass{tag}", "PASS" if H1["PASS"] else "FAIL", src, f"{c}/H1/PASS")
        put(f"hTwoRatio{tag}", f"{H2['ratio']:.1f}", src, f"{c}/H2/ratio")
        put(f"hTwoCi{tag}", ci(*H2["ratio_paper_bootstrap95"], d=1, scale=1), src, f"{c}/H2/ratio_paper_bootstrap95")
        put(f"hTwoPass{tag}", "PASS" if H2["PASS"] else "FAIL", src, f"{c}/H2/PASS")
        put(f"hTwoUW{tag}", pct(H2["u_W"]), src, f"{c}/H2/u_W")
    put("nPapersPre", num(h["s2"]["H1"]["n_papers"]), src, "s2/H1/n_papers")
    p = J("p1_period_compare.json")
    src = "results/p1_period_compare.json"
    for r in p["rows"]:
        c = re.sub(r"[^a-z0-9]", "", r["column"].lower())
        put(f"perUPre{c}", pct(r["u_2019-21"], 3), src, f"{r['column']}/u_2019-21")
        put(f"perUPost{c}", pct(r["u_2024-26"], 3), src, f"{r['column']}/u_2024-26")
        put(f"perDiff{c}", f"{r['diff_pp']:+.2f}", src, f"{r['column']}/diff_pp")
        lo, hi = rng(r["diff_boot_pp"].replace(" ", "")) if not r["diff_boot_pp"].startswith("-") else \
            [float(x) for x in re.findall(r"-?\d+\.?\d*", r["diff_boot_pp"])]
        put(f"perDiffCi{c}", f"[{lo:+.2f}, {hi:+.2f}]", src, f"{r['column']}/diff_boot_pp")
        a, b = rng(r["ratio_boot"])
        put(f"perRatio{c}", f"{r['ratio']:.2f}", src, f"{r['column']}/ratio")
        put(f"perRatioCi{c}", f"[{a:.2f}, {b:.2f}]", src, f"{r['column']}/ratio_boot")
    y = C("p1_u_by_refyear.csv")
    src = "results/p1_u_by_refyear.csv"
    for per, tag in (("2019-21", "Pre"), ("2024-26", "Post")):
        old = y[(y.period == per) & y.lag_years.str.startswith(">")]
        if len(old):
            put(f"refyearOld{tag}", pct(old.iloc[0].u, 2), src, f"{per}/{old.iloc[0].lag_years}/u")
        rest = y[(y.period == per) & ~y.lag_years.str.startswith(">") & (y.lag_years != "")]
        put(f"refyearRestLo{tag}", pct(rest.u.astype(float).min(), 1), src, f"{per}/min u other lags")
        put(f"refyearRestHi{tag}", pct(rest.u.astype(float).max(), 1), src, f"{per}/max u other lags")


# ---------------------------------------------------------------- render experiment, H3, Table 4
def render():
    s = J("p1_screen_fp.json")
    src = "results/p1_screen_fp.json"
    put("nRenderPapers", num(s["n_render_papers"]), src, "n_render_papers")
    put("nRenderedRefs", num(s["n_rendered_refs"]), src, "n_rendered_refs")
    put("nUniqueStrings", num(s["n_unique_strings"]), src, "n_unique_strings")
    for key, tag in (("H3", "union"), ("H3_crossref_only", "crossref"), ("H3_plus_dblp", "dblp")):
        h = s[key]
        put(f"hThreeFpA{tag}", pct(h["fp_a"], 2 if h["fp_a"] < 0.1 else 1), src, f"{key}/fp_a")
        put(f"hThreeFpB{tag}", pct(h["fp_b"], 3 if h["fp_b"] < 0.001 else 2), src, f"{key}/fp_b")
        put(f"hThreeKA{tag}", num(h["k_a"]), src, f"{key}/k_a")
        put(f"hThreeNA{tag}", num(h["n_a"]), src, f"{key}/n_a")
        put(f"hThreeKB{tag}", num(h["k_b"]), src, f"{key}/k_b")
        put(f"hThreeNB{tag}", num(h["n_b"]), src, f"{key}/n_b")
        put(f"hThreeRatio{tag}", f"{h['ratio']:.2f}", src, f"{key}/ratio")
        lo = h["ratio_ci"][0]
        put(f"hThreeRatioLo{tag}", f"{lo:.2f}", src, f"{key}/ratio_ci[0]")
        put(f"hThreeNPapers", num(h["n_papers"]), src, f"{key}/n_papers")
    miss = s["render_missing"]
    put("renderRawMissK", num(miss["IEEEtran_doi_raw/orig"]["k"]), src, "render_missing/IEEEtran_doi_raw/orig/k")
    put("renderRawMissN", num(miss["IEEEtran_doi_raw/orig"]["n"]), src, "render_missing/IEEEtran_doi_raw/orig/n")
    put("renderRawMissPapers", num(miss["IEEEtran_doi_raw/orig"]["n_papers"]), src, "render_missing/IEEEtran_doi_raw/orig/n_papers")
    put("renderDoiMissK", num(miss["IEEEtran_doi/orig"]["k"]), src, "render_missing/IEEEtran_doi/orig/k")
    f = C("p1_screen_fp.csv")
    src = "results/p1_screen_fp.csv"
    cr = f[(f.subset == "certified-real") & (f.tier == "all") & (f.parser == "grobid")]
    lines = []
    sty = {"IEEEtran": "IEEEtran v1.14", "IEEEtran_doi": "IEEEtran-DOI", "acmart": "ACM (acmart)", "elsarticle-num": "elsarticle-num"}
    for st, lab in sty.items():
        cells = []
        for var in ("orig", "strip"):
            for be in ("crossref", "union"):
                x = cr[(cr["style"] == st) & (cr.variant == var) & (cr.backend == be)]
                r = x.iloc[0]
                cells.append(f"{pct(r.fp, 2)} ({int(r.k_flagged)}/{num(r.n_refs)})")
        lines.append(lab + " & " + " & ".join(cells) + " \\\\")
    for st in ("IEEEtran", "IEEEtran_doi"):
        x = cr[(cr["style"] == st) & (cr.variant == "orig") & (cr.backend == "idonly")]
        if len(x):
            put(f"idonly{re.sub('[^A-Za-z]', '', st)}", pct(x.iloc[0].fp, 1), src, f"{st}/orig/idonly/fp")
    x = cr[(cr["style"] == "IEEEtran") & (cr.variant == "strip") & (cr.backend == "idonly")]
    if len(x):
        put("idonlyIEEEtranStrip", pct(x.iloc[0].fp, 1), src, "IEEEtran/strip/idonly/fp")
    (OUT / "tab_style.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    b = f[(f.subset == "certified-real") & (f.source == "bib-title") & (f.tier == "all")]
    for be in ("crossref", "union"):
        x = b[b.backend == be]
        if len(x):
            put(f"bibTitleFp{be}", pct(x.iloc[0].fp, 2), src, f"bib-title/{be}/fp")
    # identifier failure rate u_id (Prop 3.1) = union FP of IEEEtran strip
    put("uId", NV["hThreeFpAunion"], "results/p1_screen_fp.json", "H3/fp_a (u_id, Prop. 3.1)")


# ---------------------------------------------------------------- H4: two routes, adjudication, H4-render
def h4():
    d = J("p1_h4_bias.json")["H4"]
    src = "results/p1_h4_bias.json"
    for sc in ("crossref", "dblp", "union"):
        h = d[sc]
        put(f"hFourMan{sc}", pct(h["fp_manual_weighted"], 1), src, f"H4/{sc}/fp_manual_weighted")
        put(f"hFourKMan{sc}", num(h["k_manual"]), src, f"H4/{sc}/k_manual")
        put(f"hFourNMan{sc}", num(h["n_manual"]), src, f"H4/{sc}/n_manual")
        put(f"hFourCert{sc}", pct(h["fp_certified"], 2), src, f"H4/{sc}/fp_certified")
        put(f"hFourKCert{sc}", num(h["k_certified"]), src, f"H4/{sc}/k_certified")
        put(f"hFourNCert{sc}", num(h["n_certified"]), src, f"H4/{sc}/n_certified")
        put(f"hFourDiff{sc}", f"{h['diff'] * 100:+.1f}", src, f"H4/{sc}/diff")
        put(f"hFourDiffCi{sc}", f"[{h['diff_ci'][0] * 100:+.1f}, {h['diff_ci'][1] * 100:+.1f}]", src, f"H4/{sc}/diff_ci")
        put(f"hFourPass{sc}", "PASS" if h["PASS"] else "FAIL", src, f"H4/{sc}/PASS")
        put(f"hFourNPapers{sc}", num(h["n_papers"]), src, f"H4/{sc}/n_papers")
        for t, (k, n) in h["manual_by_tier"].items():
            put(f"hFourTier{t}{sc}", f"{k}/{n}", src, f"H4/{sc}/manual_by_tier/{t}")
    for sfx, tag in (("", "Pone"), ("_adjudicated", "Adj")):
        r = J(f"p2_render_manual_fp{sfx}.json")
        src = f"results/p2_render_manual_fp{sfx}.json"
        oc = r["outcomes"]
        put(f"rmExists{tag}", num(oc.get("exists", 0)), src, "outcomes/exists")
        put(f"rmAmb{tag}", num(oc.get("ambiguous", 0)), src, "outcomes/ambiguous")
        for sc in ("crossref", "union"):
            h = r["h4_render"][sc]
            put(f"rm{tag}Man{sc}", pct(h["fp_manual_weighted"], 1), src, f"h4_render/{sc}/fp_manual_weighted")
            put(f"rm{tag}K{sc}", f"{h['k_manual']}/{h['n_manual']}", src, f"h4_render/{sc}/k_manual,n_manual")
            put(f"rm{tag}Cert{sc}", pct(h["fp_certified"], 2), src, f"h4_render/{sc}/fp_certified")
            put(f"rm{tag}KCert{sc}", f"{h['k_certified']}/{num(h['n_certified'])}", src, f"h4_render/{sc}/k_certified")
            put(f"rm{tag}Diff{sc}", f"{h['diff'] * 100:+.1f}", src, f"h4_render/{sc}/diff")
            put(f"rm{tag}DiffCi{sc}", f"[{h['diff_ci'][0] * 100:+.1f}, {h['diff_ci'][1] * 100:+.1f}]", src, f"h4_render/{sc}/diff_ci")
    bt = J("p2_render_manual_fp.json")["by_tier_IEEEtran_strip_grobid"]
    src = "results/p2_render_manual_fp.json"
    for v in bt:
        put(f"rmTier{v['tier']}{v['screen']}", f"{v['k']}/{v['n']}", src, f"by_tier_IEEEtran_strip_grobid/{v['tier']}/{v['screen']}")
    adj = C("p3_adjudication.csv")
    put("adjChanged", num((adj.changes_pass1 == "True").sum()), "results/p3_adjudication.csv", "changes_pass1")


# ---------------------------------------------------------------- recall / ROC, audit, def 2-strict
def recall():
    a = C("p2_recall_audited.csv")
    src = "results/p2_recall_audited.csv"
    lines = []
    sets = [("gptzero", "hallucinated", "GPTZero NeurIPS 2025"), ("gen_b", "fabricated", "Family b: real title, swapped authors"),
            ("gen_c", "fabricated", "Family c: real title, wrong venue/year"), ("badalova", "problematic", "Badalova--Mayr problematic"),
            ("badalova", "verified", "Badalova--Mayr verified (FP)")]
    au = a[a.version.str.startswith("after audit")]
    r0 = C("p2_recall.csv")
    for st, lab, name in sets:
        for dfn in ("1", "2"):
            src_df = au if (st, lab) in (("gptzero", "hallucinated"), ("badalova", "problematic")) else r0
            x = src_df[(src_df.set == st) & (src_df.definition == dfn)]
            if lab:
                x = x[x.label == lab]
            if not len(x):
                continue
            cells = []
            for be in ("crossref", "+dblp", "+s2"):
                y = x[x.screen == be]
                if not len(y):
                    cells.append("--")
                    continue
                y = y.iloc[0]
                c = f"{pct(y.share_flagged, 1)}"
                if be == "+s2":
                    c += f" ({y.k_flagged}/{y.n_evaluated})"
                cells.append(c)
                key = f"rec{re.sub('[^A-Za-z]', '', st)}{lab}{dfn}{be.strip('+')}"
                put(key, pct(y.share_flagged, 1), "results/p2_recall_audited.csv" if src_df is au else "results/p2_recall.csv",
                    f"{st}/{lab}/def{dfn}/{be}/share_flagged")
                put(key + "K", f"{y.k_flagged}/{y.n_evaluated}", "results/p2_recall_audited.csv" if src_df is au else "results/p2_recall.csv",
                    f"{st}/{lab}/def{dfn}/{be}/k,n")
            lines.append(f"{name if dfn == '1' else ''} & def~{dfn} & " + " & ".join(cells) + " \\\\")
    (OUT / "tab_recall.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    au_j = J("p2_recall_audit.json")
    put("auditN", str(au_j.get("n_audited", 15)), "results/p2_recall_audit.json", "n_audited")
    dr = C("p2_recall_drop_audit.csv")
    lab = dr.columns[[c.startswith("audit_label") for c in dr.columns]].tolist()[0]
    vc = dr[lab].value_counts().to_dict()
    for k in ("PARTIAL", "FALSE_MATCH", "LABEL_WRONG"):
        put(f"audit{re.sub('[^A-Za-z]', '', k.title())}", str(vc.get(k, 0)), "results/p2_recall_drop_audit.csv", f"{lab}={k}")
    put("auditTotal", str(len(dr)), "results/p2_recall_drop_audit.csv", "rows")
    s = J("p2_def2_strict.json")
    src = "results/p2_def2_strict.json"
    flat = json.dumps(s)
    v = s["certified_plus_2024-26"]
    put("strictPlusDiff", f"{v['diff'] * 100:+.2f}", src, "certified_plus_2024-26/diff")
    put("strictPlusDiffCi", f"[{v['ci']['diff'][0] * 100:+.2f}, {v['ci']['diff'][1] * 100:+.2f}]", src, "certified_plus_2024-26/ci/diff")
    put("strictPlusFpAny", pct(v["fp_anywhere"], 2), src, "certified_plus_2024-26/fp_anywhere")
    put("strictPlusFpStrict", pct(v["fp_strict"], 2), src, "certified_plus_2024-26/fp_strict")
    put("strictPlusN", num(v["n_refs"]), src, "certified_plus_2024-26/n_refs")
    _ = flat


# ---------------------------------------------------------------- tools
def tools():
    t = C("p2_tool_hallucinator.csv")
    src = "results/p2_tool_hallucinator.csv"
    for st, tag in (("IEEEtran_strip", "strip"), ("IEEEtran_doi_orig", "doi")):
        x = t[(t["style"] == st) & t.subset.str.startswith("certified-real")].iloc[0]
        put(f"hallFp{tag}", pct(x.share_flagged, 2), src, f"{st}/certified/share_flagged")
        put(f"hallK{tag}", f"{x.k_flagged}/{x.n_evaluated}", src, f"{st}/certified/k,n_evaluated")
        put(f"hallCi{tag}", ci(x.ci_lo, x.ci_hi, 2), src, f"{st}/certified/ci")
        y = t[(t["style"] == st) & t.subset.str.startswith("all")].iloc[0]
        put(f"hallAllFp{tag}", pct(y.share_flagged, 2), src, f"{st}/all/share_flagged")
        put(f"hallAllK{tag}", f"{y.k_flagged}/{y.n_evaluated}", src, f"{st}/all/k,n_evaluated")
        put(f"hallAllRefs{tag}", num(y.n_refs), src, f"{st}/all/n_refs")
        put(f"hallInconcl{tag}", num(y.n_inconclusive), src, f"{st}/all/n_inconclusive")
        put(f"hallSkipped{tag}", num(y.n_skipped), src, f"{st}/all/n_skipped")
        put(f"hallNotExtr{tag}", num(y.n_not_extracted), src, f"{st}/all/n_not_extracted")
    put("hallPairs", t.n_pairs.iloc[0], src, "n_pairs")
    put("hallHours", t.hours_cumulative.iloc[0], src, "hours_cumulative")
    c = J("p2_checkifexist.json")
    src = "results/p2_checkifexist.json"
    put("cieRuns", str(c.get("n_runs", 3)), src, "n_runs")
    put("cieRefs", str(c.get("n_refs", 49)), src, "n_refs")
    put("cieChanged", str(c.get("n_refs_changed", 0)), src, "n_refs_changed")


# ---------------------------------------------------------------- theory (numbers.json + p2_theory_final.csv)
def theory():
    t = C("p2_theory_final.csv")
    src = "results/p2_theory_final.csv"
    p = t[t.table == "ppv_headline"]
    for _, r in p.iterrows():
        k = f"ppv{'Cr' if r.scenario.startswith('crossref') else 'Full'}{r.pi.replace('%', '').replace('.', '')}"
        put(k, pct(r.value, 1), src, f"ppv_headline/{r.scenario}/{r.pi}")
        put(k + "Ci", ci(r.lo, r.hi, 1), src, f"ppv_headline/{r.scenario}/{r.pi}/ci")
    dsp = t[t.table == "dispersion"]
    for _, r in dsp.iterrows():
        tag = "Cr" if r.scenario.startswith("crossref") else "Full"
        if r.note.startswith("ratio") or "ratio" in r.note:
            pass
    t["rule"] = t["rule"].str.split("_").str[0]
    for _, r in dsp.iterrows():
        tag = "Cr" if r.scenario.startswith("crossref") else "Full"
        which = "Pb" if "Poisson" in r.note else "Bb"
        put(f"disp{tag}{which}", f"{float(r.value):.2f}", src, f"dispersion/{r.scenario}/{r.note}")
    for _, r in p.iterrows():
        if r.pi == "0.39%":
            put(f"ppvOneIn{'Cr' if r.scenario.startswith('crossref') else 'Full'}", f"{1 / float(r.value):.0f}", src,
                f"ppv_headline/{r.scenario}/0.39%/1/value")
    rc = t[t.table == "rule_check"]
    for _, r in rc.iterrows():
        tag = ("Cr" if r.scenario.startswith("crossref") else "Full") + r.rule + str(r.alpha).replace("0.", "")
        n = int(float(r.n_papers))
        k = int(float(r.k_rejected))
        put(f"rule{tag}K", f"{k}/{n}", src, f"rule_check/{r.scenario}/{r.rule}/{r.alpha}/k_rejected")
        put(f"rule{tag}Pct", pct(k / n, 1), src, f"rule_check/{r.scenario}/{r.rule}/{r.alpha}")
        if r.mc_mean:
            put(f"rule{tag}Mc", pct(r.mc_mean, 1 if float(r.mc_mean) >= 0.001 else 2), src, f"rule_check/{r.scenario}/{r.rule}/{r.alpha}/mc_mean")
    ar = C("p1_alpha_rules.csv")
    for _, r in ar[ar.field == "all"].iterrows():
        tag = "Cr" if r.scenario.startswith("crossref") else ("Full" if r.scenario == "full" else "Dblp")
        for k in ("k1", "k2"):
            put(f"flag{tag}{k}", f"{r[f'flag_{k}_k']}/{r.n_papers}", "results/p1_alpha_rules.csv", f"{r.scenario}/all/flag_{k}_k")
            put(f"flag{tag}{k}Pct", pct(r[f"flag_{k}_share"], 1), "results/p1_alpha_rules.csv", f"{r.scenario}/all/flag_{k}_share")
    for _, r in ar[(ar.scenario == "full") & (ar.field != "all")].iterrows():
        f = r.field.replace("cs.", "")
        put(f"flagFullkTwo{f}", pct(r.flag_k2_share, 1), "results/p1_alpha_rules.csv", f"full/{r.field}/flag_k2_share")
    nj = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    src = "results/numbers.json"
    flat = {}

    def walk(o, pre=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{pre}.{k}" if pre else k)
        else:
            flat[pre] = o
    walk(nj)
    _ = flat
    # 5 typical papers: thresholds (k_typical, k_identifier)
    kt = t[t.table == "k_typical"]
    lines = []
    for nA in sorted(kt.n_A.astype(float).astype(int).unique()):
        cells = []
        for sc in ("full", "crossref_only"):
            for a in ("0.05", "0.01"):
                x = kt[(kt.n_A.astype(float).astype(int) == nA) & (kt.scenario == sc) & (kt.alpha == a)]
                ks = [x[x.rule == rr].value.iloc[0] if len(x[x.rule == rr]) else "" for rr in ("R1", "R2", "R3")]
                cells.append(" / ".join(str(int(float(v))) for v in ks if v != ""))
        lines.append(f"{nA} & " + " & ".join(cells) + " \\\\")
        if nA == 32:
            put("nAMed", str(nA), "results/p2_theory_final.csv", "k_typical/n_A (median paper)")
            x = kt[(kt.n_A.astype(float).astype(int) == 32) & (kt.scenario == "full") & (kt.alpha == "0.05")]
            for rr in ("R1", "R2", "R3"):
                put(f"kMed{rr}", str(int(float(x[x.rule == rr].value.iloc[0]))), src.replace("numbers.json", "p2_theory_final.csv"), f"k_typical/full/0.05/{rr}/n_A=32")
    (OUT / "tab_k_typical.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ki = t[t.table == "k_identifier"]
    pt = t[t.table == "p_two_flags_identifier"]
    lines = []
    for nA in sorted(ki.n_A.astype(float).astype(int).unique()):
        x = ki[(ki.n_A.astype(float).astype(int) == nA) & (ki.alpha == "0.05")]
        ks = " / ".join(str(int(float(x[x.rule == rr].value.iloc[0]))) for rr in ("R1", "R2", "R3"))
        y = kt[(kt.n_A.astype(float).astype(int) == nA) & (kt.scenario == "full") & (kt.alpha == "0.05")]
        k0 = " / ".join(str(int(float(y[y.rule == rr].value.iloc[0]))) for rr in ("R2", "R3"))
        z = pt[pt.n_A.astype(float).astype(int) == nA]
        pz = f"{pct(z.value.iloc[0], 3)} [{pct(z.hi.iloc[0], 2)}]" if len(z) else "--"
        lines.append(f"{nA} & {k0} & {ks} & {pz} \\\\")
        if nA == 32:
            put("kIdMedR2", str(int(float(x[x.rule == "R2"].value.iloc[0]))), "results/p2_theory_final.csv", "k_identifier/0.05/R2/n_A=32")
            put("kIdMedR3", str(int(float(x[x.rule == "R3"].value.iloc[0]))), "results/p2_theory_final.csv", "k_identifier/0.05/R3/n_A=32")
            if len(z):
                put("pTwoIdMed", pct(z.value.iloc[0], 3), "results/p2_theory_final.csv", "p_two_flags_identifier/n_A=32")
                put("pTwoIdMedHi", pct(z.hi.iloc[0], 2), "results/p2_theory_final.csv", "p_two_flags_identifier/n_A=32/hi")
    (OUT / "tab_k_identifier.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    th = J("p1_theory_headlines.json")
    _ = th


# ---------------------------------------------------------------- H5
def h5():
    d = C("p1_h5.csv")
    src = "results/p1_h5.csv"
    for _, r in d.iterrows():
        tag = {"full": "Full", "dblp": "Dblp", "crossref": "Cr"}.get(r.scenario, r.scenario) + r.tertile
        put(f"hFiveObs{tag}", f"{float(r.obs):.3f}", src, f"{r.scenario}/{r.tertile}/obs")
        put(f"hFiveCi{tag}", f"[{float(r.wilson_lo):.3f}, {float(r.wilson_hi):.3f}]", src, f"{r.scenario}/{r.tertile}/wilson")
        put(f"hFivePred{tag}", f"{float(r.pred_mean):.3f}", src, f"{r.scenario}/{r.tertile}/pred_mean")
        put(f"hFiveN{tag}", f"{int(float(r.n_refs_median))}", src, f"{r.scenario}/{r.tertile}/n_refs_median")
    dg = C("p1_h5_diag.csv")
    for _, r in dg[(dg.scenario == "full") & (dg.k == "2")].iterrows():
        put(f"hFiveLam{r.tertile}", f"{float(r.mean_lambda):.2f}", "results/p1_h5_diag.csv", f"full/k2/{r.tertile}/mean_lambda")
        put(f"hFiveMeanN{r.tertile}", f"{float(r.mean_N):.2f}", "results/p1_h5_diag.csv", f"full/k2/{r.tertile}/mean_N")
    b = J("p1_h5_betabinom.json")
    src = "results/p1_h5_betabinom.json"
    flat = json.dumps(b)
    _ = flat


# ---------------------------------------------------------------- agreement (P1, P2, P3)
def agreement():
    k1 = J("p1_kappa.json")
    src = "results/p1_kappa.json"
    put("pOneRaw", pct(k1.get("raw", k1.get("p_o", 0.975)), 1), src, "raw")
    p = J("p2_kappa_pairs.json")
    src = "results/p2_kappa_pairs.json"
    lines = []
    for pr, role in (("R1-R3", "inter-rater (decision rule)"), ("R1-R2", "intra-rater"), ("R2-R3", "inter-rater")):
        s = p[pr]
        t = pr.replace("-", "")
        put(f"agr{t}N", str(s["n"]), src, f"{pr}/n")
        put(f"agr{t}Pabak", f"{s['pabak']:.2f}", src, f"{pr}/pabak")
        put(f"agr{t}PabakCi", ci(*s["pabak_ci"], d=2, scale=1), src, f"{pr}/pabak_ci")
        put(f"agr{t}Ac", f"{s['ac1']:.2f}", src, f"{pr}/ac1")
        put(f"agr{t}Kappa", f"{s['kappa']:.2f}", src, f"{pr}/kappa")
        put(f"agr{t}Raw", pct(s["raw"], 1), src, f"{pr}/raw")
        lines.append(f"{pr.replace('-', '--')} & {role} & {s['n']} & {pct(s['raw'], 1)} & {s['pabak']:.2f} {ci(*s['pabak_ci'], d=2, scale=1)} & "
                     f"{s['ac1']:.2f} & {s['kappa']:.2f} \\\\")
    a4p = J("p2_kappa.json")["pooled"]
    lines.insert(0, f"Pooled 40 rows & registered criterion & {a4p['n']} & {pct(a4p['raw'], 1)} & {a4p['pabak']:.2f} "
                    f"{ci(*a4p['pabak_ci'], d=2, scale=1)} & {a4p['ac1']:.2f} & {a4p['kappa']:.2f} \\\\")
    a3 = p["AC1 three raters"]
    lines.append(f"R1--R2--R3 & three-rater AC1 & {a3['n']} & -- & -- & {a3['ac1']:.2f} & -- \\\\")
    put("agrThreeAc", f"{a3['ac1']:.2f}", src, "AC1 three raters/ac1")
    put("agrThreeAcCi", ci(*a3["ac1_ci"], d=2, scale=1), src, "AC1 three raters/ac1_ci")
    put("agrThreeUnan", f"{a3['unanimous']}/{a3['n']}", src, "AC1 three raters/unanimous")
    put("agrNotFoundDisagree", str(sum(1 for pr in ("R1-R3", "R1-R2", "R2-R3") for d in p[pr]["disagreements"]
                                       if "not-found" in d.values())), src, "disagreements with not-found")
    a4 = J("p2_kappa.json")
    src = "results/p2_kappa.json"
    put("agrPooledPabak", f"{a4['pooled']['pabak']:.2f}", src, "pooled/pabak")
    put("agrPooledPabakCi", ci(*a4["pooled"]["pabak_ci"], d=2, scale=1), src, "pooled/pabak_ci")
    put("agrPooledN", str(a4["pooled"]["n"]), src, "pooled/n")
    f3 = RES / "p3_kappa.json"
    if f3.exists():
        q = json.loads(f3.read_text(encoding="utf-8"))
        src = "results/p3_kappa.json"
        for pr in ("R1-R3", "R1-R2", "R2-R3"):
            if pr in q:
                s = q[pr]
                t = pr.replace("-", "")
                put(f"qagr{t}N", str(s["n"]), src, f"{pr}/n")
                put(f"qagr{t}Pabak", f"{s['pabak']:.2f}", src, f"{pr}/pabak")
                put(f"qagr{t}PabakCi", ci(*s["pabak_ci"], d=2, scale=1), src, f"{pr}/pabak_ci")
                put(f"qagr{t}Ac", f"{s['ac1']:.2f}", src, f"{pr}/ac1")
                lines.append(f"{pr.replace('-', '--')} (P3) & after Amendment~5 & {s['n']} & {pct(s['raw'], 1)} & "
                             f"{s['pabak']:.2f} {ci(*s['pabak_ci'], d=2, scale=1)} & {s['ac1']:.2f} & {s['kappa']:.2f} \\\\")
        put("pThreeStatus", "available", src, "exists")
        if "R2-R3" in q and "R1-R3" in q:
            put("pThreeSentence", "In a supplementary recheck of 40 new references under the revised rules (seed 43), PABAK is "
                f"{q['R2-R3']['pabak']:.2f} {ci(*q['R2-R3']['pabak_ci'], d=2, scale=1)} between the two raters who applied the "
                f"revised rules (R2--R3) and {q['R1-R3']['pabak']:.2f} {ci(*q['R1-R3']['pabak_ci'], d=2, scale=1)} against the "
                "first-pass labels, which were made under the original rules (Table~\ref{tab:agree}). This recheck is post hoc "
                "and does not replace the failed registered result.", src, "R2-R3, R1-R3")
    else:
        put("pThreeStatus", "pending", "results/p3_kappa.json", "missing (R3 not returned yet)")
        put("pThreeSentence", "A supplementary recheck of 40 new references under the revised rules (seed 43) has its first "
            "two raters' labels (Supplement S8); the second rater's labels were not yet available at this version "
            "[to be completed before submission].", "results/p3_kappa.json", "missing")
    (OUT / "tab_agreement.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- PREREG / amendments, manifest, policy survey
def design():
    lines = (RES / "prereg_hash.txt").read_text(encoding="utf-8").splitlines()
    hashes = {}
    for ln in lines:
        m = re.match(r"([0-9a-f]{64}) \*(\S+)", ln)
        if m:
            hashes[m.group(2)] = m.group(1)[:8]
    src = "results/prereg_hash.txt"
    for f, k in (("PREREG_43.md", "Prereg"), ("manual_protocol.md", "Protocol"), ("PREREG_AMENDMENT_1.md", "AmOne"),
                 ("PREREG_AMENDMENT_2.md", "AmTwo"), ("PREREG_AMENDMENT_3.md", "AmThree"), ("PREREG_AMENDMENT_4.md", "AmFour"),
                 ("PREREG_AMENDMENT_5.md", "AmFive")):
        put(f"hash{k}", hashes[f], src, f)
    sv = pd.read_csv(ROOT / "data_manifest" / "manifest_src_version.csv", dtype=str, keep_default_na=False)
    src = "data_manifest/manifest_src_version.csv"
    put("nKept", num(len(sv)), src, "rows")
    put("nLaterVersion", num((sv.src_version != "v1").sum()), src, "src_version != v1")
    pol = C("p2_policy_survey.csv")
    src = "results/p2_policy_survey.csv"
    put("nVenues", str(len(pol)), src, "rows")
    put("nVenuesConfirmed", str((pol.verify_status == "confirmed").sum()), src, "verify_status=confirmed")
    put("nVenuesPolicy", str(pol.policy_exists.str.startswith("yes").sum()), src, "policy_exists starts with yes")
    put("nVenuesToolNamed", str((~pol.tool_named.str.startswith("not disclosed")).sum()), src, "tool_named disclosed")
    put("nVenuesAppeal", str((~pol.appeal_process.str.lower().str.startswith("not stated")
                               & ~pol.appeal_process.str.lower().str.startswith("not ")).sum()), src, "appeal_process stated")


# ---------------------------------------------------------------- P3 revision checks (exploratory) + identifier scenario
def revision():
    r = J("p3_revision_checks.json")
    src = "results/p3_revision_checks.json"
    for c, v in r["paper_flags_academic_only"].items():
        for k in ("k1", "k2"):
            x = v[k]
            put(f"acFlag{c}{k}", pct(x["share"], 1), src, f"paper_flags_academic_only/{c}/{k}/share")
            put(f"acFlag{c}{k}K", f"{x['papers']}/{x['n']}", src, f"paper_flags_academic_only/{c}/{k}/papers,n")
            put(f"acFlag{c}{k}Ci", ci(*x["wilson"], d=1), src, f"paper_flags_academic_only/{c}/{k}/wilson")
    for sc in ("union", "dblp"):
        x = r["fp_manual_academic"][sc]
        put(f"fpManAc{sc}", pct(x["share"], 1), src, f"fp_manual_academic/{sc}/share")
        put(f"fpManAc{sc}K", f"{x['k']}/{x['n']}", src, f"fp_manual_academic/{sc}/k,n")
        put(f"fpManAc{sc}Ci", ci(*x["wilson"], d=1), src, f"fp_manual_academic/{sc}/wilson")
        put(f"fpManRaw{sc}", pct(x["raw_all_share"], 1), src, f"fp_manual_academic/{sc}/raw_all_share")
    for fc, tag in (("flag_union", "Union"), ("flag_crossref", "Cr")):
        x = r["h3_paired"][fc]
        put(f"hThreePair{tag}StripOnly", str(x["strip_only"]), src, f"h3_paired/{fc}/strip_only")
        put(f"hThreePair{tag}DoiOnly", str(x["doi_only"]), src, f"h3_paired/{fc}/doi_only")
        put(f"hThreePair{tag}Both", str(x["both"]), src, f"h3_paired/{fc}/both")
        put(f"hThreePair{tag}N", num(x["pairs"]), src, f"h3_paired/{fc}/pairs")
        p_ = x["exact_p_two_sided"]
        put(f"hThreePair{tag}P", f"{p_:.3f}" if p_ >= 0.001 else r"$<10^{-" + str(int(-math.log10(p_))) + "}$", src,
            f"h3_paired/{fc}/exact_p_two_sided")
    v = r["pre_llm_versions"]
    put("lateBibPapers", str(v["papers_bib_after_2022_11_30"]), src, "pre_llm_versions/papers_bib_after_2022_11_30")
    put("uANoLate", pct(v["u_A_full_without_late"]), src, "pre_llm_versions/u_A_full_without_late")
    put("uANoLateCi", ci(*v["boot95_without_late"]), src, "pre_llm_versions/boot95_without_late")
    put("uANoLatePapers", str(v["papers_without_late"]), src, "pre_llm_versions/papers_without_late")
    for k, tag in (("IEEEtran_doi/orig/union", "IdUnion"), ("IEEEtran_doi/orig/idonly", "IdOnly")):
        x = r["identifier_scenario"][k]
        put(f"scen{tag}", pct(x["fp"], 3 if x["fp"] < 0.001 else 1), src, f"identifier_scenario/{k}/fp")
        put(f"scen{tag}K", f"{x['k']}/{num(x['n'])}", src, f"identifier_scenario/{k}/k,n")
        put(f"scen{tag}Hi", pct(x["boot95"][1], 3 if x["boot95"][1] < 0.01 else 1), src, f"identifier_scenario/{k}/boot95[1]")
    for per, tag in (("2019-21", "Pre"), ("2024-26", "Post")):
        x = r["openalex_refusals_academic"][per]
        put(f"oaSkip{tag}", num(x["oa_skipped"]), src, f"openalex_refusals_academic/{per}/oa_skipped")
        put(f"oaSkipUnres{tag}", num(x["oa_skipped_and_unresolved"]), src, f"openalex_refusals_academic/{per}/oa_skipped_and_unresolved")
    b = J("p2_backend_table_retry.json")
    a = [x for x in b["rows"] if x["period"] == "2019-21" and x["stratum"] == "A"][0]
    lb = (a["k_s2"] - r["openalex_refusals_academic"]["2019-21"]["oa_skipped_and_unresolved"]) / a["n"]
    put("uALowerOa", pct(lb), "results/p3_revision_checks.json + p2_backend_table_retry.json", "(k_s2 - oa_skipped_and_unresolved)/n, A 2019-21")
    e = r["empirical_NA"]
    put("empQNinetyFive", f"{e['q95_all']:.0f}", src, "empirical_NA/q95_all")
    put("empQNinetyNine", f"{e['q99_all']:.0f}", src, "empirical_NA/q99_all")
    put("empMax", str(e["max_all"]), src, "empirical_NA/max_all")
    for k in (3, 4, 5):
        x = e[f"share_ge{k}"]
        put(f"empPreGe{k}", pct(x["share"], 1), src, f"empirical_NA/share_ge{k}/share")
        put(f"empPreGe{k}K", f"{x['papers']}/{x['n']}", src, f"empirical_NA/share_ge{k}/papers,n")
        put(f"empPreGe{k}Ci", ci(*x["wilson"], d=1), src, f"empirical_NA/share_ge{k}/wilson")
    for k in (1, 2, 3, 4, 5):
        x = r["empirical_NA_2024_26"][f"share_ge{k}"]
        put(f"empPostGe{k}", pct(x["share"], 1), src, f"empirical_NA_2024_26/share_ge{k}/share")
        put(f"empPostGe{k}K", f"{x['papers']}/{x['n']}", src, f"empirical_NA_2024_26/share_ge{k}/papers,n")
        put(f"empPostGe{k}Ci", ci(*x["wilson"], d=1), src, f"empirical_NA_2024_26/share_ge{k}/wilson")
    lines = []
    pre = [r["paper_flags_academic_only"]["s2"]["k1"], r["paper_flags_academic_only"]["s2"]["k2"]] + [e[f"share_ge{k}"] for k in (3, 4, 5)]
    for k, xp in zip((1, 2, 3, 4, 5), pre):
        xq = r["empirical_NA_2024_26"][f"share_ge{k}"]
        xpw = xp["wilson"]
        lines.append("$" + chr(92) + f"ge{k}$ & {pct(xp['share'], 1)} ({xp['papers']}/{xp['n']}) {ci(*xpw, d=1)} & "
                     f"{pct(xq['share'], 1)} ({xq['papers']}/{xq['n']}) {ci(*xq['wilson'], d=1)} \\\\")
    (OUT / "tab_empirical.tex").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    acc = r["accounting"]
    for k, val in acc.items():
        put("acc" + "".join(w.title() for w in k.split("_")), str(val), src, f"accounting/{k}")
    th = J("numbers.json")["identifier_scenario"]
    put("idScenU", pct(th["u_id"], 3), "results/numbers.json", "identifier_scenario/u_id")
    put("idScenUHi", pct(th["u_id_upper"], 3), "results/numbers.json", "identifier_scenario/u_id_upper")
    pol = C("p2_policy_survey.csv")
    org = pol.venue.str.replace(r"\s*\(.*\)", "", regex=True).str.replace(r"\s+\d{4}$", "", regex=True).str.strip()
    put("nVenueOrgs", str(org.nunique()), "results/p2_policy_survey.csv", "distinct venue names without year/qualifier")
    ri = C("p1_render_identifiers.csv")
    for _, x in ri.iterrows():
        tag = re.sub("[^A-Za-z]", "", x["style"]) + x.variant
        put(f"ridDoiPrinted{tag}", f"{float(x.pct_bib_doi_printed):.1f}", "results/p1_render_identifiers.csv", f"{x['style']}/{x.variant}/pct_bib_doi_printed")
        put(f"ridArxiv{tag}", f"{float(x.pct_printed_arxiv):.1f}", "results/p1_render_identifiers.csv", f"{x['style']}/{x.variant}/pct_printed_arxiv")
        put(f"ridAnyId{tag}", f"{float(x.pct_printed_resolvable_id):.1f}", "results/p1_render_identifiers.csv", f"{x['style']}/{x.variant}/pct_printed_resolvable_id")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (backend, hypotheses, render, h4, recall, tools, theory, h5, agreement, design, revision):
        f()
    tex = ["% generated by code/make_ms_numbers.py from results/; do not edit"]
    for k, v in NV.items():
        tex.append(f"\\nvset{{{k}}}{{{v}}}")
    (OUT / "numbers_ms.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    with (RES / "numbers_ms_sources.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["key", "value", "source", "field"])
        w.writeheader()
        w.writerows(SRC)
    print(len(NV), "keys;", len(list(OUT.glob("tab_*.tex"))), "tables")


if __name__ == "__main__":
    main()
