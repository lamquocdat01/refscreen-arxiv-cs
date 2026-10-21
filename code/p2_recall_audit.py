#!/usr/bin/env python3
"""Topic 43 / P2: audit of the recall drop (decision LQD 21-10): labelled-fabricated items (GPTZero NeurIPS 2025,
Badalova-Mayr problematic) that Crossref does NOT resolve but a later backend of the cascade does (sim >= 0.9).

list   one row per such item: cited raw string, parsed title/authors, first resolving backend, matched record
       (id, title, authors, year, URL), similarity. Everything comes from the API cache (no network).
       -> results/p2_recall_drop_audit.csv (audit columns empty: audit_label, audit_evidence_url, audit_note)
apply  after the manual audit: audit_label in {LABEL_WRONG, FALSE_MATCH, PARTIAL}; recall per backend recomputed
       with LABEL_WRONG items removed from the fabricated denominator (both versions reported)
       -> results/p2_recall_audited.csv, results/p2_recall_audit.json
Usage: python p2_recall_audit.py list ;  python p2_recall_audit.py apply --seed 42
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p2_fake_refs as fr  # noqa: E402
import refmatch as rm  # noqa: E402
from ground_truth import ROOT  # noqa: E402

RES = ROOT / "results"
SETS = [("gptzero", "hallucinated"), ("badalova", "problematic")]
LATER = ["arxiv", "dblp", "openalex", "s2"]


def record(backend, title, rid):
    """(matched title, authors, year, url) of record rid from the cached answer to `title`."""
    if backend == "dblp":
        st, p = rm.cached_get("dblp", *rm.dblp_req(title), cache_only=True)
        for h in (p or {}).get("hits", []):
            if h.get("key") == rid:
                return h.get("title", ""), "; ".join(h.get("authors", [])), h.get("year", ""), \
                    f"https://dblp.org/rec/{rid}"
    if backend == "s2":
        st, p = rm.cached_get("s2", *rm.s2_match_req(title), cache_only=True)
        for d in (p or {}).get("data", []):
            if d.get("paperId") == rid:
                st2, a = rm.cached_get("s2", f"https://api.semanticscholar.org/graph/v1/paper/{rid}",
                                       {"fields": "authors"}, cache_only=True)
                au = "; ".join(x.get("name", "") for x in (a or {}).get("authors", [])) if st2 == 200 else ""
                return d.get("title", ""), au, d.get("year", ""), f"https://www.semanticscholar.org/paper/{rid}"
    if backend == "arxiv":
        import feedparser
        st, txt = rm.cached_get("arxiv", *rm._arxiv_ti_req(title), cache_only=True)
        for e in feedparser.parse(txt or "").entries:
            if e.id == rid:
                return " ".join(e.title.split()), "; ".join(a.get("name", "") for a in e.get("authors", [])), \
                    e.get("published", "")[:4], rid
    if backend == "openalex":
        st, p = rm.cached_get("openalex", *rm._openalex_req(title), cache_only=True)
        for w in (p or {}).get("results", []):
            if w.get("id") == rid:
                au = "; ".join((a.get("author") or {}).get("display_name", "") for a in w.get("authorships", []))
                return w.get("title", ""), au, w.get("publication_year", ""), rid
    return "", "", "", ""


def list_(args):
    u = pd.read_csv(RES / "p2_fake_items.csv", dtype=str, keep_default_na=False)
    rows = []
    for st, lab in SETS:
        g = u[(u["set"] == st) & (u.label == lab) & (u.status == "ok")]
        for r in g.itertuples():
            sc = r.sim_crossref
            if sc not in ("", None) and float(sc) >= rm.SIM_THRESHOLD:
                continue  # Crossref resolves: not part of the drop
            for b in LATER:
                if b == "arxiv" and not (str(r.has_arxiv) == "1" or r.tier == "P"):
                    continue  # not asked in the cascade (Amendment 1)
                s = getattr(r, f"sim_{b}")
                if s not in ("", None) and float(s) >= rm.SIM_THRESHOLD:
                    rid = getattr(r, f"id_{b}")
                    mt, ma, my, url = record(b, r.title, rid)
                    rows.append(dict(item_id=r.item_id, set=st, label=lab, cited_raw=r.raw, cited_title=r.title,
                                     cited_authors=r.author, first_backend=b, similarity=float(s), record_id=rid,
                                     record_title=mt, record_authors=ma, record_year=my, record_url=url,
                                     sim_crossref=sc, audit_label="", audit_evidence_url="", audit_note=""))
                    break
    out = pd.DataFrame(rows)
    f = RES / "p2_recall_drop_audit.csv"
    if f.exists():  # keep labels already given; new items get empty labels (to audit)
        old = pd.read_csv(f, dtype=str, keep_default_na=False).set_index("item_id")
        for c in ("audit_label", "audit_evidence_url", "audit_note", "auditor", "audited_at"):
            if c in old:
                out[c] = out.item_id.map(old[c]).fillna("")
        print("new items without audit label:", int((out.audit_label == "").sum()))
    out.insert(0, "interim", "False")
    out.to_csv(f, index=False)
    print(out.groupby(["set", "first_backend"]).size().to_string())
    print(len(out), "items to audit")


def apply(args):
    a = pd.read_csv(RES / "p2_recall_drop_audit.csv", dtype=str, keep_default_na=False)
    assert set(a.audit_label) <= {"LABEL_WRONG", "FALSE_MATCH", "PARTIAL"},         f"unaudited or unknown labels: {set(a.audit_label)} (audit new items first)"
    wrong = set(a[a.audit_label == "LABEL_WRONG"].item_id)
    u = pd.read_csv(RES / "p2_fake_items.csv", dtype=str, keep_default_na=False)
    for b in fr.SCREENS:
        for c in (f"sim_{b}", f"fail_{b}", f"auth_{b}"):
            if c not in u:
                u[c] = ""
    rows = []
    for version, df in (("original labels", u), ("after audit (LABEL_WRONG removed)", u[~u.item_id.isin(wrong)])):
        for (st, lab), g in df.groupby(["set", "label"]):
            if (st, lab) not in SETS:
                continue
            for i, b in enumerate(fr.SCREENS):
                for d in (1, 2):
                    f = fr.flags(g, i, d)
                    n, k = int(np.isfinite(f).sum()), int(np.nansum(f))
                    lo, hi = fr.wilson(k, n)
                    rows.append(dict(version=version, set=st, label=lab, screen="crossref" if i == 0 else f"+{b}",
                                     definition=d, n_items=len(g), n_evaluated=n, k_flagged=k,
                                     share_flagged=k / n if n else np.nan, wilson_lo=lo, wilson_hi=hi,
                                     bound_lo=k / len(g), bound_hi=(k + len(g) - n) / len(g), seed=args.seed,
                                     interim=False))
    out = pd.DataFrame(rows)
    out.to_csv(RES / "p2_recall_audited.csv", index=False)
    meta = dict(interim=False, seed=args.seed, n_audited=len(a), counts=a.audit_label.value_counts().to_dict(),
                by_set={s: g.audit_label.value_counts().to_dict() for s, g in a.groupby("set")},
                n_label_wrong_removed=len(wrong))
    (RES / "p2_recall_audit.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))
    piv = out[out.definition == 1].pivot_table(index=["set", "version"], columns="screen", values="share_flagged")
    print(piv[["crossref", "+arxiv", "+dblp", "+openalex", "+s2"]].round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["list", "apply"])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    (list_ if args.stage == "list" else apply)(args)


if __name__ == "__main__":
    main()
