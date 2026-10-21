#!/usr/bin/env python3
"""Topic 43 / P2 / T10a: route (b) on the render set (PREREG_AMENDMENT_4 (f); descriptive).

FP among the pass-1 *exists* rows of results/p2_manual_sample.csv (60 refs from the 100 render papers) for
3 styles (IEEEtran v1.14, IEEEtran-DOI, elsarticle-num) x 2 variants (orig / strip) x 2 parsers (GROBID / anystyle)
x 2 screens (Crossref-only = flag_crossref, full cascade = flag_union of screen_baseline.py), read from
$THS_DATASETS/_derived/43/screen_p1/screen_refs.csv. A failed query (NaN flag) is excluded from that cell and counted.
Next to each cell: the certified-real FP of the same cell (results/p1_screen_fp.csv). Intervals: Wilson (refs);
n per tier < 10 -> k/n only. H3 check: ratio FP(IEEEtran strip) / FP(IEEEtran-DOI orig), union, GROBID, on these rows;
a ratio < 1 is reported as a threat to H3.
Decision 21-10 (LQD): the 60 refs carry no identifier by design, so they are uninformative for H3 (Amendment 4 (f) is
read this way); they are used for H4 on the render set ("H4-render", descriptive): FP_manual weighted by the share of
each tier among the render refs without identifier, minus FP_certified of the same cell; paper bootstrap over the 100
render papers (B = 1000, seed 42), resampling manual and certified refs of the drawn papers together.
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
    # H4-render
    lab = pd.read_csv(DATA / "_derived" / "43" / "screen_p1" / "screen_refs.csv", dtype=str, keep_default_na=False,
                      usecols=["arxiv_id", "style", "variant", "parser", "key", "tier", "label", "bib_has_doi",
                               "bib_has_arxiv"] + list(SCREENS.values()))
    lab = lab[(lab["style"] == "IEEEtran") & (lab.variant == "orig") & (lab.parser == "grobid")]
    noid = lab[(lab.bib_has_doi == "0") & (lab.bib_has_arxiv == "0")]
    w = (noid.tier.value_counts() / len(noid)).to_dict()
    h4 = {}
    rng0 = args.seed
    for sc, fc in SCREENS.items():
        man = m[(m["style"] == "IEEEtran") & (m.variant == "orig") & (m.parser == "grobid")].copy()
        man["f"] = pd.to_numeric(man[fc], errors="coerce")
        man = man[man.f.notna()]
        cer = lab[lab.label == "certified-real"].copy()
        cer["f"] = pd.to_numeric(cer[fc], errors="coerce")
        cer = cer[cer.f.notna()]

        def est(mm, cc):
            g = mm.groupby("tier").f.agg(["sum", "count"])
            ws = {t: w.get(t, 0) for t in g.index}
            tot = sum(ws.values())
            fm = sum(ws[t] * g.loc[t, "sum"] / g.loc[t, "count"] for t in g.index) / tot if tot else np.nan
            return fm, cc.f.mean()
        fm, fcz = est(man, cer)
        rng = np.random.default_rng(rng0)
        papers = np.array(sorted(set(lab.arxiv_id)))
        mg, cg = dict(tuple(man.groupby("paper_id"))), dict(tuple(cer.groupby("arxiv_id")))
        diffs = []
        for _ in range(1000):
            pick = rng.choice(papers, len(papers), replace=True)
            bm = pd.concat([mg[p] for p in pick if p in mg]) if any(p in mg for p in pick) else man.head(0)
            bc = pd.concat([cg[p] for p in pick if p in cg])
            if len(bm):
                a, b = est(bm, bc)
                diffs.append(a - b)
        lo, hi = np.nanpercentile(diffs, [2.5, 97.5])
        h4[sc] = dict(fp_manual_weighted=fm, k_manual=int(man.f.sum()), n_manual=len(man),
                      fp_certified=fcz, k_certified=int(cer.f.sum()), n_certified=len(cer), diff=fm - fcz,
                      diff_ci=[float(lo), float(hi)], above_zero=bool(lo > 0),
                      manual_by_tier={t: [int(x.f.sum()), len(x)] for t, x in man.groupby("tier")})
    meta = dict(interim=False, seed=args.seed, n_sample=len(ms), outcomes=ms.exists.value_counts().to_dict(),
                n_exists=len(ex), n_papers=ex.paper_id.nunique(), label="descriptive (PREREG_AMENDMENT_4 (f))",
                h3_check_grobid=h3, h3_reading="uninformative for H3 by design: 0 of the 60 refs carries a DOI or "
                "arXiv id (decision LQD 21-10-2026)", by_tier_IEEEtran_strip_grobid=by_tier,
                h4_render=dict(style="IEEEtran orig, GROBID", weights_noid_tier_share=w, boot=1000, **h4))
    (ROOT / "results" / "p2_render_manual_fp.json").write_text(json.dumps(meta, indent=1, default=float),
                                                               encoding="utf-8")
    print(out[["style", "variant", "parser", "screen", "k_manual", "n_manual", "fp_manual", "k_cert", "n_cert",
               "fp_cert"]].to_string())
    print(json.dumps(h3, indent=1, default=float))
    print(json.dumps(h4, indent=1, default=float))


if __name__ == "__main__":
    main()
