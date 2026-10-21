#!/usr/bin/env python3
"""Topic 43 / P2 — EXPLORATORY (not preregistered; decision LQD 21-10): def 2-strict.

def 2 (PREREG): the first .bib surname occurs (as whole tokens) in ANY registry author name.
def 2-strict:   the first .bib surname occurs in the FIRST registry author name (position 1).
def 2-strict+: as strict, with two repairs applied to BOTH rules: .bib author fields are also split on ";" (some
                .bib files use "A; B; C", which bib_surnames reads as one name), and registry entries that are not
                persons (Crossref `name` without `family`: consortia, institutions) are skipped before taking the
                first registry author.
Both rules are applied to the same ordered registry author list, so a difference is due to the rule alone:
  - FP on certified-real references with a DOI (2019-21 and 2024-26 citing papers): ordered authors of the DOI record
    from the cached Crossref answer works/<doi> (no network; refs without a cached record or without authors are
    excluded and counted). FP = share whose check fails. Paper-bootstrap 95 % CI (B = 1000, seed 42) of each rate and
    of the difference strict - anywhere.
  - recall on the 13 PARTIAL items of results/p2_recall_drop_audit.csv (record author order as listed there).
Outputs: results/p2_def2_strict.csv (per item / per ref check), results/p2_def2_strict.json
Usage: python p2_def2_strict.py --seed 42
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
from ground_truth import DATA, ROOT  # noqa: E402

RES = ROOT / "results"


def toks(name):
    return [t for t in rm.norm(name).split() if not t.isdigit()]


def check_plus(bib_author, persons):
    """(anywhere, strict) with ';' splitting of the .bib field and person-only registry names."""
    return check(" and ".join(x.strip() for x in re.split(r";|\s+and\s+", bib_author or "") if x.strip()), persons)


def check(bib_author, names):
    """(anywhere, strict) for the first .bib surname against an ordered list of registry names; None if n/a."""
    bs = rm.bib_surnames(bib_author)
    names = [n for n in names if toks(n)]
    if not bs or not names:
        return None, None
    s = bs[0].split()
    anywhere = any(all(t in toks(n) for t in s) for n in names)
    strict = all(t in toks(names[0]) for t in s)
    return anywhere, strict


def crossref_authors(doi, persons_only=False):
    st, p = rm.cached_get("crossref", f"https://api.crossref.org/works/{doi}", {"mailto": rm.MAILTO}, cache_only=True)
    if st != 200 or not p:
        return None
    au = p.get("message", {}).get("author", [])
    au = sorted(au, key=lambda a: 0 if a.get("sequence") == "first" else 1)  # Crossref marks the first author
    if persons_only:
        au = [a for a in au if a.get("family")]
    return [f"{a.get('given', '')} {a.get('family') or a.get('name') or ''}".strip() for a in au] or None


def boot(df, cols, seed, B=1000):
    rng = np.random.default_rng(seed)
    g = {p: x for p, x in df.groupby("arxiv_id")}
    papers = np.array(sorted(g))
    out = {c: [] for c in cols}
    for _ in range(B):
        bd = pd.concat([g[p] for p in rng.choice(papers, len(papers), replace=True)])
        for c in cols:
            out[c].append(bd[c].mean() if c != "diff" else bd.fp_strict.mean() - bd.fp_anywhere.mean())
    return {c: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for c, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    full = pd.read_csv(DATA / "_derived" / "43" / "p1_groundtruth_refs_full.csv", dtype=str, keep_default_na=False,
                       low_memory=False)
    cert = full[(full.certified_real == "1") & (full.has_doi == "1") & (full.author != "")].copy()
    rows, meta = [], {"interim": False, "seed": args.seed, "label": "EXPLORATORY (not preregistered)"}
    for r in cert.itertuples():
        doi = rm.clean_doi(r.doi) if r.doi else ""
        names = crossref_authors(doi) if doi else None
        persons = crossref_authors(doi, persons_only=True) if doi else None
        a, s = check(r.author, names or [])
        a2, s2 = check_plus(r.author, persons or [])
        rows.append(dict(kind="certified-real", period=r.period, arxiv_id=r.arxiv_id, key=r.key,
                         anywhere=a, strict=s, anywhere_plus=a2, strict_plus=s2, n_registry_authors=len(names or [])))
    df = pd.DataFrame(rows)
    ev = df[df.anywhere.notna()].copy()
    ev["fp_anywhere"] = (~ev.anywhere.astype(bool)).astype(float)
    ev["fp_strict"] = (~ev.strict.astype(bool)).astype(float)
    ev2 = df[df.anywhere_plus.notna()].copy()
    ev2["fp_anywhere"] = (~ev2.anywhere_plus.astype(bool)).astype(float)
    ev2["fp_strict"] = (~ev2.strict_plus.astype(bool)).astype(float)
    for per, g in ev2.groupby("period"):
        ci = boot(g, ["fp_anywhere", "fp_strict", "diff"], args.seed)
        meta[f"certified_plus_{per}"] = dict(n_refs=len(g), n_papers=g.arxiv_id.nunique(),
                                             fp_anywhere=g.fp_anywhere.mean(), k_anywhere=int(g.fp_anywhere.sum()),
                                             fp_strict=g.fp_strict.mean(), k_strict=int(g.fp_strict.sum()),
                                             diff=g.fp_strict.mean() - g.fp_anywhere.mean(), ci=ci)
    for per, g in ev.groupby("period"):
        ci = boot(g, ["fp_anywhere", "fp_strict", "diff"], args.seed)
        meta[f"certified_{per}"] = dict(n_refs=len(g), n_papers=g.arxiv_id.nunique(),
                                        n_excluded=int((df.period == per).sum() - len(g)),
                                        fp_anywhere=g.fp_anywhere.mean(), k_anywhere=int(g.fp_anywhere.sum()),
                                        fp_strict=g.fp_strict.mean(), k_strict=int(g.fp_strict.sum()),
                                        diff=g.fp_strict.mean() - g.fp_anywhere.mean(), ci=ci)
    a = pd.read_csv(RES / "p2_recall_drop_audit.csv", dtype=str, keep_default_na=False)
    part = a[a.audit_label == "PARTIAL"]
    prow = []
    for r in part.itertuples():
        x, s = check(r.cited_authors, [n.strip() for n in r.record_authors.split(";")])
        x2, s2 = check_plus(r.cited_authors, [n.strip() for n in r.record_authors.split(";")])
        prow.append(dict(kind="PARTIAL", period="", arxiv_id="", key=r.item_id, anywhere=x, strict=s,
                         anywhere_plus=x2, strict_plus=s2, n_registry_authors=len(r.record_authors.split(";"))))
    pp = pd.DataFrame(prow)
    meta["partial"] = dict(n=len(pp), flagged_anywhere=int((pp.anywhere == False).sum()),  # noqa: E712
                           flagged_strict=int((pp.strict == False).sum()),  # noqa: E712
                           items_strict_only=list(pp[(pp.anywhere == True) & (pp.strict == False)].key),  # noqa: E712
                           flagged_anywhere_plus=int((pp.anywhere_plus == False).sum()),  # noqa: E712
                           flagged_strict_plus=int((pp.strict_plus == False).sum()))  # noqa: E712
    out = pd.concat([df, pp], ignore_index=True)
    out.insert(0, "interim", "False")
    out.to_csv(RES / "p2_def2_strict.csv", index=False)
    (RES / "p2_def2_strict.json").write_text(json.dumps(meta, indent=1, default=float), encoding="utf-8")
    print(json.dumps(meta, indent=1, default=float))


if __name__ == "__main__":
    main()
