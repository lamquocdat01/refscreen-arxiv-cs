#!/usr/bin/env python3
"""Topic 43 / P3: recheck after Amendment 5 (POST-HOC, supplementary) — PREREG_AMENDMENT_5.md (b')-(e').

draw   Pool = pass-1 rows of results/p1_manual_sample.csv (minus the 40 P1 recheck rows) and results/p2_manual_sample.csv,
       minus the 40 P2 recheck rows (K01-K40). Stratum N (20): pass-1 not-found/ambiguous rows, filled with pass-1
       exists rows that are def-1 unresolved (results/p1_groundtruth.csv), stratified by tier; stratum E (20): other
       pass-1 exists rows, stratified by tier. Seed 43.
       Writes $THS_DATASETS/_derived/43/p3_recheck_key.csv (internal key) and results/p3_recheck_sheet.csv (blind sheet,
       one sheet for every rater: id, v1 date, .bib-version date (c'), tier, title, author, .bib entry, author's .bbl item
       (d'), empty outcome columns; seed-shuffled order).
kappa  Reads R2 = results/p3_recheck_r2.csv and R3 = results/p3_recheck_r3.csv (each a filled copy of the sheet), joins
       R1 (pass 1) from the key, and reports PABAK, Gwet AC1, raw kappa, raw agreement and the 3 x 3 table for R1-R3,
       R1-R2, R2-R3, plus the three-rater AC1; bootstrap 95 % CI resampling citing papers (B = 1000, seed 43).
       Outputs: results/p3_kappa.json, results/p3_kappa.csv
merge  Joins R1 (key), R2, R3 and the hand-coded route table results/p3_recheck_diagnosis.csv (how each rater found the
       resource; coded by CC from the evidence notes) -> results/p3_recheck_merged.csv (no internal paths, no emails).
stats  Reads only results/p3_recheck_merged.csv (so reproduce.py can rerun it without the internal key) and writes
       results/p3_recheck_stats.json: per pair and three-rater, 3-outcome and binary statistics (exists vs not-exists;
       ambiguous = disagreement with both sides, and a variant dropping ambiguous), paper-bootstrap CI (B = 1000, seed
       43), an exact Clopper-Pearson bound on the disagreement rate (the bootstrap is degenerate when no row disagrees),
       kappa = null when undefined, PASS/FAIL against PABAK >= 0.8 labelled post hoc, flat recheck_posthoc_* keys, and
       the route counts by stratum.
Usage: python p3_recheck.py draw --seed 43 ;  python p3_recheck.py kappa --seed 43 [--boot 1000]
       python p3_recheck.py merge ;  python p3_recheck.py stats --seed 43 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground_truth as gtm  # noqa: E402
from p2_recheck import CATS, FILL, RES, stats, strat_draw  # noqa: E402
from p2_recheck_pairs import ac1_multi  # noqa: E402

KEY = gtm.DATA / "_derived" / "43" / "p3_recheck_key.csv"
P2KEY = gtm.DATA / "_derived" / "43" / "p2_recheck_key.csv"
SHEET = RES / "p3_recheck_sheet.csv"
SHOW = ["recheck_id", "citing_paper_date", "bib_version_date", "tier", "title", "author", "bib_entry", "bbl_item"]


def bbl_lookup(paper_id, key, cache):
    if paper_id not in cache:
        pdir = gtm.SRC / paper_id.replace("/", "_")
        cache[paper_id] = {k: t for k, t, _ in gtm.bbl_items(pdir)} if pdir.exists() else {}
    return " ".join(cache[paper_id].get(key, "").split())


def draw(args):
    if SHEET.exists() or KEY.exists():
        sys.exit("p3 sheet/key exist; not overwritten")
    p1 = pd.read_csv(RES / "p1_manual_sample.csv", dtype=str, keep_default_na=False)
    p1r = set(pd.read_csv(RES / "p1_manual_recheck.csv", dtype=str, keep_default_na=False).sample_id)
    p2 = pd.read_csv(RES / "p2_manual_sample.csv", dtype=str, keep_default_na=False)
    used = set(pd.read_csv(P2KEY, dtype=str, keep_default_na=False).sample_id)
    cols = ["sample_id", "citing_paper_date", "tier", "title", "author", "bib_entry", "paper_id", "key", "exists",
            "checked_at"]
    p2 = p2.assign(author=p2.get("author", ""))
    pool = pd.concat([p1[~p1.sample_id.isin(p1r)][cols].assign(origin="P1"), p2[cols].assign(origin="P2")])
    pool = pool[(pool.exists != "") & ~pool.sample_id.isin(used)]
    pool = pool.rename(columns={"exists": "pass1", "checked_at": "pass1_at"}).reset_index(drop=True)
    gt = pd.read_csv(RES / "p1_groundtruth.csv", dtype=str, keep_default_na=False)[["paper_id", "key", "def1_status"]]
    pool = pool.merge(gt.drop_duplicates(["paper_id", "key"]), on=["paper_id", "key"], how="left")
    sv = pd.read_csv(gtm.ROOT / "data_manifest" / "manifest_src_version.csv", dtype=str, keep_default_na=False)
    pool = pool.merge(sv[["arxiv_id", "src_version", "src_version_date"]].rename(columns={"arxiv_id": "paper_id"}),
                      on="paper_id", how="left").rename(columns={"src_version_date": "bib_version_date"})
    assert (pool.bib_version_date.fillna("") != "").all(), "paper without .bib version date"
    rng = np.random.default_rng(args.seed)
    nf = pool[pool.pass1.isin(["not-found", "ambiguous"])]
    if len(nf) > 20:
        nf = strat_draw(nf, 20, rng, by="pass1")
    nf = nf.assign(stratum="N", n_role="pass1 " + nf.pass1)
    hard = pool[(pool.pass1 == "exists") & (pool.def1_status == "unresolved")]
    fill = strat_draw(hard, 20 - len(nf), rng).assign(stratum="N", n_role="fill: exists, unresolved after +S2")
    rest = pool[(pool.pass1 == "exists") & ~pool.index.isin(fill.index)]
    e = strat_draw(rest, 20, rng).assign(stratum="E", n_role="")
    rc = pd.concat([nf, fill, e]).sort_values("sample_id").reset_index(drop=True)
    rc["recheck_id"] = [f"Q{i + 1:02d}" for i in range(len(rc))]
    cache = {}
    rc["bbl_item"] = [bbl_lookup(p, k, cache) for p, k in zip(rc.paper_id, rc.key)]
    rc.to_csv(KEY, index=False)
    sh = rc[SHOW].sample(frac=1, random_state=args.seed).reset_index(drop=True)
    for c in FILL:
        sh[c] = ""
    sh.to_csv(SHEET, index=False)
    print("pool", len(pool), pool.pass1.value_counts().to_dict(), "| hard exists", len(hard))
    print(rc.groupby(["stratum", "n_role", "tier"]).size().to_string())
    print("bbl_item non-empty:", int((rc.bbl_item != "").sum()), "| .bib version > v1:", int((rc.src_version != "v1").sum()))
    last = pd.to_datetime(rc.pass1_at, utc=True, errors="coerce").max()
    print("latest pass 1 in sample:", last, "-> recheck allowed from", last + pd.Timedelta(hours=48))


def kappa(args):
    rc = pd.read_csv(KEY, dtype=str, keep_default_na=False).rename(columns={"pass1": "R1"})
    for r, f in (("R2", "p3_recheck_r2.csv"), ("R3", "p3_recheck_r3.csv")):
        if (RES / f).exists():
            x = pd.read_csv(RES / f, dtype=str, keep_default_na=False)[["recheck_id", "exists"]]
            rc = rc.merge(x.rename(columns={"exists": r}), on="recheck_id", how="left")
        else:
            rc[r] = ""
    out = {"seed": args.seed, "boot": args.boot, "label": "recheck after Amendment 5 (post-hoc, supplementary)",
           "threshold": "PABAK >= 0.8 (as P2); R1 labels under the original rules, R2/R3 under (b')-(d')"}
    rows = []
    for a, b in (("R1", "R3"), ("R1", "R2"), ("R2", "R3")):
        d = rc[rc[a].isin(CATS) & rc[b].isin(CATS)].assign(pass1=lambda x: x[a], pass2=lambda x: x[b])
        if not len(d):
            continue
        s = stats(d)
        rng = np.random.default_rng(args.seed)
        papers = d.paper_id.unique()
        bs = []
        for _ in range(args.boot):
            bs.append(stats(pd.concat([d[d.paper_id == p] for p in rng.choice(papers, len(papers), replace=True)])))
        for k in ("raw", "pabak", "ac1", "kappa"):
            s[f"{k}_ci"] = [float(np.nanpercentile([x[k] for x in bs], q)) for q in (2.5, 97.5)]
        s.update(n_papers=int(len(papers)), disagreements=d[d[a] != d[b]][["recheck_id", "stratum", a, b]].to_dict("records"))
        out[f"{a}-{b}"] = s
        rows.append(dict(pair=f"{a}-{b}", **{k: v for k, v in s.items() if k not in ("table", "disagreements")}))
    d3 = rc[rc.R1.isin(CATS) & rc.R2.isin(CATS) & rc.R3.isin(CATS)]
    if len(d3):
        f3 = lambda x: ac1_multi(x[["R1", "R2", "R3"]])  # noqa: E731
        rng = np.random.default_rng(args.seed)
        papers = d3.paper_id.unique()
        bs = [f3(pd.concat([d3[d3.paper_id == p] for p in rng.choice(papers, len(papers), replace=True)]))
              for _ in range(args.boot)]
        out["AC1 three raters"] = {"n": len(d3), "ac1": f3(d3), "ac1_ci": [float(np.nanpercentile(bs, q)) for q in (2.5, 97.5)]}
        rows.append(dict(pair="R1-R2-R3", n=len(d3), ac1=out["AC1 three raters"]["ac1"]))
    if "R1-R3" in out:
        out["meets_threshold_R1R3"] = bool(out["R1-R3"]["pabak"] >= 0.8)
    if "R2-R3" in out:
        out["meets_threshold_R2R3"] = bool(out["R2-R3"]["pabak"] >= 0.8)
    (RES / "p3_kappa.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    pd.DataFrame(rows).to_csv(RES / "p3_kappa.csv", index=False)
    print(json.dumps({k: v for k, v in out.items()}, indent=1)[:4000])


MERGED = RES / "p3_recheck_merged.csv"
RATERS = ["R1", "R2", "R3"]


def merge(args):
    rc = pd.read_csv(KEY, dtype=str, keep_default_na=False).rename(columns={"pass1": "R1"})
    rc["R1_note"] = "first pass (original rules)"
    for r, f in (("R2", "p3_recheck_r2.csv"), ("R3", "p3_recheck_r3.csv")):
        x = pd.read_csv(RES / f, dtype=str, keep_default_na=False)
        x = x[["recheck_id", "exists", "evidence_url", "evidence_note", "checker", "checked_at"]]
        rc = rc.merge(x.rename(columns={c: f"{r}_{c}" if c != "exists" else r for c in x.columns if c != "recheck_id"}),
                      on="recheck_id", how="left")
    dg = pd.read_csv(RES / "p3_recheck_diagnosis.csv", dtype=str, keep_default_na=False)
    rc = rc.merge(dg, on="recheck_id", how="left")
    cols = ["recheck_id", "paper_id", "stratum", "tier", "def1_status", "src_version", "citing_paper_date",
            "bib_version_date", "title", "R1", "R2", "R3", "R2_evidence_url", "R2_evidence_note", "R3_evidence_url",
            "R3_evidence_note", "R2_checker", "R3_checker", "R2_checked_at", "R3_checked_at", "r2_route", "r3_route",
            "entry_defect", "note"]
    out = rc[cols].sort_values("recheck_id")
    assert not out.apply(lambda c: c.str.contains(r"@[\w-]+\.[a-z]{2,}", regex=True)).any().any(), "email-like string"
    out.to_csv(MERGED, index=False)
    print(out[["recheck_id", "stratum", "tier", "R1", "R2", "R3", "r2_route", "r3_route"]].to_string())


def pair_stats(x, y):
    """3-outcome and binary statistics for two label vectors (strings in CATS)."""
    x, y = list(x), list(y)
    t = np.zeros((3, 3))
    for a, b in zip(x, y):
        t[CATS.index(a), CATS.index(b)] += 1
    n = len(x)
    po = float(np.trace(t) / n)
    pe = float((t.sum(0) * t.sum(1)).sum() / n ** 2)
    pi = (t.sum(0) + t.sum(1)) / (2 * n)
    pe_ac = float((pi * (1 - pi)).sum() / 2)
    # binary: exists vs not-exists; ambiguous disagrees with both sides
    agree_b = [a == b and a != "ambiguous" for a, b in zip(x, y)]
    pob = float(np.mean(agree_b))
    ex = np.array([[a == "exists", b == "exists"] for a, b in zip(x, y)], dtype=float)
    pib = ex.mean()
    pe_acb = float(2 * pib * (1 - pib))
    keep = [a != "ambiguous" and b != "ambiguous" for a, b in zip(x, y)]
    pox = float(np.mean([a == b for a, b, k in zip(x, y, keep) if k])) if any(keep) else np.nan
    return dict(n=n, raw=po, pabak=(3 * po - 1) / 2, ac1=(po - pe_ac) / (1 - pe_ac),
                kappa=(po - pe) / (1 - pe) if pe < 1 else None, table=t.astype(int).tolist(),
                bin_raw=pob, bin_pabak=2 * pob - 1, bin_ac1=(pob - pe_acb) / (1 - pe_acb),
                noamb_n=int(sum(keep)), noamb_pabak=2 * pox - 1 if any(keep) else None,
                disagree_n=int(n - np.trace(t)))


def cp_upper(k, n, conf=0.95):
    return float(beta.ppf(1 - (1 - conf) / 2, k + 1, n - k)) if k < n else 1.0


def stats_posthoc(args):
    m = pd.read_csv(MERGED, dtype=str, keep_default_na=False)
    assert m[RATERS].isin(CATS).all().all(), "unlabelled rows"
    out = {"seed": args.seed, "boot": args.boot, "n": len(m), "n_papers": int(m.paper_id.nunique()),
           "label": "recheck after Amendment 5 (post hoc, supplementary); does not replace the registered P2 FAIL",
           "criterion": "PABAK >= 0.8 (Amendment 4)", "labels": {r: m[r].value_counts().to_dict() for r in RATERS}}
    flat = {}
    rng0 = args.seed
    papers = m.paper_id.unique()
    for a, b in (("R1", "R2"), ("R1", "R3"), ("R2", "R3")):
        s = pair_stats(m[a], m[b])
        rng = np.random.default_rng(rng0)
        bs = []
        for _ in range(args.boot):
            d = pd.concat([m[m.paper_id == p] for p in rng.choice(papers, len(papers), replace=True)])
            bs.append(pair_stats(d[a], d[b]))
        for k in ("pabak", "ac1", "bin_pabak", "bin_ac1"):
            s[f"{k}_ci"] = [float(np.nanpercentile([z[k] for z in bs], q)) for q in (2.5, 97.5)]
        ub = cp_upper(s["disagree_n"], s["n"])
        s["disagree_cp_upper"] = ub
        s["pabak_cp_lower"] = (3 * (1 - ub) - 1) / 2
        s["bin_pabak_cp_lower"] = 2 * (1 - ub) - 1
        s["pass"] = bool(s["pabak"] >= 0.8)
        s["disagreements"] = m[m[a] != m[b]][["recheck_id", "stratum", a, b]].to_dict("records")
        out[f"{a}-{b}"] = s
        t = f"{a}{b}".lower()
        for k in ("n", "raw", "pabak", "ac1", "bin_pabak", "pabak_cp_lower", "disagree_n"):
            flat[f"recheck_posthoc_{t}_{k}"] = s[k]
        flat[f"recheck_posthoc_{t}_pabak_ci_lo"], flat[f"recheck_posthoc_{t}_pabak_ci_hi"] = s["pabak_ci"]
        flat[f"recheck_posthoc_{t}_kappa_defined"] = s["kappa"] is not None
    a3 = ac1_multi(m[RATERS])
    rng = np.random.default_rng(rng0)
    bs = [ac1_multi(pd.concat([m[m.paper_id == p] for p in rng.choice(papers, len(papers), replace=True)])[RATERS])
          for _ in range(args.boot)]
    unan = int((m.R1.eq(m.R2) & m.R2.eq(m.R3)).sum())
    out["three raters"] = {"ac1": a3, "ac1_ci": [float(np.nanpercentile(bs, q)) for q in (2.5, 97.5)],
                           "unanimous": unan}
    flat.update(recheck_posthoc_three_ac1=a3, recheck_posthoc_three_unanimous=unan, recheck_posthoc_n=len(m),
                recheck_posthoc_n_papers=out["n_papers"],
                recheck_posthoc_r1_nonexists=int((m.R1 != "exists").sum()),
                recheck_posthoc_pass_r1r3=out["R1-R3"]["pass"])
    routes = {}
    for st in ("N", "E"):
        d = m[m.stratum == st]
        routes[st] = {"n": len(d), "tiers": d.tier.value_counts().to_dict(),
                      "def1_status": d.def1_status.value_counts().to_dict(),
                      "r2_route": d.r2_route.value_counts().to_dict(), "r3_route": d.r3_route.value_counts().to_dict(),
                      "entry_defect": int((d.entry_defect != "none").sum()),
                      "r3_review_secondary": d[d.R3_evidence_note.str.contains("REVIEW")].recheck_id.tolist()}
        for k, v in routes[st]["r3_route"].items():
            flat[f"recheck_posthoc_{st.lower()}_r3_{k}"] = v
        for k, v in routes[st]["r2_route"].items():
            flat[f"recheck_posthoc_{st.lower()}_r2_{k}"] = v
        flat[f"recheck_posthoc_{st.lower()}_entry_defect"] = routes[st]["entry_defect"]
    nd = m[m.stratum == "N"]
    flat["recheck_posthoc_n_any_indirect"] = int(((nd.r2_route != "direct") | (nd.r3_route != "direct")).sum())
    out["routes"] = routes
    out["flat"] = flat
    (RES / "p3_recheck_stats.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps(flat, indent=1, default=float))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["draw", "kappa", "merge", "stats"])
    ap.add_argument("--seed", type=int, default=43)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    {"draw": draw, "kappa": kappa, "merge": merge, "stats": stats_posthoc}[args.stage](args)


if __name__ == "__main__":
    main()
