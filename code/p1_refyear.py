#!/usr/bin/env python3
"""Topic 43 / P1 (EXPLORATORY, not preregistered): u_acad by the publication year of the cited reference.

Expectation: u rises for references published close to the crawl date (2025-26), because the backends have not yet
indexed them. Reference year = `year` field of the .bib entry (or the year in `date`); for BibTeX .bbl items, the
last 4-digit year 1950-2026 in the item text. Def 1, cumulative cascade end state (+S2), academic tier A = J+C+P.
Input:  $THS_DATASETS/_derived/43/p1_groundtruth_refs_full.csv, $THS_DATASETS/arxiv_src_43 (sources)
Output: results/p1_u_by_refyear.{csv,json,png}
Usage:  python p1_refyear.py --seed 42 [--boot 1000] [--interim]
        --interim: input _derived/43/interim/, output results/interim/; the state is the +DBLP column of the cascade
        (exact before S2), not the final +S2 state, which is still pending.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, DERIVED, ROOT, SRC, bbl_items, boot_ratio, wilson  # noqa: E402
from ground_truth_p1 import ACADEMIC, parse_bibs  # noqa: E402

YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20[0-2]\d)(?!\d)")


def ref_years():
    with (DATA / "arxiv_src_43" / "manifest.csv").open(encoding="utf-8") as f:
        mrows = [r for r in csv.DictReader(f) if r["status"] == "kept"]
    out = {}
    for r in mrows:
        pdir = SRC / r["arxiv_id"].replace("/", "_")
        bibs = sorted(pdir.rglob("*.bib"))
        if bibs:
            for k, e in parse_bibs(bibs).items():
                m = YEAR_RE.search(e.get("year", "") or e.get("date", ""))
                if m:
                    out[(r["arxiv_id"], e.get("ID", k))] = int(m.group(1))
        for key, text, fields in bbl_items(pdir):
            if (r["arxiv_id"], key) in out:
                continue
            src = (fields.get("year", "") or fields.get("date", "")) if fields else text
            ys = [int(y) for y in YEAR_RE.findall(src or "") if int(y) <= int(r["year"])]
            if ys:
                out[(r["arxiv_id"], key)] = ys[-1]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--interim", action="store_true")
    args = ap.parse_args()
    der, out_dir = (DERIVED / "interim", ROOT / "results" / "interim") if args.interim else (DERIVED, ROOT / "results")
    out_dir.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(der / "p1_groundtruth_refs_full.csv", dtype={"arxiv_id": str, "key": str}, low_memory=False)
    d = d[d.tier.isin(ACADEMIC) & d.def1_status.isin(["resolved", "unresolved"])].copy()
    yrs = ref_years()
    d["ref_year"] = [yrs.get((a, k)) for a, k in zip(d.arxiv_id, d.key)]
    n_noyear = int(d.ref_year.isna().sum())
    d = d[d.ref_year.notna()].copy()
    d["ref_year"] = d.ref_year.astype(int)
    d["lag"] = d.year - d.ref_year  # citing-paper year minus reference year
    d["x"] = (d.def1_status == "unresolved").astype(int)
    if args.interim:  # +DBLP column: not resolved by crossref / arxiv / dblp
        from p1_backend_table import COLS, first_hit_stage
        d["x"] = ((d.def1_status == "unresolved") | (d.backends_hit.map(first_hit_stage) > COLS.index("dblp"))).astype(int)
    bins = [(-99, 0, "0 (same year)"), (1, 1, "1"), (2, 2, "2"), (3, 5, "3-5"), (6, 10, "6-10"), (11, 99, ">10")]
    rows = []
    for per, g0 in d.groupby("period"):
        for lo_, hi_, lab in bins:
            g = g0[(g0.lag >= lo_) & (g0.lag <= hi_)]
            if g.empty:
                continue
            k, n = int(g.x.sum()), len(g)
            wl, wh = wilson(k, n)
            bl, bh = boot_ratio(g, "x", g.index == g.index, args.seed, args.boot)
            rows.append(dict(period=per, lag_years=lab, k=k, n=n, n_papers=int(g.arxiv_id.nunique()),
                             u=round(k / n, 4), boot=f"{bl:.4f}-{bh:.4f}", wilson=f"{wl:.4f}-{wh:.4f}"))
        for y, g in g0[g0.ref_year >= 2016].groupby("ref_year"):
            k, n = int(g.x.sum()), len(g)
            bl, bh = boot_ratio(g, "x", g.index == g.index, args.seed, args.boot)
            rows.append(dict(period=per, ref_year=int(y), k=k, n=n, n_papers=int(g.arxiv_id.nunique()),
                             u=round(k / n, 4), boot=f"{bl:.4f}-{bh:.4f}"))
    tab = pd.DataFrame(rows)
    tab.to_csv(out_dir / "p1_u_by_refyear.csv", index=False)
    meta = {"label": "EXPLORATORY (not preregistered)", "seed": args.seed, "boot": args.boot,
            "definition": "def 1, final cascade state, tier A; lag = citing-paper year - reference year",
            "n_refs_no_year_excluded": n_noyear, "rows": rows}
    if args.interim:
        meta.update(interim=True, s2_pending=int((d.get("s2_pending", 0) == 1).sum()),
                    definition="def 1, +DBLP column of the cascade (S2 pending), tier A; lag = citing-paper year - reference year")
    (out_dir / "p1_u_by_refyear.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for per, mk in (("2019-21", "o"), ("2024-26", "s")):
        t = tab[(tab.period == per) & tab.ref_year.notna()] if "ref_year" in tab else tab.iloc[:0]
        if t.empty:
            continue
        lo = [float(b.split("-")[0]) for b in t.boot]
        hi = [float(b.split("-")[1]) for b in t.boot]
        ax.errorbar(t.ref_year, 100 * t.u, yerr=[100 * (t.u - lo), 100 * (np.array(hi) - t.u)], marker=mk,
                    capsize=2, label=f"citing papers {per}")
    ax.set_xlabel("publication year of the cited reference")
    ax.set_ylabel("u_acad, def 1 (%)")
    ax.set_title(("INTERIM, +DBLP state — " if args.interim else "") + f"EXPLORATORY: u_acad by reference year (seed {args.seed}, paper bootstrap B={args.boot})",
                 fontsize=8)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "p1_u_by_refyear.png", dpi=150)
    print(tab.to_string(index=False))
    print(f"refs without a year (excluded): {n_noyear}")


if __name__ == "__main__":
    main()
