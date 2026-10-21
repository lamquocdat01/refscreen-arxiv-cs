#!/usr/bin/env python3
"""Topic 43 / P2 / T10a: route (b) on the render set (PREREG_AMENDMENT_4 (f); descriptive).

FP among the pass-1 *exists* rows of results/p2_manual_sample.csv (60 refs from the 100 render papers) for
3 styles (IEEEtran v1.14, IEEEtran-DOI, elsarticle-num) x 2 variants (orig / strip) x 2 parsers (GROBID / anystyle)
x 2 screens (Crossref-only = flag_crossref, full cascade = flag_union of screen_baseline.py), read from
$THS_DATASETS/_derived/43/screen_p1/screen_refs.csv. A failed query (NaN flag) is excluded from that cell and counted.
Next to each cell: the certified-real FP of the same cell (results/p1_screen_fp.csv). Intervals: Wilson (refs);
n per tier < 10 -> k/n only. H3 check: ratio FP(IEEEtran strip) / FP(IEEEtran-DOI orig), union, GROBID, on these rows;
a ratio < 1 is reported as a threat to H3.
Outputs: results/p2_render_manual_fp.csv, results/p2_render_manual_fp.json
Usage: python p2_render_manual_fp.py --seed 42
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, ROOT  # noqa: E402
from p2_fake_refs import wilson  # noqa: E402

STYLES = ["IEEEtran", "IEEEtran_doi", "elsarticle-num"]
SCREENS = {"crossref": "flag_crossref", "union": "flag_union"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    ms = pd.read_csv(ROOT / "results" / "p2_manual_sample.csv", dtype=str, keep_default_na=False)
    ex = ms[ms.exists == "exists"][["sample_id", "paper_id", "key", "tier"]]
    cols = ["arxiv_id", "style", "variant", "parser", "key"] + list(SCREENS.values())
    sr = pd.read_csv(DATA / "_derived" / "43" / "screen_p1" / "screen_refs.csv", dtype=str, keep_default_na=False,
                     usecols=cols)
    m = ex.merge(sr, left_on=["paper_id", "key"], right_on=["arxiv_id", "key"], how="left")
    cert = pd.read_csv(ROOT / "results" / "p1_screen_fp.csv", dtype=str, keep_default_na=False)
    cert = cert[(cert.subset == "certified-real") & (cert.source == "render") & (cert.tier == "all")]
    rows = []
    for st in STYLES:
        for var in ("orig", "strip"):
            for par in ("grobid", "anystyle"):
                g = m[(m["style"] == st) & (m.variant == var) & (m.parser == par)]
                for sc, fc in SCREENS.items():
                    f = pd.to_numeric(g[fc], errors="coerce")
                    n, k = int(f.notna().sum()), int(f.sum())
                    lo, hi = wilson(k, n)
                    c = cert[(cert["style"] == st) & (cert.variant == var) & (cert.parser == par)
                             & (cert.backend == sc)]
                    c = c.iloc[0] if len(c) else None
                    rows.append(dict(style=st, variant=var, parser=par, screen=sc, n_manual=n,
                                     n_excluded=len(g) - n, n_papers=g.paper_id.nunique(), k_manual=k,
                                     fp_manual=k / n if n else np.nan, wilson_lo=lo, wilson_hi=hi,
                                     n_cert=None if c is None else int(c.n_refs),
                                     k_cert=None if c is None else int(c.k_flagged),
                                     fp_cert=None if c is None else float(c.fp),
                                     cert_ci_lo=None if c is None else float(c.ci_lo),
                                     cert_ci_hi=None if c is None else float(c.ci_hi),
                                     seed=args.seed, interim=False))
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "results" / "p2_render_manual_fp.csv", index=False)
    by_tier = []
    g = m[(m["style"] == "IEEEtran") & (m.variant == "strip") & (m.parser == "grobid")]
    for t, x in g.groupby("tier"):
        for sc, fc in SCREENS.items():
            f = pd.to_numeric(x[fc], errors="coerce")
            by_tier.append(dict(tier=t, screen=sc, k=int(f.sum()), n=int(f.notna().sum())))

    def cell(st, var, sc):
        r = out[(out["style"] == st) & (out.variant == var) & (out.parser == "grobid") & (out.screen == sc)].iloc[0]
        return r

    h3 = {}
    for sc in SCREENS:
        a, b = cell("IEEEtran", "strip", sc), cell("IEEEtran_doi", "orig", sc)
        ratio = a.fp_manual / b.fp_manual if b.fp_manual > 0 else (np.inf if a.fp_manual > 0 else np.nan)
        h3[sc] = dict(k_a=int(a.k_manual), n_a=int(a.n_manual), k_b=int(b.k_manual), n_b=int(b.n_manual),
                      ratio=None if not np.isfinite(ratio) else ratio, ratio_note="inf (k_b = 0)" if ratio == np.inf
                      else "", reverses_h3=bool(np.isfinite(ratio) and ratio < 1))
    meta = dict(interim=False, seed=args.seed, n_sample=len(ms), outcomes=ms.exists.value_counts().to_dict(),
                n_exists=len(ex), n_papers=ex.paper_id.nunique(), label="descriptive (PREREG_AMENDMENT_4 (f))",
                h3_check_grobid=h3, by_tier_IEEEtran_strip_grobid=by_tier)
    (ROOT / "results" / "p2_render_manual_fp.json").write_text(json.dumps(meta, indent=1, default=float),
                                                               encoding="utf-8")
    print(out[["style", "variant", "parser", "screen", "k_manual", "n_manual", "fp_manual", "k_cert", "n_cert",
               "fp_cert"]].to_string())
    print(json.dumps(h3, indent=1, default=float))


if __name__ == "__main__":
    main()
