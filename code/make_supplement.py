#!/usr/bin/env python3
"""Topic 43 / P3 (T11b): build submission_package/supplement/supplement.pdf.

Content
  S1 statements and full proofs (theory/THEORY_43_v4.md, sections 0-4, 8, 9, through pandoc)
  S2 pre-registration documents (PREREG_43.md, manual_protocol.md, Amendments 1-5) and their sha256; internal labels are
     replaced by neutral ones (sanitize below), and the byte-exact files are in the repository
  S3 venue and publisher policy survey (results/p2_policy_survey.csv; re-verified quotations)
  S4 unresolved rates by tier, cumulative backend set and period, with paper-bootstrap intervals
  S5 diagnosis of unresolved journal/conference references (results/p1_diag_unresolved_jc60.csv)
  S6 audit of the recall drop (results/p2_recall_drop_audit.csv)
  S7 H5 by tertile: Proposition 2(a) under independence and the beta-binomial variant (results/p1_h5_betabinom.csv)
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


def rp(f):
    """P3E: the result file recomputed on the completed ground truth (<stem>_p3e.<ext>) when it exists."""
    q = RES / f"{Path(f).stem}_p3e{Path(f).suffix}"
    return q if q.exists() else RES / f


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
    return wrap_tables(r.stdout.decode("utf-8"))


def wrap_tables(tex):
    """pandoc writes pipe tables as unwrapped l columns under --wrap=none, and a long cell then runs off the page.
    Give every table with a long row p columns, each as wide as its longest cell allows."""
    def fix(m):
        cols, body = m.group(1), m.group(2)
        rows = [r for r in re.split(r"\\\\\s*\n", body) if " & " in r]
        if not rows or max(len(r) for r in rows) < 90:
            return m.group(0)
        k = len(cols)
        width = [1] * k
        for r in rows:
            for i, c in enumerate(r.split(" & ")[:k]):
                width[i] = max(width[i], len(c.strip()))
        raw = [max(w ** 0.5, 4) for w in width]
        share = [0.97 * w / sum(raw) for w in raw]
        spec = "".join(r">{\raggedright\arraybackslash}p{" + f"{s:.3f}" + r"\linewidth}" for s in share)
        return r"\begin{longtable}[]{@{}" + spec + "@{}}" + body + r"\end{longtable}"
    return re.sub(r"\\begin\{longtable\}\[\]\{@\{\}([lrc]+)@\{\}\}(.*?)\\end\{longtable\}", fix, tex, flags=re.S)


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
    """S1: statements and proofs of the theory note, sections 0-4, without any measured number (P3H, closure S19):
    the paragraphs that report measured values before the cascade was complete are cut, and the note's numbering is
    mapped to the article's (Theorem 1 -> Proposition 3, Proposition 3 -> 4, Proposition 4 -> 5)."""
    t = (ROOT / "theory" / "THEORY_43_v4.md").read_text(encoding="utf-8")
    t = t[t.index("## 0. Setting"):t.index("## 5. Open points")]
    L = t.splitlines()
    cut = {i for i, l in enumerate(L) if l.lstrip("- ").startswith(("Consequence, on the main", "*Consequence for rules.*",
                                                                     "*Measured rates.*"))}
    a = next(i for i, l in enumerate(L) if l.startswith("**Corollary 1.3"))
    b = next(i for i, l in enumerate(L) if l.startswith("## 2. Proposition 2"))
    cut |= set(range(a, b))
    m = next(i for i, l in enumerate(L) if l.startswith("*Measured (§9"))
    cut |= set(range(m, len(L)))
    # a cut line takes its continuation lines (until the next blank line or heading) with it
    for i in sorted(cut):
        j = i + 1
        while j < len(L) and L[j].strip() and not L[j].startswith(("#", "**", "*")) and j not in cut:
            cut.add(j)
            j += 1
    t = "\n".join(l for i, l in enumerate(L) if i not in cut)
    t = t.replace("with u_W = 0.618, u_J = 0.0373 and u_P = 0.0101,",
                  "with illustrative rates u_W = 0.618, u_J = 0.0373 and u_P = 0.0101 (from a run before the cascade was "
                  "complete; the article's rates differ),")
    for x, y in (("Proposition 4", "@P5@"), ("Proposition 3", "@P4@"), ("Theorem 1", "@P3@")):
        t = t.replace(x, y)
    t = t.replace("@P5@", "Proposition 5").replace("@P4@", "Proposition 4").replace("@P3@", "Proposition 3")
    return r"\section{Statements and full proofs}\label{sec:s1}" + "\n" + \
        "This section reproduces the statements and proofs of sections 0--4 of the theory note in the repository, with " \
        "the note's numbering mapped to the article's (Propositions 3--5). Proposition 2 has two parts and one auxiliary " \
        "lemma (Lemma 4.0) is not used in the article. Assumption A$'$ is conditional independence of references given " \
        "the paper. Paragraphs of the note that report measured values are omitted, because they were written before the " \
        "cascade was complete; every measured number is in the article and in Sections S4--S12." \
        "\n\n" + _short_proofs() + "\n\n" + pandoc(t)


def _short_proofs():
    """P4: the short proofs that were the article's appendix, in the article's numbering (Propositions 1-5)."""
    t = (ROOT / "supplement" / "moved" / "moved_appendix_p4.tex").read_text(encoding="utf-8")
    t = t.replace(r"\begin{appendices}", "").replace(r"\end{appendices}", "")
    t = re.sub(r"\\section\{Proofs\}\\label\{app:proofs\}", r"\\subsection*{Short proofs (numbering of the article)}", t)
    num = {"prop:ppv": "1", "prop:count": "2", "thm:us": "3", "prop:id": "4", "prop:rules": "5"}
    t = re.sub(r"\\ref\{([^}]+)\}", lambda m: num.get(m.group(1), "?"), t)
    return t + "\n\n\\subsection*{Statements and proofs of the theory note}"


def s2_prereg():
    h = (RES / "prereg_hash.txt").read_text(encoding="utf-8")
    rows = []
    for ln in h.splitlines():
        m = re.match(r"([0-9a-f]{64}) \*(\S+)", ln)
        if m:
            rows.append([r"\texttt{" + esc(Path(m.group(2)).name) + "}", r"\texttt{\footnotesize " + m.group(1) + "}"])
    a6 = ROOT / "PREREG_AMENDMENT_6.md"  # hashed in the phase log, not in prereg_hash.txt
    i7 = next(i for i, r in enumerate(rows) if r"AMENDMENT\_7.md" in r[0])  # A6 sits just before A7
    rows.insert(i7, [r"\texttt{" + esc(a6.name) + "}",
                                r"\texttt{\footnotesize " + hashlib.sha256(a6.read_bytes()).hexdigest() + "}"])
    out = [r"\section{Pre-registration documents}\label{sec:s2}",
           "The documents below are reproduced with internal labels replaced or removed: the author's initials by ``the "
           "author'', project phases by ``stage 0--3'', project decisions by ``decision point'', names of internal project "
           "notes and local file paths by a short description, run names by ``an earlier run'', and decision times by the "
           "date only, and one sentence of addendum 3 about an internal deadline is omitted. Nothing else differs. The "
           "post-hoc note and Amendment 9 are reproduced at the end. The note was written before the deep-search "
           "request window closed and states that window; the last request was sent at 05:49 UTC on 12 November 2026. "
           "The byte-exact files, with the sha256 values below, are in the repository "
           "(\\texttt{supplement/prereg/}). Note on roles: the protocol calls the second rater ``the second author''. The "
           "article has a single author. In execution, the second rater's searches were carried out by an AI assistant blind "
           "to earlier labels, and every decision was reviewed and approved by the author (main article, Methods and ``Use "
           "of AI tools'').",
           longtable("@{}lp{11cm}@{}", ["File", "sha256"], rows, "*Hashes of the pre-registration documents (unnumbered).", "tab:hash")]
    # P3H (CP3e question 6): the table of documents and what was known, moved from the article (unnumbered here)
    pt = _moved("moved_prereg_p3h.tex", _nv())
    pt = re.sub(r"\\caption\{([^{}]*)\}\\label\{tab:prereg\}",
                lambda m: r"\textbf{Documents and what was known when each was written (unnumbered).} " + m.group(1) + r"\par",
                pt)
    out.append(pt)
    for f, title in (("PREREG_43.md", "Protocol"), ("manual_protocol.md", "Manual verification protocol"),
                     ("PREREG_AMENDMENT_1.md", "Amendment 1"), ("PREREG_AMENDMENT_2.md", "Amendment 2"),
                     ("PREREG_AMENDMENT_3.md", "Amendment 3"), ("PREREG_AMENDMENT_4.md", "Amendment 4"),
                     ("PREREG_AMENDMENT_5.md", "Amendment 5 (post hoc)"), ("PREREG_AMENDMENT_6.md", "Amendment 6 (post hoc)"),
                     ("PREREG_AMENDMENT_7.md", "Amendment 7 (post hoc)"),
                     ("P3E/AMENDMENT_7_ADDENDUM.md", "Amendment 7, addendum A (post hoc, procedural deviation)"),
                     ("P3E/AMENDMENT_7_ADDENDUM_2.md", "Amendment 7, addendum 2 (post hoc, procedural deviation)"),
                     ("P3E/AMENDMENT_7_ADDENDUM_3.md", "Amendment 7, addendum 3 (post hoc; withdrawn by Amendment 8)"),
                     ("P3E/AMENDMENT_7_ADDENDUM_4.md", "Amendment 7, addendum 4 (post hoc, procedural deviation)"),
                     ("PREREG_AMENDMENT_8.md", "Amendment 8 (post hoc)"),
                     ("P3G/POSTHOC_NOTE_P3G.md", "Post-hoc note (not registered)"),
                     ("PREREG_AMENDMENT_9.md", "Amendment 9 (post hoc)")):
        out.append(r"\clearpage\subsection*{" + title + r" --- \texttt{" + esc(Path(f).name) + "}}")
        md = (ROOT / f).read_text(encoding="utf-8")
        md = _print_copy(f, md)
        out.append(pandoc(md))
    return "\n".join(out)


def _print_copy(f, md):
    """P4 (closure2 M9): readable printed copies of the post-hoc note and Amendment 9; internal file names and labels
    are replaced before the general sanitising, so that the replacements do not run into each other."""
    if f.endswith("POSTHOC_NOTE_P3G.md"):
        md = md.replace("after the results of v1.4 and the S6′ pre-submission review by an AI model "
                        "(`P3/R2_REVIEW_43_S6P_20261112.md`, Fable 5.2 · high) were known",
                        "after the results of draft 2 and a second pre-submission review by an AI model were known")
        md = md.replace("and the first line of `P3G/P3G_LOG.md`", "and the first line of a project log")
        md = re.sub(r"Inputs are the stored answers in `cache/`, `cache_p3e/` and `cache_p3f/`, the state files "
                    r"`P3E/cascade_passes.json` and `P3F/deep_search_state.json`, and",
                    "Inputs are the stored answers of every backend and of the deep search, two state files of the "
                    "completion and of the deep search (the stored answers are not redistributed; the state files are in the "
                    "repository), and", md)
        md = md.replace("new outputs carry the suffix `_p3g`", "new outputs carry a separate suffix")
        md = re.sub(r"\(S6′ (S\d+)\)", r"(review item \1)", md)
        md = re.sub(r"\(S6′ (S\d+)", r"(review item \1", md)
        md = re.sub(r"\bP(\d{1,2})(?=[.\s,;:)\-])", r"PH\1", md)
    if f.endswith("PREREG_AMENDMENT_9.md"):
        md = re.sub(r"\s*\(`CP3e_DECISION_43_20261113\.md`; prompt\s*`[^`]*`\)", "", md)
        md = md.replace("The labels of the human rater R_B (key opened earlier) and of the AI rater.",
                        "The labels of the AI rater R_B (key opened earlier; called a human rater here, see Table S29).")
        md = re.sub(r"\s*\(`P3/R2_CLOSURE_43_20261113\.md`\)", "", md)
    return md


def s3_policy():
    d = pd.read_csv(RES / "p2_policy_survey.csv", dtype=str, keep_default_na=False)
    rows = []
    for r in d.itertuples():
        q = r.verify_quote or r.quote
        m = re.search(r"'(further examined and verified by the senior program committee[^']*)'", r.notes)
        if m:  # P3H (closure N12): the sentence the coding rests on, as recorded at first access
            q = f"{r.quote} [...] Flagged entries are “{m.group(1)}” (recorded at first access, {r.access_date})."
        rows.append([esc(r.venue), esc(r.threshold_or_rule)[:400], esc(r.tool_named)[:160], esc(r.appeal_process)[:160],
                     esc(q)[:420], url(r.verify_url or r.source_url), esc(r.verify_date or r.access_date), esc(r.verify_status)])
    return r"\section{Venue and publisher policies}\label{sec:s3}" + "\n" + \
        "Policies as stated on official pages (first access 18 October 2026; re-verified 21 October 2026, one on 24 " \
        "October). Quotations are " \
        "verbatim excerpts.\n\n{\\scriptsize\\setlength{\\tabcolsep}{2pt}\n" + longtable(
            r"@{}p{1.6cm}p{3.2cm}p{1.8cm}p{1.8cm}p{3.6cm}p{2.6cm}p{1.2cm}p{1.1cm}@{}",
            ["Venue", "Rule / threshold", "Tool named", "Appeal", "Quotation", "Source", "Checked", "Status"],
            rows, "Venue and publisher policy survey.", "tab:policy") + "}"


def s4_backend():
    d = json.loads((rp("p2_backend_table_retry.json")).read_text(encoding="utf-8"))
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
        "A random sample of unresolved academic references, inspected by Claude Code (an AI agent) before DBLP was added to the cascade " \
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
    d = pd.read_csv(rp("p1_h5_betabinom.csv"), dtype=str, keep_default_na=False)
    rows = [[esc(r.scenario), r.k, r.tertile, r.n_papers, f"{float(r.n_refs_median):.0f}",
             f"{float(r.obs):.3f} [{float(r.wilson_lo):.3f}, {float(r.wilson_hi):.3f}]",
             f"{float(r.pred_binomial):.3f}", f"{float(r.pred_betabinom):.3f}", r.bin_in_ci, r.bb_in_ci] for r in d.itertuples()]
    return r"\section{H5: predicted and observed paper-level flags}\label{sec:s7}" + "\n" + \
        "Share of legitimate 2019--2021 papers with at least $k$ unresolved references, by length tertile, against " \
        "Proposition 2(a) under independence (leave-one-paper-out rates) and the exploratory beta-binomial variant.\n\n" \
        "{\\scriptsize\n" + longtable("@{}lllrrllll l@{}".replace(" ", ""),
                                      ["Scenario", "k", "Tertile", "Papers", "Median n", "Observed [Wilson]", "Prop 2(a)",
                                       "Beta-bin.", "Prop 2(a) in CI", "BB in CI"], rows, "H5 by tertile.", "tab:h5") + "}"


def s8_agree():
    out = [r"\section{Agreement of the verification passes (AI-agent labels)}\label{sec:s8}"]
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
                   "unresolved. R2 (a fresh Claude Code sub-agent) and R3 (an AI assistant; the author reviewed and approved "
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
        out.append(r"\subsection*{Screen-unresolved references in the post-hoc recheck: routes to confirmation}")
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
                   "would therefore flag several real references, which is the screen's own failure mode (Proposition 3 "
                   "of the article: unresolved is not nonexistent). In the registered P2 recheck, all four R1--R3 and all four R2--R3 "
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
                   ("F3_ppv_ceiling", "Precision ceiling (Proposition 1) as a function of the share of web references, for the measured tier rates."),
                   ("F5_fp_style", "False positives by style and variant: certified-real versus AI-agent-verified references (AI-agent labels; descriptive)."),
                   ("F6_u_by_tier", "Unresolved rate by tier and period under the full cascade.")):
        src = ROOT / "figures" / f"{f}_p3g.pdf"  # P3G: corrected wording, same data as the _p3e figure
        src = src if src.exists() else ROOT / "figures" / f"{f}_p3e.pdf"  # P3E: drawn from the completed ground truth
        src = src if src.exists() else ROOT / "figures" / f"{f}.pdf"
        shutil.copy2(src, OUT / src.name)
        out.append(r"\begin{figure}[htbp]\centering\includegraphics[width=0.9\linewidth]{" + src.stem + r".pdf}\caption{" + cap + r"}\end{figure}")
    return "\n".join(out)


def _nv():
    """the formatted numbers of the article (numbers_ms.tex), so that text moved from the article keeps its values"""
    t = (ROOT / "submission_package" / "latex" / "numbers_ms.tex").read_text(encoding="utf-8")
    return dict(re.findall(r"\\nvset\{([^{}]+)\}\{(.*)\}\s*$", t, re.M))


def _tab(name):
    return (ROOT / "submission_package" / "latex" / name).read_text(encoding="utf-8").strip()


def _tabular(cols, header_lines, body, caption, label):
    return ("\\begin{table}[htbp]\\centering\\footnotesize\\caption{" + caption + "}\\label{" + label + "}\n"
            "\\begin{tabular}{" + cols + "}\n\\toprule\n" + "\n".join(header_lines) + "\n\\midrule\n" + body +
            "\n\\bottomrule\n\\end{tabular}\n\\end{table}")


def s12_p3g():
    """S12: post-hoc analyses of the last revision (P3G/POSTHOC_NOTE_P3G.md, hashed before they ran) and the material
    moved from the article (thresholds by tertile, rules R1-R3, identifier scenario). Numbers from results/numbers.json
    (keys *_p3g) and the generated table bodies of the article."""
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    bs, te, bd, pc = (nums[k] for k in ("branch_split_p3g", "two_ends_p3g", "bounds_p3g", "policy_coding_p3g"))
    NV = _nv()
    ev = json.loads((RES / "p3h_evidence_score.json").read_text(encoding="utf-8"))
    W = lambda e: f"{pct(e['share'], 1)} ({e['papers']}) [{pct(e['wilson'][0], 1)}, {pct(e['wilson'][1], 1)}]"  # noqa: E731
    out = [r"\section{Post-hoc analyses of the last revision}\label{sec:s12}",
           "Every analysis in this section was specified after the registered results, the deep search and a "
           "pre-submission review by an AI model were known, in a note hashed before any of them ran (Section S2). "
           "The rows and columns marked web come from Amendment 9 (Section S2, last document). All are post hoc and "
           "offline: they read stored answers only. Units are references (rows) unless a caption says otherwise."]
    # branch split
    rows = []
    for per in ("2019-21", "2024-26"):
        for br in ("bib", "bbl", "pooled"):
            c = bs[f"{per}|{br}"]
            bb = c["by_backend"]
            rows.append([per.replace("-", "--"), {"bib": ".bib", "bbl": ".bbl (GROBID)", "pooled": "pooled"}[br],
                         c["paper_level_papers"], f"{c['N']:,}", c["U"],
                         f"{pct(bb['crossref']['u_A'], 1)} [{pct(bb['crossref']['u_A_ci'][0], 1)}, {pct(bb['crossref']['u_A_ci'][1], 1)}]",
                         pct(bb["arxiv"]["u_A"], 1), pct(bb["dblp"]["u_A"], 2), pct(bb["openalex"]["u_A"], 2),
                         f"{pct(c['u_A'], 2)} [{pct(c['u_A_ci'][0], 2)}, {pct(c['u_A_ci'][1], 2)}]", c["F"], c["R"],
                         pct(c["F_over_U"], 1) if c["F_over_U"] is not None else "--"])
    out.append("{\\scriptsize\n" + longtable("@{}llrrrlrrrlrrr@{}", ["Period", "Branch", "Papers", "N", "U", r"Crossref (\%)",
                                                                  "+arXiv", "+DBLP", "+OpenAlex", r"Full (\%)", "F", "R", r"F/U"],
                                            rows, "Academic references by branch and cumulative backend set (paper-bootstrap "
                                            "95\\% intervals). Branch: titles from the authors' .bib, or parsed by GROBID "
                                            "from a .bbl. Papers do not mix branches.", "tab:s12branch") + "}")
    r = bs["rule"]
    m = bs["bbl_missing_author_year"]
    out.append(f"Choice of the main branch (rule fixed in the note before the split was computed): $|u_A^{{bib}}-u_A^{{bbl}}|$ = "
               f"{r['diff_uA_points']:.2f} points (threshold 0.5) and relative difference of the dispersion ratios "
               f"{pct(r['rel_diff_dispersion'], 0)}\\% (threshold 20\\%), so the main numbers come from the .bib branch. Of the "
               f"{m['n_bbl_unresolved_academic']} distinct unresolved academic .bbl references of 2019--21, {m['no_surnames']} "
               f"lack surnames and {m['no_year']} a year after parsing ({m['no_surnames_or_year']} either); the deep search "
               f"could match these only at a title similarity of 0.90, and found none of them.")
    # both ends, paper level
    rows = []
    for s_, sn in (("pooled", "pooled"), ("bib", ".bib")):
        for per in ("2019-21", "2024-26"):
            for end, en in (("upper", "all flags"), ("lower", "found by the deep search")):
                e = te[f"{s_}|{per}|{end}"]
                ke = e["k_emp"]
                rows.append([per.replace("-", "--"), f"{sn} ({e['papers']})", en, W(e["flags"]["1"]), W(e["flags"]["2"]),
                             W(e["flags"]["3"]), f"{ke['a0.05']['k_emp']} / {ke['a0.05']['k_wilson_upper'] or 'none'}",
                             f"{ke['a0.01']['k_emp']} / {ke['a0.01']['k_wilson_upper'] or 'none'}"])
                if s_ == "bib" and per == "2019-21" and end == "lower":
                    for vk, vn in (("rule_only", "found or rule-checked (web)"), ("with_web", "found or web-confirmed")):
                        e = ev["ends"][vk]["paper"]
                        ke = e["k_emp"]
                        rows.append([per.replace("-", "--"), f"{sn} ({e['papers']})", vn, W(e["flags"]["1"]),
                                     W(e["flags"]["2"]), W(e["flags"]["3"]),
                                     f"{ke['a0.05']['k_emp']} / {ke['a0.05']['k_wilson_upper'] or 'none'}",
                                     f"{ke['a0.01']['k_emp']} / {ke['a0.01']['k_wilson_upper'] or 'none'}"])
    out.append("{\\scriptsize\n" + longtable("@{}lllllll l@{}", ["Period", "Papers", "Flags", r"$\ge1$ (\%)", r"$\ge2$ (\%)",
                                                              r"$\ge3$ (\%)", r"$k_{emp}$ / Wilson $k$, 5\%", "1\\%"], rows,
                                            "Paper-level flags on academic references at both ends: all flags (every "
                                            "unresolved reference counts) and references found by the deep search; web rows "
                                            "add references the author confirmed on web evidence (Amendment 9). Wilson 95\\% intervals; Wilson $k$: smallest $k$ whose Wilson upper limit "
                                            "is at most $\\alpha$.", "tab:s12ends") + "}")
    rows = []
    for s_, sn in (("pooled", "pooled"), ("bib", ".bib")):
        b = te[f"{s_}|bounds"]
        p = te[f"{s_}|ppv"]
        rows.append([sn, f"{b['N']:,}", b["U"], b["F"], b["R"],
                     f"{pct(b['fp_lower'], 2)} [{pct(b['fp_lower_ci'][0], 2)}, {pct(b['fp_lower_ci'][1], 2)}]",
                     f"{pct(b['fp_upper'], 2)} [{pct(b['fp_upper_ci'][0], 2)}, {pct(b['fp_upper_ci'][1], 2)}]",
                     f"{pct(p['0.39%']['upper_end'], 0)} / {pct(p['0.39%']['lower_end'], 0)}",
                     f"{pct(p['0.5%']['upper_end'], 0)} / {pct(p['0.5%']['lower_end'], 0)}"])
        if s_ == "bib":
            for vk, vn in (("rule_only", ".bib, rule-checked (web)"), ("with_web", ".bib, web")):
                b2, p2 = ev["ends"][vk]["bounds"], ev["ends"][vk]["ppv"]
                rows.append([vn, f"{b2['N']:,}", b2["U"], b2["F"], b2["R"],
                             f"{pct(b2['fp_lower'], 2)} [{pct(b2['fp_lower_ci'][0], 2)}, {pct(b2['fp_lower_ci'][1], 2)}]",
                             "as .bib", f"-- / {pct(p2['0.39%']['lower_end'], 0)}", f"-- / {pct(p2['0.5%']['lower_end'], 0)}"])
    out.append(longtable("@{}lrrrrllll@{}", ["Scope", "N", "U", "F", "R", "FP lower [CI]", "FP upper [CI]",
                                              r"PPV$^*$, $\pi$=0.39\%", r"$\pi$=0.5\%"], rows,
                         "Bounds of the academic tier, 2019--21, and the precision ceiling (\\%) at the upper / lower end.",
                         "tab:s12bounds"))
    # sensitivity, decoys, families, URL answers
    out.append(_tabular("@{}rlrrrr@{}", [r"$f$ (\%) & Source & Pooled (\%) & .bib (\%) & .bib, rule-checked (\%) & .bib, web (\%) \\"], _tab("tab_sens.tex"),
                        "Lower end of the bounds at other false-match rates $f$ (academic references, 2019--21).", "tab:s12sens"))
    d4 = bd["P4_decoys"]
    out.append(f"Decoys: pool of {d4['build']['pool']:,} titles; skipped when built: same paper "
               f"{d4['build']['skipped']['same_paper']}, no surname or year {d4['build']['skipped']['A_no_surname_or_year']}, "
               f"similarity $\\ge0.80$ with a source title {d4['build']['skipped']['sim_ge_080']}. Every kept decoy has a "
               "similarity below 0.80 with both source titles by construction, so the record of its first source cannot "
               "match it. With the 4 unanswered spliced decoys in the denominator: counted as not found, "
               f"{d4['unanswered_as_not_found']['k']}/{d4['unanswered_as_not_found']['n']}, $f_{{hi}}$ = "
               f"{pct(d4['unanswered_as_not_found']['f_hi'], 2)}\\%, lower end {pct(d4['unanswered_as_not_found']['fp_lower_A'], 2)}\\%; "
               f"counted as found, {d4['unanswered_as_found']['k']}/{d4['unanswered_as_found']['n']}, $f_{{hi}}$ = "
               f"{pct(d4['unanswered_as_found']['f_hi'], 2)}\\%, lower end {pct(d4['unanswered_as_found']['fp_lower_A'], 2)}\\%.")
    out.append(_tabular("@{}lrrlrl@{}", [r"Set & Items & Answered & Rule applied & Found & $f$ (\%) [Clopper--Pearson] \\"],
                        _tab("tab_fam.tex"),
                        "The deep-search match rule applied offline to every candidate stored for the cascade's title "
                        "requests of each labelled item (not the deep search's full-string Crossref request). Items without "
                        "a year fall back to a title similarity of 0.90 with the surname condition kept, as in the deep search. "
                        "The last row holds real references.",
                        "tab:s12fam"))
    u = bd["P6_url"]
    out.append("Found software and web references of 2019--21 by kind of URL answer (rows): " +
               "; ".join(f"{t}: " + ", ".join(f"{k} {v}" for k, v in u[t].items()) for t in ("B", "S", "W")) +
               ". Redirect codes among the 3xx answers: " + ", ".join(f"{esc(k)} {v}" for k, v in u["codes_3xx"].items()) +
               ". A 3xx answer was not followed, so it shows only that the host answers.")
    # periods by tier
    out.append(_tabular("@{}lrrrrl@{}", [r"Tier & $k/N$ 2019--21 & \% & $k/N$ 2024--26 & \% & Difference, points [CI] \\"],
                        _tab("tab_periods.tex"),
                        "R/N by tier in the two periods (exploratory, post hoc), paper bootstrap; the last row gives U/N "
                        "for preprints without an identifier. Power to detect a rise of 0.39 points in the academic R/N: "
                        f"{pct(bd['P7_periods']['power_rn_A_039']['power'], 0)}\\% (two-sided 0.05, bootstrap SE).",
                        "tab:s12periods"))
    n8 = bd["P8_notfound_split"]
    out.append("Not-found academic references of 2019--21 by the best stored deep-search candidate (rows; by branch): " +
               "; ".join(f".{br}: " + ", ".join(f"{ {'a_best_060_080': 'best similarity 0.60--0.80', 'a_best_below_060': 'best below 0.60', 'b_candidate_fails_author_year': 'group b'}.get(k, esc(k))} {v}"
                                                for k, v in g.items()) for br, g in n8["by_branch_rows"].items()) +
               ". Group b: a candidate at or above the rule's similarity failed the surname or year condition.")
    # tier rule binary, H4 without labels
    tb = bd["P10_tier_binary"]
    out.append(f"Tier rule, academic against non-academic ({tb['n']:,} resolved references): agreement "
               f"{pct(tb['binary_agreement'], 1)}\\%; precision of the academic side {pct(tb['precision_academic'], 1)}\\%, of "
               f"the non-academic side {pct(tb['precision_nonacademic'], 1)}\\%; rule says W but the record is J, C or P: "
               f"{tb['rule_W_record_JCP']:,} of {tb['rule_W']:,}; rule says academic but the record is B, S or W: "
               f"{tb['rule_academic_record_nonacademic']:,}.")
    h = bd["P12_h4_auto"]
    rows = [["Identifier-free academic references, 2019--21", f"{h['n_nonid_academic']:,}"],
            ["Tier weights (J, C, P)", ", ".join(f"{k} {pct(v, 1)}" for k, v in h["weights"].items())],
            ["FP certified-real (\\%)", pct(h["fp_certified"], 2)],
            ["FP identifier-free, lower end (\\%)", pct(h["fp_nonid_lower"], 2)],
            ["FP identifier-free, upper end (\\%)", pct(h["fp_nonid_upper"], 2)],
            ["Difference at the lower end (points) [CI]",
             f"{h['effect_lower_end_points']:.2f} [{pct(h['diff_lower_ci'][0], 2)}, {pct(h['diff_lower_ci'][1], 2)}]"],
            ["Difference at the upper end (points) [CI]",
             f"{h['effect_upper_end_points']:.2f} [{pct(h['diff_upper_ci'][0], 2)}, {pct(h['diff_upper_ci'][1], 2)}]"]]
    out.append(longtable("@{}p{0.6\\linewidth}l@{}", ["H4 without labels", "Value"], rows,
                         "H4 without labels (Amendment 8 (J); exploratory): certified-real against identifier-free "
                         "academic references at both ends of the bounds.", "tab:s12h4auto"))
    na = nums["nonacad_interval_2024_26_p3g"]
    out.append("Non-academic tiers of 2024--26 under the full cascade, as the registered interval (references that OpenAlex "
               "never answered count as resolved for the lower and unresolved for the upper value): " +
               "; ".join(f"{t}: {pct(e['lower'], 1)}--{pct(e['upper'], 1)}\\% ({e['U_oa_unanswered']:,} of {e['U']:,} unresolved "
                         f"without an OpenAlex answer, N = {e['n']:,})" for t, e in na.items()) + ".")
    # policy coding
    pcsv = pd.read_csv(RES / "p3g_policy_coding.csv", dtype=str, keep_default_na=False)
    rows = [[esc(r.venue), esc(r.code.replace("_", " ")), esc(r.rests_on), esc(r.numeric_threshold) or "--"] for r in pcsv.itertuples()]
    out.append("{\\footnotesize\n" + longtable("@{}p{0.27\\linewidth}lp{0.42\\linewidth}l@{}", ["Statement", "Code", "Rests on",
                                                                                         "Number"], rows,
                         f"The step between a flag and a rejection in the {pc['n']} counted statements, coded by Claude Code "
                         f"from the stored quotations (descriptive): confirm {pc['counts'].get('confirm', 0)}, no confirm "
                         f"{pc['counts'].get('no_confirm', 0)}, no rule {pc['counts'].get('no_rule', 0)}.", "tab:s12policy") + "}")
    # moved from the article: thresholds by tertile, rules R1-R3 and the identifier scenario
    out.append(r"\subsection*{Thresholds by tertile, conservative rules and identifiers (moved from the article)}")
    out.append(_tabular("@{}llllll@{}", [r"& & \multicolumn{2}{c}{Full cascade} & \multicolumn{2}{c}{Crossref-only} \\",
                                         r"Period & Papers & $\alpha=0.05$ & $\alpha=0.01$ & $\alpha=0.05$ & $\alpha=0.01$ \\"],
                        _tab("tab_kemp.tex"),
                        "Empirical thresholds by tertile of the number of academic references (pooled corpus; cut points "
                        "on 2019--21, " + NV.get("kEmpCuts", "") + "), with the share (\\%) flagged at that $k$.", "tab:s12kemp"))
    out.append("Rules R2 and R3 also bound the intra-paper correlation. For the median paper, with " + NV["nAMed"] +
               " academic references, they need " + NV["kMedR2"] + " and " + NV["kMedR3"] + " unresolved academic references "
               "at $\\alpha=0.05$. With Bonferroni bounds that hold jointly with probability 0.95, the median paper needs " +
               NV["bonfKMedRone"] + " / " + NV["bonfKMedRtwo"] + " / " + NV["bonfKMedRthree"] + " under R1 / R2 / R3, and R1 "
               "still rejects " + NV["bonfRoneFivePct"] + "\\% of legitimate papers at $\\alpha=0.05$. R2 and R3 reject " +
               NV["ruleFullR205K"] + " and " + NV["ruleFullR305K"] + " papers, but their thresholds exceed almost every "
               "observed count, so the low counts do not show that they are calibrated.")
    out.append(_tabular("@{}rllll@{}", [r"& \multicolumn{2}{c}{Full cascade} & \multicolumn{2}{c}{Crossref-only} \\",
                                        r"$n_A$ & $\alpha=0.05$ & $\alpha=0.01$ & $\alpha=0.05$ & $\alpha=0.01$ \\"],
                        _tab("tab_k_typical.tex"),
                        "Per-paper thresholds R1 / R2 / R3 for five typical papers (academic-reference counts $n_A$ at the "
                        "10/25/50/75/90\\% quantiles of the pre-LLM corpus), per-tier bounds as registered. A threshold above "
                        "$n_A$ can never be reached.", "tab:s12ktyp"))
    out.append("A screen can check a printed identifier first and fall back to the title cascade. On certified-real "
               "references rendered with the DOI-printing style, that union screen flags " + NV["scenIdUnion"] + "\\% (" +
               NV["scenIdUnionK"] + "; paper-bootstrap upper bound " + NV["scenIdUnionHi"] + "\\%). The rate rests on one "
               "flag, among references that already resolve by identifier. The identifier route alone fails for " +
               NV["scenIdOnly"] + "\\% (" + NV["scenIdOnlyK"] + "), mostly where no identifier was printed or extracted. "
               "The union rate bounds false rejections only: a fabrication whose title matches a record passes the title "
               "route, so the union screen has no recall guarantee.")
    out.append(_tabular("@{}rlllll@{}", [r"& Without & \multicolumn{2}{c}{Union} & Union & Identifier only \\",
                                         r"$n_A$ & R2 / R3 & $\rho=0$: R2 / R3 & $\rho^+$: R1 / R2 / R3 & $P(N\ge2)$, \% & R1 / R2 / R3 \\"],
                        _tab("tab_k_identifier.tex"),
                        "Thresholds at $\\alpha=0.05$ without and with printed identifiers for the papers of Table "
                        "\\ref{tab:s12ktyp}.", "tab:s12kid"))
    return "\n\n".join(out)


REC = "@@REC@@"  # placeholder for the name of an internal record; resolved by context at the end of sanitize()
TT = r"\\texttt\{(?:[^{}]|\{\})*?"  # start of a \texttt{...} whose body may contain \textbackslash{}


def s11_gt3():
    """S11: automated ground truth of Amendment 8 (GT-3, decoys, positive control, bounds, tier check), the AI rater and
    the errata of Amendment 8. Every number from results/numbers.json (keys *_p3f) and results/p3f_*.csv."""
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    g, tv, rb, rbx, nf, ph = (nums[k] for k in ("gt3_p3f", "tier_validation_p3f", "rB_score_p3f", "rB_vs_gt3_p3f",
                                                  "notfound_profile_p3f", "posthoc_p3f"))
    out = [r"\section{Automated ground truth, AI rater and errata (Amendment 8)}\label{sec:s11}",
           "Amendment 8 (Section S2) withdrew the human-rated checks of Amendment 7 before any human label was read and "
           "defined the ground truth by provenance (GT-1), identifiers (GT-2) and a deep search specified post hoc before "
           "its own execution (GT-3). The tables below are generated from the result files. Units: the tables of "
           "deep-search states, search depth and unanswered shares count distinct (paper, key) pairs; the bounds count "
           "references (rows of the ground truth, the unit of $N$ and $U$). In 2019--21 the academic set has 211 distinct "
           "pairs in 215 rows; in 2024--26 the two counts coincide (827)."]
    # states by set
    st = {}
    for r in g["states"]:
        st.setdefault(r["set"], {})[r["state"]] = r["n"]
    names = {"acad1921": "academic 2019--21 (i)", "acad2426": "academic 2024--26 (ii)", "decoy": "decoys (iii)",
             "posctl": "positive control (iv)", "nonacad1921": "B/S/W 2019--21 (v)"}
    rows = [[names[s], st[s].get("found", 0), st[s].get("not found", 0), st[s].get("unanswered", 0), sum(st[s].values())]
            for s in ("acad1921", "acad2426", "nonacad1921", "decoy", "posctl") if s in st]
    out.append(longtable("@{}lrrrr@{}", ["Set", "Found", "Not found", "Unanswered", "Total"], rows,
                         "Deep-search states by set (unit: distinct (paper, key) pairs). Unanswered: some source failed after three "
                         "passes; it counts with not found in R.", "tab:gt3states"))
    fm = g["false_match"]
    rows = [[esc(f), fm[f]["k"], fm[f]["n"], fm[f]["n_unanswered"], pct(fm[f]["f_hi"], 2)] for f in ("D-splice", "gen_a", "pooled")]
    pc = g["posctl"]["recall"]
    out.append(longtable("@{}lrrrr@{}", ["Decoy family", "Found", "Answered", "Unanswered", r"$f_{\mathrm{hi}}$ (\%)"], rows,
                         f"False-match rate on decoys (Clopper--Pearson upper 95\\% bound). The bounds use "
                         f"$f_{{\\mathrm{{hi}}}}={pct(fm['f_hi_used'], 2)}$\\%. Positive control: {pc['k']} of {pc['n']} "
                         f"certified-real references with identifiers removed were found (recall {pct(pc['rate'], 0)}\\%, "
                         f"Clopper--Pearson [{pct(pc['cp95'][0], 1)}, {pct(pc['cp95'][1], 1)}]\\%).", "tab:gt3decoy"))
    rows = []
    for per in ("2019-21", "2024-26"):
        for t in ("J", "C", "P", "A", "B", "S", "W"):
            e = g["cells"][f"{per}|{t}"]
            b = (f"{pct(e['fp_lower'], 2)} [{pct(e['fp_lower_ci'][0], 2)}, {pct(e['fp_lower_ci'][1], 2)}]",
                 f"{pct(e['fp_upper'], 2)} [{pct(e['fp_upper_ci'][0], 2)}, {pct(e['fp_upper_ci'][1], 2)}]",
                 pct(e["bias_bound_X_hi_over_N"], 2)) if per == "2019-21" else ("--", "--", "--")
            if per == "2024-26" and e["U"] > 0 and e["not_in_set"] == e["U"]:  # tier not in the deep search
                rows.append([per.replace("-", "--"), t, f"{e['N']:,}", f"{e['U']:,}"] + ["--"] * 7)
                continue
            if per == "2019-21" and t in ("S", "W"):  # P3G (S6' S7): URL answers; upper end only
                b = ("--", b[1], b[2])
            rows.append([per.replace("-", "--"), t, f"{e['N']:,}", f"{e['U']:,}", f"{e['F']:,}", e["R_not_found"],
                         e["R_unanswered"], *b, pct(e["R_over_N"], 2)])
    out.append("{\\footnotesize\n" + longtable("@{}llrrrrrlllr@{}", ["Period", "Tier", "N", "U", "F", "R: not f.", "R: unans.",
                                                  "FP lower [CI]", "FP upper [CI]", r"$X_{\mathrm{hi}}/N$", "R/N"], rows,
                         "Bounds by tier and period (\\%). FP $\\in[\\max(0,U-X_{\\mathrm{hi}})/N,\\,U/N]$ with "
                         "$X_{\\mathrm{hi}}=R/(1-f_{\\mathrm{hi}})$; paper bootstrap, $B=1000$, seed 42. "
                         "Unit: references (rows). $X_{\\mathrm{hi}}/N$ is the width of the interval. S and W: upper end "
                         "only, because a URL answer is not evidence of the cited document. B, S and W of 2024--26 were not "
                         "in the deep search (--).", "tab:gt3bounds") + "}")
    # depth and source
    rows = []
    for s in ("acad1921", "acad2426", "nonacad1921"):
        for k, v in sorted(g["depth"].get(s, {}).items()):
            rows.append([names[s], esc(k), v])
    src = "; ".join(f"{names[s]}: " + ", ".join(f"{esc(k)} {v}" for k, v in sorted(g["depth_source"].get(s, {}).items()))
                    for s in ("acad1921", "acad2426", "nonacad1921"))
    out.append(longtable("@{}llr@{}", ["Set", "Search-depth class (first that applies)", "Found"], rows,
                         "Why the deep search found what the cascade did not (Amendment 8 (D); unit: distinct pairs; "
                         "the article counts rows). By source: " + src + ".",
                         "tab:gt3depth"))
    # POST-HOC coverage, R/N sensitivity, unanswered by source
    cv = ph["coverage_academic"]
    rows = [[p.replace("-", "--"), e["U"], e["F"], e["not_found"], e["unanswered"],
             f"{pct(e['not_found_over_U'], 1)} [{pct(e['cp95_not_found_over_U'][0], 1)}, {pct(e['cp95_not_found_over_U'][1], 1)}]"]
            for p, e in cv.items()]
    out.append(longtable("@{}lrrrrl@{}", ["Period", "U", "F", "Not found", "Unanswered", r"Not found / U (\%)"], rows,
                         "POST-HOC (written after the interim deep-search results; descriptive). Academic references "
                         "unresolved by the cascade that no open source finds under the relaxed rule.", "tab:gt3cov"))
    a, n2 = ph["rn_registered"], ph["rn_notfound_only"]
    rows = [["registered: R = not found + unanswered", pct(a["r_over_n_1921"], 2), pct(a["r_over_n_2426"], 2),
             f"{pct(a['diff'], 2)} [{pct(a['ci'][0], 2)}, {pct(a['ci'][1], 2)}]"],
            ["POST-HOC: R = not found only", pct(n2["r_over_n_1921"], 2), pct(n2["r_over_n_2426"], 2),
             f"{pct(n2['diff'], 2)} [{pct(n2['ci'][0], 2)}, {pct(n2['ci'][1], 2)}]"]]
    for s, e in ph["unanswered_by_source"].items():
        rows.append([f"unanswered share, {names[s]}", "", "",
                     f"{e['unanswered']}/{e['n']}" + ("; " + ", ".join(f"missing {esc(k)}: {v['k']}" for k, v in e["by_missing_source"].items())
                                                       if e["by_missing_source"] else "")])
    out.append(longtable("@{}p{0.36\\linewidth}rrp{0.36\\linewidth}@{}", ["Line", r"R/N 2019--21 (\%)", r"R/N 2024--26 (\%)",
                                                                          r"Difference, points [paper bootstrap 95\% CI]"], rows,
                         "R/N between the periods, academic references (exploratory). The registered line counts "
                         "unanswered references in R; the POST-HOC line and the unanswered shares by missing source do "
                         "not replace it. Unanswered shares count distinct pairs (5 of 211 pairs are 5 of 215 rows in "
                         "2019--21).", "tab:gt3rn"))
    # not-found profile (POST-HOC)
    rows = [[esc(k), v] for k, v in nf["by_sign"].items()]
    out.append(longtable("@{}p{0.75\\linewidth}r@{}", ["Sign of a title-extraction error (fixed list)", "References"], rows,
                         f"POST-HOC, descriptive: the {nf['n']} academic references of 2019--21 that the deep search did "
                         f"not find. From .bib: {nf['by_source']['.bib']} ({nf['extract_sign']['.bib']} with a sign); from "
                         f".bbl parsed by GROBID: {nf['by_source']['.bbl (GROBID)']} ({nf['extract_sign']['.bbl (GROBID)']} "
                         f"with a sign). Cited before 2000: {nf['cited_before_2000']}; titles of at most five words: "
                         f"{nf['title_le5_words']}.", "tab:gt3nf"))
    # tier-rule validation
    lab = tv["labels"]
    rows = [[lab[i]] + [f"{v:,}" for v in r] for i, r in enumerate(tv["confusion_machine_rows_record_cols"])]
    out.append(longtable("@{}l" + "r" * len(lab) + "@{}", ["Rule \\textbackslash{} record"] + lab, rows,
                         f"Tier rule against the type of the matched registry record, {tv['n']:,} resolved references "
                         f"(Amendment 8 (I)): agreement {pct(tv['agreement'], 1)}\\%, $\\kappa={tv['kappa']:.2f}$; "
                         f"{tv['version_mismatch_n']:,} preprint--published version mismatches; agreement without them "
                         f"{pct(tv['agreement_without_version_mismatches'], 1)}\\%. Excluded: " +
                         ", ".join(f"{esc(k)} {v:,}" for k, v in tv["excluded_counts"].items()) + ".", "tab:tierval"))
    # AI rater R_B (descriptive; not used for inference)
    rows = [[esc(m["metric"]), esc(m["family"]), f"{m['k']}/{m['n']}",
             f"[{pct(m['cp95_lo'], 0)}, {pct(m['cp95_hi'], 0)}]"] for m in rb["metrics"]]
    out.append(longtable("@{}p{0.5\\linewidth}lrl@{}", ["Measure", "Rows", "k/n", "Clopper--Pearson (\\%)"], rows,
                         "AI rater (a fresh Claude sub-agent) on the sheet of the withdrawn human-rated check: descriptive; "
                         "not used for inference (Amendment 8 (B)). Limits: " + esc(rb["limits"][0]) + "; the notes of rows H40, H50 "
                         "and H54 report a title variant beyond a dropped subtitle (suffix variant, truncated title).",
                         "tab:rbscore"))
    ct = rbx["crosstab"]
    cols = ["found", "not found", "unanswered", "total"]
    rows = [[k] + [ct[k][c] for c in cols] for k in ("exists", "ambiguous", "not-exists", "total")]
    out.append(longtable("@{}lrrrr@{}", ["AI label \\textbackslash{} deep search", "Found", "Not found", "Unanswered", "Total"], rows,
                         f"AI rater label against the deep-search state on the {rbx['n']} flagged references (AI rater; "
                         "descriptive; not used for inference).", "tab:rbgt3"))
    # spot-check (a table to read, not a rating step)
    sp = ROOT / "P3F" / "gt3_spotcheck.md"
    rows = []
    for ln in sp.read_text(encoding="utf-8").splitlines():
        if re.match(r"\|\s*\d+\s*\|", ln):
            c = [x.strip().strip("`") for x in re.split(r"(?<!\\)\|", ln)[1:-1]]
            rows.append([c[0], esc(c[3]), esc(c[4]), c[5], esc(c[8].replace("\\|", "|")), esc(c[9].replace("\\|", "|"))])
    out.append("{\\footnotesize\n" + longtable("@{}rllrp{0.33\\linewidth}p{0.33\\linewidth}@{}",
                                                ["\\#", "Tier", "Source", "Sim.", "Cited title", "Record title"], rows,
                         "Spot-check: ten found references drawn with seed 51, cited title beside the matched record "
                         "title, for the reader to inspect; not a rating step. POST HOC: the seed and the draw are not in "
                         "Amendment 8, and 8 of the 10 rows are 2024--26 references, outside the set the bounds use.",
                         "tab:gt3spot") + "}")
    # registered H4: the hand-verified samples (moved from the article; manual arm AI-assisted, criterion failed)
    nv = pd.read_csv(RES / "numbers_ms_sources.csv", dtype=str, keep_default_na=False).set_index("key").value
    lab = {"accP1ManualExists": "2019--21 sample: references labelled exists",
           "accP1ManualExistsUsedInH4": "of these, with a screen decision on the BibTeX title",
           "fpManRawunion": "full cascade flags, raw (\%)", "hFourManunion": "FP manual, tier-weighted (\%)",
           "fpManAcunionK": "academic identifier-free references flagged", "fpManAcunion": "academic, share (\%)",
           "fpManAcunionCi": "academic, Wilson 95\%", "hFourDiffdblp": "H4 difference with DBLP (points)",
           "hFourDiffCidblp": "interval", "rmTierJunion": "render sample (60): journal flagged",
           "rmTierCunion": "render sample: conference flagged", "rmTierPunion": "render sample: preprint flagged",
           "rmTierBunion": "render sample: book flagged", "rmTierSunion": "render sample: software flagged",
           "rmTierWunion": "render sample: web flagged", "rmPoneDiffunion": "render H4, first-pass labels (points)",
           "rmPoneDiffCiunion": "interval", "rmAdjDiffunion": "render H4, adjudicated (Amendment 5; points)",
           "rmAdjDiffCiunion": "interval", "adjChanged": "labels changed by the adjudication"}
    rows = [[v, nv[k]] for k, v in lab.items() if k in nv.index]
    out.append(longtable("@{}p{0.7\linewidth}l@{}", ["Registered H4, AI-agent-verified samples", "Value"], rows,
                         "Detail of the registered H4 (manual arm AI-assisted; reliability criterion failed; not used for "
                         "inference). The pre-LLM H4 is unchanged by the adjudication, because the three adjudicated "
                         "pre-LLM rows keep their first-pass label.", "tab:h4detail"))
    # errata of Amendment 8 (the hashed file is not edited)
    rows = [["Amendment 8, header", "``Written on 2026-11-08 (about 09:15 UTC)''",
             "The file was hashed at 2026-11-08T09:00:21Z, so it was written before 09:00 UTC; the hash time is the binding one."],
            ["Amendment 8 (B)", "``three rows were rated leniently''",
             "The word does not occur in the AI rater's notes; rows H40, H50 and H54 note a title variant beyond a dropped "
             "subtitle. The phrase described the rater brief, not the file."],
            ["Amendment 9, ``What was known''", "``The labels of the human rater R\\_B''",
             "R\\_B is the AI rater (a fresh Claude sub-agent); no human label had been read."],
            ["Amendment 9 (D)", "needs\\_browser: \\texttt{robots.txt}, bot-block page or refused fetch",
             "When the rule check was written (2026-11-13, about 01:00 UTC), before the author's form was built and "
             "before the key was opened, two further causes were put in this class: a fetch error and a page the fetch "
             "tool returned without readable content (compressed PDF). Table S41 gives the cause of every such row."],
            ["Amendment 9 (F), printed copy", "``the~the AI rater labels''",
             "A doubled article in the printed copy of an earlier draft of this supplement, made when the rater's code "
             "name was replaced by ``the AI rater''; the hashed file has a single article. The printed copy in S2 now "
             "reads ``the AI rater labels''."]]
    out.append(longtable("@{}p{0.2\\linewidth}p{0.25\\linewidth}p{0.5\\linewidth}@{}", ["Document", "Text", "Erratum"], rows,
                         "Errata of Amendments 8 and 9, recorded here because the hashed files are not edited.", "tab:errata"))
    return "\n\n".join(out)


def sanitize(tex):
    """Internal labels out of the printed supplement (R2 Q16; the repository keeps the byte-exact documents):
    internal record names, project and phase labels, run names, local paths, decision times and the agent's initials."""
    # P3G (S6' S11): one sentence of addendum 3 about an internal deadline is omitted (said in the S2 preamble)
    tex = re.sub(r"\s*The paper should be resubmitted before the 2026-11-14 deadline of\s+Amendment 7 \(option A/B\)\.", "", tex)
    tex = re.sub(r"\\texttt\{[^{}]*?(?:REPORT|DECISION|STATUS|PLAN|PROMPT|\\_LOG|HOSTILE|P3[A-E]/)[^{}]*?\}", REC, tex)
    tex = re.sub(r"\b(?:P\d[A-Z]?|PLAN|CP)(?:\\?_[A-Za-z0-9]+)+(?:\\?\.md)\b", REC, tex)
    tex = re.sub(r"\bPLAN(?:\\?_[A-Za-z0-9]+)+", REC, tex)
    tex = re.sub(r"\bP3[A-E]/[\w\\.]+", REC, tex)
    # local paths and backups outside the repository
    tex = re.sub(TT + r"(?:[A-Z]:\\textbackslash|\\%TEMP\\%)(?:[^{}]|\{\})*\}", "a local file outside the repository", tex)
    # scripts and result files whose names carry a phase label
    tex = re.sub(r"\\texttt\{code/p3[a-e]\\_[^{}]*\}", "the corresponding script of the repository", tex)
    tex = re.sub(r"\\texttt\{results/p3[a-e]\\_[^{}]*\}", "a result file of the repository", tex)
    tex = re.sub(r"results/p3[a-e]\\_[\w\\.]+", "a result file", tex)
    tex = re.sub(r"\\texttt\{theory/THEORY\\_43\\_v\d\\?\.md\}", "the theory note", tex)
    # project, phase and checkpoint labels
    tex = re.sub(r"\s*\(topic \d+,\s*(?:phase\s*)?P?\d\)", "", tex)
    tex = re.sub(r"\s*---\s*topic \d+,\s*(?:phase\s*)?P?\d", "", tex)
    tex = re.sub(r"\\texttt\{[^{}]*keys/[^{}]*\}", "an encrypted key file outside the repository", tex)
    tex = re.sub(r"\\texttt\{[^{}]*p3[a-e]\\_[^{}]*\}", "a project file", tex)
    tex = re.sub(r"second author \(\\texttt\{LQD\}\)", "second author", tex)
    tex = re.sub(r"\\texttt\{LQD\}", "the author", tex)
    tex = tex.replace("LQD", "the author")
    tex = re.sub(r"\bCP-?B?(\d)b?\b", r"decision point \1", tex)
    tex = re.sub(r"\bCP-B\*?", "decision point", tex)
    tex = re.sub(r"\bP([0-3])[BC]?\b(?!\()", r"stage \1", tex)
    tex = re.sub(r"\bP3[D-E]\b", "the revision", tex)
    tex = tex.replace("stage 1 run10", "stage 1, final run")
    tex = re.sub(r"\\texttt\{[^{}]*?\\_run\d+[^{}]*\}", "an earlier run", tex)  # e.g. ground_truth_run6 (G11+)
    tex = re.sub(r"(?<![A-Za-z])run\d+\b", "an earlier run", tex)
    tex = re.sub(r"\\texttt\{CC\}", "Claude Code", tex)
    tex = re.sub(r"\bCC\b(?! ?BY)", "Claude Code", tex)
    tex = tex.replace("Cowork", "AI assistant")
    tex = tex.replace("stage stage", "stage").replace('option "stage 2"', "option 2")
    # decision times (dates stay; server timestamps marked UTC stay)
    tex = re.sub(r"\b(20\d\d-\d\d-\d\d) \d\d:\d\d\b(?! UTC)", r"\1", tex)
    # internal-record placeholders, by context
    tex = re.sub(r"\(\s*" + REC + r"(?:\s*§\s*\d+)?(?:\s*,\s*" + REC + r"(?:\s*§\s*\d+)?)*\s*\)", "", tex)
    tex = re.sub(r"\(\s*" + REC + r"\s*,\s*", "(", tex)
    tex = re.sub(r"the diagnostic\s+(?:\\texttt\{)?" + REC + r"\}?", "the diagnostic note", tex)
    tex = re.sub(r"\\texttt\{" + REC + r"\}", "a project note", tex)
    tex = tex.replace(REC, "a project note")
    tex = re.sub(r"decision point (\d) decision", r"decision \1", tex)
    tex = re.sub(r"\s*\(prompt a project note\)", "", tex)
    # P3G (S6' S18): jargon and process leaks in the reproduced documents
    tex = tex.replace("a result file of the repository = a result file of the repository verbatim",
                      "the final rules file is the provisional one, verbatim")
    tex = tex.replace("file a result file of the repository exists", "file exists")
    # whole \texttt{...} tokens that name a local data path or a response cache, then bare occurrences
    tex = re.sub(r"\\texttt\{(?:[^{}]|\{\})*?(?:THS\\_DATASETS|\\_derived/43|cache(?:\\_p3[ef])?/)(?:[^{}]|\{\})*\}",
                 lambda m: "the stored responses (not redistributed)" if "cache" in m.group(0) else "a derived data file (release v1.0.0)", tex)
    tex = re.sub(r"\\?\$THS\\_DATASETS/\\_derived/43/", "the data directory/", tex)
    tex = re.sub(r"(?:the data directory/|\\_derived/43/)?cache\\_p3[ef]/(?:\\textless\{\}source\\textgreater\{\}/|[a-z]+/)?",
                 "the response cache of the revision", tex)
    tex = re.sub(r"(?:the data directory/)?(?:\\_derived/43/)cache/", "the response cache", tex)
    tex = re.sub(r"(\d{4}-\d\d-\d\d) ICT", r"\1", tex)
    tex = re.sub(r"\\texttt\{code/p\d[a-z]?\\_(?:[^{}\\]|\\_|\\\{|\\\}|\\[a-z]+\{\})*\}", "a script of the repository", tex)
    tex = re.sub(r"\bcode/p\d[a-z]?\\_(?:\w|\\_|\.)+", "a script of the repository", tex)
    tex = re.sub(r"\\texttt\{results/p\d[a-z]?\\_(?:[^{}\\]|\\_|\\\{|\\\}|\\[a-z]+\{\})*\}", "a result file of the repository", tex)
    tex = re.sub(r"\bresults/p\d[a-z]?\\_(?:\w|\\_|\.|\*)+(?:\\\{[\w,]+\\\})?", "a result file of the repository", tex)
    tex = re.sub(r"(?:the )?(\\texttt\{)?\.env(\})?(?: (?:file )?of the topic folder)?",
                 lambda m: "a local key file" + ("}" if (m.group(2) and not m.group(1)) else ""), tex)
    tex = re.sub(r"\(Reviewer 2,? (?:questions? )?[^)]*\)", "(pre-submission review by an AI model)", tex)
    tex = tex.replace("(Reviewer 2)", "(pre-submission review by an AI model)").replace("Reviewer 2", "the review")
    tex = re.sub(r"manuscript v1\.\d", "an earlier version of the manuscript", tex)
    tex = re.sub(r"an independent re-?\s*view", "a pre-submission review by an AI model", tex)
    tex = re.sub(r"\bthe independent review\b", "the pre-submission review by an AI model", tex)
    tex = tex.replace("RAM rule", "free-memory rule")
    tex = re.sub(r"(?:\\texttt\{)?2504\.01380/alderlake-micro\}?", "one reference", tex)
    tex = re.sub(r"\s*\d\d:\d\d ICT", "", tex)
    tex = re.sub(r"\bCP3d decision\b", "decision", tex)
    tex = re.sub(r"\bdecision [0-9]\b", "a decision of the author", tex)
    tex = re.sub(r"\bthe a decision of the author\b", "a decision of the author", tex)
    tex = re.sub(r"\bR\\_H1\b", "the human rater", tex)
    tex = re.sub(r"\br\\?_h1\b", "rhone", tex)  # pandoc section ids
    tex = re.sub(r"\s*---\s*Topic \d+ \(RefScreen\)", "", tex)
    tex = re.sub(r"\bR\\_B\b", "the AI rater", tex)
    tex = re.sub(r" +([.,;)])", r"\1", tex)
    # P3H (closure S18): version and review labels, repeated replacements, output suffixes
    tex = re.sub(r"\bmanuscript v1\.2\b|\bv1\.2\b", "draft 1", tex)
    tex = re.sub(r"\bmanuscript v1\.4\b|\bv1\.4\b(?!\d)", "draft 2", tex)
    tex = re.sub(r"S6′(\\textquotesingle s|'s)", "the second review's", tex)
    tex = tex.replace("The S6′ review", "The second pre-submission review")  # P4B: avoid "The the ... review review"
    tex = tex.replace("S6′", "the second pre-submission review")
    tex = re.sub(r"\(?Fable 5\.2\s*·\s*high\)?", "(an AI model)", tex)
    tex = re.sub(r"\s*\(pre-submission review by an AI model\)", "", tex)
    tex = re.sub(r"the stored responses \(not redistributed\)(?:, the stored responses \(not redistributed\))*"
                 r"(?: and the stored responses \(not redistributed\))?", "the stored responses (not redistributed)", tex)
    tex = re.sub(r"\b(the AI rater)(?: the AI rater)+", r"\1", tex)
    tex = re.sub(r"\b([Tt])he the (AI rater|human rater|second human rater)\b", r"\1he \2", tex)  # P4B: "the R_B labels" printed as "the the AI rater labels"
    tex = re.sub(r"a project note(?:, a project note)+", "project notes", tex)
    tex = tex.replace("a project note §6", "a project note")
    tex = re.sub(r"The reviewer\\textquotesingle s objections Q1, Q2, Q5 and Q11 were known\.",
                 "The objections of that review were known.", tex)
    tex = re.sub(r"\\texttt\{[^{}]*?\\_p3[a-h][^{}]*\}", "a result file of the repository", tex)
    tex = re.sub(r"\\texttt\{[^{}]*deep\\_search\\_state[^{}]*\}", "a state file of the repository", tex)
    tex = re.sub(r"\bR\\_H2\b", "the second human rater", tex)
    tex = re.sub(r"stage 3/R2\\_REVIEW[^\s}]*", "the review", tex)
    tex = re.sub(r"\bTheorem 1\b", "Proposition 3", tex)
    tex = re.sub(r"\bCP3[a-z]\b", "a decision point", tex)
    tex = re.sub(r"\\texttt\{[^{}]*p3h\\_evidence\\_key[^{}]*\}", "an encrypted key file", tex)
    tex = re.sub(r"\\texttt\{[^{}]*\bp3[a-h]\\_[^{}]*\}", "a project file of the repository", tex)
    tex = tex.replace("of an earlier version of the manuscript", "of an earlier draft of the manuscript")
    tex = re.sub(r"\b([Tt])he the (AI rater|human rater|second human rater)\b", r"\1he \2", tex)  # P4B, after R_H2
    return tex


def _moved(name, nv):
    """text moved from the article (P3H, CP3e question 6): \nv keys replaced by their values, references to the
    article's sections and propositions written out."""
    t = (ROOT / "supplement" / "moved" / name).read_text(encoding="utf-8")
    t = re.sub(r"\\nv\{([^{}]+)\}", lambda m: nv[m.group(1)], t)
    t = re.sub(r"\\inputtab\s+(\S+)", lambda m: _tab(m.group(1)), t)
    t = re.sub(r"\(Sects?\.~\\ref\{sec:[^}]+\}\)", "(see the article)", t)
    t = re.sub(r"(Sects?\.)~\\ref\{sec:[^}]+\}", "the article", t)
    t = re.sub(r"Proposition~\\ref\{[^}]+\}", "the article's Proposition", t)
    t = re.sub(r"Table~\\ref\{tab:fabsplit\}", "Table 2 of the article", t)
    t = re.sub(r"Table~\\ref\{tab:(?!tau|style|recall)[^}]+\}", "the corresponding table of the article", t)
    t = t.replace("figures/F2_roc_backend_p3e.pdf", "F2_roc_backend_p3e.pdf")
    t = t.replace(chr(92) + "citet{Badalova2026detecting}", "Badalova and Mayr (2026)")
    t = t.replace(chr(92) + "botrule", chr(92) + "bottomrule")
    t = t.replace(r"\begin{table}[t]", r"\begin{table}[htbp]").replace(r"\begin{figure}[t]", r"\begin{figure}[htbp]")
    return t


def s13_p3h():
    """S13 (P3H, POST HOC): web evidence of Amendment 9, dispersion intervals, the two periods by branch, and the render
    and recall sections moved from the article."""
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    nv = _nv()
    ps = nums["period_std_p3h"]
    out = [r"\section{Web evidence, dispersion, periods by branch, render experiment and recall}\label{sec:s13}"]
    out.append(r"\subsection*{Web evidence for the flagged \texttt{.bib} references (Amendment 9; post hoc)}")
    out.append(
        f"The sheet held {nv['evRealN']} flagged academic references of the 2019--21 \\texttt{{.bib}} branch and "
        f"{nv['evPlantN']} planted fabrications, shuffled. Machine states of the real rows: PASS {nv['evPass']}, NEAR "
        f"{nv['evNear']}, unreadable or blocked {nv['evNb']}, FAIL {nv['evFail']}, no page {nv['evNone']}. The author "
        f"confirmed {nv['evConf']} ({nv['evConfOpened']} on pages the tool could not read); planted rows confirmed: "
        f"{nv['evPlantConfK']} (Clopper--Pearson {nv['evPlantConfCi']}\\%), and the search returned no page for any of them. "
        f"Found by the deep search or confirmed: {nv['evNewF']} of {nv['evRealN']}. Every row below gives the one URL "
        "released for it, the rule state and the author's decision (y, n, ?; blank: not asked). The capture time and the "
        "sha256 of every captured page are in a result file of the repository (release v1.0.0).")
    sc = pd.read_csv(RES / "p3h_evidence_score.csv", dtype=str, keep_default_na=False)
    rows = []
    for r in sc.itertuples():
        rows.append([r.ID, "planted" if r.origin == "planted" else "real", esc(r.reference)[:200],
                     (r.url_class_audited or "--") + ("*" if r.url_class_audited != r.url_class else ""),
                     esc(r.state), esc(r.nb_reason), r.author_check or "",
                     "yes" if r.confirmed == "True" else ""])
    out.append("{\\scriptsize\\setlength{\\tabcolsep}{2pt}\n" + longtable(
        "@{}llp{8.0cm}llp{1.6cm}ll@{}", ["ID", "Origin", "Reference (as on the sheet)", "Class", "Rule", "Cause",
                                         "Author", "Conf."], rows,
        "Web evidence, one row per sheet reference (Amendment 9). Class: 1 publisher or issuer, 2 repository, "
        "3 catalogue or bibliography, 4 author page. Rule: PASS, NEAR, FAIL, NONE (no page), needs\\_browser. "
        "Cause: why the fetch tool could not read the page (rows needs\\_browser). Class marked *: corrected on audit "
        "(the searcher's class differed). The URL of each row is listed below the table.",
        "tab:s13web") + "}")
    out.append("\\begin{flushleft}\\scriptsize\n" + "\\\\\n".join(f"{r.ID}: {url(r.url)}" for r in sc.itertuples() if r.url)
               + "\n\\end{flushleft}")
    out.append(_tabular("@{}llll@{}", [r"Web evidence & GT-3 found & GT-3 not found & GT-3 unanswered \\\\"],
                        _tab("tab_cross3_p3h.tex"),
                        "Flagged .bib references of 2019--21 (81): web evidence (Amendment 9) by deep-search state; in "
                        "brackets, rows that the AI rater (Supplement S11) labelled exists. The other rows were not on "
                        "the AI rater's sheet. NEAR+y: the author accepted a NEAR page, which does not count as confirmed.",
                        "tab:s13cross"))
    fm = ps["field_mix_2019_21"]
    cats = ["cs.CV", "cs.LG", "cs.CL", "cs.NI", "cs.CR"]
    frows = []
    for b_, bn in (("bib", ".bib"), ("bbl", ".bbl (GROBID)")):
        n_ = sum(fm[b_].values())
        frows.append(f"{bn} & {n_} & " + " & ".join(f"{fm[b_].get(c, 0)} ({100 * fm[b_].get(c, 0) / n_:.0f})" for c in cats)
                     + f" & {100 * (fm[b_].get('cs.CR', 0) + fm[b_].get('cs.NI', 0)) / n_:.0f} \\\\")
    out.append(_tabular("@{}lrllllll@{}", [r"Branch & Papers & " + " & ".join(cats) + r" & cs.CR + cs.NI (\\%) \\\\"],
                        "\n".join(frows), "Papers of 2019--21 by arXiv category and branch (count, \\% in brackets). The "
                        "branch is a property of the paper (post hoc).", "tab:s13field"))
    out.append(r"\subsection*{Dispersion ratios with intervals (post hoc)}")
    out.append(_tabular("@{}llrrl@{}", [r"Period & Branch & Papers & Ratio & 95\% paper bootstrap \\"],
                        _tab("tab_disp_p3h.tex"),
                        "Dispersion ratio $\\sum_i(N_{A,i}-\\lambda_i)^2/\\sum_iV_{0,i}$ of academic flags, full cascade, "
                        "with each branch's own tier rates; paper bootstrap B = 1000, seed 42.", "tab:s13disp"))
    d = ps["diffs"]
    rows = []
    for m, mn in (("uN", "$U/N$"), ("rN", "$R/N$")):
        for k, kn in (("bib", ".bib"), ("bbl", ".bbl"), ("pooled", "pooled"), ("std", "standardised to the 2019--21 mix")):
            e = d[f"{m}_{k}_diff"]
            rows.append(f"{mn} & {kn} & {100 * e['point']:+.2f} & [{100 * e['ci'][0]:+.2f}, {100 * e['ci'][1]:+.2f}] \\\\")
    out.append(_tabular("@{}llrl@{}", [r"Measure & Branch & 2024--26 minus 2019--21 (points) & 95\% paper bootstrap \\"],
                        "\n".join(rows).replace("-", "$-$").replace("2019$-$$-$21", "2019--21"),
                        "Two periods by branch, academic references, full cascade (post hoc). Share of \\texttt{.bbl} "
                        f"titles among academic references: {nv['psWBblPre']}\\% in 2019--21, {nv['psWBblPost']}\\% in "
                        "2024--26. Standardised: 2024--26 branch rates weighted by the 2019--21 branch mix. Intervals: "
                        "papers resampled within each period, with the 2019--21 weights recomputed in every draw; the "
                        "pooled rows therefore differ slightly from the pooled intervals of the article, which come "
                        "from separate draws.", "tab:s13per"))
    for f in ("F2_roc_backend_p3e.pdf",):
        shutil.copy2(ROOT / "figures" / f, OUT / f)
    out.append(r"\subsection*{Matcher or coverage (moved from the article; exploratory)}")
    out.append(_moved("moved_match_p3h.tex", nv))
    out.append(r"\subsection*{Identifiers and bibliography style (moved from the article)}")
    out.append(_moved("moved_style_p3h.tex", nv))
    out.append(r"\subsection*{Recall on fabricated references and public tools (moved from the article)}")
    out.append(_moved("moved_recall_p3h.tex", nv))
    return "\n\n".join(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s8 = s8_agree()  # P4 (closure2 M14): raters A1-A3 here, so that they do not share names with rules R1-R3
    s8 = re.sub(r"\bR([123])\b", r"A\1", s8)
    s8 = s8.replace(r"\label{sec:s8}", r"\label{sec:s8}" + "\n\nThe raters are called A1--A3 in this section (R1--R3 in "
                    "the protocol documents of Section S2), so that they are not confused with the decision rules R1--R3 "
                    "of the article.", 1)
    parts = [s1_theory(), s2_prereg(), s3_policy(), s4_backend(), s5_diag(), s6_audit(), s7_h5(), s8, s9_tools(), s10_figs(), s11_gt3(),
             s12_p3g(), s13_p3h()]
    pre = r"""\documentclass[10pt]{article}
\usepackage[a4paper,margin=2cm]{geometry}
\usepackage{fontspec}\setmainfont{Cambria}[Ligatures=NoCommon]
\usepackage{unicode-math}\setmathfont{Cambria Math}
\usepackage{longtable,booktabs,array,calc,graphicx,amsmath,tabularx}
\usepackage[hidelinks]{hyperref}\usepackage{xurl}
\newcounter{none}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\renewcommand{\thetable}{S\arabic{table}}\renewcommand{\thefigure}{S\arabic{figure}}\renewcommand{\thesection}{S\arabic{section}}
\setcounter{secnumdepth}{1}
\title{Supplementary material for ``Which Data Source Decides? False Positives of Reference-Existence Checks on arXiv
Computer-Science Bibliographies''}
\author{Dat Lam Quoc}
\date{}
\begin{document}
\maketitle
\tableofcontents
\clearpage
"""
    tex = sanitize(pre + "\n\n\\clearpage\n".join(parts)) + "\n\\end{document}\n"
    (OUT / "supplement.tex").write_text(tex, encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "supplement.tex"], cwd=OUT, capture_output=True)
    log = (OUT / "supplement.log").read_text(encoding="utf-8", errors="replace")
    errs = re.findall(r"^! .*", log, re.M)
    print("errors:", errs[:10], "| pages:", re.search(r"Output written on \S+ \((\d+) pages", log).group(1) if "Output written" in log else "?")


if __name__ == "__main__":
    main()
