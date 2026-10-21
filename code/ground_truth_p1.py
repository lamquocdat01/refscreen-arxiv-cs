#!/usr/bin/env python3
"""Topic 43 / P1 / T07 route (a): reference-level ground truth on the full corpus, as pre-registered (PREREG_43.md).

Per cited reference of every kept paper (P0 helpers from ground_truth.py are reused for parsing):
  tier            P / S / J / C / B / W by the machine rule of PREREG §2 (conflict order P > S > J > C > B > W)
  has_doi, has_arxiv, certified_real (identifier resolves AND title similarity >= 0.9; PREREG §3)
  def1_status     title-only cascade (PREREG_AMENDMENT_3 order): round 1 Crossref -> arXiv ti: (only refs with an
                  arXiv id or tier P) -> DBLP (offline dump, dblp_offline.py) -> OpenAlex (keyless pool, skipped once
                  refused) -> S2 (stored answers only); round 2 (after round 1 of every set) re-queries the
                  non-resolved refs with live S2 calls;
                  resolved / unresolved / rate-limited / no-title (PREREG §4)
  def2_status     def 1 + first .bib author surname in the matched record; adds excluded-no-author,
                  excluded-no-registry-authors
  backends_hit    backends whose best candidate reached similarity >= 0.9
Rate-limited references are re-queried after round 2 in up to 3 rounds spaced 2, 4, 8 minutes (PREREG §4).
Interim outputs: $THS_DATASETS/_derived/43/p1_refs_stage0.csv (refs + tiers + identifier labels, before the cascade);
results/p1_groundtruth_round1_<set>.json (u_s after round 1 of a set, label "round 1, before S2").
Papers whose \\cite keys are all missing from their .bib fall back to their .bbl (source = bbl); without a usable
.bbl they are excluded and listed.
Outputs: $THS_DATASETS/_derived/43/p1_groundtruth_refs_full.csv (all columns)
         results/p1_groundtruth.csv (per reference, PREREG columns), results/p1_groundtruth_papers.csv,
         results/p1_groundtruth.json (corpus counts, exclusions, u_s by tier x period x definition)
Usage: python ground_truth_p1.py --seed 42 [--limit N] [--sets prellm,pilot] [--workers 6] [--resume] [--interim]
       (--resume: answers come from the on-disk API cache, so a re-run only queries what is missing)
       --interim: offline replay of round 1 from the cache (no request at all; S2 = answers stored so far, the rest
       s2_pending), no round 2; outputs go to results/interim/ and $THS_DATASETS/_derived/43/interim/ with
       "interim": true and "s2_pending": n. Nothing directly under results/ is written.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
from ground_truth import (DATA, DERIVED, ROOT, SRC, bbl_items, boot_ratio, cited_keys, identifiers,  # noqa: E402
                          label_identifiers, parse_bibs, wilson)

TIERS = ["J", "C", "P", "B", "S", "W"]
ACADEMIC = {"J", "C", "P"}
BACKENDS = ("crossref", "arxiv", "dblp", "openalex", "s2")  # cascade order, PREREG_AMENDMENT_3
TEXT_FIELDS = ["journal", "booktitle", "note", "howpublished", "publisher", "institution", "url", "doi", "eprint",
               "archiveprefix"]
PRE_RE = re.compile(r"arxiv|biorxiv|medrxiv|ssrn|10\.48550/|10\.1101/|10\.2139/ssrn", re.I)
SW_RE = re.compile(r"github|gitlab|huggingface|zenodo|kaggle", re.I)
RETRY_WAITS = [120, 240, 480]  # seconds, PREREG §4
PERIOD = {"prellm": "2019-21", "pilot": "2024-26"}


# ------------------------------------------------------------------------------------------------ tiers (PREREG §2)
def assign_tier(entrytype, f):
    et = (entrytype or "").lower()
    g = {k: rm.strip_latex(str(f.get(k, "") or "")) for k in TEXT_FIELDS}
    if g["eprint"].strip() or g["archiveprefix"].strip().lower() == "arxiv" or PRE_RE.search(" ".join(g.values())):
        return "P"
    if et in ("software", "dataset") or (et in ("misc", "online")
                                         and SW_RE.search(" ".join([g["url"], g["howpublished"], g["note"]]))):
        return "S"
    if et == "article" and g["journal"].strip():
        return "J"
    if et in ("inproceedings", "proceedings", "conference"):
        return "C"
    if et in ("book", "inbook", "incollection", "phdthesis", "mastersthesis", "thesis"):
        return "B"
    return "W"


def tei_entrytype(g):
    """Pseudo entry type of a GROBID-parsed .bbl item (PREREG §2, bbl-only references)."""
    if g.get("journal"):
        return "article"
    if g.get("has_analytic") and g.get("booktitle"):
        return "inproceedings"
    if not g.get("has_analytic") and g.get("booktitle") and g.get("publisher"):
        return "book"
    return "misc"


# ------------------------------------------------------------------------------------------------ loading
def refs_from_bbl_p1(r, pdir):
    items = bbl_items(pdir)
    texts = [it[1] for it in items if it[2] is None]
    parsed = iter(rm.grobid_parse(texts)) if texts else iter([])
    out = []
    for key, text, f in items:
        if f is None:
            g = next(parsed, {}) or {}
        else:  # biblatex .bbl: fields already parsed; no TEI -> treat as misc unless the text says otherwise
            g = {"title": f.get("title", ""), "doi": f.get("doi", ""), "arxiv": f.get("arxiv", ""),
                 "journal": "", "booktitle": "", "publisher": "", "url": "", "has_analytic": 1}
        doi = rm.clean_doi(g.get("doi", "") or (rm.DOI_RE.search(text).group(1) if rm.DOI_RE.search(text) else ""))
        aid = rm.arxiv_from_text(g.get("arxiv", "")) or rm.arxiv_from_text(text)
        if not aid and re.fullmatch(r"\d{4}\.\d{4,5}", g.get("arxiv", "") or ""):
            aid = g["arxiv"]
        if doi.startswith("10.48550/arxiv."):
            aid = aid or doi.split("arxiv.", 1)[1]
        # the raw item text stands in for the free-text fields (note) of a .bib entry
        fields = {"journal": g.get("journal", ""), "booktitle": g.get("booktitle", ""),
                  "publisher": g.get("publisher", ""), "url": g.get("url", ""), "doi": doi, "eprint": aid,
                  "note": text}
        et = tei_entrytype(g)
        out.append(dict(arxiv_id=r["arxiv_id"], set=r["set"], field=r["field"], year=int(r["year"]), key=key,
                        entrytype=et, title=rm.strip_latex(g.get("title", "")), doi=doi, arxiv=aid,
                        # GROBID's first-author surname, written as "Surname, X" so bib_surnames() reads it (def 2)
                        author=f"{g['first_author_surname']}, X" if g.get("first_author_surname") else "",
                        has_doi=int(bool(doi) and not doi.startswith("10.48550/")), has_arxiv=int(bool(aid)),
                        has_url=int("http" in text), ref_source="bbl", tier=assign_tier(et, fields),
                        **{f"f_{k}": str(fields.get(k, ""))[:300] for k in ("journal", "booktitle", "url")}))
    return out


def load_refs_p1(rows):
    refs, papers = [], []
    for r in rows:
        pdir = SRC / r["arxiv_id"].replace("/", "_")
        bibs = sorted(pdir.rglob("*.bib"))
        has_bbl = any(pdir.rglob("*.bbl"))
        keys, ksrc = cited_keys(pdir, r["main_tex"])
        prow = dict(arxiv_id=r["arxiv_id"], set=r["set"], field=r["field"], year=int(r["year"]),
                    n_bib_files=len(bibs), n_cited_keys=len(keys), cited_source=ksrc, has_bbl=int(has_bbl),
                    ref_source="", n_refs=0, n_cited_missing_in_bib=0, excluded="")
        entries = parse_bibs(bibs) if bibs else {}
        used = []
        if entries and keys:
            used = [entries[k.lower()] for k in keys if k.lower() in entries]
            prow["n_cited_missing_in_bib"] = sum(1 for k in keys if k.lower() not in entries)
        elif entries:
            used, prow["cited_source"] = list(entries.values()), "all-bib"
        if used:
            prow["ref_source"] = "bib"
            for e in used:
                doi, aid = identifiers(e)
                refs.append(dict(arxiv_id=r["arxiv_id"], set=r["set"], field=r["field"], year=int(r["year"]),
                                 key=e.get("ID", ""), entrytype=e.get("ENTRYTYPE", "").lower(),
                                 title=rm.strip_latex(e.get("title", "")), doi=doi, arxiv=aid,
                                 author=e.get("author", ""),
                                 has_doi=int(bool(doi) and not doi.startswith("10.48550/")),
                                 has_arxiv=int(bool(aid)), has_url=int(bool(e.get("url", "").strip())),
                                 ref_source="bib", tier=assign_tier(e.get("ENTRYTYPE", ""), e),
                                 **{f"f_{k}": rm.strip_latex(str(e.get(k, "")))[:300]
                                    for k in ("journal", "booktitle", "url")}))
            prow["n_refs"] = len(used)
        elif has_bbl:
            br = refs_from_bbl_p1(r, pdir)
            refs += br
            prow["ref_source"], prow["n_refs"] = "bbl", len(br)
            if not br:
                prow["excluded"] = "bbl-without-items"
        else:
            prow["excluded"] = "cite-keys-missing-in-bib-no-bbl" if keys else "no-usable-bibliography"
        papers.append(prow)
    return refs, papers


# ------------------------------------------------------------------------------------------------ def 1 / def 2
def _authors(backend, rid, title="", s2_live=True):
    """(ok, names): ok=False when the registry call failed (rate limit / network), names None when no list."""
    if backend == "crossref":
        if str(rid).lower() in rm.CR_AUTHORS:  # from the search answer (no second request)
            return True, rm.CR_AUTHORS[str(rid).lower()] or None
        st, p = rm.cached_get("crossref", f"https://api.crossref.org/works/{rid}", {"mailto": rm.MAILTO})
        if st == -1:
            return False, None
        names = [rm.norm(a.get("family") or a.get("name") or "") for a in (p or {}).get("message", {})
                 .get("author", [])] if st == 200 and p else None
        return True, names or None
    if backend == "s2":
        # round 1 (PREREG_AMENDMENT_1): stored answers only; a missing one leaves def 2 rate-limited until round 2
        st, p = rm.cached_get("s2", f"https://api.semanticscholar.org/graph/v1/paper/{rid}", {"fields": "authors"},
                              tries=2, cache_only=not s2_live)
        if st in (-1, -3):
            return False, None
        names = [rm.norm(a.get("name") or "") for a in (p or {}).get("authors", [])] if st == 200 and p else None
        return True, names or None
    if backend == "arxiv":
        import feedparser
        names = rm.arxiv_search_authors(title, rid) if title else None  # from the stored ti: answer, no request
        if names:
            return True, names
        aid = re.sub(r"v\d+$", "", rid.rsplit("/abs/", 1)[-1])
        st, txt = rm.cached_get("arxiv", "http://export.arxiv.org/api/query", {"id_list": aid, "max_results": 1})
        if st == -1:
            return False, None
        es = feedparser.parse(txt).entries if st == 200 and txt else []
        return True, ([rm.norm(a.get("name", "")) for a in es[0].get("authors", [])] or None) if es else None
    if backend == "openalex":
        return True, (rm.openalex_search_authors(title, rid) if title else None)
    if backend == "dblp":
        return True, (rm.dblp_search_authors(title, rid) if title else None)
    return True, None


def _arxiv_applies(r):
    """PREREG_AMENDMENT_1: the arXiv ti: search is only queried for refs with an arXiv id or in tier P."""
    return bool(r.get("has_arxiv")) or r.get("tier") == "P"


def resolve_ref(r, s2_live=False):
    t = r["title"]
    if len(rm.norm(t)) < 10:
        r.update(def1_status="no-title", def2_status="no-title", backends_hit="", backends_failed="", s2_pending=0,
                 oa_skipped=0)
        return r
    sims, ids, failed = {}, {}, []
    s2_pending = oa_skipped = dblp_missing = 0
    # PREREG_AMENDMENT_3 order = the cumulative backend table: crossref > arxiv (where it applies) > dblp (offline)
    # > openalex > s2 (stored answers in round 1, live from round 2)
    cascade = [("crossref", rm.crossref_search)]
    if _arxiv_applies(r):
        cascade.append(("arxiv", rm.arxiv_title_search))
    cascade += [("dblp", rm.dblp_search), ("openalex", lambda q: rm.openalex_search(q, force=True)),
                ("s2", (lambda q: rm.s2_match(q, tries=2)) if s2_live else (lambda q: rm.s2_match(q, cache_only=True)))]
    for name, fn in cascade:
        if any(v >= rm.SIM_THRESHOLD for v in sims.values()):
            break  # resolved: later backends are not asked
        res = fn(t)
        if isinstance(res, str):  # "not-cached" (S2 round 1, DBLP not matched) / "skipped" (OpenAlex refused)
            if name == "s2":
                s2_pending = 1
            elif name == "dblp":
                dblp_missing = 1
            else:
                oa_skipped = 1
            continue
        if res is None:
            failed.append(name)
            continue
        s, i = rm.best_sim(res, title=t)
        sims[name], ids[name] = round(s, 4), i
    hit = [b for b, v in sims.items() if v >= rm.SIM_THRESHOLD]
    r.update({f"sim_{b}": sims.get(b, np.nan) for b in BACKENDS})
    r.update(backends_hit=";".join(hit), backends_failed=";".join(failed),
             match_id=";".join(f"{b}:{ids[b]}" for b in hit), s2_pending=int(s2_pending and not hit),
             oa_skipped=oa_skipped, dblp_missing=dblp_missing)
    if hit:
        r["def1_status"] = "resolved"
    elif failed:
        r["def1_status"] = "rate-limited"
    else:
        r["def1_status"] = "unresolved"  # with s2_pending=1 this is provisional until round 2
    # def 2
    if r["def1_status"] != "resolved":
        r["def2_status"] = r["def1_status"]
        return r
    bs = rm.bib_surnames(r.get("author", ""))
    if not bs:
        r["def2_status"] = "excluded-no-author"
        return r
    names, any_fail = None, False
    for b in BACKENDS:
        if b in hit:
            ok, names = _authors(b, ids[b], t, s2_live=s2_live)
            any_fail |= not ok
            if names:
                break
    if not names:
        r["def2_status"] = "rate-limited" if any_fail else "excluded-no-registry-authors"
        return r
    r["def2_status"] = "resolved" if rm.first_author_match(bs, names) else "unresolved"
    return r


def run_resolution(refs, workers, label, s2_live=False):
    done, t0 = [0], time.time()

    def wrapped(r):
        try:
            resolve_ref(r, s2_live=s2_live)
        except Exception as e:  # one bad reference never kills the run
            r.update(def1_status="rate-limited", def2_status="rate-limited", err=f"{e.__class__.__name__}: {e}"[:200])
            print(f"  ! {label} error {r['arxiv_id']}/{r['key']}: {e.__class__.__name__}: {e}", flush=True)
        done[0] += 1
        if done[0] % 500 == 0:
            print(f"  {label} {done[0]}/{len(refs)} ({time.time() - t0:.0f}s)", flush=True)
        return r

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(wrapped, refs))


# ------------------------------------------------------------------------------------------------ summaries
def rate_block(g, col, flag_value, seed, B=1000):
    ev = g[g[col].isin(["resolved", "unresolved"])].copy()
    ev["x"] = (ev[col] == flag_value).astype(int)
    k, n = int(ev.x.sum()), int(len(ev))
    out = {"k": k, "n": n, "n_papers": int(ev.arxiv_id.nunique()), "u": round(k / n, 4) if n else None,
           "wilson95": [round(x, 4) for x in wilson(k, n)] if n else None,
           "paper_bootstrap95": [round(x, 4) for x in boot_ratio(ev, "x", ev.index == ev.index, seed, B)] if n else None,
           "n_rate_limited": int((g[col] == "rate-limited").sum())}
    return out


def summarise(df, pdf, seed, p0_ids):
    out = {"seed": seed, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "prereg_sha256": (ROOT / "results" / "prereg_hash.txt").read_text(encoding="utf-8").split()[6]
           if (ROOT / "results" / "prereg_hash.txt").exists() else None,
           "backends": {"cascade": "PREREG_AMENDMENT_3: round 1 crossref > arxiv (arXiv id or tier P) > dblp "
                                   "(offline dump " + rm.DBLP_RELEASE + ") > openalex (keyless until refused) > s2 "
                                   "(stored answers); round 2 live s2 for non-resolved refs",
                        "openalex_key": bool(rm.OPENALEX_API_KEY), "s2_key": bool(rm.S2_API_KEY),
                        "openalex_refused": rm.OA_EXHAUSTED.is_set()},
           "corpus": {}, "exclusions": {}, "tiers": {}, "u": {}}
    for s, g in pdf.groupby("set"):
        out["corpus"][s] = {"papers_kept": int(len(g)), "papers_used": int((g.excluded == "").sum()),
                            "source_bib": int((g.ref_source == "bib").sum()), "source_bbl": int((g.ref_source == "bbl").sum()),
                            "refs": int(df[df.set == s].shape[0])}
        out["exclusions"][s] = {k: sorted(v.arxiv_id) for k, v in g[g.excluded != ""].groupby("excluded")}
    for (s, t), g in df.groupby(["set", "tier"]):
        out["tiers"].setdefault(s, {})[t] = int(len(g))
    for sub_name, sub in [("all", df), ("without_p0", df[~df.arxiv_id.isin(p0_ids)])]:
        for s in ["prellm", "pilot"]:
            g0 = sub[sub.set == s]
            if g0.empty:
                continue
            for d, col in [("def1", "def1_status"), ("def2", "def2_status")]:
                blk = out["u"].setdefault(sub_name, {}).setdefault(PERIOD[s], {}).setdefault(d, {})
                for t in TIERS:
                    blk[t] = rate_block(g0[g0.tier == t], col, "unresolved", seed)
                blk["A"] = rate_block(g0[g0.tier.isin(ACADEMIC)], col, "unresolved", seed)
                blk["all"] = rate_block(g0, col, "unresolved", seed)
                blk["certified_real"] = rate_block(g0[g0.certified_real == 1], col, "unresolved", seed)
                if "s2_pending" in g0:
                    blk["n_s2_pending"] = int((g0.s2_pending == 1).sum())
                if "dblp_missing" in g0:
                    blk["n_dblp_missing"] = int((g0.dblp_missing == 1).sum())
                if "oa_skipped" in g0:
                    blk["n_oa_skipped"] = int((g0.oa_skipped == 1).sum())
                if d == "def2":
                    blk["n_excluded_no_author"] = int((g0.def2_status == "excluded-no-author").sum())
                    blk["n_excluded_no_registry_authors"] = int((g0.def2_status == "excluded-no-registry-authors")
                                                               .sum())
            out["u"][sub_name][PERIOD[s]]["n_no_title"] = int((g0.def1_status == "no-title").sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="max papers per set (0 = all kept)")
    ap.add_argument("--sets", default="prellm,pilot", help="order of processing; both are written")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--resume", action="store_true", help="documented no-op: the API cache makes re-runs resume")
    ap.add_argument("--no-retry-rounds", action="store_true", help="testing only: skip the 2/4/8-min retry rounds")
    ap.add_argument("--interim", action="store_true", help="offline replay of round 1 from the cache -> results/interim")
    args = ap.parse_args()
    res_dir, der_dir = (ROOT / "results", DERIVED)
    if args.interim:
        rm.OFFLINE = True
        res_dir, der_dir = ROOT / "results" / "interim", DERIVED / "interim"
        res_dir.mkdir(parents=True, exist_ok=True)
        der_dir.mkdir(parents=True, exist_ok=True)

    with (DATA / "arxiv_src_43" / "manifest.csv").open(encoding="utf-8") as f:
        mrows = [r for r in csv.DictReader(f) if r["status"] == "kept"]
    sets = args.sets.split(",")
    sel = []
    for s in sets:
        rs = sorted((r for r in mrows if r["set"] == s), key=lambda r: r["arxiv_id"])
        sel += rs[:args.limit] if args.limit else rs
    p0_ids = set((ROOT / "data_manifest" / "p0_papers.txt").read_text().split())
    counts = ", ".join(f"{s}={sum(r['set'] == s for r in sel)}" for s in sets)
    print(f"papers kept: {len(sel)} ({counts}); openalex {'key' if rm.OPENALEX_API_KEY else 'keyless (until refused)'}; s2 key {'yes' if rm.S2_API_KEY else 'no'}",
          flush=True)

    refs, papers = load_refs_p1(sel)
    print(f"refs: {len(refs)}; papers excluded: {sum(1 for p in papers if p['excluded'])}", flush=True)
    label_identifiers(refs)
    print("identifier labels done", flush=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    if not args.limit and not args.interim:
        pd.DataFrame(refs).assign(period=lambda d: d.set.map(PERIOD)).to_csv(DERIVED / "p1_refs_stage0.csv",
                                                                             index=False)
        print("stage0 written (refs + tiers + identifier labels)", flush=True)
    for s in sets:
        rs = [r for r in refs if r["set"] == s]
        print(f"round 1 (no live S2), set {s}: {len(rs)} refs", flush=True)
        run_resolution(rs, args.workers, f"round1-{s}")
        if args.interim:
            continue
        interim = summarise(_frame(rs, p0_ids), pd.DataFrame([p for p in papers if p["set"] == s]), args.seed, p0_ids)
        interim.update(label="round 1, before S2 (provisional; PREREG_AMENDMENT_1)", limit=args.limit)
        (ROOT / "results" / f"p1_groundtruth_round1_{s}.json").write_text(json.dumps(interim, indent=1),
                                                                          encoding="utf-8")
        _print_u(interim, f"round1-{s}")
    if args.interim:
        return write_outputs(refs, papers, p0_ids, args, res_dir, der_dir)
    todo = [r for r in refs if r.get("def1_status") not in ("resolved", "no-title")
            or r.get("def2_status") == "rate-limited"]
    print(f"round 2 (live S2, 1 req/s): {len(todo)} refs (def 1 not resolved, or def 2 waiting for S2 authors)",
          flush=True)
    run_resolution(todo, args.workers, "round2", s2_live=True)
    if not args.no_retry_rounds:
        for i, w in enumerate(RETRY_WAITS, 1):
            todo = [r for r in refs if "rate-limited" in (r.get("def1_status"), r.get("def2_status"))]
            if not todo:
                break
            print(f"retry round {i}: {len(todo)} rate-limited refs, waiting {w}s", flush=True)
            time.sleep(w)
            run_resolution(todo, max(1, args.workers // 2), f"retry{i}", s2_live=True)
    write_outputs(refs, papers, p0_ids, args, res_dir, der_dir)


def write_outputs(refs, papers, p0_ids, args, res_dir, der_dir):
    df = _frame(refs, p0_ids)
    df["s2_pending"] = df.s2_pending.fillna(0).astype(int)
    df.to_csv(der_dir / "p1_groundtruth_refs_full.csv", index=False)
    cols = ["arxiv_id", "set", "period", "field", "year", "key", "entrytype", "tier", "ref_source", "has_doi",
            "has_arxiv", "certified_real", "def1_status", "def2_status", "backends_hit", "s2_pending", "oa_skipped",
            "p0_paper"]
    df[cols].rename(columns={"arxiv_id": "paper_id"}).to_csv(res_dir / "p1_groundtruth.csv", index=False)
    pdf = pd.DataFrame(papers)
    pdf.to_csv(res_dir / "p1_groundtruth_papers.csv", index=False)
    out = summarise(df, pdf, args.seed, p0_ids)
    out.update(smoke_test=bool(args.limit), limit=args.limit, retry_rounds=not args.no_retry_rounds)
    if args.interim:
        out.update(interim=True, s2_pending=int((df.s2_pending == 1).sum()),
                   n_offline_failed=int(df.backends_failed.fillna("").astype(str).str.len().gt(0).sum()),
                   label="INTERIM: offline replay of round 1 from the cache; S2 = answers stored so far "
                         "(run7-run10), the rest s2_pending; no live S2 round")
    (res_dir / "p1_groundtruth.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    _print_u(out, "interim" if args.interim else "final")


def _frame(refs, p0_ids):
    df = pd.DataFrame(refs)
    for c in ["def1_status", "def2_status", "backends_hit", "backends_failed", "s2_pending", "oa_skipped",
              "dblp_missing"]:
        if c not in df:
            df[c] = np.nan
    df["certified_real"] = (df.label == "certified-real").astype(int)
    df["period"] = df.set.map(PERIOD)
    df["p0_paper"] = df.arxiv_id.isin(p0_ids).astype(int)
    return df


def _print_u(out, tag):
    for per in out["u"].get("all", {}):
        a = out["u"]["all"][per]["def1"]
        print(tag, per, "def1:", {t: (a[t]["k"], a[t]["n"], a[t]["u"]) for t in TIERS + ["A", "all"]}, flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        with (DERIVED / "logs" / "ground_truth_p1_crash.log").open("a", encoding="utf-8") as f:
            f.write(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} argv={sys.argv}\n{traceback.format_exc()}\n")
        raise
