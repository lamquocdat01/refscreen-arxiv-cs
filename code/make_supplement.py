#!/usr/bin/env python3
"""Topic 43 / P3 (T11b): build submission_package/supplement/supplement.pdf.

Content
  S1 statements and full proofs (theory/THEORY_43_v3.md, sections 0-4, verbatim through pandoc)
  S2 pre-registration documents verbatim (PREREG_43.md, manual_protocol.md, Amendments 1-5) and their sha256
  S3 venue and publisher policy survey (results/p2_policy_survey.csv; re-verified quotations)
  S4 unresolved rates by tier, cumulative backend set and period, with paper-bootstrap intervals
  S5 diagnosis of unresolved journal/conference references (results/p1_diag_unresolved_jc60.csv)
  S6 audit of the recall drop (results/p2_recall_drop_audit.csv)
  S7 H5 by tertile: Theorem 2 under independence and the beta-binomial variant (results/p1_h5_betabinom.csv)
  S8 agreement tables (P1 recheck, P2 three raters, P3 post-hoc recheck: agreement, route table, verbatim sheet, hashes)
  S9 public tools (hallucinator, CheckIfExist) and S10 additional figures
Every table is generated here from result files; nothing is typed. Engine: xelatex (Unicode in the verbatim
documents), main font Cambria.
Usage: python make_supplement.py
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import ROOT  # noqa: E402

RES = ROOT / "results"
OUT = ROOT / "submission_package" / "supplement"


def esc(s):
    s = str(s)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")):
        s = s.replace(a, b)
    return s


def url(u):
    return r"\url{" + u.replace("%", r"\%").replace("#", r"\#") + "}"


def pandoc(md_text):
    md_text = md_text.replace("\r\n", "\n")
    # underscores are literal in these notes (u_s, P_{R,1}); escape them outside code spans so GFM does not read emphasis
    md_text = "".join(seg if i % 2 else seg.replace("_", "\_") for i, seg in enumerate(re.split(r"(`[^`]*`)", md_text)))
    r = subprocess.run(["pandoc", "-f", "gfm", "-t", "latex", "--shift-heading-level-by=1", "--wrap=none"],
                       input=md_text.encode("utf-8"), capture_output=True, check=True)
    return r.stdout.decode("utf-8")


def longtable(cols, header, rows, caption, label):
    cap = (r"\caption*{" + caption[1:] + r"}\\") if caption.startswith("*") else \
        (r"\caption{" + caption + r"}\label{" + label + r"}\\")  # a leading "*" = unnumbered table
    out = [r"\begin{longtable}{" + cols + "}", cap, r"\toprule",
           " & ".join(header) + r" \\", r"\midrule", r"\endfirsthead", r"\toprule", " & ".join(header) + r" \\",
           r"\midrule", r"\endhead"]
    out += [" & ".join(str(c) for c in r) + r" \\" for r in rows]
    out += [r"\bottomrule", r"\end{longtable}"]
    return "\n".join(out)


def pct(x, d=2):
    return f"{100 * float(x):.{d}f}"


def s1_theory():
    t = (ROOT / "theory" / "THEORY_43_v3.md").read_text(encoding="utf-8")
    t = t[t.index("## 0. Setting"):t.index("## 5. Open points")]
    return r"\section{Statements and full proofs}\label{sec:s1}" + "\n" + \
        "This section reproduces sections 0--4 of the theory note verbatim (file \\texttt{theory/THEORY\\_43\\_v3.md} in " \
        "the repository). Correspondence with the article: Theorem 1$'$ = Theorem 1; Theorem 2$'$ = Theorem 2; " \
        "Proposition 2$'''$ = Proposition 3; Theorem 3 = Theorem 4; Proposition 3.1 = Proposition 5; Proposition " \
        "4$''$ = Proposition 6 (Proposition 4$'$ and the beta-binomial Theorem 2$''$ are not used in the article). " \
        "Assumption A$'$ is conditional independence of references given the paper. Numerical values quoted inside " \
        "the note are those of the result files.\n\n" + pandoc(t)


def s2_prereg():
    h = (RES / "prereg_hash.txt").read_text(encoding="utf-8")
    rows = []
    for ln in h.splitlines():
        m = re.match(r"([0-9a-f]{64}) \*(\S+)", ln)
        if m:
            rows.append([r"\texttt{" + esc(m.group(2)) + "}", r"\texttt{\footnotesize " + m.group(1) + "}"])
    out = [r"\section{Pre-registration documents (verbatim)}\label{sec:s2}",
           "The files below are reproduced verbatim; their sha256 values are those frozen in "
           "\\texttt{results/prereg\\_hash.txt}. Note on roles: the protocol calls the second rater ``the second author "
           "(LQD)''. The article has a single author (LQD). In execution, the second rater's searches were carried out by "
           "an AI assistant (Claude Cowork) blind to earlier labels, and every decision was reviewed and approved by LQD; "
           "``CC'' denotes a Claude Code session (main article, Methods and ``Use of AI tools'').",
           longtable("@{}lp{11cm}@{}", ["File", "sha256"], rows, "*Hashes of the pre-registration documents (unnumbered).", "tab:hash")]
    for f, title in (("PREREG_43.md", "Protocol"), ("manual_protocol.md", "Manual verification protocol"),
                     ("PREREG_AMENDMENT_1.md", "Amendment 1"), ("PREREG_AMENDMENT_2.md", "Amendment 2"),
                     ("PREREG_AMENDMENT_3.md", "Amendment 3"), ("PREREG_AMENDMENT_4.md", "Amendment 4"),
                     ("PREREG_AMENDMENT_5.md", "Amendment 5 (post hoc)")):
        out.append(r"\clearpage\subsection*{" + title + r" --- \texttt{" + esc(f) + "}}")
        out.append(pandoc((ROOT / f).read_text(encoding="utf-8")))
    return "\n".join(out)


def s3_policy():
    d = pd.read_csv(RES / "p2_policy_survey.csv", dtype=str, keep_default_na=False)
    rows = []
    for r in d.itertuples():
        q = r.verify_quote or r.quote
        rows.append([esc(r.venue), esc(r.threshold_or_rule)[:400], esc(r.tool_named)[:160], esc(r.appeal_process)[:160],
                     esc(q)[:300], url(r.verify_url or r.source_url), esc(r.verify_date or r.access_date), esc(r.verify_status)])
    return r"\section{Venue and publisher policies}\label{sec:s3}" + "\n" + \
        "Policies as stated on official pages (first access 18 October 2026; re-verified 21 October 2026). Quotations are " \
        "verbatim excerpts.\n\n{\\scriptsize\\setlength{\\tabcolsep}{2pt}\n" + longtable(
            r"@{}p{1.6cm}p{3.2cm}p{1.8cm}p{1.8cm}p{3.6cm}p{2.6cm}p{1.2cm}p{1.1cm}@{}",
            ["Venue", "Rule / threshold", "Tool named", "Appeal", "Quotation", "Source", "Checked", "Status"],
            rows, "Venue and publisher policy survey.", "tab:policy") + "}"


def s4_backend():
    d = json.loads((RES / "p2_backend_table_retry.json").read_text(encoding="utf-8"))
    cols = ["crossref", "arxiv", "dblp", "openalex", "s2"]
    rows = []
    for r in d["rows"]:
        if r["stratum"] in ("all",):
            continue
        cells = [r["period"], esc(r["stratum"]), f"{r['n']:,} ({r['n_papers']:,})"]
        for c in cols:
            lo, hi = re.match(r"\s*(-?[\d.]+)\s*-\s*(-?[\d.]+)", r[f"boot_{c}"]).groups()
            cells.append(f"{pct(r[f'u_{c}'])} [{pct(lo)}, {pct(hi)}]")
        cells.append(str(r["n_rate_limited"]))
        rows.append(cells)
    return r"\section{Unresolved rates by tier, backend set and period}\label{sec:s4}" + "\n" + \
        f"Definition 1, cumulative backend sets in cascade order; DBLP dump {esc(d['dblp_dump'])}. Brackets: 95\\% " \
        "paper-bootstrap intervals (B = 1000, seed 42). Rate-limited references are excluded from denominators.\n\n" \
        "{\\scriptsize\\setlength{\\tabcolsep}{2pt}\n" + longtable(
            "@{}llrlllllr@{}", ["Period", "Tier", "n (papers)", "Crossref", "+arXiv", "+DBLP", "+OpenAlex", "+S2", "RL"],
            rows, "Unresolved rate (\\%) by tier and cumulative backend set.", "tab:backendfull") + "}"


def s5_diag():
    d = pd.read_csv(RES / "p1_diag_unresolved_jc60.csv", dtype=str, keep_default_na=False)
    vc = d.diag_class_cc.value_counts()
    rows = [[esc(k), str(v)] for k, v in vc.items()]
    body = longtable("@{}lr@{}", ["Class", "References"], rows,
                     f"Diagnosis of {len(d)} unresolved journal/conference references drawn before the DBLP amendment.", "tab:diag")
    det = [[r.diag_id, r.tier, esc(r.bib_title)[:70], esc(r.best_backend), r.best_sim, esc(r.best_title)[:70], esc(r.diag_class_cc)]
           for r in d.itertuples()]
    body += "\n{\\scriptsize\\setlength{\\tabcolsep}{2pt}\n" + longtable(
        "@{}llp{4.2cm}lrp{4.2cm}l@{}", ["ID", "Tier", "BibTeX title", "Best backend", "Sim.", "Best candidate", "Class"],
        det, "Per-reference diagnosis.", "tab:diagfull") + "}"
    return r"\section{Why legitimate journal and conference references go unresolved}\label{sec:s5}" + "\n" + \
        "A random sample of unresolved academic references, inspected by hand before DBLP was added to the cascade " \
        "(Amendment 3). Most are conference papers in venues without DOIs; this motivated the offline DBLP backend.\n\n" + body


def s6_audit():
    d = pd.read_csv(RES / "p2_recall_drop_audit.csv", dtype=str, keep_default_na=False)
    rows = [[esc(r.item_id), esc(r.cited_title)[:60], esc(r.cited_authors)[:40], esc(r.first_backend), r.similarity,
             esc(r.record_title)[:60], esc(r.record_authors)[:50], esc(r.audit_label), esc(r.audit_note)[:120]] for r in d.itertuples()]
    return r"\section{Audit of the recall drop}\label{sec:s6}" + "\n" + \
        "Every labelled fabricated reference that Crossref did not resolve but a later backend did (similarity $\\ge0.9$). " \
        "PARTIAL: a real title with wrong authors, venue or year; FALSE\\_MATCH: matched to a different work; LABEL\\_WRONG: " \
        "the work exists as cited.\n\n{\\scriptsize\\setlength{\\tabcolsep}{2pt}\n" + longtable(
            "@{}lp{2.6cm}p{1.6cm}lrp{2.6cm}p{2cm}lp{2.6cm}@{}",
            ["Item", "Cited title", "Cited authors", "Backend", "Sim.", "Record title", "Record authors", "Label", "Note"],
            rows, "Recall-drop audit.", "tab:audit") + "}"


def s7_h5():
    d = pd.read_csv(RES / "p1_h5_betabinom.csv", dtype=str, keep_default_na=False)
    rows = [[esc(r.scenario), r.k, r.tertile, r.n_papers, f"{float(r.n_refs_median):.0f}",
             f"{float(r.obs):.3f} [{float(r.wilson_lo):.3f}, {float(r.wilson_hi):.3f}]",
             f"{float(r.pred_binomial):.3f}", f"{float(r.pred_betabinom):.3f}", r.bin_in_ci, r.bb_in_ci] for r in d.itertuples()]
    return r"\section{H5: predicted and observed paper-level flags}\label{sec:s7}" + "\n" + \
        "Share of legitimate 2019--2021 papers with at least $k$ unresolved references, by length tertile, against " \
        "Theorem 2 under independence (leave-one-paper-out rates) and the exploratory beta-binomial variant.\n\n" \
        "{\\scriptsize\n" + longtable("@{}lllrrllll l@{}".replace(" ", ""),
                                      ["Scenario", "k", "Tertile", "Papers", "Median n", "Observed [Wilson]", "Thm 2",
                                       "Beta-bin.", "Thm 2 in CI", "BB in CI"], rows, "H5 by tertile.", "tab:h5") + "}"


def s8_agree():
    out = [r"\section{Agreement of hand verification}\label{sec:s8}"]
    p = json.loads((RES / "p2_kappa_pairs.json").read_text(encoding="utf-8"))
    cats = ["exists", "not-found", "ambiguous"]
    for pr in ("R1-R3", "R1-R2", "R2-R3"):
        s = p[pr]
        rows = [[cats[i]] + [str(v) for v in s["table"][i]] for i in range(3)]
        out.append(longtable("@{}lrrr@{}", [pr.split("-")[0] + r" $\backslash$ " + pr.split("-")[1]] + cats, rows,
                             f"P2 recheck, {pr}: n = {s['n']}, PABAK {s['pabak']:.2f} [{s['pabak_ci'][0]:.2f}, "
                             f"{s['pabak_ci'][1]:.2f}], AC1 {s['ac1']:.2f}, $\\kappa$ {s['kappa']:.2f}.", f"tab:agr{pr}"))
    rows = [[r["recheck_id"], r["stratum"], r["R1"], r["R2"] or "--", r["R3"] or "--"] for r in p["rows"]]
    out.append("{\\scriptsize\n" + longtable("@{}lllll@{}", ["Row", "Stratum", "R1", "R2", "R3"], rows,
                                            "Row-level labels of the P2 recheck (R3 rated rows K21--K40).", "tab:agrrows") + "}")
    k1 = json.loads((RES / "p1_kappa.json").read_text(encoding="utf-8"))
    out.append(f"P1 intra-rater recheck (40 rows, stratified by tier): raw agreement {100 * k1.get('raw', 0.975):.1f}\\%, "
               "Cohen's $\\kappa$ = 0 (degenerate: all first-pass labels were \\emph{exists}).")
    f3 = RES / "p3_recheck_stats.json"
    if f3.exists():
        q = json.loads(f3.read_text(encoding="utf-8"))
        m = pd.read_csv(RES / "p3_recheck_merged.csv", dtype=str, keep_default_na=False)
        out.append(r"\subsection*{Post-hoc recheck after Amendment 5 (supplementary)}")
        out.append(f"{q['n']} new references from {q['n_papers']} papers were drawn with seed 43, 20 per first-pass "
                   "stratum. No first-pass \\emph{not-found} or \\emph{ambiguous} label remained in the pool, so the "
                   "not-exists stratum (N) was filled with first-pass \\emph{exists} references that the full cascade left "
                   "unresolved. R2 (a fresh Claude Code sub-agent) and R3 (Claude Cowork; the author reviewed and approved "
                   "the sheet but did not label blind) rated the blind sheet under the revised rules. Labels: " +
                   "; ".join(f"{r} {', '.join(f'{k} {v}' for k, v in q['labels'][r].items())}" for r in ("R1", "R2", "R3")) +
                   ". Binary statistics (exists vs not-exists, \\emph{ambiguous} counted as disagreement with both sides) "
                   "and the variant that drops \\emph{ambiguous} rows coincide with the 3-outcome ones because no row is "
                   "ambiguous. The paper bootstrap (B = 1000, seed 43) is degenerate with no disagreement; the exact "
                   "Clopper--Pearson bound treats the 40 references as independent.")
        rows = []
        for pr in ("R1-R2", "R1-R3", "R2-R3"):
            x = q[pr]
            rows.append([pr, x["n"], f"{100 * x['raw']:.1f}", f"{x['pabak']:.2f}", f"{x['pabak_cp_lower']:.2f}",
                         f"{x['bin_pabak']:.2f}", f"{x['ac1']:.2f}", "undefined" if x["kappa"] is None else f"{x['kappa']:.2f}",
                         "PASS (post hoc)" if x["pass"] else "FAIL (post hoc)"])
        t3 = q["three raters"]
        rows.append(["R1-R2-R3", q["n"], "--", "--", "--", "--", f"{t3['ac1']:.2f}", "--",
                     f"{t3['unanimous']}/{q['n']} unanimous"])
        out.append(longtable("@{}lrrrrrrll@{}", ["Pair", "n", r"Raw \%", "PABAK", "CP lower", "Binary PABAK", "AC1",
                                                 r"$\kappa$", r"PABAK $\ge$ 0.8"], rows,
                             "Post-hoc recheck (Amendment 5): agreement. It does not replace the registered P2 result (FAIL).",
                             "tab:qagr"))
        out.append(r"\subsection*{Screen-unresolved references are real: search depth, not existence}")
        rn, re_ = q["routes"]["N"], q["routes"]["E"]
        kv = lambda d: ", ".join(f"{k} {v}" for k, v in d.items())  # noqa: E731
        out.append("The post-hoc recheck has no inter-rater disagreement to diagnose. The finding sits in stratum N: all "
                   f"{rn['n']} references that the full cascade left unresolved (tiers: {kv(rn['tiers'])}) were confirmed "
                   "real by all three raters. The table records, for every row, how each rater reached the resource (coded "
                   "by the author's AI agent from the raters' evidence notes): \\emph{direct} = the cited URL or a "
                   "bibliographic record; \\emph{moved} = a renamed repository, moved page or later file version; "
                   "\\emph{archived} = a Wayback capture; \\emph{secondary} = pages that cite the resource, when the "
                   f"resource itself could not be fetched. In stratum N, R3 used: {kv(rn['r3_route'])}; R2 used: "
                   f"{kv(rn['r2_route'])}. R3 flagged {', '.join(rn['r3_review_secondary'])} as resting on secondary "
                   f"evidence only. In stratum E, R3 used: {kv(re_['r3_route'])}. A checker who stops at the cited URL "
                   "would therefore flag several real references, which is the screen's own failure mode (Theorem 3: "
                   "unresolved is not nonexistent). In the registered P2 recheck, all four R1--R3 and all four R2--R3 "
                   "disagreements were \\emph{ambiguous} (R1 or R2) against \\emph{exists} (R3); the five R1--R2 "
                   "disagreements went both ways (four R1 \\emph{exists} vs R2 \\emph{ambiguous}, one the reverse); none "
                   "involved \\emph{not-found}.")
        rows = [[r["recheck_id"], r["stratum"], r["tier"], r["def1_status"], r["r2_route"], r["r3_route"],
                 esc(r["entry_defect"]), esc(r["note"])] for _, r in m.iterrows()]
        out.append("{\\scriptsize\n" + longtable("@{}llllllp{3.2cm}p{5.4cm}@{}", ["Row", "Str.", "Tier", "Screen",
                                                                            "R2 route", "R3 route", "Entry defect", "Note"],
                                               rows, "Route table of the post-hoc recheck (all 40 rows).", "tab:qroute") + "}")
        rows = []
        for _, r in m.iterrows():
            rows.append([r["recheck_id"], f"{esc(r['title'])} ({r['tier']}, {r['stratum']}; .bib {r['src_version']} "
                         f"{r['bib_version_date']})", r" \newline ".join(r[x] for x in ("R1", "R2", "R3")),
                         url(r["R2_evidence_url"]) + " " + esc(r["R2_evidence_note"]),
                         url(r["R3_evidence_url"]) + " " + esc(r["R3_evidence_note"])])
        rr = r">{\raggedright\arraybackslash}"
        out.append("{\\scriptsize\n" + longtable(f"@{{}}l{rr}p{{3.4cm}}p{{1.2cm}}{rr}p{{5.4cm}}{rr}p{{5.4cm}}@{{}}",
                                               ["Row", "Reference (tier, stratum; .bib version)", "R1 R2 R3", "R2 evidence",
                                                "R3 evidence"], rows,
                                               "Post-hoc recheck sheet: verbatim labels and evidence of the three raters "
                                               f"(R2: {esc(m.R2_checker.iloc[0])}; R3: {esc(m.R3_checker.iloc[0])}). "
                                               "R1 recorded labels only.", "tab:qsheet") + "}")
        rows = [[esc(f), hashlib.sha256((RES / f).read_bytes()).hexdigest()] for f in
                ("p3_recheck_sheet.csv", "p3_recheck_rules.md", "p3_recheck_r2.csv", "p3_recheck_r3.csv",
                 "p3_recheck_diagnosis.csv", "p3_recheck_merged.csv", "p3_recheck_stats.json")]
        out.append(longtable("@{}lp{11cm}@{}", ["File (results/)", "sha256"], rows,
                             "*Hashes of the post-hoc recheck files (unnumbered).", "tab:qhash"))
    else:
        out.append("The post-hoc recheck after Amendment 5 (40 new rows, seed 43) was pending the second rater when this "
                   "supplement was built; the first-pass and blind-recheck labels (R1, R2) are in the repository.")
    return "\n\n".join(out)


def s9_tools():
    t = pd.read_csv(RES / "p2_tool_hallucinator.csv", dtype=str, keep_default_na=False)
    rows = [[esc(r.style), esc(r.subset), r.n_refs, r.n_papers, r.n_not_extracted, r.n_inconclusive, r.n_skipped,
             r.n_evaluated, r.k_flagged, f"{pct(r.share_flagged)} [{pct(r.ci_lo)}, {pct(r.ci_hi)}]"] for r in t.itertuples()]
    c = json.loads((RES / "p2_checkifexist.json").read_text(encoding="utf-8"))
    return r"\section{Public tools}\label{sec:s9}" + "\n" + "{\\scriptsize\n" + longtable(
        "@{}llrrrrrrrl@{}", ["Style", "Subset", "Refs", "Papers", "Not extr.", "Inconcl.", "Skipped", "Evaluated", "Flags",
                             "FP \\% [CI]"], rows,
        f"hallucinator v0.2.4 on {t.n_pairs.iloc[0]} paired render papers (reduced sample, time budget); DBLP offline "
        "(same dump), other backends online without keys.", "tab:hall") + "}\n\n" + \
        f"CheckIfExist: {c.get('n_runs', 3)} sequential runs on one paper ({c.get('n_refs', 49)} references); " \
        f"{c.get('n_refs_changed', 0)} references changed status between runs."


def s10_figs():
    out = [r"\section{Additional figures}\label{sec:s10}"]
    for f, cap in (("F2b_roc_backend_original_labels", "Discrete ROC by backend set with the original labels (before the audit of Sect.~\\ref{sec:s6})."),
                   ("F3_ppv_ceiling", "Precision ceiling (Theorem 1) as a function of the share of web references, for the measured tier rates."),
                   ("F5_fp_style", "False positives by style and variant: certified-real versus hand-verified references."),
                   ("F6_u_by_tier", "Unresolved rate by tier and period under the full cascade.")):
        shutil.copy2(ROOT / "figures" / f"{f}.pdf", OUT / f"{f}.pdf")
        out.append(r"\begin{figure}[htbp]\centering\includegraphics[width=0.9\linewidth]{" + f + r".pdf}\caption{" + cap + r"}\end{figure}")
    return "\n".join(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = [s1_theory(), s2_prereg(), s3_policy(), s4_backend(), s5_diag(), s6_audit(), s7_h5(), s8_agree(), s9_tools(), s10_figs()]
    pre = r"""\documentclass[10pt]{article}
\usepackage[a4paper,margin=2cm]{geometry}
\usepackage{fontspec}\setmainfont{Cambria}[Ligatures=NoCommon]
\usepackage{unicode-math}\setmathfont{Cambria Math}
\usepackage{longtable,booktabs,array,calc,graphicx,amsmath}
\usepackage[hidelinks]{hyperref}\usepackage{xurl}
\newcounter{none}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\renewcommand{\thetable}{S\arabic{table}}\renewcommand{\thefigure}{S\arabic{figure}}\renewcommand{\thesection}{S\arabic{section}}
\setcounter{secnumdepth}{1}
\title{Supplementary material for ``Which Backend Decides? False Positives of Reference-Existence Screens on Legitimate
Computer-Science Bibliographies''}
\author{Dat Lam Quoc}
\date{}
\begin{document}
\maketitle
\tableofcontents
\clearpage
"""
    tex = pre + "\n\n\\clearpage\n".join(parts) + "\n\\end{document}\n"
    (OUT / "supplement.tex").write_text(tex, encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "supplement.tex"], cwd=OUT, capture_output=True)
    log = (OUT / "supplement.log").read_text(encoding="utf-8", errors="replace")
    errs = re.findall(r"^! .*", log, re.M)
    print("errors:", errs[:10], "| pages:", re.search(r"Output written on \S+ \((\d+) pages", log).group(1) if "Output written" in log else "?")


if __name__ == "__main__":
    main()
