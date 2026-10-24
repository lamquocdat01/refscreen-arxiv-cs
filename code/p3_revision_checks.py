#!/usr/bin/env python3
"""Topic 43 / P3: EXPLORATORY checks requested by the hostile read (HOSTILE_READ_43.md); post hoc, offline.

  1 paper-level flags on ACADEMIC references only (k = 1, 2), 2019-21, per cumulative backend set (Wilson)
  2 FP_manual on academic identifier-free references (raw k/n, full cascade and +DBLP), from results/p1_h4_bias.json
  3 H3 paired comparison: the same certified-real references rendered IEEEtran v1.14 strip vs IEEEtran-DOI orig,
    union screen, GROBID; discordant counts and exact two-sided binomial (McNemar) p
  4 pre-LLM legitimacy: 2019-21 papers whose .bib comes from an arXiv version dated after 2022-11-30, and u_A (full
    cascade) without them (paper bootstrap B = 1000, seed 42)
  5 identifier scenario: union FP of the DOI-printing style with identifiers kept (identifier first, title fallback),
    and the identifier-only route, from results/p1_screen_fp.csv
  6 OpenAlex refusals (oa_skipped) among academic references, 2019-21 and 2024-26
  7 accounting rows: GPTZero items (listed / after audit / evaluated), P1 manual sample exists vs H4 denominator
Outputs: results/p3_revision_checks.json
Usage: python p3_revision_checks.py --seed 42
"""
import argparse
import json
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, ROOT, wilson  # noqa: E402
from p1_backend_table import COLS, first_hit_stage  # noqa: E402

RES = ROOT / "results"
D = DATA / "_derived" / "43"


def binom_two_sided(b, c):
    n, k = b + c, min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = {"label": "EXPLORATORY, post hoc (revision checks after the hostile read)", "seed": args.seed}
    gt = pd.read_csv(D / "p2_groundtruth_refs_full.csv", dtype=str, keep_default_na=False, low_memory=False)
    pre = gt[gt.period == "2019-21"].copy()
    papers = sorted(pre.arxiv_id.unique())
    a = pre[pre.tier.isin(["J", "C", "P"]) & pre.def1_status.isin(["resolved", "unresolved"])].copy()
    a["stage"] = np.where(a.def1_status == "resolved", a.backends_hit.map(first_hit_stage), len(COLS))
    # 1
    res1 = {}
    for j, c in enumerate(COLS):
        cnt = a.assign(f=(a.stage > j).astype(int)).groupby("arxiv_id").f.sum().reindex(papers, fill_value=0)
        res1[c] = {}
        for k in (1, 2):
            m = int((cnt >= k).sum())
            lo, hi = wilson(m, len(papers))
            res1[c][f"k{k}"] = {"papers": m, "n": len(papers), "share": m / len(papers), "wilson": [lo, hi]}
    out["paper_flags_academic_only"] = res1
    # 2
    h4 = json.loads((RES / "p1_h4_bias.json").read_text(encoding="utf-8"))["H4"]
    res2 = {}
    for sc in ("union", "dblp", "crossref"):
        t = h4[sc]["manual_by_tier"]
        k = sum(t[x][0] for x in ("J", "C", "P"))
        n = sum(t[x][1] for x in ("J", "C", "P"))
        lo, hi = wilson(k, n)
        res2[sc] = {"k": k, "n": n, "share": k / n, "wilson": [lo, hi], "raw_all_k": h4[sc]["k_manual"],
                    "raw_all_n": h4[sc]["n_manual"], "raw_all_share": h4[sc]["k_manual"] / h4[sc]["n_manual"]}
    out["fp_manual_academic"] = res2
    # 3
    sr = pd.read_csv(D / "screen_p1" / "screen_refs.csv", dtype=str, keep_default_na=False,
                     usecols=["arxiv_id", "style", "variant", "parser", "key", "label", "flag_union", "flag_crossref"])
    sr = sr[(sr.parser == "grobid") & (sr.label == "certified-real")] if "certified-real" in set(sr.label) else sr[sr.parser == "grobid"]
    res3 = {}
    for fc in ("flag_union", "flag_crossref"):
        x = sr[(sr["style"] == "IEEEtran") & (sr.variant == "strip")][["arxiv_id", "key", fc]].rename(columns={fc: "a"})
        y = sr[(sr["style"] == "IEEEtran_doi") & (sr.variant == "orig")][["arxiv_id", "key", fc]].rename(columns={fc: "b"})
        m = x.merge(y, on=["arxiv_id", "key"])
        m = m[(m.a != "") & (m.b != "")]
        aa, bb = pd.to_numeric(m.a), pd.to_numeric(m.b)
        b_only, c_only = int(((aa == 1) & (bb == 0)).sum()), int(((aa == 0) & (bb == 1)).sum())
        res3[fc] = {"pairs": len(m), "strip_only": b_only, "doi_only": c_only, "both": int(((aa == 1) & (bb == 1)).sum()),
                    "exact_p_two_sided": binom_two_sided(b_only, c_only), "papers": int(m.arxiv_id.nunique())}
    out["h3_paired"] = res3
    # 4
    sv = pd.read_csv(ROOT / "data_manifest" / "manifest_src_version.csv", dtype=str, keep_default_na=False)
    late = set(sv[(sv.src_version_date > "2022-11-30") & sv.arxiv_id.isin(papers)].arxiv_id)
    keep = a[~a.arxiv_id.isin(late)]
    rng = np.random.default_rng(args.seed)
    full = (keep.stage > len(COLS) - 1).astype(int)
    by = keep.assign(f=full).groupby("arxiv_id").f.agg(["sum", "count"])
    bs = []
    for _ in range(1000):
        s = by.iloc[rng.integers(0, len(by), len(by))]
        bs.append(s["sum"].sum() / s["count"].sum())
    allu = (a.stage > len(COLS) - 1).mean()
    out["pre_llm_versions"] = {"papers": len(papers), "papers_bib_after_2022_11_30": len(late),
                               "u_A_full_all": float(allu), "u_A_full_without_late": float(full.mean()),
                               "k_without_late": int(full.sum()), "n_without_late": int(len(keep)),
                               "papers_without_late": int(by.shape[0]),
                               "boot95_without_late": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
    # 5
    sf = pd.read_csv(RES / "p1_screen_fp.csv", dtype=str, keep_default_na=False)
    c = sf[(sf.subset == "certified-real") & (sf.source == "render") & (sf.tier == "all") & (sf.parser == "grobid")]
    res5 = {}
    for st, var in (("IEEEtran_doi", "orig"), ("IEEEtran", "orig"), ("IEEEtran", "strip")):
        for be in ("union", "idonly"):
            r = c[(c["style"] == st) & (c.variant == var) & (c.backend == be)]
            if len(r):
                r = r.iloc[0]
                res5[f"{st}/{var}/{be}"] = {"k": int(r.k_flagged), "n": int(r.n_refs), "fp": float(r.fp),
                                            "boot95": [float(r.ci_lo), float(r.ci_hi)]}
    out["identifier_scenario"] = res5
    # 6
    res6 = {}
    for per in ("2019-21", "2024-26"):
        g = gt[(gt.period == per) & gt.tier.isin(["J", "C", "P"]) & gt.def1_status.isin(["resolved", "unresolved"])]
        res6[per] = {"n": int(len(g)), "oa_skipped": int((g.oa_skipped == "1").sum()),
                     "oa_skipped_and_unresolved": int(((g.oa_skipped == "1") & (g.def1_status == "unresolved")).sum())}
    out["openalex_refusals_academic"] = res6
    # 8 empirical (in-sample) distribution of N_A under the full cascade: 95 % / 99 % quantiles, all papers and papers
    #   with n_A within +-25 % of the median paper of Table 7 (n_A = 32)
    na = a.assign(f=(a.stage > len(COLS) - 1).astype(int)).groupby("arxiv_id").agg(N=("f", "sum"), n=("f", "size"))
    near = na[(na.n >= 24) & (na.n <= 40)]
    out["empirical_NA"] = {"papers": int(len(na)), "q95_all": float(np.quantile(na.N, 0.95)),
                           "q99_all": float(np.quantile(na.N, 0.99)), "max_all": int(na.N.max()),
                           "papers_near_median": int(len(near)), "q95_near": float(np.quantile(near.N, 0.95)),
                           "q99_near": float(np.quantile(near.N, 0.99)), "max_near": int(near.N.max())}
    post = gt[gt.period == "2024-26"]
    ppost = sorted(post.arxiv_id.unique())
    b_ = post[post.tier.isin(["J", "C", "P"]) & post.def1_status.isin(["resolved", "unresolved"])].copy()
    b_["stage"] = np.where(b_.def1_status == "resolved", b_.backends_hit.map(first_hit_stage), len(COLS))
    npost = b_.assign(f=(b_.stage > len(COLS) - 1).astype(int)).groupby("arxiv_id").f.sum().reindex(ppost, fill_value=0)
    out["empirical_NA_2024_26"] = {}
    for k in (1, 2, 3, 4, 5):
        m = int((npost >= k).sum())
        out["empirical_NA_2024_26"][f"share_ge{k}"] = {"papers": m, "n": len(ppost), "share": m / len(ppost),
                                                       "wilson": list(wilson(m, len(ppost)))}
    allp = na.N.reindex(papers, fill_value=0)
    for k in (3, 4, 5):
        m = int((allp >= k).sum())
        out["empirical_NA"][f"share_ge{k}"] = {"papers": m, "n": len(papers), "share": m / len(papers),
                                               "wilson": list(wilson(m, len(papers)))}
    # 7
    rec = pd.read_csv(RES / "p2_recall.csv", dtype=str, keep_default_na=False)
    g = rec[(rec.set == "gptzero") & (rec.definition == "1") & (rec.screen == "+s2")].iloc[0]
    au = pd.read_csv(RES / "p2_recall_audited.csv", dtype=str, keep_default_na=False)
    g2 = au[(au.set == "gptzero") & (au.definition == "1") & (au.screen == "+s2") & au.version.str.startswith("after")].iloc[0]
    ms = pd.read_csv(RES / "p1_manual_sample.csv", dtype=str, keep_default_na=False)
    out["accounting"] = {"gptzero_items": int(g.n_items), "gptzero_items_after_audit": int(g2.n_items),
                         "gptzero_evaluated_after_audit": int(g2.n_evaluated),
                         "p1_manual_exists": int((ms.exists == "exists").sum()),
                         "p1_manual_exists_used_in_h4": int(h4["union"]["n_manual"])}
    (RES / "p3_revision_checks.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
