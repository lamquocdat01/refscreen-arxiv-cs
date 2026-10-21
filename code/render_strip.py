#!/usr/bin/env python3
"""Topic 43 / P0 / T04: render -> (strip) -> extract the bibliographies of the 30 render-pilot papers.

For each render-pilot paper (refmatch.select_render_papers, seed): the CITED .bib entries (from groundtruth_refs.csv)
are written to a fresh refs.bib in two variants
   orig  : entries as authored
   strip : fields doi, url, eprint, archiveprefix removed (the "identifier-stripped" worst case)
and compiled with a 1-page skeleton (\\nocite{*}) under three numeric styles
   IEEEtran      : stock IEEEtran.bst v1.14 (does not print `doi`)
   IEEEtran_doi  : DOI-printing patch (maxkratz), see env/SETUP.md for repo/commit/sha256
   elsarticle-num: elsarticle-num.bst v2.1
pdflatex -> bibtex -> pdflatex x2 -> pdftotext -enc UTF-8 -> split on "[n]" -> map n to the \\bibitem order of the .bbl.
Per rendered reference we record: the string, a regex-parsed title (style-specific), and whether the entry's own DOI /
arXiv id is printed on the page (whitespace-insensitive check against the .bib value).
Outputs: $THS_DATASETS/_derived/43/render/<id>/<style>_<variant>/ (work dirs),
         $THS_DATASETS/_derived/43/render/rendered_refs.csv, results/p0_render_identifiers.csv
Usage: python render_strip.py --seed 42 [--limit N] [--styles IEEEtran,IEEEtran_doi,elsarticle-num]
"""
import argparse
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
from ground_truth import SRC, DERIVED, parse_bibs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RENDER = DERIVED / "render"
STRIP_FIELDS = {"doi", "url", "eprint", "archiveprefix"}
BST_DIR = ROOT / "env" / "bst"
SKELETON = r"""\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{url}
\usepackage{amsmath,amssymb}
\providecommand{\doi}[1]{doi:\url{#1}}
\providecommand{\href}[2]{#2}
\begin{document}
\nocite{*}
\bibliographystyle{%s}
\bibliography{refs}
\end{document}
"""


SKELETON_ACM = r"""\documentclass[sigconf,nonacm]{acmart}
\citestyle{acmnumeric}
\settopmatter{printacmref=false}
\begin{document}
\title{x}\author{x}\maketitle

\nocite{*}
\bibliographystyle{%s}
\bibliography{refs}
\end{document}
"""


def find_doi_bst():
    for p in sorted(BST_DIR.glob("*.bst")):
        if "doi" in p.stem.lower():
            return p
    return None


DOI_SPECIAL = re.compile(r"(?<!\\)([_%#&])")


def write_bib(entries, path, strip, escape_doi=False):
    import bibtexparser
    from bibtexparser.bibdatabase import BibDatabase
    from bibtexparser.bwriter import BibTexWriter
    db = BibDatabase()
    out = []
    for e in entries:
        e2 = {k: v for k, v in e.items() if not (strip and k.lower() in STRIP_FIELDS)}
        if escape_doi and e2.get("doi"):
            # the DOI-printing IEEEtran patch typesets the DOI as text: an unescaped _ % # & breaks the rest of
            # the bibliography (P0: 109 of 2,664 refs lost). P1 escapes them before rendering (PREREG §6.2).
            e2["doi"] = DOI_SPECIAL.sub(lambda m: "\\" + m.group(1), e2["doi"])
        out.append(e2)
    db.entries = out
    w = BibTexWriter()
    w.indent = "  "
    path.write_text(bibtexparser.dumps(db, w), encoding="utf-8")


def run(cmd, cwd, timeout=180):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return -9, "timeout"


def compile_dir(d, style):
    sk = SKELETON_ACM if style == "ACM-Reference-Format" else SKELETON  # acmart: P1 secondary style
    (d / "main.tex").write_text(sk % style, encoding="utf-8")
    log = []
    for cmd in (["pdflatex", "-interaction=nonstopmode", "main.tex"], ["bibtex", "main"],
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                ["pdflatex", "-interaction=nonstopmode", "main.tex"]):
        rc, out = run(cmd, d)
        log.append((cmd[0], rc))
    if (d / "main.pdf").exists():
        run(["pdftotext", "-enc", "UTF-8", "main.pdf", "main.txt"], d)
    blg = (d / "main.blg").read_text(encoding="utf-8", errors="replace") if (d / "main.blg").exists() else ""
    m = re.search(r"\(There (?:were|was) (\d+) error", blg)
    w = re.search(r"\(There (?:were|was) (\d+) warning", blg)
    return {"pdf": (d / "main.pdf").exists(), "bibtex_errors": int(m.group(1)) if m else 0,
            "bibtex_warnings": int(w.group(1)) if w else 0, "steps": log}


def bbl_keys(d):
    t = (d / "main.bbl").read_text(encoding="utf-8", errors="replace") if (d / "main.bbl").exists() else ""
    return re.findall(r"\\bibitem\s*(?:\[(?:[^\[\]]|\[[^\]]*\])*\])?\s*%?\s*\{([^}]+)\}", t)


def split_refs(txt):
    """Split pdftotext output into numbered references [n] ... ; joins hyphenated line breaks."""
    txt = txt.replace("\f", "\n")
    m = re.search(r"^\s*References\s*$", txt, re.M)
    if m:
        txt = txt[m.end():]
    lines = []
    nxt = 1
    # pdftotext sometimes runs several entries into one line ("... 2024. [48] X. Zhao, ..."): split before an
    # inline "[n]" when n is the next expected number (P1 fix; P0 lost 4 refs of 2608.26587 this way)
    for ln in txt.splitlines():
        ln = ln.rstrip()
        m0 = re.match(r"^\s*\[(\d+)\]", ln)
        if m0:
            nxt = int(m0.group(1)) + 1
        while True:
            m1 = re.search(r"(?<=\S)\s+\[%d\]\s" % nxt, ln)
            if not m1:
                break
            lines.append(ln[:m1.start()])
            ln = ln[m1.start():].lstrip()
            nxt += 1
        lines.append(ln)
    refs, cur, num = {}, [], None
    for ln in lines:
        mm = re.match(r"^\s*\[(\d+)\]\s*(.*)$", ln)
        if mm:
            if num is not None:
                refs[num] = cur
            num, cur = int(mm.group(1)), [mm.group(2)]
        elif num is not None and ln.strip() and not re.fullmatch(r"\s*\d+\s*", ln):
            cur.append(ln.strip())
    if num is not None:
        refs[num] = cur
    out = {}
    for n, parts in refs.items():
        s = ""
        for p in parts:
            if s.endswith("-") and p[:1].islower():
                s = s[:-1] + p
            else:
                s = (s + " " + p).strip()
        out[n] = " ".join(s.split())
    return out


AUTHOR_SEG = re.compile(r"^(and\s+)?((?:[A-Z][a-z]?\.?[\s\-~]*){1,4})?(?:(?:van|von|de|der|den|du|da|di|la|le|del|dos)\s+)*"
                        r"[A-Z][\w'’`\-]+(?:\s+(?:[A-Z][\w'’`\-]+|de|van|der|von|la|di))*$|"
                        r"^et al\.?$|^(and\s+)?others$")
VENUE_SEG = re.compile(r"(\b(19|20)\d\d\b|\bIn:|\bin:|\bProceedings\b|\bProc\.|\bJournal\b|\bConference\b|\bTrans\.|"
                       r"\barXiv\b|\bpreprint\b|\bvol\.|\bpp\.|\bURL\b|\bdoi\b|\bPress\b|\bSpringer\b|\bIEEE\b|\bACM\b)")


def parse_title(s, style):
    """Regex fallback parser (style-aware). Returns the best-guess title or ''."""
    if style.startswith("IEEEtran"):
        m = re.search(r"[“\"](.+?)[,]?[”\"]", s)
        if m:
            return m.group(1).strip(" ,.")
    if style == "acmart":  # "Authors. 2020. Title. In Venue ..."
        m = re.search(r"\.\s(?:19|20)\d\d[a-z]?\.\s(.+?)(?:\.\s|\?\s|$)", s)
        if m:
            return m.group(1).strip(" ,.")
    segs = [x.strip() for x in s.split(", ")]
    i = 0
    while i < len(segs) and AUTHOR_SEG.match(segs[i].rstrip(".,")):
        i += 1
    if i >= len(segs):
        return ""
    title = [segs[i]]
    for x in segs[i + 1:]:
        if VENUE_SEG.search(x):
            break
        title.append(x)
    t = ", ".join(title)
    if style.startswith("IEEEtran") and " and " in t[:60] and i == 0:  # last author 'and X. Y,' glued
        t = t.split(",", 1)[-1]
    return t.strip(" ,.")


def select_render100(gt, seed, per_field=20):
    """P1 render set (PREREG §6.2): the 30 P0 render papers + random 2024-26 papers with a .bib, 20 per field."""
    p0 = set((ROOT / "data_manifest" / "render30_p0.txt").read_text().split())
    rng = random.Random(seed)
    out = []
    for f in ["cs.CV", "cs.LG", "cs.CL", "cs.NI", "cs.CR"]:
        g = gt[(gt.set == "pilot") & (gt.field == f) & (gt.ref_source == "bib")]
        have = sorted(p0 & set(g.arxiv_id))
        rest = sorted(set(g.arxiv_id) - p0)
        rng.shuffle(rest)
        out += have + rest[:max(0, per_field - len(have))]
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="max papers")
    ap.add_argument("--styles", default="IEEEtran,IEEEtran_doi,elsarticle-num")
    ap.add_argument("--no-parsers", action="store_true", help="skip GROBID/anystyle title extraction")
    ap.add_argument("--phase", default="p0", choices=["p0", "p1"],
                    help="p0: 30 papers, groundtruth_refs.csv, p0_* outputs; p1: 100 papers (P0's 30 + 14/field, "
                         "seed), p1_groundtruth_refs_full.csv, p1_* outputs, IEEEtran_doi with escaped DOIs")
    ap.add_argument("--resume", action="store_true", help="p1: skip papers whose render dirs are complete")
    ap.add_argument("--stage0", action="store_true", help="p1: read refs/labels from p1_refs_stage0.csv (identifier "
                    "labels only; route (a) still running) instead of p1_groundtruth_refs_full.csv")
    args = ap.parse_args()
    global RENDER
    if args.phase == "p1":
        RENDER = DERIVED / "render_p1"
        if args.styles == "IEEEtran,IEEEtran_doi,elsarticle-num":
            args.styles = "IEEEtran,IEEEtran_doi,elsarticle-num,acmart,IEEEtran_doi_raw"
        gt = pd.read_csv(DERIVED / ("p1_refs_stage0.csv" if args.stage0 else "p1_groundtruth_refs_full.csv"),
                         dtype={"doi": str, "arxiv": str, "arxiv_id": str, "key": str}, low_memory=False)
        papers = select_render100(gt, args.seed)
    else:
        gt = pd.read_csv(DERIVED / "groundtruth_refs.csv", dtype={"doi": str, "arxiv": str, "arxiv_id": str,
                                                                  "key": str})
        papers = sorted(gt[gt.render30 == 1].arxiv_id.unique())
    if args.limit:
        papers = papers[:args.limit]
    doi_bst = find_doi_bst()
    styles = args.styles.split(",")
    rows, status = [], []
    for pid in papers:
        g = gt[gt.arxiv_id == pid]
        pdir = SRC / pid.replace("/", "_")
        entries = parse_bibs(sorted(pdir.rglob("*.bib")))
        keys = [k for k in g.key if k.lower() in entries]
        ents = [entries[k.lower()] for k in keys]
        meta = g.set_index(g.key.str.lower())
        for style in styles:
            bst = "ACM-Reference-Format" if style == "acmart" else style
            if style.startswith("IEEEtran_doi"):
                if doi_bst is None:
                    status.append(dict(arxiv_id=pid, style=style, variant="-", ok=False, note="BLOCKED: no doi bst"))
                    continue
                bst = doi_bst.stem
            for variant in ("orig", "strip"):
                d = RENDER / pid.replace("/", "_") / f"{style}_{variant}"
                if d.exists():
                    shutil.rmtree(d)
                d.mkdir(parents=True)
                if style.startswith("IEEEtran_doi"):
                    shutil.copy2(doi_bst, d / doi_bst.name)
                write_bib(ents, d / "refs.bib", strip=(variant == "strip"),
                          escape_doi=(args.phase == "p1" and style == "IEEEtran_doi"))
                info = compile_dir(d, bst)
                order = bbl_keys(d)
                txt = (d / "main.txt").read_text(encoding="utf-8", errors="replace") if (d / "main.txt").exists() else ""
                rr = split_refs(txt)
                status.append(dict(arxiv_id=pid, style=style, variant=variant, ok=info["pdf"],
                                   n_bib=len(ents), n_bbl=len(order), n_text=len(rr),
                                   bibtex_errors=info["bibtex_errors"], bibtex_warnings=info["bibtex_warnings"]))
                for n, key in enumerate(order, start=1):
                    s = rr.get(n, "")
                    m = meta.loc[key.lower()] if key.lower() in meta.index else None
                    if isinstance(m, pd.DataFrame):
                        m = m.iloc[0]
                    ns = re.sub(r"\s+", "", s).lower()
                    doi = "" if m is None or pd.isna(m["doi"]) else str(m["doi"])
                    aid = "" if m is None or pd.isna(m["arxiv"]) else str(m["arxiv"])
                    rows.append(dict(arxiv_id=pid, style=style, variant=variant, n=n, key=key, refstr=s,
                                     parsed_title=parse_title(s, style.replace("_raw", "")),
                                     bib_title="" if m is None or pd.isna(m["title"]) else str(m["title"]),
                                     label=None if m is None else m["label"],
                                     bib_has_doi=int(bool(doi) and not doi.startswith("10.48550/")),
                                     bib_has_arxiv=int(bool(aid)),
                                     printed_doi=int(bool(doi) and doi.lower() in ns),
                                     printed_arxiv=int(bool(aid) and aid in ns),
                                     printed_url=int("http" in s or "url" in s.lower()),
                                     id_resolved=int(m is not None and m["id_status"] == "resolved")))
        print(f"{pid}: {len(ents)} entries rendered", flush=True)
    rdf = pd.DataFrame(rows)
    # parser comparison: regex (style-aware) vs GROBID vs anystyle titles, scored against the .bib title
    if not args.no_parsers:
        u = rdf.refstr.fillna("").unique().tolist()
        g = dict(zip(u, rm.grobid_parse(u)))
        a = dict(zip(u, rm.anystyle_parse(u, RENDER / "_anystyle")))
        rdf["title_grobid"] = rdf.refstr.map(lambda s: (g.get(s) or {}).get("title", ""))
        rdf["title_anystyle"] = rdf.refstr.map(lambda s: (a.get(s) or {}).get("title", ""))
        acc = []
        for (st, va), x in rdf[rdf.bib_title.str.len() >= 10].groupby(["style", "variant"]):
            for col in ["parsed_title", "title_grobid", "title_anystyle"]:
                ok = x.apply(lambda r: rm.title_sim(r[col] or "", r.bib_title) >= rm.SIM_THRESHOLD, axis=1)
                acc.append(dict(style=st, variant=va, parser=col.replace("parsed_title", "regex")
                                .replace("title_", ""), n_refs=len(x), n_papers=x.arxiv_id.nunique(),
                                pct_title_correct=round(100 * ok.mean(), 2), seed=args.seed))
        pd.DataFrame(acc).to_csv(ROOT / "results" / f"{args.phase}_parser_accuracy.csv", index=False)
        print(pd.DataFrame(acc).to_string())
    rdf.to_csv(RENDER / "rendered_refs.csv", index=False)
    pd.DataFrame(status).to_csv(ROOT / "results" / f"{args.phase}_render_status.csv", index=False)
    rdf["printed_resolvable_id"] = (((rdf.printed_doi == 1) | (rdf.printed_arxiv == 1)) & (rdf.id_resolved == 1)).astype(int)
    summ = rdf.groupby(["style", "variant"]).agg(n_refs=("key", "size"), n_papers=("arxiv_id", "nunique"),
                                                 pct_text_found=("refstr", lambda x: 100 * (x != "").mean()),
                                                 pct_printed_doi=("printed_doi", lambda x: 100 * x.mean()),
                                                 pct_printed_arxiv=("printed_arxiv", lambda x: 100 * x.mean()),
                                                 pct_printed_resolvable_id=("printed_resolvable_id",
                                                                            lambda x: 100 * x.mean()),
                                                 pct_bib_has_doi=("bib_has_doi", lambda x: 100 * x.mean()))
    sub = rdf[rdf.bib_has_doi == 1].groupby(["style", "variant"]).printed_doi.agg(
        n_refs_with_bib_doi="size", pct_bib_doi_printed=lambda x: 100 * x.mean())
    summ = summ.join(sub).round(2).reset_index()
    summ["seed"] = args.seed
    summ.to_csv(ROOT / "results" / f"{args.phase}_render_identifiers.csv", index=False)
    print(summ.to_string())


if __name__ == "__main__":
    main()
