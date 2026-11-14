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
# P3E (PREREG_AMENDMENT_7 (a)): every number comes from the completed ground truth. A result file <stem>_p3e.<ext>
# (code/p3e_recompute.py) replaces <stem>.<ext>, and in numbers.json a key k_p3e replaces k. MS_V12=1 rebuilds v1.2.
P3E = __import__("os").environ.get("MS_V12", "0") != "1"


def _pick(f):
    q = RES / f"{Path(f).stem}_p3e{Path(f).suffix}"
    return q if (P3E and q.exists()) else RES / f


def J(f):
    d = json.loads(_pick(f).read_text(encoding="utf-8"))
    if f == "numbers.json":
        if P3E:
            d = {**{k: v for k, v in d.items() if not k.endswith("_p3e")},
                 **{k[:-4]: v for k, v in d.items() if k.endswith("_p3e")}}
        else:
            d = {k: v for k, v in d.items() if not k.endswith("_p3e")}
    return d


def C(f):
    return pd.read_csv(_pick(f), dtype=str, keep_default_na=False)


def _src(src):
    """Name the _p3e file in the evidence column when that is the file read."""
    def rep(m):
        f = m.group(1)
        return f"results/{_pick(f).name}" if f != "numbers.json" else "results/numbers.json" + (" (keys *_p3e)" if P3E else "")
    return re.sub(r"results/([\w.]+\.(?:json|csv))", rep, src)


def put(key, val, src, field=""):
    if key in NV and NV[key] != val:
        raise SystemExit(f"duplicate key with different value: {key}")
    NV[key] = val
    SRC.append(dict(key=key, value=val, source=_src(src), field=field))


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
        if c == "s2":  # R2 Q9: power to see the 0.39-point excess of Zhao et al. at this precision (normal approximation)
            from scipy.stats import norm
            se = (hi - lo) / (2 * 1.959964)
            put("perPowerZhao", f"{100 * (1 - norm.cdf(1.959964 - 0.39 / se)):.0f}", src,
                f"{r['column']}/diff_boot_pp: se = width/3.92; power = 1 - Phi(1.96 - 0.39/se)")
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
        # R2 Q18: pi is borrowed from another pipeline, so the ceilings are printed as orders of magnitude (whole %)
        d0 = 0 if (not P3E or float(r.value) >= 0.1) else 1
        put(k, pct(r.value, 1 if not P3E else d0), src, f"ppv_headline/{r.scenario}/{r.pi}")
        put(k + "Ci", ci(r.lo, r.hi, 1 if not P3E else d0), src, f"ppv_headline/{r.scenario}/{r.pi}/ci")
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
    # erratum (P3D): rules, thresholds and identifier tables come from p3d_theory_fix.csv; p2_theory_final.csv keeps the earlier values
    fix = C("p3d_theory_fix.csv")
    fix["rule"] = fix["rule"].str.split("_").str[0]
    fsrc = "results/p3d_theory_fix.csv"
    rc = fix[fix.table == "rule_check"]
    for _, r in rc.iterrows():
        tag = {"crossref_only": "Cr", "plus_dblp": "Dblp", "full": "Full"}[r.scenario] + r.rule + str(r.alpha).replace("0.", "")
        n = int(float(r.n_papers))
        k = int(float(r.k_rejected))
        put(f"rule{tag}K", f"{k}/{n}", fsrc, f"rule_check/{r.scenario}/{r.rule}/{r.alpha}/k_rejected")
        put(f"rule{tag}Pct", pct(k / n, 1), fsrc, f"rule_check/{r.scenario}/{r.rule}/{r.alpha}")
        put(f"rule{tag}Ci", ci(r.lo, r.hi, 1), fsrc, f"rule_check/{r.scenario}/{r.rule}/{r.alpha}/wilson")
        if r.mc_mean:
            put(f"rule{tag}Mc", pct(r.mc_mean, 1 if float(r.mc_mean) >= 0.001 else 2), fsrc, f"rule_check/{r.scenario}/{r.rule}/{r.alpha}/mc_mean")
        p_ = float(r.p_one_sided)
        put(f"rule{tag}P", f"{p_:.2f}" if p_ >= 0.01 else r"$<10^{-" + str(int(-math.log10(p_))) + "}$", fsrc,
            f"rule_check/{r.scenario}/{r.rule}/{r.alpha}/p_one_sided")
    ar = C("p1_alpha_rules.csv")
    for _, r in ar[ar.field == "all"].iterrows():
        tag = "Cr" if r.scenario.startswith("crossref") else ("Full" if r.scenario == "full" else "Dblp")
        for k in ("k1", "k2"):
            put(f"flag{tag}{k}", f"{r[f'flag_{k}_k']}/{r.n_papers}", "results/p1_alpha_rules.csv", f"{r.scenario}/all/flag_{k}_k")
            put(f"flag{tag}{k}Pct", pct(r[f"flag_{k}_share"], 1), "results/p1_alpha_rules.csv", f"{r.scenario}/all/flag_{k}_share")
    for _, r in ar[(ar.scenario == "full") & (ar.field != "all")].iterrows():
        f = r.field.replace("cs.", "")
        put(f"flagFullkTwo{f}", pct(r.flag_k2_share, 1), "results/p1_alpha_rules.csv", f"full/{r.field}/flag_k2_share")
    nj = J("numbers.json")
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
    kt = fix[(fix.table == "k_typical") & (fix.scenario != "plus_dblp")]
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
            put("nAMed", str(nA), fsrc, "k_typical/n_A (median paper)")
            x = kt[(kt.n_A.astype(float).astype(int) == 32) & (kt.scenario == "full") & (kt.alpha == "0.05")]
            for rr in ("R1", "R2", "R3"):
                put(f"kMed{rr}", str(int(float(x[x.rule == rr].value.iloc[0]))), fsrc, f"k_typical/full/0.05/{rr}/n_A=32")
    (OUT / "tab_k_typical.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ki = fix[(fix.table == "k_identifier") & (fix.scenario == "identifier")]
    pt = fix[(fix.table == "p_two_flags_identifier") & (fix.scenario == "identifier")]
    kio = fix[(fix.table == "k_identifier") & (fix.scenario == "identifier_only")]
    pio = fix[(fix.table == "p_two_flags_identifier") & (fix.scenario == "identifier_only")]
    lines = []
    for nA in sorted(ki.n_A.astype(float).astype(int).unique()):
        x = ki[(ki.n_A.astype(float).astype(int) == nA) & (ki.alpha == "0.05")]
        ks = " / ".join(str(int(float(x[x.rule == rr].value.iloc[0]))) for rr in ("R1", "R2", "R3"))
        y = kt[(kt.n_A.astype(float).astype(int) == nA) & (kt.scenario == "full") & (kt.alpha == "0.05")]
        k0 = " / ".join(str(int(float(y[y.rule == rr].value.iloc[0]))) for rr in ("R2", "R3"))
        z = pt[pt.n_A.astype(float).astype(int) == nA]
        pz = f"{pct(z.value.iloc[0], 3)} [{pct(z.hi.iloc[0], 2)}]" if len(z) else "--"
        xo = kio[(kio.n_A.astype(float).astype(int) == nA) & (kio.alpha == "0.05")]
        ko = " / ".join(str(int(float(xo[xo.rule == rr].value.iloc[0]))) for rr in ("R1", "R2", "R3"))
        if P3E and _pick("p3e_exploratory.json").exists():  # Amendment 7 (d)6: the union thresholds at rho = 0 as well
            d6 = J("p3e_exploratory.json")["d6"]["identifier"][str(nA)]["a0.05"]["rho0"]
            r0 = f"{d6['R2']} / {d6['R3']}"
            lines.append(f"{nA} & {k0} & {r0} & {ks} & {pz} & {ko} \\\\")
            if nA == 32:
                put("kIdRhoZeroMedRtwo", str(d6["R2"]), "results/p3e_exploratory.json", "d6/identifier/32/a0.05/rho0/R2")
                put("kIdRhoZeroMedRthree", str(d6["R3"]), "results/p3e_exploratory.json", "d6/identifier/32/a0.05/rho0/R3")
        else:
            lines.append(f"{nA} & {k0} & {ks} & {pz} & {ko} \\\\")
        if nA == 32:
            put("kIdMedR2", str(int(float(x[x.rule == "R2"].value.iloc[0]))), fsrc, "k_identifier/identifier/0.05/R2/n_A=32")
            put("kIdMedR3", str(int(float(x[x.rule == "R3"].value.iloc[0]))), fsrc, "k_identifier/identifier/0.05/R3/n_A=32")
            for rr in ("R1", "R2", "R3"):
                put(f"kIdOnlyMed{rr}", str(int(float(xo[xo.rule == rr].value.iloc[0]))), fsrc, f"k_identifier/identifier_only/0.05/{rr}/n_A=32")
            zo = pio[pio.n_A.astype(float).astype(int) == nA]
            put("pTwoIdOnlyMed", pct(zo.value.iloc[0], 1), fsrc, "p_two_flags_identifier/identifier_only/n_A=32")
            if len(z):
                put("pTwoIdMed", pct(z.value.iloc[0], 3), fsrc, "p_two_flags_identifier/identifier/n_A=32")
                put("pTwoIdMedHi", pct(z.hi.iloc[0], 2), fsrc, "p_two_flags_identifier/identifier/n_A=32/hi")
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
    f3 = _pick("p3_recheck_stats.json")
    if f3.exists():
        q = json.loads(f3.read_text(encoding="utf-8"))
        src = "results/p3_recheck_stats.json"
        fl = q["flat"]
        for t in ("r1r2", "r1r3", "r2r3"):
            T = t.upper()
            put(f"rph{T}Pabak", f"{fl[f'recheck_posthoc_{t}_pabak']:.2f}", src, f"flat/recheck_posthoc_{t}_pabak")
            put(f"rph{T}Disagree", str(fl[f"recheck_posthoc_{t}_disagree_n"]), src, f"flat/recheck_posthoc_{t}_disagree_n")
        lo = fl["recheck_posthoc_r1r3_pabak_cp_lower"]
        put("rphPabakCpLo", f"{lo:.2f}", src, "flat/recheck_posthoc_r1r3_pabak_cp_lower")
        put("rphBinPabakCpLo", f"{q['R1-R3']['bin_pabak_cp_lower']:.2f}", src, "R1-R3/bin_pabak_cp_lower")
        put("rphDisCpUp", pct(q["R1-R3"]["disagree_cp_upper"], 1), src, "R1-R3/disagree_cp_upper")
        put("rphThreeAc", f"{fl['recheck_posthoc_three_ac1']:.2f}", src, "flat/recheck_posthoc_three_ac1")
        put("rphUnan", f"{fl['recheck_posthoc_three_unanimous']}/{fl['recheck_posthoc_n']}", src,
            "flat/recheck_posthoc_three_unanimous")
        put("rphN", str(fl["recheck_posthoc_n"]), src, "flat/recheck_posthoc_n")
        put("rphPapers", str(fl["recheck_posthoc_n_papers"]), src, "flat/recheck_posthoc_n_papers")
        put("rphROneNonExists", str(fl["recheck_posthoc_r1_nonexists"]), src, "flat/recheck_posthoc_r1_nonexists")
        rn = q["routes"]["N"]
        put("rphNStratum", str(rn["n"]), src, "routes/N/n")
        put("rphNTierSW", str(rn["tiers"].get("S", 0) + rn["tiers"].get("W", 0)), src, "routes/N/tiers S+W")
        for k in ("direct", "moved", "secondary"):
            put(f"rphNRthree{k.capitalize()}", str(rn["r3_route"].get(k, 0)), src, f"routes/N/r3_route/{k}")
        put("rphNRtwoArchived", str(rn["r2_route"].get("archived", 0)), src, "routes/N/r2_route/archived")
        put("rphNAnyIndirect", str(fl["recheck_posthoc_n_any_indirect"]), src, "flat/recheck_posthoc_n_any_indirect")
        put("rphNReview", str(len(rn["r3_review_secondary"])), src, "routes/N/r3_review_secondary")
        put("rphDefects", str(q["routes"]["N"]["entry_defect"] + q["routes"]["E"]["entry_defect"]), src,
            "routes/*/entry_defect")
        k3 = "undefined" if not fl["recheck_posthoc_r1r3_kappa_defined"] else f"{q['R1-R3']['kappa']:.2f}"
        lines.append(f"R1--R2--R3, post hoc$^{{a}}$ & after Amendment~5, new rows & {q['n']} & "
                     f"{pct(q['R1-R3']['raw'], 1)} & {fl['recheck_posthoc_r1r3_pabak']:.2f} [{lo:.2f}, 1.00]$^{{b}}$ & "
                     f"{fl['recheck_posthoc_three_ac1']:.2f} & {k3} \\\\")
        put("pThreeStatus", "available", src, "exists")
        put("pThreeSentence", f"A supplementary recheck after Amendment~5 drew {q['n']} new references from "
            f"{q['n_papers']} papers (seed 43) and was rated blind by R2 and R3 under the revised rules. All three raters "
            f"labelled all {q['n']} references \emph{{exists}}: every pairwise PABAK is "
            f"{fl['recheck_posthoc_r1r3_pabak']:.2f} (exact 95\% lower bound {lo:.2f}; $\kappa$ undefined), which meets "
            "the 0.8 bar post hoc. The result is narrower than it looks: no first-pass label in the pool was "
            "\emph{not-found} or \emph{ambiguous}, so the not-exists side of the stratification was filled with "
            "references the screen left unresolved, and the recheck tests agreement on real references only. This "
            "recheck does not replace the failed registered result.", src, "R1-R3, n, n_papers")
    else:
        put("pThreeStatus", "pending", "results/p3_recheck_stats.json", "missing (R3 not returned yet)")
        put("pThreeSentence", "A supplementary recheck of 40 new references under the revised rules (seed 43) has its first "
            "two raters' labels (Supplement S8); the second rater's labels were not yet available at this version "
            "[to be completed before submission].", "results/p3_recheck_stats.json", "missing")
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
                 ("PREREG_AMENDMENT_5.md", "AmFive"), ("PREREG_AMENDMENT_7.md", "AmSeven"),
                 ("P3E/AMENDMENT_7_ADDENDUM.md", "AmSevenA")):  # addendum A: part of Amendment 7, not an eighth
        put(f"hash{k}", hashes[f], src, f)
    # Amendment 6 was hashed in the phase log, not in prereg_hash.txt: the prefix is the sha256 of the file itself
    import hashlib
    put("hashAmSix", hashlib.sha256((ROOT / "PREREG_AMENDMENT_6.md").read_bytes()).hexdigest()[:8],
        "PREREG_AMENDMENT_6.md", "sha256 of the file")
    put("nAmendments", "eight", src, "Amendments 1-8")
    # written after interim or review results (Table 3, column "Known when written"): Amendments 2-7
    put("nAmendmentsAfter", "seven", src, "Amendments 2-8")
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
    # R2 Q17(d): count only official statements that could be read; news reports and an unfetchable page are listed
    ok = (pol.source_type == "official") & (pol.verify_status != "not-found-at-source")
    po = pol[ok]
    s = "results/p2_policy_survey.csv"
    put("nVenOff", str(int(ok.sum())), s, "source_type=official and verify_status!=not-found-at-source")
    put("nVenOffOrgs", str(org[ok].nunique()), s, "distinct venue names of those rows")
    put("nVenNews", str(int((pol.source_type == "news").sum())), s, "source_type=news")
    put("nVenNotFound", str(int((pol.verify_status == "not-found-at-source").sum())), s, "verify_status=not-found-at-source")
    put("nVenOffPolicy", str(int(po.policy_exists.str.startswith("yes").sum())), s, "official rows, policy_exists starts with yes")
    put("nVenOffTool", str(int((~po.tool_named.str.startswith("not disclosed")).sum())), s, "official rows, tool disclosed")
    put("nVenOffAppeal", str(int((~po.appeal_process.str.lower().str.startswith("not ")).sum())), s,
        "official rows, appeal_process stated")
    ri = C("p1_render_identifiers.csv")
    for _, x in ri.iterrows():
        tag = re.sub("[^A-Za-z]", "", x["style"]) + x.variant
        put(f"ridDoiPrinted{tag}", f"{float(x.pct_bib_doi_printed):.1f}", "results/p1_render_identifiers.csv", f"{x['style']}/{x.variant}/pct_bib_doi_printed")
        put(f"ridArxiv{tag}", f"{float(x.pct_printed_arxiv):.1f}", "results/p1_render_identifiers.csv", f"{x['style']}/{x.variant}/pct_printed_arxiv")
        put(f"ridAnyId{tag}", f"{float(x.pct_printed_resolvable_id):.1f}", "results/p1_render_identifiers.csv", f"{x['style']}/{x.variant}/pct_printed_resolvable_id")


# ---------------------------------------------------------------- P3E (Amendment 7): completion, exploratory, human check
def _orig(f):
    return json.loads((RES / f).read_text(encoding="utf-8"))


def _date(s):
    import datetime as dt
    d = dt.date.fromisoformat(s[:10])
    return f"{d.day} {d.strftime('%B')} {d.year}"


def p3e_block():
    if not P3E:
        return
    # before completion (the v1.2 files, kept unchanged) and after
    b0 = {(r["period"], r["stratum"]): r for r in _orig("p2_backend_table_retry.json")["rows"]}
    s0 = "results/p2_backend_table_retry.json (before completion)"
    put("uAPres2Before", pct(b0[("2019-21", "A")]["u_s2"]), s0, "2019-21/A/u_s2")
    r0 = _orig("p3_revision_checks.json")["openalex_refusals_academic"]
    s0 = "results/p3_revision_checks.json (before completion)"
    put("oaSkipUnresPreBefore", num(r0["2019-21"]["oa_skipped_and_unresolved"]), s0, "2019-21/oa_skipped_and_unresolved")
    put("oaSkipPreBefore", num(r0["2019-21"]["oa_skipped"]), s0, "2019-21/oa_skipped")
    put("oaSkipPostBefore", num(r0["2024-26"]["oa_skipped"]), s0, "2024-26/oa_skipped")
    r = J("p3_revision_checks.json")["openalex_refusals_academic"]
    src = "results/p3_revision_checks.json"
    left_pre = int(r["2019-21"]["oa_skipped_and_unresolved"])
    put("oaLeftUnresPre", num(left_pre), src, "2019-21/oa_skipped_and_unresolved (after completion)")
    put("oaLeftUnresPost", num(r["2024-26"]["oa_skipped_and_unresolved"]), src, "2024-26/oa_skipped_and_unresolved")
    put("absOaClause", "" if left_pre == 0 else
        f" ({NV['uALowerOa']}\\% if the {num(left_pre)} references that OpenAlex never answered all resolve)", src,
        "2019-21 oa_skipped_and_unresolved > 0")
    cs = _pick("p3e_cascade_summary.json")
    if cs.exists():
        c = json.loads(cs.read_text(encoding="utf-8"))
        put("cacheLastDate", _date(c["cache_last_date"]), "results/p3e_cascade_summary.json", "cache_last_date")
    x = J("p3e_exploratory.json")
    src = "results/p3e_exploratory.json"
    # R2 Q18: the tier weights of FP_manual (corpus share of each tier among identifier-free references)
    w = J("p1_h4_bias.json")["H4"]["union"]["weights"]
    put("hFourWeights", ", ".join(f"{t} {100 * w[t]:.1f}" for t in ("J", "C", "P", "B", "S", "W")) + "\\%",
        "results/p1_h4_bias.json", "H4/union/weights")
    # H1 without DBLP (registered backends), d7
    d7 = x["d7"]
    put("hOneNoDblpLo", pct(d7["u_lower"]), src, "d7/u_lower")
    put("hOneNoDblpHi", pct(d7["u_upper"]), src, "d7/u_upper")
    put("hOneNoDblpVerdict", "PASS" if d7["h1_upper_in_window"] and d7["h1_lower_in_window"] else
        ("FAIL" if not (d7["h1_upper_in_window"] or d7["h1_lower_in_window"]) else "undetermined"), src, "d7/h1_*_in_window")
    put("hOneNoDblpWhere", "inside the window" if d7["h1_upper_in_window"] and d7["h1_lower_in_window"] else
        ("outside the window" if not (d7["h1_upper_in_window"] or d7["h1_lower_in_window"]) else
         "partly outside the window"), src, "d7/h1_*_in_window")
    # empirical thresholds, d5
    d5 = x["d5"]
    for sc, tg in (("full", "Full"), ("crossref_only", "Cr")):
        for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
            for a, at in (("0.05", "Five"), ("0.01", "One")):
                put(f"kEmp{tg}{pt}{at}", str(d5[sc][f"{per}/all/a{a}"]["k_emp"]), src, f"d5/{sc}/{per}/all/a{a}/k_emp")
    allk = [d5[sc][f"{per}/all/a{a}"]["k_emp"] for sc in ("full", "crossref_only") for per in ("2019-21", "2024-26")
            for a in ("0.05", "0.01")]
    put("kEmpVsDeployed", "The deployed thresholds of one to three flags lie below every one of them." if min(allk) > 3
        else f"The smallest of them, {min(allk)}, lies within the deployed range of one to three flags.", src,
        "d5: min k_emp over the all-papers cells")
    cuts = d5["full"]["tertile_cuts_nA"]
    put("kEmpCuts", f"$n_A\\le{cuts[0]:.0f}$, ${cuts[0]:.0f}<n_A\\le{cuts[1]:.0f}$, $n_A>{cuts[1]:.0f}$", src, "d5/full/tertile_cuts_nA")
    lines = []
    lab = {"all": "all", "T1": f"$n_A\\le{cuts[0]:.0f}$", "T2": f"${cuts[0]:.0f}<n_A\\le{cuts[1]:.0f}$",
           "T3": f"$n_A>{cuts[1]:.0f}$"}
    for per, pn in (("2019-21", "2019--21 (in sample)"), ("2024-26", "2024--26 (hold-out)")):
        for i, b in enumerate(("all", "T1", "T2", "T3")):
            cells = []
            for sc in ("full", "crossref_only"):
                for a in ("0.05", "0.01"):
                    e = d5[sc][f"{per}/{b}/a{a}"]
                    cells.append(f"{e['k_emp']} ({pct(e['share_at_k'], 1)})" if e["k_emp"] else "--")
            n = d5["full"][f"{per}/{b}/a0.05"]["n_papers"]
            lines.append(f"{pn if i == 0 else ''} & {lab[b]} ({n}) & " + " & ".join(cells) + " \\\\")
        if per == "2019-21":
            lines.append("\\midrule")
    (OUT / "tab_kemp.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Bonferroni, d4
    d4 = x["d4"]["full"]
    for rule, tg in (("R1_CI", "Rone"), ("R2_betaq", "Rtwo"), ("R3_cantelli", "Rthree")):
        put(f"bonfKMed{tg}", str(d4["k_typical"][f"{rule}_a0.05"]["32"]), src, f"d4/full/k_typical/{rule}_a0.05/32")
    put("bonfRoneFivePct", pct(d4["R1_CI_a0.05"]["share"], 1), src, "d4/full/R1_CI_a0.05/share")
    put("bonfRthreeFiveK", f"{d4['R3_cantelli_a0.05']['k_rejected']}/{d4['R3_cantelli_a0.05']['n_papers']}", src,
        "d4/full/R3_cantelli_a0.05")
    # tau sweep, d1
    tw = {0.8: "Eighty", 0.85: "EightyFive", 0.9: "Ninety", 0.95: "NinetyFive"}
    lines = []
    fm = {(c["family"], c["tau"]): c for c in x["d1"]["false_match"]}
    for c in x["d1"]["cells"]:
        if c["period"] == "2019-21" and c["stratum"] == "A":
            t = tw[round(c["tau"], 2)]
            put(f"tauCr{t}", pct(c["u_crossref"]), src, f"d1/2019-21/A/{c['tau']}/u_crossref")
            # registered state (an unasked backend counts as no match) with the lower end in brackets
            full = pct(c["u_full_upper"]) if c["k_full_upper"] == c["k_full_lower"] else \
                f"{pct(c['u_full_upper'])} [{pct(c['u_full_lower'])}]"
            put(f"tauFull{t}", pct(c["u_full_upper"]), src, f"d1/2019-21/A/{c['tau']}/u_full_upper")
            put(f"tauFullLo{t}", pct(c["u_full_lower"]), src, f"d1/2019-21/A/{c['tau']}/u_full_lower")
            g = fm[("gptzero", c["tau"])]
            put(f"tauGz{t}", pct(g["rate_full"], 1), src, f"d1/false_match/gptzero/{c['tau']}/rate_full")
            lines.append(f"{c['tau']:.2f} & {pct(c['u_crossref'])} & {full} & {pct(g['rate_full'], 1)} & "
                         f"{pct(fm[('gen_a', c['tau'])]['rate_full'], 1)} \\\\")
    (OUT / "tab_tau.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # absent vs present-but-unmatched, d2
    for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
        e = x["d2"][f"{per}/J+C"]
        put(f"absN{pt}", num(e["unresolved_crossref_title"]), src, f"d2/{per}/J+C/unresolved_crossref_title")
        put(f"absPresentK{pt}", num(e["present_but_unmatched"]), src, f"d2/{per}/J+C/present_but_unmatched")
        put(f"absAbsentK{pt}", num(e["absent_from_crossref"]), src, f"d2/{per}/J+C/absent_from_crossref")
        put(f"absPresentPct{pt}", pct(e["present_share"], 0) if e["present_share"] is not None else "--", src,
            f"d2/{per}/J+C/present_share")
        put(f"absCert{pt}", num(e["n_certified_doi"]), src, f"d2/{per}/J+C/n_certified_doi")
    for cse in x["d2"]["cases"]:
        if cse["id"].startswith("D"):
            put(f"case{cse['id']}Sim", f"{cse['best_sim']:.2f}", src, f"d2/cases/{cse['id']}/best_sim")
        else:
            put("caseGZSim", f"{cse['similarity']:.2f}", src, "d2/cases/GZ023/similarity")
    # PDF-parsed screen on the 60 identifier-free render references, d3
    d3 = x["d3"]
    b = d3["bib_title"]["flag_union"]
    put("pdfBibK", f"{b['k']}/{b['n']}", src, "d3/bib_title/flag_union")
    put("pdfBibFp", pct(b["fp"], 1), src, "d3/bib_title/flag_union/fp")
    for par, tg in (("grobid", "Grobid"), ("anystyle", "Any")):
        v = [c for c in d3["rendered"] if c["parser"] == par and c["screen"] == "flag_union" and c["n"]]
        put(f"pdf{tg}Min", pct(min(c["fp"] for c in v), 1), src, f"d3/rendered/{par}/flag_union/min fp")
        put(f"pdf{tg}Max", pct(max(c["fp"] for c in v), 1), src, f"d3/rendered/{par}/flag_union/max fp")
        put(f"pdf{tg}Cells", str(len(v)), src, f"d3/rendered/{par}/cells")
    put("pdfN", str(d3["n_rows"]), src, "d3/n_rows")
    gv = [c["fp"] for c in d3["rendered"] if c["parser"] == "grobid" and c["screen"] == "flag_union" and c["n"]]
    lead = ("The parsed screen flags more" if min(gv) > b["fp"] else
            "The parsed screen flags fewer" if max(gv) < b["fp"] else "The parsed screen flags more or fewer")
    put("pdfSentence", lead + " of these references than the BibTeX-title screen. The two differ in the matcher as well "
        "as the input: the rendered screen sends the whole reference string to Crossref and accepts a record whose title "
        "the string contains, so this comparison cannot separate parsing errors from the more lenient match.", src,
        "d3: grobid range vs bib-title fp")
    # title vs metadata fabrications in the labelled sets
    ra = C("p2_recall_audited.csv")
    rr = C("p2_recall.csv")
    au = J("p2_recall_drop_audit.json") if _pick("p2_recall_drop_audit.json").exists() else None
    _ = au
    lines = []

    def row(df, st, lb, ver=None):
        q = df[(df.set == st) & (df.label == lb) & (df.definition == "1") & (df.screen == "+s2")]
        if ver is not None:
            q = q[q.version.str.startswith(ver)]
        q = q.iloc[0]
        return int(q.n_evaluated), int(q.k_flagged)

    kinds = {"gen_a": "title fabrication (by construction)", "gen_b": "metadata: real title, swapped authors",
             "gen_c": "metadata: real title, wrong venue or year"}
    for st, name in (("gen_a", "Family a"), ("gen_b", "Family b"), ("gen_c", "Family c")):
        n, k = row(rr, st, "fabricated")
        lines.append(f"{name} & {n} & {k} & {n - k} & {kinds[st]} \\\\")
    n, k = row(ra, "gptzero", "hallucinated", "after")
    put("fsGzN", str(n), "results/p2_recall_audited.csv", "gptzero/hallucinated/def1/+s2/after audit/n_evaluated")
    put("fsGzFoundK", str(n - k), "results/p2_recall_audited.csv", "n_evaluated - k_flagged")
    dra = C("p2_recall_drop_audit.csv")
    gz = dra[dra.set == "gptzero"].audit_label.value_counts()
    bm = dra[dra.set == "badalova"].audit_label.value_counts()
    put("auditGzN", str(int(gz.sum())), "results/p2_recall_drop_audit.csv", "set=gptzero rows")
    put("auditGzPartial", str(int(gz.get("PARTIAL", 0))), "results/p2_recall_drop_audit.csv", "set=gptzero, PARTIAL")
    put("auditBmN", str(int(bm.sum())), "results/p2_recall_drop_audit.csv", "set=badalova rows")
    put("auditBmPartial", str(int(bm.get("PARTIAL", 0))), "results/p2_recall_drop_audit.csv", "set=badalova, PARTIAL")
    lines.append(f"GPTZero NeurIPS list & {n} & {k} & {n - k} & audit: {int(gz.get('PARTIAL', 0))} of {int(gz.sum())} "
                 f"audited borrow a real title \\\\")
    n, k = row(rr, "badalova", "problematic")
    lines.append(f"Badalova and Mayr, problematic & {n} & {k} & {n - k} & audit: {int(bm.get('PARTIAL', 0))} of "
                 f"{int(bm.sum())} audited borrow a real title \\\\")
    (OUT / "tab_fabsplit.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # human-rated check and tier sheet of Amendment 7 (b), (c): withdrawn by Amendment 8 (A); nothing is printed from them


# ---------------------------------------------------------------- P3F (Amendment 8): automated ground truth, bounds
def _src_name(k):
    return {"openalex": "OpenAlex", "crossref": "Crossref", "dblp": "DBLP", "arxiv": "arXiv", "s2": "Semantic Scholar",
            "url": "URL", "wayback": "Wayback"}.get(k, k)


def p3f_block():
    import hashlib
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    if "gt3_p3f" not in nums:
        raise SystemExit("numbers.json has no *_p3f keys: run code/p3f_numbers.py")
    g, tv, rbx, nf, ph = (nums[k] for k in ("gt3_p3f", "tier_validation_p3f", "rB_vs_gt3_p3f",
                                              "notfound_profile_p3f", "posthoc_p3f"))
    if g.get("interim") or tv.get("interim"):
        raise SystemExit("P3F results are interim")
    src = "results/numbers.json (key gt3_p3f)"
    fm = g["false_match"]
    for fam, tg in (("D-splice", "Ds"), ("gen_a", "Ga"), ("pooled", "Pool")):
        e = fm[fam]
        put(f"gtF{tg}K", f"{e['k']}/{e['n']}", src, f"false_match/{fam}/k,n")
        put(f"gtF{tg}Hi", pct(e["f_hi"], 1), src, f"false_match/{fam}/f_hi")
        put(f"gtF{tg}Unans", str(e["n_unanswered"]), src, f"false_match/{fam}/n_unanswered")
    put("gtFhiUsed", pct(fm["f_hi_used"], 2), src, "false_match/f_hi_used")  # P3G: 1.86 everywhere (S6' mismatch 5)
    pc = g["posctl"]["recall"]
    put("gtPosK", f"{pc['k']}/{pc['n']}", src, "posctl/recall/k,n")
    put("gtPosRecall", pct(pc["rate"], 0), src, "posctl/recall/rate")
    put("gtPosCi", ci(*pc["cp95"], d=1), src, "posctl/recall/cp95")
    put("gtPosUnans", str(g["posctl"]["n_unanswered"]), src, "posctl/n_unanswered")
    c = g["cells"]
    names = {"J": "J", "C": "C", "P": "P", "B": "B", "S": "S", "W": "W", "A": "\\textbf{A}"}
    lines = []
    for per, tag in (("2019-21", "Pre"), ("2024-26", "Post")):
        for t in ("J", "C", "P", "A", "B", "S", "W"):
            e = c[f"{per}|{t}"]
            for q in ("N", "U", "F", "R"):
                put(f"gt{q}{t}{tag}", num(e[q]), src, f"cells/{per}|{t}/{q}")
            put(f"gtRnf{t}{tag}", num(e["R_not_found"]), src, f"cells/{per}|{t}/R_not_found")
            put(f"gtRun{t}{tag}", num(e["R_unanswered"]), src, f"cells/{per}|{t}/R_unanswered")
            fu = pct(e["F_over_U"], 1) if e["F_over_U"] is not None else "--"
            put(f"gtFU{t}{tag}", fu, src, f"cells/{per}|{t}/F_over_U")
            put(f"gtUN{t}{tag}", pct(e["U_over_N"], 2), src, f"cells/{per}|{t}/U_over_N")
            put(f"gtRN{t}{tag}", pct(e["R_over_N"], 2), src, f"cells/{per}|{t}/R_over_N")
            if per == "2019-21":
                put(f"gtLo{t}", pct(e["fp_lower"], 2), src, f"cells/{per}|{t}/fp_lower")
                put(f"gtHi{t}", pct(e["fp_upper"], 2), src, f"cells/{per}|{t}/fp_upper")
                put(f"gtLoCi{t}", ci(*e["fp_lower_ci"], d=2), src, f"cells/{per}|{t}/fp_lower_ci")
                put(f"gtHiCi{t}", ci(*e["fp_upper_ci"], d=2), src, f"cells/{per}|{t}/fp_upper_ci")
                put(f"gtBias{t}", pct(e["bias_bound_X_hi_over_N"], 2), src, f"cells/{per}|{t}/bias_bound_X_hi_over_N")
                last = (f"{pct(e['fp_lower'], 2)}--{pct(e['fp_upper'], 2)} "
                        f"{{\\scriptsize{ci(e['fp_lower_ci'][0], e['fp_upper_ci'][1], d=2)}}}")
                if t in ("S", "W"):  # P3G (S6' S7): a URL answer is no evidence of the cited document; upper end only
                    last = f"$\\le${pct(e['fp_upper'], 0)} (URL answers)"
            else:
                last = f"{pct(e['R_over_N'], 2)} (R/N)"
            first = ("2019--21" if per == "2019-21" else "2024--26") if t == "J" else ""
            outside = e["U"] > 0 and e["not_in_set"] == e["U"]  # tier not in the deep search (2024-26 B/S/W)
            fr = ("--", "--", "--", "--") if outside else (num(e["F"]), num(e["R"]), fu, last)
            lines.append(f"{first} & {names[t]} & {num(e['N'])} & {num(e['U'])} & {fr[0]} & {fr[1]} & "
                         f"{fr[2]} & {fr[3]} \\\\")
        if per == "2019-21":
            lines.append("\\midrule")
    (OUT / "tab_gt3.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # depth / source breakdown of F (academic sets)
    for s, tag in (("acad1921", "Pre"), ("acad2426", "Post")):
        ds = g["depth_source"].get(s, {})
        dp = g["depth"].get(s, {})
        if "units_p3g" in nums:  # P3G: one unit (rows of the ground truth) for the whole of Sect. 5.2
            ur = nums["units_p3g"]["2019-21" if s == "acad1921" else "2024-26"]["rows"]
            ds, dp = ur["F_by_source"], ur["F_by_depth"]
            src = "results/numbers.json (key units_p3g)"
        put(f"gtFsrc{tag}", ", ".join(f"{_src_name(k)} {v}" for k, v in sorted(ds.items(), key=lambda kv: -kv[1])) or "none",
            src, f"depth_source/{s}")
        for k, tg in (("1 full string", "Full"), ("2 threshold band", "Band"),
                      ("3 source or candidate beyond cascade top", "Beyond"), ("4 DBLP only", "Dblp")):
            put(f"gtDepth{tg}{tag}", str(dp.get(k, 0)), src, f"depth/{s}/{k}")
    rn = g["rn_diff_academic"]
    put("gtRnDiff", pct(rn["diff"], 2), src, "rn_diff_academic/diff")
    put("gtRnDiffCi", ci(*rn["ci"], d=2), src, "rn_diff_academic/ci")
    h = g["h4_auto"]
    put("hFourAutoCert", pct(h["fp_certified"], 2), src, "h4_auto/fp_certified")
    put("hFourAutoLo", pct(h["fp_nonid_lower"], 2), src, "h4_auto/fp_nonid_lower")
    put("hFourAutoHi", pct(h["fp_nonid_upper"], 2), src, "h4_auto/fp_nonid_upper")
    put("hFourAutoDiffLoCi", ci(*h["diff_lower_ci"], d=2), src, "h4_auto/diff_lower_ci")
    put("hFourAutoDiffHiCi", ci(*h["diff_upper_ci"], d=2), src, "h4_auto/diff_upper_ci")
    put("hFourAutoVerdict", h["verdict"], src, "h4_auto/verdict")
    put("hFourAutoN", num(h["n_nonid_academic"]), src, "h4_auto/n_nonid_academic")
    # POST-HOC coverage and sensitivity lines (P3F2 3a/3b)
    src = "results/numbers.json (key posthoc_p3f)"
    for per, tag in (("2019-21", "Pre"), ("2024-26", "Post")):
        e = ph["coverage_academic"][per]
        put(f"covNf{tag}", pct(e["not_found_over_U"], 0), src, f"coverage_academic/{per}/not_found_over_U")
        put(f"covNfK{tag}", f"{num(e['not_found'])}/{num(e['U'])}", src, f"coverage_academic/{per}/not_found,U")
        put(f"covNfCi{tag}", ci(*e["cp95_not_found_over_U"], d=0), src, f"coverage_academic/{per}/cp95")
    e = ph["rn_notfound_only"]
    put("phRnNfPre", pct(e["r_over_n_1921"], 2), src, "rn_notfound_only/r_over_n_1921")
    put("phRnNfPost", pct(e["r_over_n_2426"], 2), src, "rn_notfound_only/r_over_n_2426")
    put("phRnNfDiff", pct(e["diff"], 2), src, "rn_notfound_only/diff")
    put("phRnNfDiffCi", ci(*e["ci"], d=2), src, "rn_notfound_only/ci")
    un = ph["unanswered_by_source"]
    for s, tag in (("acad1921", "Pre"), ("acad2426", "Post")):
        e = un[s]
        put(f"phUnans{tag}", f"{e['unanswered']}/{e['n']}", src, f"unanswered_by_source/{s}")
        put(f"phUnansSrc{tag}", ", ".join(f"{_src_name(k)} {v['k']}" for k, v in e["by_missing_source"].items()) or "none",
            src, f"unanswered_by_source/{s}/by_missing_source")
    # tier-rule validation (Amendment 8 (I))
    src = "results/numbers.json (key tier_validation_p3f)"
    put("tvN", num(tv["n"]), src, "n")
    put("tvAgree", pct(tv["agreement"], 1), src, "agreement")
    put("tvKappa", f"{tv['kappa']:.2f}", src, "kappa")
    put("tvVersion", num(tv["version_mismatch_n"]), src, "version_mismatch_n")
    put("tvAgreeNoVersion", pct(tv["agreement_without_version_mismatches"], 1), src, "agreement_without_version_mismatches")
    put("tvExcluded", num(sum(tv["excluded_counts"].values())), src, "excluded_counts (sum)")
    put("tierAccSentence", rf"against the type of the matched registry record (Amendment~8), the rule agrees for "
        rf"{pct(tv['agreement'], 1)}\% of {num(tv['n'])} resolved references ($\kappa={tv['kappa']:.2f}$), and for "
        rf"{pct(tv['agreement_without_version_mismatches'], 1)}\% when the {num(tv['version_mismatch_n'])} mismatches "
        r"between a cited preprint and its published version are set apart (Sect.~\ref{sec:res-gt}).", src,
        "agreement, kappa, version_mismatch_n")
    # AI rater (one descriptive sentence; full table in the Supplement) and the not-found profile (POST-HOC)
    s2 = "results/numbers.json (key rB_vs_gt3_p3f)"
    x = rbx["crosstab"]["exists"]
    put("rbExistsN", str(x["total"]), s2, "crosstab/exists/total")
    put("rbExistsFound", str(x["found"]), s2, "crosstab/exists/found")
    put("rbExistsNotFound", str(x["not found"]), s2, "crosstab/exists/not found")
    put("rbExistsUnans", str(x["unanswered"]), s2, "crosstab/exists/unanswered")
    src = "results/numbers.json (key notfound_profile_p3f)"
    put("nfN", str(nf["n"]), src, "n")
    put("nfBib", str(nf["by_source"][".bib"]), src, "by_source/.bib")
    put("nfBbl", str(nf["by_source"][".bbl (GROBID)"]), src, "by_source/.bbl")
    put("nfSignBib", str(nf["extract_sign"][".bib"]), src, "extract_sign/.bib")
    put("nfSignBbl", str(nf["extract_sign"][".bbl (GROBID)"]), src, "extract_sign/.bbl")
    put("nfSign", str(nf["extract_sign_total"]), src, "extract_sign_total")
    put("nfPre2000", str(nf["cited_before_2000"]), src, "cited_before_2000")
    put("nfShort", str(nf["title_le5_words"]), src, "title_le5_words")
    put("hashAmEight", hashlib.sha256((ROOT / "PREREG_AMENDMENT_8.md").read_bytes()).hexdigest()[:8],
        "PREREG_AMENDMENT_8.md", "sha256 of the file")
    for f, k in (("P3E/AMENDMENT_7_ADDENDUM_2.md", "AmSevenB"), ("P3E/AMENDMENT_7_ADDENDUM_3.md", "AmSevenC"),
                 ("P3E/AMENDMENT_7_ADDENDUM_4.md", "AmSevenD")):
        put(f"hash{k}", hashlib.sha256((ROOT / f).read_bytes()).hexdigest()[:8], f, "sha256 of the file")


def sg(x, d=2):
    """signed number for the text: a minus sign in math mode"""
    return f"{x:+.{d}f}".replace("-", "$-$")


def p3g_block():
    """P3G (POSTHOC_NOTE_P3G.md, POST HOC): branch split, both ends, bound sensitivity, decoys, fabricated families,
    URL answers, periods by tier, not-found split, tier rule binary, policy coding; numbers.json keys *_p3g."""
    import hashlib
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    if "branch_split_p3g" not in nums:
        raise SystemExit("numbers.json has no *_p3g keys: run code/p3g_numbers.py")
    bs, te, bd, pc = (nums[k] for k in ("branch_split_p3g", "two_ends_p3g", "bounds_p3g", "policy_coding_p3g"))
    S = "results/numbers.json (key branch_split_p3g)"
    tg = {"bib": "Bib", "bbl": "Bbl", "pooled": "Pool"}
    rows = []
    for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
        for br in ("bib", "bbl", "pooled"):
            c = bs[f"{per}|{br}"]
            k = f"{tg[br]}{pt}"
            put(f"br{k}Papers", num(c["paper_level_papers"]), S, f"{per}|{br}/paper_level_papers")
            put(f"br{k}N", num(c["N"]), S, f"{per}|{br}/N")
            put(f"br{k}U", num(c["U"]), S, f"{per}|{br}/U")
            put(f"br{k}uA", pct(c["u_A"], 2), S, f"{per}|{br}/u_A")
            put(f"br{k}uACi", ci(*c["u_A_ci"], d=2), S, f"{per}|{br}/u_A_ci")
            put(f"br{k}F", num(c["F"]), S, f"{per}|{br}/F")
            put(f"br{k}FU", pct(c["F_over_U"], 1), S, f"{per}|{br}/F_over_U")
            for kk in ("1", "2", "3"):
                e = c["flags"][kk]
                put(f"br{k}Ge{kk}", pct(e["share"], 1), S, f"{per}|{br}/flags/{kk}/share")
                put(f"br{k}Ge{kk}K", f"{e['papers']}/{e['n']}", S, f"{per}|{br}/flags/{kk}/papers,n")
                put(f"br{k}Ge{kk}Ci", ci(*e["wilson"], d=1), S, f"{per}|{br}/flags/{kk}/wilson")
            for a, at in (("a0.05", "Five"), ("a0.01", "One")):
                put(f"br{k}Kemp{at}", str(c["k_emp"][a]["k_emp"]), S, f"{per}|{br}/k_emp/{a}/k_emp")
            put(f"br{k}Disp", f"{c['dispersion']['ratio']:.2f}", S, f"{per}|{br}/dispersion/ratio")
            for bk, bt in (("crossref", "Cr"), ("arxiv", "Ax"), ("dblp", "Db"), ("openalex", "Oa")):
                e = c["by_backend"][bk]
                put(f"br{k}{bt}", pct(e["u_A"], 2 if e["u_A"] < 0.1 else 1), S, f"{per}|{br}/by_backend/{bk}/u_A")
                put(f"br{k}{bt}Ci", ci(*e["u_A_ci"], d=2 if e["u_A"] < 0.1 else 1), S, f"{per}|{br}/by_backend/{bk}/u_A_ci")
            put(f"br{k}Fold", f"{c['by_backend']['crossref']['u_A'] / c['u_A']:.0f}", S, f"{per}|{br}: crossref u_A / full u_A")
            ge2 = c["flags"]["2"]
            rows.append((per, br, c))
    lines = []
    for per, br, c in rows:
        ge2 = c["flags"]["2"]
        first = ("2019--21" if per == "2019-21" else "2024--26") if br == "bib" else ""
        name = {"bib": "\\texttt{.bib}", "bbl": "\\texttt{.bbl} (GROBID)", "pooled": "pooled"}[br]
        lines.append(f"{first} & {name} & {c['paper_level_papers']} & {num(c['N'])} & {num(c['U'])} & "
                     f"{pct(c['u_A'], 2)} {{\\scriptsize{ci(*c['u_A_ci'], d=2)}}} & {pct(c['F_over_U'], 1)} & "
                     f"{pct(ge2['share'], 1)} & {c['k_emp']['a0.05']['k_emp']} / {c['k_emp']['a0.01']['k_emp']} & "
                     f"{c['dispersion']['ratio']:.2f} \\\\")
        if per == "2019-21" and br == "pooled":
            lines.append("\\midrule")
    (OUT / "tab_branch.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = bs["rule"]
    put("brRuleDu", f"{r['diff_uA_points']:.2f}", S, "rule/diff_uA_points")
    put("brRuleDr", pct(r["rel_diff_dispersion"], 0), S, "rule/rel_diff_dispersion")
    put("brRuleMain", "the \\texttt{.bib} branch" if r["main"] == "bib" else "the pooled corpus", S, "rule/main")
    m = bs["bbl_missing_author_year"]
    put("brBblUnres", str(m["n_bbl_unresolved_academic"]), S, "bbl_missing_author_year/n_bbl_unresolved_academic")
    put("brBblNoAY", str(m["no_surnames_or_year"]), S, "bbl_missing_author_year/no_surnames_or_year")
    put("brBblNoAYNf", str(m["state_of_those"].get("not found", 0)), S, "bbl_missing_author_year/state_of_those/not found")
    # both ends
    S = "results/numbers.json (key two_ends_p3g)"
    sc = {"pooled": "Pool", "bib": "Bib"}
    for s_, st in sc.items():
        for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
            for end, et in (("upper", "Up"), ("lower", "Lo")):
                e = te[f"{s_}|{per}|{end}"]
                k = f"te{st}{pt}{et}"
                for kk in ("1", "2", "3"):
                    f_ = e["flags"][kk]
                    put(f"{k}Ge{kk}", pct(f_["share"], 1), S, f"{s_}|{per}|{end}/flags/{kk}/share")
                    put(f"{k}Ge{kk}K", f"{f_['papers']}/{f_['n']}", S, f"{s_}|{per}|{end}/flags/{kk}/papers,n")
                    put(f"{k}Ge{kk}Ci", ci(*f_["wilson"], d=1), S, f"{s_}|{per}|{end}/flags/{kk}/wilson")
                for a, at in (("a0.05", "Five"), ("a0.01", "One")):
                    x = e["k_emp"][a]
                    put(f"{k}Kemp{at}", str(x["k_emp"]), S, f"{s_}|{per}|{end}/k_emp/{a}/k_emp")
                    put(f"{k}KW{at}", str(x["k_wilson_upper"]) if x["k_wilson_upper"] else "none", S,
                        f"{s_}|{per}|{end}/k_emp/{a}/k_wilson_upper")
        b = te[f"{s_}|bounds"]
        put(f"te{st}Lo", pct(b["fp_lower"], 2), S, f"{s_}|bounds/fp_lower")
        put(f"te{st}Hi", pct(b["fp_upper"], 2), S, f"{s_}|bounds/fp_upper")
        put(f"te{st}LoCi", ci(*b["fp_lower_ci"], d=2), S, f"{s_}|bounds/fp_lower_ci")
        put(f"te{st}HiCi", ci(*b["fp_upper_ci"], d=2), S, f"{s_}|bounds/fp_upper_ci")
        put(f"te{st}F", num(b["F"]), S, f"{s_}|bounds/F")
        put(f"te{st}U", num(b["U"]), S, f"{s_}|bounds/U")
        put(f"te{st}R", num(b["R"]), S, f"{s_}|bounds/R")
        put(f"te{st}N", num(b["N"]), S, f"{s_}|bounds/N")
        put(f"te{st}FU", pct(b["F_over_U"], 1), S, f"{s_}|bounds/F_over_U")
        for pn, pk in (("0.39%", "039"), ("0.5%", "05")):
            v = te[f"{s_}|ppv"][pn]
            put(f"te{st}PpvUp{pk}", pct(v["upper_end"], 0), S, f"{s_}|ppv/{pn}/upper_end")
            put(f"te{st}PpvLo{pk}", pct(v["lower_end"], 0), S, f"{s_}|ppv/{pn}/lower_end")
            put(f"te{st}PpvUp{pk}Ci", ci(*v["upper_end_ci"], d=0), S, f"{s_}|ppv/{pn}/upper_end_ci")
            put(f"te{st}PpvLo{pk}Ci", ci(*v["lower_end_ci"], d=0), S, f"{s_}|ppv/{pn}/lower_end_ci")
    # Table 11 (both ends) and Table 12 (k_emp, both ends, with the Wilson k)
    lines = []
    for kk in ("1", "2", "3"):
        cells = []
        for s_, per, end in (("pooled", "2019-21", "upper"), ("pooled", "2019-21", "lower"), ("bib", "2019-21", "upper"),
                             ("bib", "2019-21", "lower"), ("pooled", "2024-26", "upper"), ("bib", "2024-26", "upper")):
            f_ = te[f"{s_}|{per}|{end}"]["flags"][kk]
            cells.append(f"{pct(f_['share'], 1)} ({f_['papers']})")
        lines.append(f"$\\ge{kk}$ & " + " & ".join(cells) + " \\\\")
    (OUT / "tab_empirical2.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = []
    for per, pn in (("2019-21", "2019--21 (in sample)"), ("2024-26", "2024--26 (hold-out)")):
        first = True
        for s_, sn in (("pooled", "pooled"), ("bib", "\\texttt{.bib}")):
            for end, en in (("upper", "all flags"), ("lower", "found (deep search)")):
                e = te[f"{s_}|{per}|{end}"]
                cells = []
                for a in ("a0.05", "a0.01"):
                    x = e["k_emp"][a]
                    cells.append(f"{x['k_emp']} ({pct(x['share_at_k'], 1)})" if x["k_emp"] else "--")
                    cells.append(str(x["k_wilson_upper"]) if x["k_wilson_upper"] else "none")
                lines.append(f"{pn if first else ''} & {sn} ({e['papers']}) & {en} & " + " & ".join(cells) + " \\\\")
                first = False
        if per == "2019-21":
            lines.append("\\midrule")
    (OUT / "tab_kemp2.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # sensitivity of the lower end to f (P3)
    lines = []
    sp, sb = te["pooled|sensitivity"], te["bib|sensitivity"]
    for a, b in zip(sp, sb):
        lab = {"D-splice f_hi": "$f_{\\mathrm{hi}}$, spliced decoys", "gen_a f_hi": "$f_{\\mathrm{hi}}$, planted titles",
               "F/U": "$F/U$ (pooled)", "": ""}[a["label"]]
        lines.append(f"{pct(a['f'], 2)} & {lab} & {pct(a['fp_lower'], 2)} & {pct(b['fp_lower'], 2)} \\\\")
    (OUT / "tab_sens.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for i, (a, b) in enumerate(zip(sp, sb)):
        put(f"sensF{i}", pct(a["f"], 2), S, f"pooled|sensitivity/{i}/f")
        put(f"sensPool{i}", pct(a["fp_lower"], 2), S, f"pooled|sensitivity/{i}/fp_lower")
        put(f"sensBib{i}", pct(b["fp_lower"], 2), S, f"bib|sensitivity/{i}/fp_lower")
    # decoys, families, URL answers, periods, not-found split, tier binary, H4-auto (P4-P8, P10, P12)
    S = "results/numbers.json (key bounds_p3g)"
    d4 = bd["P4_decoys"]
    put("dcPool", num(d4["build"]["pool"]), S, "P4_decoys/build/pool")
    put("dcSkipSim", str(d4["build"]["skipped"]["sim_ge_080"]), S, "P4_decoys/build/skipped/sim_ge_080")
    for lab, tg_ in (("unanswered_as_not_found", "Nf"), ("unanswered_as_found", "Fd")):
        e = d4[lab]
        put(f"dc{tg_}K", f"{e['k']}/{e['n']}", S, f"P4_decoys/{lab}/k,n")
        put(f"dc{tg_}Hi", pct(e["f_hi"], 2), S, f"P4_decoys/{lab}/f_hi")
        put(f"dc{tg_}Lo", pct(e["fp_lower_A"], 2), S, f"P4_decoys/{lab}/fp_lower_A")
    fam = bd["P5_fake_families"]
    names = [("gen_a", "Family a (fabricated titles)", "Ga"), ("gen_b", "Family b (swapped authors)", "Gb"),
             ("gen_c", "Family c (wrong venue or year)", "Gc"), ("gptzero", "GPTZero list", "Gz"),
             ("badalova_problematic", "Badalova--Mayr, problematic", "Bm"), ("badalova_verified", "Badalova--Mayr, verified (real)", "Bv")]
    lines = []
    for k_, nm, t_ in names:
        e = fam[k_]
        rule = "title $\\ge0.90$ and surname (no year)" if e["no_surname_or_year"] == e["n_items"] else "title $\\ge0.80$, surname, year"
        lines.append(f"{nm} & {e['n_items']} & {e['n_with_stored_answer']} & {rule} & {e['found']} & {pct(e['f'], 1)} "
                     f"{ci(*e['cp95'], d=1)} \\\\")
        put(f"fam{t_}K", f"{e['found']}/{e['n_with_stored_answer']}", S, f"P5_fake_families/{k_}/found,n")
        put(f"fam{t_}F", pct(e["f"], 0 if e["f"] >= 0.1 else 1), S, f"P5_fake_families/{k_}/f")
        put(f"fam{t_}Ci", ci(*e["cp95"], d=1), S, f"P5_fake_families/{k_}/cp95")
    (OUT / "tab_fam.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    u = bd["P6_url"]
    for t_ in ("S", "W"):
        for kk, kt in (("2xx", "Two"), ("3xx", "Three"), ("wayback", "Wb")):
            put(f"url{t_}{kt}", str(u[t_].get(kk, 0)), S, f"P6_url/{t_}/{kk}")
    p7 = bd["P7_periods"]
    lines = []
    for k_, nm, t_ in (("rn|J", "J", "J"), ("rn|C", "C", "C"), ("rn|P", "P", "P"), ("rn|A", "A", "A"),
                       ("rn|P_noid", "P without identifier", "Pn"), ("un|P_noid", "P without identifier, $U/N$", "PnU")):
        e = p7[k_]
        put(f"per{t_}Pre", pct(e["pre"], 2), S, f"P7_periods/{k_}/pre")
        put(f"per{t_}Post", pct(e["post"], 2), S, f"P7_periods/{k_}/post")
        put(f"per{t_}K", f"{e['k_pre']}/{num(e['n_pre'])} and {e['k_post']}/{num(e['n_post'])}", S, f"P7_periods/{k_}/k,n")
        put(f"per{t_}Diff", sg(e['diff'] * 100), S, f"P7_periods/{k_}/diff")
        put(f"per{t_}DiffCi", f"[{sg(e['ci'][0] * 100)}, {sg(e['ci'][1] * 100)}]", S, f"P7_periods/{k_}/ci")
        lines.append(f"{nm} & {e['k_pre']}/{num(e['n_pre'])} & {pct(e['pre'], 2)} & {e['k_post']}/{num(e['n_post'])} & "
                     f"{pct(e['post'], 2)} & {sg(e['diff'] * 100)} [{sg(e['ci'][0] * 100)}, {sg(e['ci'][1] * 100)}] \\\\")
    (OUT / "tab_periods.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    put("perPowerRn", pct(p7["power_rn_A_039"]["power"], 0), S, "P7_periods/power_rn_A_039/power")
    e = p7["rn_notfound_only|A"]
    put("perNfDiffExact", sg(e['diff'] * 100, 3), S, "P7_periods/rn_notfound_only|A/diff")
    put("perNfCiExact", f"[{sg(e['ci'][0] * 100, 3)}, {sg(e['ci'][1] * 100, 3)}]", S, "P7_periods/rn_notfound_only|A/ci")
    e = p7["rn|A"]
    put("perRnDiffExact", sg(e['diff'] * 100, 3), S, "P7_periods/rn|A/diff")
    put("perRnCiExact", f"[{sg(e['ci'][0] * 100, 3)}, {sg(e['ci'][1] * 100, 3)}]", S, "P7_periods/rn|A/ci")
    for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
        fu = p7["fu_counts|P"][per]
        put(f"perPFU{pt}", pct(fu["F"] / fu["U"], 1), S, f"P7_periods/fu_counts|P/{per}")
    n8 = bd["P8_notfound_split"]
    put("nfsN", str(n8["n_rows"]), S, "P8_notfound_split/n_rows")
    put("nfsB", str(n8["unit_rows"].get("b_candidate_fails_author_year", 0)), S, "P8_notfound_split/unit_rows/b")
    put("nfsMid", str(n8["unit_rows"].get("a_best_060_080", 0)), S, "P8_notfound_split/unit_rows/a_060_080")
    put("nfsLow", str(n8["unit_rows"].get("a_best_below_060", 0)), S, "P8_notfound_split/unit_rows/a_below_060")
    tb = bd["P10_tier_binary"]
    put("tvBinary", pct(tb["binary_agreement"], 1), S, "P10_tier_binary/binary_agreement")
    put("tvPrecA", pct(tb["precision_academic"], 1), S, "P10_tier_binary/precision_academic")
    put("tvPrecNonA", pct(tb["precision_nonacademic"], 1), S, "P10_tier_binary/precision_nonacademic")
    put("tvWtoA", pct(tb["rule_W_record_JCP_share"], 1), S, "P10_tier_binary/rule_W_record_JCP_share")
    put("tvWtoAK", f"{num(tb['rule_W_record_JCP'])}/{num(tb['rule_W'])}", S, "P10_tier_binary/rule_W_record_JCP,rule_W")
    put("tvAtoNonA", num(tb["rule_academic_record_nonacademic"]), S, "P10_tier_binary/rule_academic_record_nonacademic")
    h = bd["P12_h4_auto"]
    put("hFourAutoEffLo", f"{h['effect_lower_end_points']:.2f}", S, "P12_h4_auto/effect_lower_end_points")
    put("hFourAutoEffHi", f"{h['effect_upper_end_points']:.2f}", S, "P12_h4_auto/effect_upper_end_points")
    put("hFourAutoNCert", num(h["n_certified"]), S, "P12_h4_auto/n_certified")
    # policy coding (P11)
    S = "results/numbers.json (key policy_coding_p3g)"
    put("polN", str(pc["n"]), S, "n")
    put("polNoConfirm", str(pc["counts"].get("no_confirm", 0)), S, "counts/no_confirm")
    put("polConfirm", str(pc["counts"].get("confirm", 0)), S, "counts/confirm")
    put("polNoRule", str(pc["counts"].get("no_rule", 0)), S, "counts/no_rule")
    put("polNumeric", str(pc["numeric_thresholds"]), S, "numeric_thresholds")
    put("polNumericConfirmed", str(pc["numeric_with_confirmation"]), S, "numeric_with_confirmation")
    # registered reporting: non-academic tiers of 2024-26 as an interval
    S = "results/numbers.json (key nonacad_interval_2024_26_p3g)"
    for t_, e in nums["nonacad_interval_2024_26_p3g"].items():
        put(f"naInt{t_}", f"{pct(e['lower'], 1)}--{pct(e['upper'], 1)}", S, f"{t_}/lower,upper")
        put(f"naInt{t_}Oa", num(e["U_oa_unanswered"]), S, f"{t_}/U_oa_unanswered")
    # units (rows / distinct) of Sect. 5.2
    S = "results/numbers.json (key units_p3g)"
    un = nums["units_p3g"]
    for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
        for q in ("U", "F", "not_found", "unanswered"):
            qt = {"U": "U", "F": "F", "not_found": "Nf", "unanswered": "Un"}[q]
            put(f"unRows{qt}{pt}", num(un[per]["rows"][q]), S, f"{per}/rows/{q}")
            put(f"unDist{qt}{pt}", num(un[per]["distinct"][q]), S, f"{per}/distinct/{q}")
    # S6' S5: keeping N (not N - X) as denominator changes each end by at most a factor X_hi/(N - X_hi)
    ca = nums["gt3_p3f"]["cells"]["2019-21|A"]
    rel = ca["X_hi"] / (ca["N"] - ca["X_hi"])
    put("gtRelErrA", pct(rel, 1), "results/numbers.json (key gt3_p3f)", "cells/2019-21|A: X_hi/(N - X_hi)")
    put("gtRelErrPtsA", f"{ca['fp_upper'] * rel * 100:.2f}", "results/numbers.json (key gt3_p3f)",
        "cells/2019-21|A: fp_upper * X_hi/(N - X_hi), points")
    # time of the last deep-search request (S6' S11): the last "end;" line of P3F/deep_search.log with requests > 0
    last = [ln for ln in (ROOT / "P3F" / "deep_search.log").read_text(encoding="utf-8").splitlines()
            if ": end; requests {" in ln and "requests {}" not in ln][-1]
    put("gtLastRequest", f"{last[11:16]} UTC on 12 November 2026" if last.startswith("2026-11-12") else last[:20],
        "P3F/deep_search.log", "last 'end; requests' line")
    # the hashed post-hoc note of P3G
    put("hashPhG", hashlib.sha256((ROOT / "P3G" / "POSTHOC_NOTE_P3G.md").read_bytes()).hexdigest()[:8],
        "P3G/POSTHOC_NOTE_P3G.md", "sha256 of the file")


def p3h_block():
    """P3H (PREREG_AMENDMENT_9.md and the closure check; POST HOC): two periods by branch with direct standardisation,
    dispersion intervals by branch, the lower end at the family-c false-match rate, web evidence (Amendment 9)."""
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    if "period_std_p3h" not in nums:
        raise SystemExit("numbers.json has no *_p3h keys: run code/p3h_numbers.py")
    ps, sx = nums["period_std_p3h"], nums["sens_extra_p3h"]
    S = "results/numbers.json (key period_std_p3h)"
    d = ps["diffs"]
    for m, mt in (("uN", "U"), ("rN", "R")):
        for k_, kt in (("bib", "Bib"), ("bbl", "Bbl"), ("pooled", "Pool"), ("std", "Std")):
            e = d[f"{m}_{k_}_diff"]
            put(f"ps{mt}{kt}Diff", sg(e["point"] * 100), S, f"diffs/{m}_{k_}_diff/point")
            put(f"ps{mt}{kt}DiffCi", f"[{sg(e['ci'][0] * 100)}, {sg(e['ci'][1] * 100)}]", S, f"diffs/{m}_{k_}_diff/ci")
        e = d[f"{m}_std_2024"]
        put(f"ps{mt}Std", pct(e["point"], 2), S, f"diffs/{m}_std_2024/point")
        for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
            r = ps["rates"][per]
            for k_, kt in (("bib", "Bib"), ("bbl", "Bbl"), ("pooled", "Pool")):
                put(f"ps{mt}{kt}{pt}", pct(r[k_][m], 2), S, f"rates/{per}/{k_}/{m}")
    for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
        put(f"psWBbl{pt}", pct(ps["rates"][per]["w_bbl"], 1), S, f"rates/{per}/w_bbl")
    lines = []
    for per, pt in (("2019-21", "Pre"), ("2024-26", "Post")):
        for k_, kt in (("pooled", "Pool"), ("bib", "Bib"), ("bbl", "Bbl")):
            e = ps["dispersion"][f"{per}|{k_}"]
            put(f"disp{kt}{pt}", f"{e['point']:.2f}", S, f"dispersion/{per}|{k_}/point")
            put(f"disp{kt}{pt}Ci", f"[{e['ci'][0]:.2f}, {e['ci'][1]:.2f}]", S, f"dispersion/{per}|{k_}/ci")
            nm = {"pooled": "pooled", "bib": "\\texttt{.bib}", "bbl": "\\texttt{.bbl} (GROBID)"}[k_]
            lines.append(f"{('2019--21' if per == '2019-21' else '2024--26') if k_ == 'pooled' else ''} & {nm} & "
                         f"{e['papers']} & {e['point']:.2f} & [{e['ci'][0]:.2f}, {e['ci'][1]:.2f}] \\\\")
    (OUT / "tab_disp_p3h.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    fm = ps["field_mix_2019_21"]
    for k_, kt in (("bib", "Bib"), ("bbl", "Bbl")):
        n = sum(fm[k_].values())
        put(f"fieldNetSec{kt}", pct((fm[k_].get("cs.CR", 0) + fm[k_].get("cs.NI", 0)) / n, 0), S,
            f"field_mix_2019_21/{k_}: (cs.CR + cs.NI) / papers")
    S = "results/numbers.json (key sens_extra_p3h)"
    for k_, kt in (("pooled", "Pool"), ("bib", "Bib")):
        e = sx[k_]
        put(f"sensFamc{kt}", pct(e["fp_lower_famc"], 2), S, f"{k_}/fp_lower_famc")
        put(f"sensZero{kt}", pct(e["f_zero"], 1), S, f"{k_}/f_zero")
    put("sensFamcF", pct(sx["pooled"]["f_famc"], 0), S, "pooled/f_famc")
    tl = [x for x in (OUT / "tab_sens.tex").read_text(encoding="utf-8").splitlines() if x.strip()]
    tl.append(f"{pct(sx['pooled']['f_famc'], 2)} & generated family~c (Table~S34) & "
              f"{pct(sx['pooled']['fp_lower_famc'], 2)} & {pct(sx['bib']['fp_lower_famc'], 2)} \\\\")
    fz = sx["bib"]["f_zero"]
    lo = {k_: max(0.0, nums["two_ends_p3g"][f"{k_}|bounds"]["U"] - nums["two_ends_p3g"][f"{k_}|bounds"]["R"] / (1 - fz))
          / nums["two_ends_p3g"][f"{k_}|bounds"]["N"] for k_ in ("pooled", "bib")}
    tl.append(f"{pct(fz, 2)} & $F/U$ (\\texttt{{.bib}}) & {pct(lo['pooled'], 2)} & {pct(lo['bib'], 2)} \\\\")
    tl.sort(key=lambda x: float(x.split("&")[0]))
    (OUT / "tab_sens.tex").write_text("\n".join(tl) + "\n", encoding="utf-8")
    import hashlib
    put("hashAmNine", hashlib.sha256((ROOT / "PREREG_AMENDMENT_9.md").read_bytes()).hexdigest()[:8],
        "PREREG_AMENDMENT_9.md", "sha256 of the file")
    S = "numbers_ms keys (derived)"
    put("accGptzeroNotEval", str(int(NV["accGptzeroItemsAfterAudit"]) - int(NV["accGptzeroEvaluatedAfterAudit"])), S,
        "accGptzeroItemsAfterAudit - accGptzeroEvaluatedAfterAudit")
    put("polNoPolicy", str(int(NV["polN"]) - int(NV["nVenOffPolicy"])), S, "polN - nVenOffPolicy")
    put("polPolicyNoRule", str(int(NV["polNoRule"]) - (int(NV["polN"]) - int(NV["nVenOffPolicy"]))), S,
        "polNoRule - (polN - nVenOffPolicy)")
    ev = nums.get("evidence_p3h")
    put("evReady", "yes" if ev else "no", "results/numbers.json (key evidence_p3h)", "present")
    if ev:
        S = "results/numbers.json (key evidence_p3h)"
        for k_, v in ev.get("nv", {}).items():
            put(k_, v, S, f"nv/{k_}")
        w = ev["ends"]["with_web"]
        b = w["bounds"]
        put("evOpen", str(b["U"] - b["F"]), S, "ends/with_web/bounds U - F")
        put("evAdded", str(b["F"] - ev["ends"]["without_web"]["bounds"]["F"]), S, "with_web F - without_web F")
        ro = ev["ends"]["rule_only"]
        rb_ = ro["bounds"]
        # exact f of each row (the printed f is rounded; closure2 M5): the decoy f_hi, F/U values, family c, others
        te_ = nums["two_ends_p3g"]
        exact = [e["f"] for e in te_["pooled|sensitivity"]] + [sx["bib"]["f_zero"], sx["pooled"]["f_famc"]]

        def fx(txt):
            v = float(txt) / 100
            return min(exact, key=lambda e: abs(e - v)) if min(abs(e - v) for e in exact) < 5e-5 else v
        # sensitivity table: columns for the .bib lower end with the web evidence, and rule-checked only (M4)
        tl = [x for x in (OUT / "tab_sens.tex").read_text(encoding="utf-8").splitlines() if x.strip()]
        new = []
        for x in tl:
            f_ = fx(x.split("&")[0])
            lo = max(0.0, b["U"] - b["R"] / (1 - f_)) / b["N"]
            lr = max(0.0, rb_["U"] - rb_["R"] / (1 - f_)) / rb_["N"]
            new.append(x.rstrip().rstrip("\\").rstrip() + f" & {pct(lr, 2)} & {pct(lo, 2)} \\\\")
        (OUT / "tab_sens.tex").write_text("\n".join(new) + "\n", encoding="utf-8")
        # empirical table: columns ".bib, found or rule-checked" and ".bib, found or web" after the .bib found column
        tl = [x for x in (OUT / "tab_empirical2.tex").read_text(encoding="utf-8").splitlines() if x.strip()]
        new = []
        for x, k_ in zip(tl, ("1", "2", "3")):
            c = x.rstrip().rstrip("\\").rstrip().split(" & ")
            e, er = w["paper"]["flags"][k_], ro["paper"]["flags"][k_]
            c.insert(5, f"{pct(e['share'], 1)} ({e['papers']})")
            c.insert(5, f"{pct(er['share'], 1)} ({er['papers']})")
            new.append(" & ".join(c) + " \\\\")
        (OUT / "tab_empirical2.tex").write_text("\n".join(new) + "\n", encoding="utf-8")
        # k_emp table: rows for the .bib branch, rule-checked and with the web evidence (2019-21)
        tl = (OUT / "tab_kemp2.tex").read_text(encoding="utf-8").splitlines()
        i = tl.index("\\midrule")
        for vv, lab in ((ro, "found or rule-checked"), (w, "found or web-confirmed")):
            cells = []
            for a_ in ("a0.05", "a0.01"):
                x = vv["paper"]["k_emp"][a_]
                cells.append(f"{x['k_emp']} ({pct(x['share_at_k'], 1)})" if x["k_emp"] else "--")
                cells.append(str(x["k_wilson_upper"]) if x["k_wilson_upper"] else "none")
            tl.insert(i, f" & \\texttt{{.bib}} ({vv['paper']['papers']}) & {lab} & " + " & ".join(cells) + " \\\\")
            i += 1
        (OUT / "tab_kemp2.tex").write_text("\n".join(tl) + "\n", encoding="utf-8")
        # web evidence x GT-3 x AI rater (Amendment 9 (F); closure2 M14), for Supplement S13
        c3 = ev["real"]["cross3"]
        lines = []
        for wv in ("confirmed", "NEAR+y", "not confirmed"):
            cells = []
            for g in ("found", "not found", "unanswered"):
                tot = sum(v for k, v in c3.items() if k.startswith(f"{wv}|{g}|"))
                ex = c3.get(f"{wv}|{g}|exists", 0)
                cells.append(f"{tot} ({ex})")
            lines.append(f"{wv} & " + " & ".join(cells) + " \\\\")
        (OUT / "tab_cross3_p3h.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (backend, hypotheses, render, h4, recall, tools, theory, h5, agreement, design, revision, p3e_block, p3f_block,
              p3g_block, p3h_block):
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
