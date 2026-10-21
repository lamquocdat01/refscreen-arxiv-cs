#!/usr/bin/env python3
"""Topic 43 / P2 / T10a: label-stratified recheck and agreement (PREREG_AMENDMENT_4 (a)-(c)).

draw   Pool = pass-1 rows of results/p1_manual_sample.csv (minus the 40 rows of p1_manual_recheck.csv) and of
       results/p2_manual_sample.csv, with a non-empty pass-1 outcome.
       Stratum N (20): every pass-1 not-found / ambiguous row (if > 20: 20 drawn, stratified by outcome); if < 20,
       filled with pass-1 *exists* rows that are def-1 unresolved after the full cascade (results/p1_groundtruth.csv),
       drawn stratified by tier. Stratum E (20): pass-1 *exists* rows not used in N, stratified by tier.
       Rater: a seed-42 shuffle within each stratum; the first 10 of each go to LQD (second author, inter-rater),
       the rest to CC (intra-rater).
       Writes $THS_DATASETS/_derived/43/p2_recheck_key.csv (internal key: stratum, pass-1 outcome, rater; kept
       outside the shared results folder so that no rater sees it),
       results/p2_recheck_sheet.csv (LQD rows: entry only, outcome columns empty) and
       results/p2_recheck_cc_input.csv (CC rows, same blinding).
kappa  Reads the filled sheets (results/p2_recheck_sheet.csv, results/p2_recheck_cc.csv), joins pass 1, and reports
       PABAK (3 outcomes; PASS if >= 0.8 pooled), Gwet's AC1, Cohen's kappa, raw agreement and the 3 x 3 table:
       pooled, inter-rater (LQD) and intra-rater (CC); bootstrap 95 % CI resampling citing papers (B = 1000).
Outputs: results/p2_kappa.json, results/p2_kappa_table.csv
Usage: python p2_recheck.py draw --seed 42 ;  python p2_recheck.py kappa --seed 42 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, ROOT  # noqa: E402

RES = ROOT / "results"
KEY = DATA / "_derived" / "43" / "p2_recheck_key.csv"  # outside the shared folder: raters never see it
CATS = ["exists", "not-found", "ambiguous"]
FILL = ["exists", "evidence_url", "evidence_note", "checker", "checked_at"]
SHOW = ["sample_id", "citing_paper_date", "tier", "title", "author", "bib_entry"]
TIERS = ["J", "C", "P", "B", "S", "W"]


def strat_draw(df, n, rng, by="tier"):
    """Round robin over groups in a seeded order; within a group, a seeded permutation."""
    groups = {g: list(rng.permutation(x.index)) for g, x in df.groupby(by)}
    order = [g for g in TIERS + CATS if g in groups] + sorted(set(groups) - set(TIERS + CATS))
    out = []
    while len(out) < n and any(groups[g] for g in order):
        for g in order:
            if groups[g] and len(out) < n:
                out.append(groups[g].pop(0))
    return df.loc[out]


def draw(args):
    p1 = pd.read_csv(RES / "p1_manual_sample.csv", dtype=str, keep_default_na=False)
    p1r = set(pd.read_csv(RES / "p1_manual_recheck.csv", dtype=str, keep_default_na=False).sample_id)
    p2 = pd.read_csv(RES / "p2_manual_sample.csv", dtype=str, keep_default_na=False)
    cols = SHOW + ["paper_id", "key", "exists", "checked_at"]
    p2 = p2.assign(author=p2.get("author", ""))  # P2 rows: authors are inside bib_entry
    pool = pd.concat([p1[~p1.sample_id.isin(p1r)][cols].assign(origin="P1"), p2[cols].assign(origin="P2")])
    pool = pool[pool.exists != ""].rename(columns={"exists": "pass1", "checked_at": "pass1_at"}).reset_index(drop=True)
    gt = pd.read_csv(RES / "p1_groundtruth.csv", dtype=str, keep_default_na=False)[["paper_id", "key", "def1_status"]]
    pool = pool.merge(gt.drop_duplicates(["paper_id", "key"]), on=["paper_id", "key"], how="left")
    rng = np.random.default_rng(args.seed)
    nf = pool[pool.pass1.isin(["not-found", "ambiguous"])]
    if len(nf) > 20:
        nf = strat_draw(nf, 20, rng, by="pass1")
    nf = nf.assign(stratum="N", n_role="pass1 " + nf.pass1)
    need = 20 - len(nf)
    hard = pool[(pool.pass1 == "exists") & (pool.def1_status == "unresolved")]
    fill = strat_draw(hard, need, rng).assign(stratum="N", n_role="fill: exists, unresolved after +S2")
    rest = pool[(pool.pass1 == "exists") & ~pool.index.isin(fill.index)]
    e = strat_draw(rest, 20, rng).assign(stratum="E", n_role="")
    rc = pd.concat([nf, fill, e])
    rc["rater"] = "CC"
    for st in ("N", "E"):
        idx = rc.index[rc.stratum == st]
        perm = rng.permutation(idx)
        rc.loc[perm[:10], "rater"] = "LQD"
    rc = rc.sort_values(["rater", "sample_id"]).reset_index(drop=True)
    rc["recheck_id"] = [f"K{i + 1:02d}" for i in range(len(rc))]
    rc.to_csv(KEY, index=False)
    for rater, f in (("LQD", "p2_recheck_sheet.csv"), ("CC", "p2_recheck_cc_input.csv")):
        sh = rc[rc.rater == rater][["recheck_id"] + SHOW[1:]].copy()
        sh = sh.sample(frac=1, random_state=args.seed).reset_index(drop=True)  # order carries no stratum info
        for c in FILL:
            sh[c] = ""
        sh.to_csv(RES / f, index=False)
    print("pool", len(pool), pool.pass1.value_counts().to_dict(), "| hard exists", len(hard))
    print(rc.groupby(["stratum", "n_role", "rater"]).size().to_string())
    last = pd.to_datetime(rc.pass1_at, utc=True, errors="coerce").max()
    print("latest pass 1 in sample:", last, "-> recheck allowed from", last + pd.Timedelta(hours=48))


def pabak(t, k=3):
    po = np.trace(t) / t.sum()
    return (k * po - 1) / (k - 1)


def kappa_c(t):
    n = t.sum()
    po = np.trace(t) / n
    pe = (t.sum(0) * t.sum(1)).sum() / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def ac1(t):
    n, q = t.sum(), t.shape[0]
    po = np.trace(t) / n
    pi = (t.sum(0) + t.sum(1)) / (2 * n)
    pe = (pi * (1 - pi)).sum() / (q - 1)
    return (po - pe) / (1 - pe)


def table(a, b):
    t = np.zeros((3, 3))
    for x, y in zip(a, b):
        t[CATS.index(x), CATS.index(y)] += 1
    return t


def stats(df):
    t = table(df.pass1, df.pass2)
    return dict(n=len(df), raw=float(np.trace(t) / t.sum()), pabak=float(pabak(t)), ac1=float(ac1(t)),
                kappa=float(kappa_c(t)), table=t.astype(int).tolist())


def kappa(args):
    rc = pd.read_csv(KEY, dtype=str, keep_default_na=False)
    got = []
    for f in ("p2_recheck_sheet.csv", "p2_recheck_cc.csv"):
        if (RES / f).exists():
            got.append(pd.read_csv(RES / f, dtype=str, keep_default_na=False))
    p2 = pd.concat(got)[["recheck_id"] + FILL].rename(columns={"exists": "pass2", "checker": "checker2",
                                                               "checked_at": "checked_at2"})
    m = rc.merge(p2, on="recheck_id", how="left")
    m = m[m.pass2.isin(CATS)]
    out = {"interim": False, "seed": args.seed, "boot": args.boot, "criterion": "PABAK >= 0.8 (pooled)",
           "n_filled": len(m), "n_sample": len(rc)}
    rows = []
    for name, d in (("pooled", m), ("inter-rater (LQD)", m[m.rater == "LQD"]), ("intra-rater (CC)", m[m.rater == "CC"]),
                    ("stratum E", m[m.stratum == "E"]), ("stratum N", m[m.stratum == "N"])):
        if not len(d):
            continue
        s = stats(d)
        rng = np.random.default_rng(args.seed)
        papers = d.paper_id.unique()
        bs = {k: [] for k in ("raw", "pabak", "ac1", "kappa")}
        for _ in range(args.boot):
            pick = rng.choice(papers, len(papers), replace=True)
            bd = pd.concat([d[d.paper_id == p] for p in pick])
            sb = stats(bd)
            for k in bs:
                bs[k].append(sb[k])
        for k in bs:
            s[f"{k}_ci"] = [float(np.nanpercentile(bs[k], 2.5)), float(np.nanpercentile(bs[k], 97.5))]
        s["n_papers"] = len(papers)
        out[name] = s
        rows.append(dict(group=name, **{k: v for k, v in s.items() if k != "table"}, interim=False))
    if "pooled" in out:
        out["PASS"] = bool(out["pooled"]["pabak"] >= 0.8)
    (RES / "p2_kappa.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    pd.DataFrame(rows).to_csv(RES / "p2_kappa_table.csv", index=False)
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["draw", "kappa"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    (draw if args.stage == "draw" else kappa)(args)


if __name__ == "__main__":
    main()
