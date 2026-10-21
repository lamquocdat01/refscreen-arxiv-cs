#!/usr/bin/env python3
"""Topic 43 / P1 / T07 route (b): draw the manual-verification sample of PREREG_43.md §6.3.

Eligible: references of the 2019-2021 set (results/p1_groundtruth.csv) with neither DOI nor arXiv id.
Allocation: 33 per tier (J, C, P, B, S, W) + 1 extra for each of the two tiers with the most eligible references;
a tier with fewer eligible references gives all of them and its remainder is split equally over the other tiers
(integer leftovers go to the tiers with the most eligible references). Simple random sampling within tier.
Recheck list: 40 rows (20 %), seed 42, spread over tiers as evenly as the sample allows.
Outputs: results/p1_manual_sample.csv (columns to fill: exists, evidence_url, evidence_note, checker, checked_at;
         the screen status columns come last, per manual_protocol.md), results/p1_manual_recheck.csv
Usage: python manual_sample.py --seed 42 [--n 200] [--limit N] [--resume] [--force]
       --resume keeps an existing sample untouched (it never overwrites filled rows); --force redraws.
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, ROOT, SRC, parse_bibs  # noqa: E402

TIERS = ["J", "C", "P", "B", "S", "W"]
FILL = ["exists", "evidence_url", "evidence_note", "checker", "checked_at"]


def allocate(avail, n):
    base = {t: n // len(TIERS) for t in TIERS}                     # 33
    for t in sorted(TIERS, key=lambda t: -avail.get(t, 0))[: n - sum(base.values())]:
        base[t] += 1                                               # +1 for the two largest tiers
    alloc = {t: min(base[t], avail.get(t, 0)) for t in TIERS}
    while True:
        short = n - sum(alloc.values())
        open_ = [t for t in TIERS if alloc[t] < avail.get(t, 0)]
        if short <= 0 or not open_:
            return alloc
        share = max(1, short // len(open_))
        for t in sorted(open_, key=lambda t: -avail.get(t, 0)):
            add = min(share, avail[t] - alloc[t], n - sum(alloc.values()))
            alloc[t] += add


def bib_entry_text(paper_id, key, cache):
    if paper_id not in cache:
        pdir = SRC / paper_id.replace("/", "_")
        cache[paper_id] = parse_bibs(sorted(pdir.rglob("*.bib")))
    e = cache[paper_id].get(str(key).lower())
    if not e:
        return ""
    body = ", ".join(f"{k} = {{{v}}}" for k, v in e.items() if k not in ("ID", "ENTRYTYPE"))
    return f"@{e.get('ENTRYTYPE', 'misc')}{{{e.get('ID', key)}, {body}}}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--n-recheck", type=int, default=40)
    ap.add_argument("--limit", type=int, default=0, help="testing: draw from the first N eligible refs only")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--stage0", action="store_true", help="draw from p1_refs_stage0.csv (same rows and order as the "
                    "final ground truth; def1/def2 statuses left empty and joined after route (a))")
    args = ap.parse_args()
    out = ROOT / "results" / "p1_manual_sample.csv"
    if out.exists() and not args.force:
        filled = pd.read_csv(out, dtype=str)[FILL].notna().any(axis=1).sum()
        print(f"{out.name} exists ({filled} rows already filled); keeping it (use --force to redraw)")
        return

    if args.stage0:  # draw before route (a) finishes: refs + tiers + identifiers only; statuses joined later
        full = pd.read_csv(DATA / "_derived" / "43" / "p1_refs_stage0.csv", dtype={"arxiv_id": str, "key": str},
                           low_memory=False)
        gt = full.rename(columns={"arxiv_id": "paper_id"}).assign(def1_status="", def2_status="")
    else:
        gt = pd.read_csv(ROOT / "results" / "p1_groundtruth.csv", dtype={"paper_id": str, "key": str})
        full = pd.read_csv(DATA / "_derived" / "43" / "p1_groundtruth_refs_full.csv",
                           dtype={"arxiv_id": str, "key": str}, low_memory=False)
    el = gt[(gt.period == "2019-21") & (gt.has_doi == 0) & (gt.has_arxiv == 0)].copy()
    if args.limit:
        el = el.head(args.limit)
    avail = el.tier.value_counts().to_dict()
    alloc = allocate(avail, args.n)
    rng = np.random.default_rng(args.seed)
    picks = []
    for t in TIERS:
        g = el[el.tier == t].sort_values(["paper_id", "key"])
        if alloc[t]:
            picks.append(g.iloc[np.sort(rng.choice(len(g), alloc[t], replace=False))])
    s = pd.concat(picks).reset_index(drop=True)
    with (DATA / "arxiv_src_43" / "manifest.csv").open(encoding="utf-8") as f:
        pub = {r["arxiv_id"]: r["published"] for r in csv.DictReader(f)}
    meta = full.set_index(["arxiv_id", "key"])
    cache = {}
    rows = []
    for i, r in s.iterrows():
        m = meta.loc[(r.paper_id, r.key)]
        m = m.iloc[0] if isinstance(m, pd.DataFrame) else m
        rows.append(dict(sample_id=f"M{i + 1:03d}", paper_id=r.paper_id, citing_paper_date=pub.get(r.paper_id, ""),
                         field=r.field, tier=r.tier, entrytype=r.entrytype, key=r.key, ref_source=r.ref_source,
                         title=m.get("title", ""), author=m.get("author", ""),
                         bib_entry=bib_entry_text(r.paper_id, r.key, cache) if r.ref_source == "bib" else "",
                         **{c: "" for c in FILL},
                         def1_status=r.def1_status, def2_status=r.def2_status))
    sample = pd.DataFrame(rows)
    sample.to_csv(out, index=False)
    # recheck: 40 rows spread over tiers (round robin over tiers in sample order), seed 42
    rr = np.random.default_rng(args.seed + 1)
    by_t = {t: list(rr.permutation(sample.index[sample.tier == t])) for t in TIERS}
    rec = []
    while len(rec) < min(args.n_recheck, len(sample)):
        for t in TIERS:
            if by_t[t] and len(rec) < args.n_recheck:
                rec.append(by_t[t].pop())
    re_ = sample.loc[sorted(rec), ["sample_id", "paper_id", "citing_paper_date", "tier", "entrytype", "key", "title",
                                   "author", "bib_entry"]].copy()
    for c in FILL:
        re_[c] = ""
    re_.to_csv(ROOT / "results" / "p1_manual_recheck.csv", index=False)
    print(f"eligible {len(el)} refs ({el.paper_id.nunique()} papers), available by tier {avail}")
    print(f"allocation {alloc}; sample {len(sample)} refs from {sample.paper_id.nunique()} papers; "
          f"recheck {len(re_)} (seed {args.seed})")


if __name__ == "__main__":
    main()
