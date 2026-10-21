#!/usr/bin/env python3
"""Topic 43 / P0 / T03: reference-level ground truth for the pilot corpus.

For every KEPT paper in manifest.csv:
  * cited keys = \\bibitem / \\entry keys of the author's .bbl (if present), else \\cite-family keys in the .tex;
  * references = cited entries of the paper's .bib file(s) (bibtexparser);  bbl-only papers are counted, not labelled;
  * identifiers: doi field / doi.org URL / 10.48550 DOI; arXiv id from eprint, url, journal, note, howpublished;
  * identifier resolution: DOI -> Crossref -> OpenAlex (doi lookup, free) -> DataCite;  arXiv id -> arXiv API;
  * label:  certified-real  = an identifier resolves AND title similarity >= 0.9 with the registry record
            mismatch        = an identifier resolves but title similarity < 0.9
            unresolved      = no identifier, or identifier not found in any registry
  * title-only resolution (the "screen" on the original .bib title): Crossref query.bibliographic + Semantic Scholar
    title match (+ arXiv title search only when both fail); resolved if similarity >= 0.9 with >= 1 source.
    Run on the pre-LLM set (-> u0) and on the 30 render-pilot papers (bib-source baseline for T04).
Outputs: $THS_DATASETS/_derived/43/groundtruth_refs.csv (one row per reference),
         results/p0_groundtruth.json, results/p0_groundtruth_papers.csv
Usage: python ground_truth.py --seed 42 [--limit N] [--title-only prellm,render30|all|none] [--workers 6]
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import time
import faulthandler
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("THS_DATASETS", r"D:\Datasets"))
SRC = DATA / "arxiv_src_43" / "src"
DERIVED = DATA / "_derived" / "43"

BIBITEM = re.compile(r"\\bibitem\s*(?:\[(?:[^\[\]]|\[[^\]]*\])*\])?\s*%?\s*\{([^}]+)\}")
BIBLATEX_ENTRY = re.compile(r"\\entry\{([^}]+)\}\{")
CITE = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]+)\}")


def read_text(p):
    b = p.read_bytes()
    for enc in ("utf-8", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def strip_comments(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def parse_bibs(paths):
    import bibtexparser
    from bibtexparser.bparser import BibTexParser
    entries = {}
    # one paper = one BibTeX namespace: @string macros may be defined in a sibling .bib (abbrev.bib)
    text = "\n".join(read_text(p) for p in paths)
    db = None
    for interp in (True, False):
        parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False, interpolate_strings=interp)
        try:
            db = bibtexparser.loads(text, parser=parser)
            break
        except Exception as e:  # undefined macro or malformed author bib
            print(f"  ! bib parse error ({'interp' if interp else 'raw'}) {paths[0].parent.name}: "
                  f"{e.__class__.__name__}", flush=True)
    if db is None:
        return entries
    for e in db.entries:
        e.update({k: str(v) for k, v in e.items() if not isinstance(v, str)})
    if True:
        for e in db.entries:
            k = e.get("ID", "").strip()
            if k and k.lower() not in entries:
                entries[k.lower()] = e
    return entries


def cited_keys(paper_dir, main_tex):
    bbls = list(paper_dir.rglob("*.bbl"))
    keys = []
    for b in bbls:
        t = read_text(b)
        keys += BIBITEM.findall(t) + BIBLATEX_ENTRY.findall(t)
    src = "bbl"
    if not keys:
        src = "tex"
        for t in paper_dir.rglob("*.tex"):
            for grp in CITE.findall(strip_comments(read_text(t))):
                keys += [k.strip() for k in grp.split(",") if k.strip()]
    seen, out = set(), []
    for k in keys:
        if k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out, src


def identifiers(e):
    doi = rm.clean_doi(e.get("doi", ""))
    if not doi:
        for f in ("url", "howpublished", "note", "eprint"):
            m = re.search(r"doi\.org/(10\.\d{4,9}/\S+)", e.get(f, ""), re.I)
            if m:
                doi = rm.clean_doi(m.group(1))
                break
    aid = ""
    if doi.startswith("10.48550/arxiv."):
        aid = doi.split("arxiv.", 1)[1]
    ep = e.get("eprint", "").strip()
    if not aid and re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", ep):
        aid = re.sub(r"v\d+$", "", ep)
    if not aid:
        for f in ("url", "journal", "booktitle", "note", "howpublished", "volume", "publisher", "eprint"):
            aid = rm.arxiv_from_text(e.get(f, ""))
            if aid:
                break
    return doi, aid


def bbl_items(pdir):
    """Reference items of the author's .bbl: list of (key, text, fields). biblatex .bbl -> fields parsed directly;
    BibTeX .bbl -> LaTeX-stripped text (to be parsed by GROBID)."""
    items = []
    for b in sorted(pdir.rglob("*.bbl")):
        t = read_text(b)
        if "\\entry{" in t:
            for m in re.finditer(r"\\entry\{([^}]+)\}\{[^}]*\}\{[^}]*\}(.*?)\\endentry", t, re.S):
                body = m.group(2)
                f = {}
                mt = re.search(r"\\field\{title\}\{(.*?)\}\s*$", body, re.M)
                f["title"] = rm.strip_latex(mt.group(1)) if mt else ""
                md = re.search(r"\\verb\{doi\}\s*\\verb\s+(\S+)", body)
                f["doi"] = md.group(1) if md else ""
                me = re.search(r"\\(?:field|verb)\{eprint\}\s*(?:\{|\\verb\s+)([^}\s]+)", body)
                f["arxiv"] = me.group(1) if me else ""
                items.append((m.group(1), rm.strip_latex(body), f))
            continue
        parts = re.split(r"\\bibitem\s*(?:\[(?:[^\[\]]|\[[^\]]*\])*\])?\s*%?\s*\{([^}]+)\}", t)
        for i in range(1, len(parts) - 1, 2):
            body = parts[i + 1].split("\\end{thebibliography}")[0]
            body = re.sub(r"\\(?:bibinfo|bibfield)\{[^}]*\}", "", body)
            body = re.sub(r"\\href\s*\{[^}]*\}", "", body)
            body = re.sub(r"\\(?:newblock|urlprefix|BIBentry\w*|providecommand\S*)", " ", body)
            body = re.sub(r"\\doi\{([^}]*)\}", r"doi:\1", body)
            body = re.sub(r"\\url\{([^}]*)\}", r"\1", body)
            items.append((parts[i], rm.strip_latex(body), None))
    return items


def refs_from_bbl(r, pdir):
    items = bbl_items(pdir)
    texts = [it[1] for it in items if it[2] is None]
    parsed = iter(rm.grobid_parse(texts)) if texts else iter([])
    out = []
    for key, text, f in items:
        if f is None:
            g = next(parsed, {}) or {}
            f = {"title": g.get("title", ""), "doi": g.get("doi", "") or (rm.DOI_RE.search(text).group(1)
                                                                         if rm.DOI_RE.search(text) else ""),
                 "arxiv": rm.arxiv_from_text(g.get("arxiv", "")) or rm.arxiv_from_text(text)}
        doi = rm.clean_doi(f["doi"])
        aid = rm.arxiv_from_text(f["arxiv"]) or (f["arxiv"] if re.fullmatch(r"\d{4}\.\d{4,5}", f["arxiv"] or "")
                                                 else "")
        if doi.startswith("10.48550/arxiv."):
            aid = aid or doi.split("arxiv.", 1)[1]
        out.append(dict(arxiv_id=r["arxiv_id"], set=r["set"], field=r["field"], year=int(r["year"]), key=key,
                        entrytype="", title=f["title"], doi=doi, arxiv=aid,
                        has_doi=int(bool(doi) and not doi.startswith("10.48550/")), has_arxiv=int(bool(aid)),
                        has_url=int("http" in text), ref_source="bbl-grobid"))
    return out


def load_refs(rows):
    refs, papers = [], []
    for r in rows:
        pdir = SRC / r["arxiv_id"].replace("/", "_")
        bibs = sorted(pdir.rglob("*.bib"))
        keys, ksrc = cited_keys(pdir, r["main_tex"])
        if not bibs:
            br = refs_from_bbl(r, pdir)
            refs += br
            papers.append(dict(arxiv_id=r["arxiv_id"], set=r["set"], field=r["field"], year=int(r["year"]),
                               n_bib_files=0, n_cited_keys=len(keys), cited_source="bbl", n_refs_bib=len(br),
                               n_cited_missing_in_bib=0, bbl_only=1))
            continue
        entries = parse_bibs(bibs) if bibs else {}
        if entries and keys:
            used = [entries[k.lower()] for k in keys if k.lower() in entries]
            missing = sum(1 for k in keys if k.lower() not in entries)
        elif entries:
            used, missing = list(entries.values()), 0
            ksrc = "all-bib"
        else:
            used, missing = [], len(keys)
        papers.append(dict(arxiv_id=r["arxiv_id"], set=r["set"], field=r["field"], year=int(r["year"]),
                           n_bib_files=len(bibs), n_cited_keys=len(keys), cited_source=ksrc,
                           n_refs_bib=len(used), n_cited_missing_in_bib=missing,
                           bbl_only=int(not bibs)))
        for e in used:
            doi, aid = identifiers(e)
            refs.append(dict(arxiv_id=r["arxiv_id"], set=r["set"], field=r["field"], year=int(r["year"]),
                             key=e.get("ID", ""), entrytype=e.get("ENTRYTYPE", ""),
                             title=rm.strip_latex(e.get("title", "")), doi=doi, arxiv=aid,
                             author=e.get("author", ""),
                             has_doi=int(bool(doi) and not doi.startswith("10.48550/")),
                             has_arxiv=int(bool(aid)), has_url=int(bool(e.get("url", "").strip())),
                             ref_source="bib"))
    return refs, papers


def label_identifiers(refs):
    arx = rm.arxiv_ids([r["arxiv"] for r in refs if r["arxiv"]])

    def one(r):
        res = []
        if r["doi"] and not r["doi"].startswith("10.48550/"):
            be, titles = rm.resolve_doi(r["doi"])
            if titles:
                res.append((be, max(rm.title_sim(t, r["title"]) for t in titles)))
        if r["arxiv"] and r["arxiv"] in arx:
            res.append(("arxiv", rm.title_sim(arx[r["arxiv"]], r["title"])))
        if not (r["doi"] or r["arxiv"]):
            r.update(id_status="no-id", label="unresolved", id_backend="", id_sim=np.nan)
        elif not res:
            r.update(id_status="not-found", label="unresolved", id_backend="", id_sim=np.nan)
        else:
            be, s = max(res, key=lambda x: x[1])
            r.update(id_status="resolved", id_backend=be, id_sim=round(s, 4),
                     label="certified-real" if s >= rm.SIM_THRESHOLD else "mismatch")
        return r

    def safe(r):  # one bad reference must not kill the run (P0B fix): record the error and keep going
        try:
            return one(r)
        except Exception as e:
            r.update(id_status="error", label="unresolved", id_backend="", id_sim=np.nan,
                     err=f"{e.__class__.__name__}: {e}"[:200])
            print(f"  ! id-label error {r['arxiv_id']}/{r['key']}: {e.__class__.__name__}: {e}", flush=True)
            return r

    with ThreadPoolExecutor(6) as ex:
        list(ex.map(safe, refs))


def title_only(refs, workers):
    def one(r):
        t = r["title"]
        if len(rm.norm(t)) < 10:
            r.update(to_status="no-title")
            return r
        cr = rm.crossref_search(t)
        cr_s, cr_id = rm.best_sim(cr, title=t)
        # S2 (keyless, heavily 429-throttled) only when Crossref does not resolve, unless already cached.
        # The union decision (to_status) is identical; only the per-backend S2 column loses coverage.
        if cr_s < rm.SIM_THRESHOLD or rm.is_cached("s2", *rm.s2_match_req(t)):
            s2 = rm.s2_match(t)
        else:
            s2 = "skipped"
        s2_s, s2_id = rm.best_sim(s2, title=t) if s2 != "skipped" else (np.nan, "")
        ax_s, ax_id = np.nan, ""
        if cr_s < rm.SIM_THRESHOLD and not (s2_s >= rm.SIM_THRESHOLD):
            ax = rm.arxiv_title_search(t)
            ax_s, ax_id = rm.best_sim(ax, title=t)
        r.update(to_cr_id=cr_id if cr_s >= rm.SIM_THRESHOLD else "", to_s2_id=s2_id if s2_s >= rm.SIM_THRESHOLD else "",
                 to_ax_id=ax_id if (not np.isnan(ax_s) and ax_s >= rm.SIM_THRESHOLD) else "")
        r.update(to_crossref=round(cr_s, 4) if cr is not None else np.nan,
                 to_s2=round(s2_s, 4) if s2 not in (None, "skipped") else np.nan,
                 to_arxiv=round(ax_s, 4) if not (isinstance(ax_s, float) and math.isnan(ax_s)) else np.nan,
                 to_err=int(cr is None or s2 is None))
        if s2 == "skipped":
            s2 = []
        best = np.nanmax([cr_s, 0 if np.isnan(s2_s) else s2_s, 0 if np.isnan(ax_s) else ax_s])
        if best < rm.SIM_THRESHOLD and cr is None and s2 is None:
            r.update(to_status="error")  # both backends failed (network/429 exhausted): not evidence of non-existence
            return r
        r.update(to_status="resolved" if best >= rm.SIM_THRESHOLD else "unresolved")
        return r

    done = [0]
    t0 = time.time()

    def wrapped(r):
        try:
            out = one(r)
        except Exception as e:
            r.update(to_status="error", to_err=1, err=f"{e.__class__.__name__}: {e}"[:200])
            print(f"  ! title-only error {r['arxiv_id']}/{r['key']}: {e.__class__.__name__}: {e}", flush=True)
            out = r
        done[0] += 1
        if done[0] % 200 == 0:
            print(f"  title-only {done[0]}/{len(refs)} ({time.time() - t0:.0f}s)", flush=True)
        return out

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(wrapped, refs))


def author_check(refs):
    """u0 definition 2: a title-resolved reference counts as matched only if the first .bib author surname occurs in
    the author list of the matched registry record (Crossref DOI record > S2 paper > arXiv entry)."""
    def one(r):
        if r.get("to_status") != "resolved":
            return r
        bs = rm.bib_surnames(r.get("author", ""))
        if not bs:
            r.update(ta_status="no-author")
            return r
        names = None
        try:
            if r.get("to_cr_id"):
                names = rm.crossref_doi_authors(r["to_cr_id"])
            if not names and r.get("to_s2_id"):
                names = rm.s2_paper_authors(r["to_s2_id"])
            if not names and r.get("to_ax_id"):
                names = rm.arxiv_entry_authors(r["to_ax_id"])
        except Exception as e:
            print(f"  ! author-check error {r['arxiv_id']}/{r['key']}: {e.__class__.__name__}: {e}", flush=True)
        m = rm.first_author_match(bs, names)
        r.update(ta_status="no-registry-authors" if m is None else ("match" if m else "author-mismatch"))
        return r

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(one, refs))


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def boot_ratio(df, num, den_mask, seed, B=1000):
    """Paper-level bootstrap of sum(num)/sum(den) (references clustered within papers)."""
    g = df[den_mask].groupby("arxiv_id")[num].agg(["sum", "count"])
    if len(g) < 10:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), (B, len(g)))
    s, c = g["sum"].values[idx].sum(1), g["count"].values[idx].sum(1)
    v = s / c
    return (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="max papers (0 = all kept)")
    ap.add_argument("--title-only", default="prellm,render30")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    with (DATA / "arxiv_src_43" / "manifest.csv").open(encoding="utf-8") as f:
        mrows = [r for r in csv.DictReader(f) if r["status"] == "kept"]
    if args.limit:
        mrows = mrows[:args.limit]
    render30 = set(rm.select_render_papers(mrows, args.seed))
    print(f"papers kept: {len(mrows)}; render pilot: {len(render30)}", flush=True)

    refs, papers = load_refs(mrows)
    print(f"refs from .bib (cited): {len(refs)}", flush=True)
    label_identifiers(refs)
    print("identifier labels done", flush=True)
    sel = args.title_only
    to_refs = [r for r in refs if sel == "all" or (r["set"] == "prellm" and "prellm" in sel)
               or (r["arxiv_id"] in render30 and "render30" in sel)]
    if sel != "none":
        print(f"title-only queries for {len(to_refs)} refs", flush=True)
        title_only(to_refs, args.workers)
        pre_refs = [r for r in to_refs if r["set"] == "prellm"]
        print(f"author check (u0 def. 2) for {len(pre_refs)} pre-LLM refs", flush=True)
        author_check(pre_refs)

    df = pd.DataFrame(refs)
    for c in ["to_status", "to_crossref", "to_s2", "to_arxiv", "to_err", "ta_status"]:
        if c not in df:
            df[c] = np.nan
    df["render30"] = df.arxiv_id.isin(render30).astype(int)
    DERIVED.mkdir(parents=True, exist_ok=True)
    df.to_csv(DERIVED / "groundtruth_refs.csv", index=False)
    pdf = pd.DataFrame(papers)
    pdf["render30"] = pdf.arxiv_id.isin(render30).astype(int)
    pdf.to_csv(ROOT / "results" / "p0_groundtruth_papers.csv", index=False)

    df["cert"] = (df.label == "certified-real").astype(int)
    df["arxiv_only"] = ((df.has_arxiv == 1) & (df.has_doi == 0)).astype(int)
    out = {"seed": args.seed, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "smoke_test": bool(args.limit), "limit": args.limit, "title_only_sets": args.title_only,
           "backends_used": {"identifier": "Crossref works/<doi> > OpenAlex works/doi (free) > DataCite; arXiv id_list",
                             "title_only": "Crossref query.bibliographic + Semantic Scholar search/match (keyless, "
                                           "1.1 s/req) + arXiv ti: search fallback",
                             "openalex_search": bool(rm.OPENALEX_SEARCH_ENABLED),
                             "openalex_api_key_present": bool(os.environ.get("OPENALEX_API_KEY"))},
           "definitions": {
               "certified_real": "identifier (DOI or arXiv id) resolves in Crossref/OpenAlex/DataCite/arXiv AND "
                                 "title similarity >= 0.9 (max of normalised Levenshtein, token Jaccard)",
               "u0": "share of pre-LLM (2019-2021) cited .bib references with a usable title (>= 10 chars) that are "
                     "NOT resolved by title-only search (Crossref query.bibliographic + Semantic Scholar match, "
                     "arXiv title search as fallback; similarity >= 0.9)"},
           "papers": {}, "strata": [], "u0": {}}
    for s in ["pilot", "prellm"]:
        p = pdf[pdf.set == s]
        out["papers"][s] = {"kept": int(len(p)), "with_bib": int((p.bbl_only == 0).sum()),
                            "bbl_only": int(p.bbl_only.sum()), "refs_labelled": int((df.set == s).sum())}
    for (s, f, y), g in df.groupby(["set", "field", "year"]):
        out["strata"].append({"set": s, "field": f, "year": int(y), "n_papers": int(g.arxiv_id.nunique()),
                              "n_refs": int(len(g)), "pct_doi": round(100 * g.has_doi.mean(), 1),
                              "pct_arxiv_only": round(100 * g.arxiv_only.mean(), 1),
                              "pct_certified_real": round(100 * g.cert.mean(), 1),
                              "pct_mismatch": round(100 * (g.label == "mismatch").mean(), 1)})
    for s in ["pilot", "prellm"]:
        g = df[df.set == s]
        if len(g):
            out[f"overall_{s}"] = {"n_papers": int(g.arxiv_id.nunique()), "n_refs": int(len(g)),
                                   "pct_doi": round(100 * g.has_doi.mean(), 2),
                                   "pct_arxiv_only": round(100 * g.arxiv_only.mean(), 2),
                                   "pct_no_identifier": round(100 * (g.id_status == "no-id").mean(), 2),
                                   "pct_certified_real": round(100 * g.cert.mean(), 2),
                                   "pct_mismatch": round(100 * (g.label == "mismatch").mean(), 2),
                                   "pct_id_not_found": round(100 * (g.id_status == "not-found").mean(), 2)}
    pre = df[(df.set == "prellm") & df.to_status.isin(["resolved", "unresolved"])].copy()
    if len(pre):
        pre["unres"] = (pre.to_status == "unresolved").astype(int)
        k, n = int(pre.unres.sum()), int(len(pre))
        out["u0"]["all_titled_refs"] = {"k_unresolved": k, "n": n, "n_papers": int(pre.arxiv_id.nunique()),
                                        "u0": round(k / n, 4), "wilson95": [round(x, 4) for x in wilson(k, n)],
                                        "paper_bootstrap95": [round(x, 4) for x in
                                                              boot_ratio(pre, "unres", pre.index == pre.index,
                                                                         args.seed)]}
        c = pre[pre.cert == 1]
        if len(c):
            k2, n2 = int(c.unres.sum()), int(len(c))
            out["u0"]["certified_real_only"] = {"k_unresolved": k2, "n": n2, "u0": round(k2 / n2, 4),
                                                "wilson95": [round(x, 4) for x in wilson(k2, n2)]}
        for be, col in [("crossref", "to_crossref"), ("s2", "to_s2")]:
            v = pre[col].dropna()
            out["u0"][f"backend_{be}_only"] = {"n": int(len(v)),
                                               "u0": round(float((v < rm.SIM_THRESHOLD).mean()), 4)}
        out["u0"]["n_query_errors"] = int(pre.to_err.fillna(0).sum())
        for src, g in pre.groupby("ref_source"):
            k3, n3 = int(g.unres.sum()), int(len(g))
            out["u0"][f"source_{src}"] = {"k_unresolved": k3, "n": n3, "n_papers": int(g.arxiv_id.nunique()),
                                          "u0": round(k3 / n3, 4), "wilson95": [round(x, 4) for x in wilson(k3, n3)]}
        out["u0"]["by_field"] = {f: {"k": int(g.unres.sum()), "n": int(len(g)), "n_papers": int(g.arxiv_id.nunique()),
                                     "u0": round(float(g.unres.mean()), 4)} for f, g in pre.groupby("field")}
        out["u0"]["def1_title_only"] = dict(out["u0"]["all_titled_refs"],
                                            definition="title-only search does not resolve (sim >= 0.9)")
        # definition 2: title resolves AND first .bib author surname is in the matched record's author list
        ev = pre[(pre.to_status == "unresolved") | pre.ta_status.isin(["match", "author-mismatch"])].copy()
        ev["unres2"] = ((ev.to_status == "unresolved") | (ev.ta_status == "author-mismatch")).astype(int)
        k2, n2 = int(ev.unres2.sum()), int(len(ev))
        out["u0"]["def2_title_author"] = {
            "definition": "title-only search does not resolve, OR it resolves but the first .bib author surname is "
                          "not in the matched registry record's authors; refs with no .bib author or no registry "
                          "author list are excluded",
            "k_unmatched": k2, "n": n2, "n_papers": int(ev.arxiv_id.nunique()),
            "u0": round(k2 / n2, 4) if n2 else None, "wilson95": [round(x, 4) for x in wilson(k2, n2)],
            "paper_bootstrap95": [round(x, 4) for x in boot_ratio(ev, "unres2", ev.index == ev.index, args.seed)],
            "k_author_mismatch_only": int((ev.ta_status == "author-mismatch").sum()),
            "n_excluded_no_bib_author": int((pre.ta_status == "no-author").sum()),
            "n_excluded_no_registry_authors": int((pre.ta_status == "no-registry-authors").sum())}
        out["u0"]["n_title_only_error_excluded"] = int((df[df.set == "prellm"].to_status == "error").sum())
    # certified-real subset vs all refs: how unrepresentative is the FP denominator?
    bias = {}
    for s_ in ["pilot", "prellm"]:
        g = df[df.set == s_]
        c = g[g.cert == 1]
        if len(g) and len(c):
            bias[s_] = {"n_refs": int(len(g)), "n_certified": int(len(c)),
                        "pct_certified": round(100 * len(c) / len(g), 2),
                        "pct_doi_all": round(100 * g.has_doi.mean(), 2), "pct_doi_cert": round(100 * c.has_doi.mean(), 2),
                        "pct_arxiv_only_all": round(100 * g.arxiv_only.mean(), 2),
                        "pct_arxiv_only_cert": round(100 * c.arxiv_only.mean(), 2),
                        "pct_article_all": round(100 * (g.entrytype.str.lower() == "article").mean(), 2),
                        "pct_article_cert": round(100 * (c.entrytype.str.lower() == "article").mean(), 2),
                        "field_share_all": {k: round(v, 3) for k, v in g.field.value_counts(normalize=True).items()},
                        "field_share_cert": {k: round(v, 3) for k, v in c.field.value_counts(normalize=True).items()}}
            if g.to_status.isin(["resolved", "unresolved"]).any():
                ga = g[g.to_status.isin(["resolved", "unresolved"])]
                ca = ga[ga.cert == 1]
                bias[s_]["title_only_unresolved_all"] = {"k": int((ga.to_status == "unresolved").sum()), "n": int(len(ga))}
                bias[s_]["title_only_unresolved_cert"] = {"k": int((ca.to_status == "unresolved").sum()), "n": int(len(ca))}
    out["certified_real_bias"] = bias
    (ROOT / "results" / "p0_groundtruth.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k.startswith("overall") or k in ("papers", "u0")}, indent=1))


if __name__ == "__main__":
    DERIVED.mkdir(parents=True, exist_ok=True)
    _fh = (DERIVED / "ground_truth_fault.log").open("a", encoding="utf-8")
    faulthandler.enable(_fh)  # hard crashes (segfault / abort) leave a stack here
    try:
        main()
    except BaseException as _e:
        tb = traceback.format_exc()
        with (DERIVED / "ground_truth_crash.log").open("a", encoding="utf-8") as f:
            f.write(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} argv={sys.argv}\n{tb}\n")
        print(tb, file=sys.stderr, flush=True)
        raise
