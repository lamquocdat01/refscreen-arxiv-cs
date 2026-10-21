#!/usr/bin/env python3
"""Topic 43 / P0 / T04: baseline existence screen on rendered reference strings; pilot false-positive rates.

Screen (per reference string, no access to the .bib):
  id      : a DOI printed in the string (regex) resolves in Crossref/OpenAlex/DataCite, or a printed arXiv id resolves in
            arXiv, AND the registry title is contained in the string (partial ratio >= 0.9)
  crossref: id OR Crossref query.bibliographic(full string) whose top-5 titles are contained in the string (>= 0.9)
  s2      : id OR Semantic Scholar title match(parsed title) with title similarity >= 0.9 (or contained >= 0.9)
  union   : id OR crossref OR s2 OR arXiv title search (arXiv queried only when the others fail)
"Unresolved" under a backend = flag. Source "bib-title" = title-only search on the original .bib title (no identifier),
taken from ground_truth.py (columns to_crossref / to_s2 / to_arxiv).
FP (pilot) = share of CERTIFIED-REAL references that are flagged, by source/style x variant x backend; 95 % CI by paper
bootstrap (B >= 200, default 1000). Flag rate on all references (not only certified) is reported too.
Outputs: $THS_DATASETS/_derived/43/screen/screen_refs.csv, results/p0_screen_fp.csv, results/p0_screen_fp.json
Usage: python screen_baseline.py --seed 42 [--limit N] [--boot 1000] [--workers 8]
       python screen_baseline.py --phase p1 --seed 42 [--boot 1000] [--s2-live] [--interim]
P1 screens: crossref (id + Crossref = Crossref-only), dblp (Crossref-only + DBLP offline), union (full cascade:
+ S2 + arXiv title search). --interim: ground truth from _derived/43/interim (ground_truth_p1.py --interim), no S2 and
no arXiv title search (union not computed, H3 on the full cascade pending), outputs in results/interim/ with
"interim": true. H4 (PREREG §5) is computed for every screen available.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
from ground_truth import DERIVED  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
T = rm.SIM_THRESHOLD


def screen_one(s, title):
    out = {}
    # identifier route
    id_ok = 0
    m = rm.DOI_RE.search(s or "")
    if m:
        doi = rm.clean_doi(m.group(1))
        be, titles = rm.resolve_doi(doi) if doi else (None, None)
        if titles and max(rm.contained_sim(t, s) for t in titles) >= T:
            id_ok = 1
    aid = rm.arxiv_from_text(s or "")
    if not id_ok and aid:
        t = rm.arxiv_ids([aid]).get(aid)
        if t and (rm.contained_sim(t, s) >= T or rm.title_sim(t, title or "") >= T):
            id_ok = 1
    out["id"] = id_ok
    cr = rm.crossref_search(s) if s else []
    cr_s, _ = rm.best_sim(cr, refstring=s)
    out["cr_sim"], out["cr_err"] = (cr_s if cr is not None else np.nan), int(cr is None)
    q = title if title and len(rm.norm(title)) >= 10 else (s or "")[:300]
    s2 = rm.s2_match(q) if q else []
    s2_t, _ = rm.best_sim(s2, title=q)
    s2_c, _ = rm.best_sim(s2, refstring=s)
    # a failed query (429 retries exhausted) is NOT "not found": NaN, excluded from that backend's denominator
    out["s2_sim"], out["s2_err"] = (max(s2_t, s2_c) if s2 is not None else np.nan), int(s2 is None)
    ax_s, ax_err = 0.0, 0
    if not id_ok and cr_s < T and not (out["s2_sim"] >= T) and q:
        ax = rm.arxiv_title_search(q)
        ax_err = int(ax is None)
        a1, _ = rm.best_sim(ax, title=q)
        a2, _ = rm.best_sim(ax, refstring=s)
        ax_s = max(a1, a2)
    out["ax_sim"], out["ax_err"] = ax_s, ax_err
    return out


def boot_ci(df, col, seed, B):
    g = df.groupby("arxiv_id")[col].agg(["sum", "count"])
    if len(g) < 10:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), (B, len(g)))
    v = g["sum"].values[idx].sum(1) / g["count"].values[idx].sum(1)
    return (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="max rendered refs screened (0 = all)")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--phase", default="p0", choices=["p0", "p1"])
    ap.add_argument("--resume", action="store_true", help="documented no-op: answers come from the API cache")
    ap.add_argument("--s2-live", action="store_true", help="p1: ask S2 live in stage B (default: S2 cache only)")
    ap.add_argument("--interim", action="store_true", help="p1: Crossref-only + DBLP offline screens only -> results/interim")
    args = ap.parse_args()
    assert args.boot >= 200
    if args.phase == "p1":
        return main_p1(args)

    rr = pd.read_csv(DERIVED / "render" / "rendered_refs.csv", dtype={"arxiv_id": str, "key": str, "refstr": str,
                                                                      "parsed_title": str}).fillna({"refstr": "",
                                                                                                    "parsed_title": ""})
    gt = pd.read_csv(DERIVED / "groundtruth_refs.csv", dtype={"arxiv_id": str, "key": str})
    if args.limit:
        rr = rr.head(args.limit)
    uniq = rr[["refstr", "parsed_title"]].drop_duplicates().reset_index(drop=True)
    print(f"rendered refs {len(rr)}, unique (string, title) {len(uniq)}", flush=True)
    t0, done = time.time(), [0]

    def job(i):
        r = uniq.loc[i]
        res = screen_one(r.refstr, r.parsed_title)
        done[0] += 1
        if done[0] % 200 == 0:
            print(f"  screened {done[0]}/{len(uniq)} ({time.time() - t0:.0f}s)", flush=True)
        return res

    with ThreadPoolExecutor(args.workers) as ex:
        res = list(ex.map(job, range(len(uniq))))
    uniq = pd.concat([uniq, pd.DataFrame(res)], axis=1)
    rr = rr.merge(uniq, on=["refstr", "parsed_title"], how="left")
    rr["source"] = "render:" + rr["style"]
    rr["flag_crossref"] = np.where(rr.cr_sim.isna() & (rr.id == 0), np.nan, ((rr.id == 0) & (rr.cr_sim < T)))
    rr["flag_s2"] = np.where(rr.s2_sim.isna() & (rr.id == 0), np.nan, ((rr.id == 0) & (rr.s2_sim < T)))
    resolved_any = (rr.id == 1) | (rr.cr_sim >= T) | (rr.s2_sim >= T) | (rr.ax_sim >= T)
    rr["flag_union"] = np.where(~resolved_any & rr.cr_sim.isna() & rr.s2_sim.isna(), np.nan, ~resolved_any)
    for c in ["flag_crossref", "flag_s2", "flag_union"]:
        rr[c] = rr[c].astype(float)
    rr["flag_idonly"] = (rr.id == 0).astype(float)
    # reference not found in the rendered text (LaTeX/pdftotext failure, e.g. a raw "_" in a DOI under the
    # DOI-printing .bst): a render failure, not a screen decision -> excluded from every FP denominator
    rr["render_missing"] = (rr.refstr.str.strip() == "").astype(int)
    for c in ["flag_crossref", "flag_s2", "flag_union", "flag_idonly"]:
        rr.loc[rr.render_missing == 1, c] = np.nan

    # bib-title source (title-only on the authored .bib title), from ground truth
    b = gt[(gt.render30 == 1) & gt.to_status.isin(["resolved", "unresolved"])].copy()
    b["style"], b["variant"], b["source"] = "bib-title", "orig", "bib-title"
    b["flag_crossref"] = np.where(b.to_crossref.isna(), np.nan, b.to_crossref < T)
    # S2 is queried lazily in ground_truth (only when Crossref fails), so an S2-only FP on bib-title would be
    # conditional and biased upward: not reported for this source (union and crossref are complete).
    b["flag_s2"] = np.nan
    b["flag_union"] = (b.to_status == "unresolved").astype(int)
    b["flag_idonly"] = 1
    cols = ["arxiv_id", "key", "style", "variant", "source", "label", "flag_crossref", "flag_s2", "flag_union",
            "flag_idonly"]
    allr = pd.concat([rr[cols + ["bib_has_doi", "bib_has_arxiv"]],
                      b.assign(bib_has_doi=b.has_doi, bib_has_arxiv=b.has_arxiv)[cols + ["bib_has_doi",
                                                                                         "bib_has_arxiv"]]])
    (DERIVED / "screen").mkdir(parents=True, exist_ok=True)
    rr.to_csv(DERIVED / "screen" / "screen_refs.csv", index=False)

    rows = []
    for subset, mask in [("certified-real", allr.label == "certified-real"),
                         ("certified-real & bib DOI", (allr.label == "certified-real") & (allr.bib_has_doi == 1)),
                         ("certified-real & arXiv-only", (allr.label == "certified-real") & (allr.bib_has_doi == 0)
                          & (allr.bib_has_arxiv == 1)),
                         ("all refs (not certified)", allr.label.notna())]:
        for (src, style, variant), g in allr[mask].groupby(["source", "style", "variant"]):
            for be in ["idonly", "crossref", "s2", "union"]:
                col = f"flag_{be}"
                gg = g[g[col].notna()]
                n, k = len(gg), int(gg[col].sum())
                lo, hi = boot_ci(gg, col, args.seed, args.boot)
                rows.append(dict(subset=subset, source=src, style=style, variant=variant, backend=be, n_refs=n,
                                 n_papers=gg.arxiv_id.nunique(), k_flagged=k, fp=k / n if n else np.nan,
                                 ci_lo=lo, ci_hi=hi, seed=args.seed, boot=args.boot))
    fp = pd.DataFrame(rows)
    fp.to_csv(ROOT / "results" / "p0_screen_fp.csv", index=False, float_format="%.4f")

    # CP-B0 criterion: FP ratio of each style vs the DOI-printing style (same variant, backend, subset), paper bootstrap
    crit = []
    cr = allr[allr.label == "certified-real"]
    papers = sorted(cr.arxiv_id.unique())
    rng = np.random.default_rng(args.seed)
    boots = rng.integers(0, len(papers), (args.boot, len(papers))) if papers else None
    for variant in ["orig", "strip"]:
        for be in ["crossref", "s2", "union"]:
            ref = cr[(cr["style"] == "IEEEtran_doi") & (cr.variant == variant)]
            if ref.empty:
                continue
            for style in ["IEEEtran", "elsarticle-num", "bib-title"]:
                v = "orig" if style == "bib-title" else variant
                g = cr[(cr["style"] == style) & (cr.variant == v)]
                if g.empty:
                    continue
                col = f"flag_{be}"
                g, ref_ = g[g[col].notna()], ref[ref[col].notna()]
                a = g.groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
                r0 = ref_.groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
                fa, f0 = a["sum"].sum() / a["count"].sum(), r0["sum"].sum() / r0["count"].sum()
                ratios = []
                for idx in boots:
                    x = a["sum"].values[idx].sum() / max(a["count"].values[idx].sum(), 1)
                    y = r0["sum"].values[idx].sum() / max(r0["count"].values[idx].sum(), 1)
                    ratios.append(x / y if y > 0 else np.inf)
                crit.append(dict(variant=variant, backend=be, style=style, fp_style=fa, fp_doi_style=f0,
                                 ratio=fa / f0 if f0 > 0 else float("inf"),
                                 ratio_ci=[float(np.quantile(ratios, 0.025)), float(np.quantile(ratios, 0.975))],
                                 n_refs=int(a["count"].sum()), n_papers=len(papers)))
    out = {"seed": args.seed, "boot": args.boot, "threshold": T, "n_rendered": int(len(rr)),
           "n_unique_strings": int(len(uniq)), "query_errors": {"crossref": int(uniq.cr_err.sum()),
                                                               "s2": int(uniq.s2_err.sum())},
           "render_missing": {f"{st}/{v}": dict(k=int(g.render_missing.sum()), n=int(len(g)),
                                                 n_papers=int(g[g.render_missing == 1].arxiv_id.nunique()))
                              for (st, v), g in rr.groupby(["style", "variant"])},
           "cpb0_ratio_vs_doi_style": crit}
    (ROOT / "results" / "p0_screen_fp.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    pd.set_option("display.width", 220)
    print(fp[(fp.subset == "certified-real")].round(4).to_string())
    print(json.dumps(crit, indent=1, default=float)[:3000])


TIERS = ["J", "C", "P", "B", "S", "W"]


def ratio_boot(a_df, b_df, col, papers, seed, B):
    """Ratio of pooled flag rates a/b with a paper-level bootstrap over the common paper list."""
    a = a_df.groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
    b = b_df.groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
    fa = a["sum"].sum() / max(a["count"].sum(), 1)
    fb = b["sum"].sum() / max(b["count"].sum(), 1)
    rng = np.random.default_rng(seed)
    rs = []
    for idx in rng.integers(0, len(papers), (B, len(papers))):
        x = a["sum"].values[idx].sum() / max(a["count"].values[idx].sum(), 1)
        y = b["sum"].values[idx].sum() / max(b["count"].values[idx].sum(), 1)
        rs.append(x / y if y > 0 else np.inf)
    return dict(fp_a=fa, k_a=int(a["sum"].sum()), n_a=int(a["count"].sum()), fp_b=fb, k_b=int(b["sum"].sum()),
                n_b=int(b["count"].sum()), ratio=fa / fb if fb > 0 else float("inf"),
                ratio_ci=[float(np.quantile(rs, 0.025)), float(np.quantile(rs, 0.975))], n_papers=len(papers))


AX_TITLES = {}  # arXiv id -> title: stored answers first, then live batches of 40 (one request per batch, not per id)
AX_NO_LIVE = False  # interim: an id without a stored answer is not looked up (id route fails, counted)


def screen_stage_a(s):
    """P1 stage A: identifier route + Crossref bibliographic search (the Crossref-only screen)."""
    id_ok = 0
    m = rm.DOI_RE.search(s or "")
    if m:
        doi = rm.clean_doi(m.group(1))
        be, titles = rm.resolve_doi(doi) if doi else (None, None)
        if titles and max(rm.contained_sim(t, s) for t in titles) >= T:
            id_ok = 1
    aid = rm.arxiv_from_text(s or "")
    if not id_ok and aid:
        t = AX_TITLES.get(aid) if aid in AX_TITLES or AX_NO_LIVE else rm.arxiv_ids([aid]).get(aid)
        if t and rm.contained_sim(t, s) >= T:
            id_ok = 1
    cr = rm.crossref_search(s) if s else []
    cr_s, _ = rm.best_sim(cr, refstring=s)
    return {"id": id_ok, "cr_sim": cr_s if cr is not None else np.nan, "cr_err": int(cr is None)}


def screen_stage_b(s, q, s2_live, dblp_only=False):
    """P1 stage B, only for strings stage A did not resolve: DBLP (offline) -> S2 -> arXiv title search, first hit
    stops (cascade of PREREG_AMENDMENT_3; OpenAlex is not part of the screen: keyless budget).
    dblp_only (interim): DBLP and nothing else."""
    out = {"dblp_sim": np.nan, "s2_sim": np.nan, "s2_err": 0, "ax_sim": np.nan, "ax_err": 0}
    if not q:
        return out
    d = rm.dblp_search(q)
    d = [] if d == "not-cached" else d
    out["dblp_sim"] = max(rm.best_sim(d, title=q)[0], rm.best_sim(d, refstring=s)[0])
    if out["dblp_sim"] >= T or dblp_only:
        return out
    s2 = rm.s2_match(q, cache_only=not s2_live)
    if isinstance(s2, list):
        out["s2_sim"] = max(rm.best_sim(s2, title=q)[0], rm.best_sim(s2, refstring=s)[0])
        if out["s2_sim"] >= T:
            return out
    else:  # None = 429 retries exhausted; "not-cached" = S2 not asked (cache-only run)
        out["s2_err"] = 1
    ax = rm.arxiv_title_search(q)
    out["ax_err"] = int(ax is None)
    out["ax_sim"] = max(rm.best_sim(ax, title=q)[0], rm.best_sim(ax, refstring=s)[0])
    return out


def _pmap(fn, items, workers, label):
    t0, done = time.time(), [0]

    def job(x):
        try:
            res = fn(x)
        except Exception as e:  # never kill the run; counted as a failed query
            print(f"  ! {label} error: {e.__class__.__name__}: {e}", flush=True)
            res = None
        done[0] += 1
        if done[0] % 500 == 0:
            print(f"  {label} {done[0]}/{len(items)} ({time.time() - t0:.0f}s)", flush=True)
        return res

    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(job, items))


def main_p1(args):
    """P1 (PREREG §6.2): 100 render papers x styles x {orig, strip} x parsers {grobid (primary), anystyle}.
    Two screens: Crossref-only (identifier route + Crossref) and the full cascade (+DBLP offline, S2, arXiv)."""
    import dblp_offline
    from p1_backend_table import first_hit_stage
    der = DERIVED / "interim" if args.interim else DERIVED
    res = ROOT / "results" / "interim" if args.interim else ROOT / "results"
    res.mkdir(parents=True, exist_ok=True)
    rr = pd.read_csv(DERIVED / "render_p1" / "rendered_refs.csv",
                     dtype={"arxiv_id": str, "key": str, "refstr": str}, low_memory=False)
    rr = rr.fillna({"refstr": "", "title_grobid": "", "title_anystyle": ""})
    gt = pd.read_csv(der / "p1_groundtruth_refs_full.csv", dtype={"arxiv_id": str, "key": str}, low_memory=False)
    meta = gt.drop_duplicates(["arxiv_id", "key"]).set_index(["arxiv_id", "key"])[["tier", "def1_status"]]
    rr = rr.join(meta, on=["arxiv_id", "key"])
    raw = rr[rr["style"] == "IEEEtran_doi_raw"]  # exploratory: only how many refs the unescaped patch loses
    rr = rr[rr["style"] != "IEEEtran_doi_raw"]
    if args.limit:
        rr = rr.head(args.limit)
    long = pd.concat([rr.assign(parser=p, ptitle=rr[f"title_{p}"]) for p in ("grobid", "anystyle")],
                     ignore_index=True)
    strings = [x for x in long.refstr.drop_duplicates() if x.strip()]
    print(f"rendered refs {len(rr)} x 2 parsers; unique strings {len(strings)}", flush=True)
    global AX_NO_LIVE
    aids = sorted({rm.arxiv_from_text(x) for x in strings} - {"", None})
    stored = rm.arxiv_titles_from_cache()
    AX_TITLES.update({i: stored[i] for i in aids if i in stored})
    n_stored = len(AX_TITLES)
    AX_NO_LIVE = rm.NO_ARXIV = args.interim  # interim: no arXiv request at all (the API answered 429 on 20-10)
    if not args.interim:  # ids absent from the batch answers fall back to a single lookup
        AX_TITLES.update(rm.arxiv_ids([i for i in aids if i not in AX_TITLES]))
    n_ax_missing = len([i for i in aids if i not in AX_TITLES])
    print(f"arXiv ids in strings: {len(aids)}; from stored answers {n_stored}; without a title {n_ax_missing}",
          flush=True)
    a = dict(zip(strings, _pmap(screen_stage_a, strings, args.workers, "stage A (id+Crossref)")))
    a_err = {"id": 0, "cr_sim": np.nan, "cr_err": 1}
    a_empty = {"id": 0, "cr_sim": np.nan, "cr_err": 0}
    long = pd.concat([long, pd.DataFrame([(a.get(x) or a_err) if x.strip() else a_empty for x in long.refstr])],
                     axis=1)
    long["q"] = [t if t and len(rm.norm(t)) >= 10 else s[:300] for t, s in zip(long.ptitle, long.refstr)]
    todo = long[(long.id == 0) & ~(long.cr_sim >= T) & (long.refstr.str.strip() != "")]
    uq = todo[["refstr", "q"]].drop_duplicates().reset_index(drop=True)
    print(f"stage B: {len(uq)} unique (string, query) not resolved by id/Crossref", flush=True)
    dblp_offline.match(list(uq.q.unique()))
    bres = _pmap(lambda i: screen_stage_b(uq.refstr[i], uq.q[i], args.s2_live, dblp_only=args.interim),
                 range(len(uq)), args.workers, "stage B (DBLP)" if args.interim else "stage B (DBLP/S2/arXiv)")
    empty_b = {"dblp_sim": np.nan, "s2_sim": np.nan, "s2_err": 1, "ax_sim": np.nan, "ax_err": 1}
    uq = pd.concat([uq, pd.DataFrame([r or empty_b for r in bres])], axis=1)
    long = long.merge(uq, on=["refstr", "q"], how="left")
    for c in ("s2_err", "ax_err"):
        long[c] = long[c].fillna(0)
    long["render_missing"] = (long.refstr.str.strip() == "").astype(int)
    long["flag_idonly"] = (long.id == 0).astype(float)
    long["flag_crossref"] = np.where(long.cr_sim.isna() & (long.id == 0), np.nan, ((long.id == 0) & (long.cr_sim < T)))
    long["flag_s2"] = np.nan  # S2 is asked only inside the cascade (stage B); no S2-only screen in P1
    # Crossref-only + DBLP offline: stage A, then the DBLP step of stage B
    long["flag_dblp"] = np.where(long.flag_crossref.isna(), np.nan,
                                 ((long.flag_crossref == 1) & ~(long.dblp_sim >= T)).astype(float))
    resolved_any = ((long.id == 1) | (long.cr_sim >= T) | (long.dblp_sim >= T) | (long.s2_sim >= T)
                    | (long.ax_sim >= T))
    # union = full cascade: a reference whose deciding queries failed is rate-limited (NaN), not flagged (PREREG §4)
    failed = (long.cr_err == 1) | (long.s2_err == 1) | (long.ax_err == 1)
    long["flag_union"] = np.where(~resolved_any & failed, np.nan, (~resolved_any).astype(float))
    if args.interim:
        long["flag_union"] = np.nan  # no S2 / arXiv title search in the interim screen
    for c in ["flag_idonly", "flag_crossref", "flag_dblp", "flag_s2", "flag_union"]:
        long[c] = long[c].astype(float)
        long.loc[long.render_missing == 1, c] = np.nan
    long["source"] = "render"
    # bib-title source: the title-only screen (def 1) on the authored .bib title, from route (a)
    b = gt[gt.arxiv_id.isin(set(rr.arxiv_id))].copy()
    b = b.merge(rr[["arxiv_id", "key"]].drop_duplicates(), on=["arxiv_id", "key"])
    b["style"], b["variant"], b["parser"], b["source"] = "bib-title", "orig", "none", "bib-title"
    b = _bib_flags(b, first_hit_stage)
    # (b) hand-checked references: the 200-ref manual sample is drawn from 2019-21 papers, none of which is among
    # the 100 (2024-26) render papers -> substitute: bib-title screen on the refs judged "exists" (labelled)
    man = pd.read_csv(ROOT / "results" / "p1_manual_sample.csv", dtype=str)
    man = man[man.exists == "exists"][["paper_id", "key"]].rename(columns={"paper_id": "arxiv_id"})
    n_man_in_render = int(man.merge(rr[["arxiv_id", "key"]].drop_duplicates()).shape[0])
    bm = _bib_flags(gt.merge(man, on=["arxiv_id", "key"]), first_hit_stage)
    bm["style"], bm["variant"], bm["parser"], bm["source"] = "bib-title", "orig", "none", "bib-title-manual"
    bm["label"] = "manual-exists"
    b = pd.concat([b, bm], ignore_index=True)
    if args.interim:
        b["flag_union"] = np.nan
    cols = ["arxiv_id", "key", "style", "variant", "parser", "source", "label", "tier", "flag_idonly",
            "flag_crossref", "flag_dblp", "flag_s2", "flag_union"]
    allr = pd.concat([long[cols], b[cols]], ignore_index=True)
    (der / "screen_p1").mkdir(parents=True, exist_ok=True)
    long.to_csv(der / "screen_p1" / "screen_refs.csv", index=False)

    rows = []
    subsets = [("certified-real", allr.label == "certified-real"), ("manual-exists", allr.label == "manual-exists"),
               ("all refs", allr.label.notna() & (allr.source != "bib-title-manual"))]
    for subset, mask in subsets:
        for keys_, g in allr[mask].groupby(["source", "style", "variant", "parser"]):
            for tier in ["all", "A"] + TIERS:
                if tier == "all":
                    gt_ = g
                elif tier == "A":
                    gt_ = g[g.tier.isin(["J", "C", "P"])]
                else:
                    gt_ = g[g.tier == tier]
                for be in ["idonly", "crossref", "dblp", "s2", "union"]:
                    col = f"flag_{be}"
                    gg = gt_[gt_[col].notna()]
                    if gg.empty:
                        continue
                    n, k = len(gg), int(gg[col].sum())
                    lo, hi = boot_ci(gg, col, args.seed, args.boot)
                    rows.append(dict(subset=subset, source=keys_[0], style=keys_[1], variant=keys_[2],
                                     parser=keys_[3], tier=tier, backend=be, n_refs=n,
                                     n_papers=gg.arxiv_id.nunique(), k_flagged=k, fp=k / n, ci_lo=lo, ci_hi=hi,
                                     seed=args.seed, boot=args.boot))
    fp = pd.DataFrame(rows)
    if args.interim:
        fp.insert(0, "interim", True)
    fp.to_csv(res / "p1_screen_fp.csv", index=False, float_format="%.5f")
    cr = allr[allr.label == "certified-real"]
    papers = sorted(cr.arxiv_id.unique())

    def sel(style, variant, parser):
        g = cr[(cr["style"] == style) & (cr.variant == variant) & (cr.parser == parser)]
        return g[g.flag_union.notna()]

    if args.interim:
        h3 = {"status": "pending: the full-cascade screen needs S2 (final run)"}
    else:
        h3 = ratio_boot(sel("IEEEtran", "strip", "grobid"), sel("IEEEtran_doi", "orig", "grobid"), "flag_union",
                        papers, args.seed, args.boot)
        h3.update(PASS=bool(h3["ratio"] >= 2), strong=bool(h3["ratio_ci"][0] > 1),
                  spec="FP(IEEEtran v1.14, strip) / FP(IEEEtran-DOI, orig); certified-real; full cascade; GROBID titles")

    def sel_be(style, variant, parser, col):
        g = cr[(cr["style"] == style) & (cr.variant == variant) & (cr.parser == parser)]
        return g[g[col].notna()]

    h3_cr = ratio_boot(sel_be("IEEEtran", "strip", "grobid", "flag_crossref"),
                       sel_be("IEEEtran_doi", "orig", "grobid", "flag_crossref"), "flag_crossref", papers, args.seed,
                       args.boot)
    h3_cr.update(PASS=bool(h3_cr["ratio"] >= 2), strong=bool(h3_cr["ratio_ci"][0] > 1),
                 spec="same as H3 but Crossref-only screen (secondary)")
    h3_db = ratio_boot(sel_be("IEEEtran", "strip", "grobid", "flag_dblp"),
                       sel_be("IEEEtran_doi", "orig", "grobid", "flag_dblp"), "flag_dblp", papers, args.seed, args.boot)
    h3_db.update(PASS=bool(h3_db["ratio"] >= 2), strong=bool(h3_db["ratio_ci"][0] > 1),
                 spec="same as H3 but Crossref-only + DBLP offline screen (secondary, not preregistered)")
    h4 = {be: h4_test(gt, man, be, args.seed, args.boot)
          for be in (["crossref", "dblp"] + ([] if args.interim else ["union"]))}
    others = []
    for style, variant in [("IEEEtran", "orig"), ("elsarticle-num", "orig"), ("elsarticle-num", "strip"),
                           ("IEEEtran_doi", "strip"), ("acmart", "orig"), ("acmart", "strip")]:
        for parser in ("grobid", "anystyle"):
            fc = "flag_crossref" if args.interim else "flag_union"
            r_ = ratio_boot(sel_be(style, variant, parser, fc), sel_be("IEEEtran_doi", "orig", parser, fc), fc,
                            papers, args.seed, args.boot)
            r_["screen"] = fc[5:]
            others.append(dict(r_, style=style, variant=variant, parser=parser, label="exploratory"))
    lost = {}
    for (st, v), g in pd.concat([rr, raw]).groupby(["style", "variant"]):
        miss = g.refstr.fillna("").str.strip() == ""
        lost[f"{st}/{v}"] = dict(k=int(miss.sum()), n=int(len(g)), n_papers=int(g[miss].arxiv_id.nunique()))
    out = {"seed": args.seed, "boot": args.boot, "threshold": T, "n_render_papers": int(rr.arxiv_id.nunique()),
           "n_rendered_refs": int(len(rr)), "n_unique_strings": int(len(strings)),
           "n_stage_b_queries": int(len(uq)), "s2_live": bool(args.s2_live),
           "arxiv_ids_in_strings": len(aids), "arxiv_ids_without_title": n_ax_missing,
           "query_errors": {"crossref": int(sum(1 for v in a.values() if v is None or v["cr_err"])),
                            "s2": int(uq.s2_err.sum()), "arxiv": int(uq.ax_err.sum())},
           "manual_exists_in_render_papers": n_man_in_render,
           "manual_note": "manual sample (2019-21 papers) does not overlap the 2024-26 render papers; "
                          "manual-exists rows are the bib-title screen (substitute, labelled)",
           "render_missing": lost, "H3": h3, "H3_crossref_only": h3_cr, "H3_plus_dblp": h3_db, "H4": h4,
           "ratios_vs_doi_style_exploratory": others}
    if args.interim:
        out.update(interim=True, s2_pending=int((gt.s2_pending == 1).sum()) if "s2_pending" in gt else None,
                   interim_note="INTERIM: screens Crossref-only and Crossref-only + DBLP offline; no S2, no arXiv "
                                "title search; H3 (full cascade) pending")
    (res / "p1_screen_fp.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    print(json.dumps({"H3": h3, "H3_crossref_only": h3_cr, "H3_plus_dblp": h3_db, "H4": h4, "render_missing": lost},
                     indent=1, default=float))


def _bib_flags(b, first_hit_stage):
    """bib-title source (route (a), def 1): full cascade = final def-1 state; Crossref-only = resolved by Crossref."""
    b = b.copy()
    b["flag_union"] = np.where(b.def1_status == "unresolved", 1.0, np.where(b.def1_status == "resolved", 0.0, np.nan))
    first = b.backends_hit.map(first_hit_stage)
    b["flag_crossref"] = np.where(b.def1_status == "resolved", (first != 0).astype(float), b.flag_union)
    b["flag_dblp"] = np.where(b.def1_status == "resolved", (first > 2).astype(float), b.flag_union)  # 2 = dblp
    b["flag_idonly"], b["flag_s2"] = np.nan, np.nan
    return b


def h4_test(gt, man, be, seed, B):
    """H4 (PREREG §5): title-only screen (def 1, bib title) on the 2019-21 corpus. FP_certified = flagged share of
    certified-real refs; FP_manual = sum_t w_t FP_manual,t over tiers, w_t = corpus share of tier t among refs with
    neither DOI nor arXiv id (the frame the manual sample was drawn from). PASS if the paper-bootstrap 95 % CI of
    FP_manual - FP_certified lies above 0. In a bootstrap draw, a tier without manual refs is dropped and the
    weights renormalised."""
    from p1_backend_table import first_hit_stage
    g = gt[gt.period == "2019-21"]
    col = f"flag_{be}"
    cert = _bib_flags(g[g.certified_real == 1], first_hit_stage)
    cert = cert[cert[col].notna()]
    mm = _bib_flags(g.merge(man, on=["arxiv_id", "key"]), first_hit_stage)
    mm = mm[mm[col].notna()]
    frame = g[(g.has_doi == 0) & (g.has_arxiv == 0) & g.def1_status.isin(["resolved", "unresolved"])]
    w = frame.tier.value_counts(normalize=True)
    tiers = sorted(mm.tier.unique())

    def stat(c_sum, c_n, m_sum, m_n):
        fc = c_sum / c_n if c_n else np.nan
        ws = {t: w.get(t, 0.0) for t in tiers if m_n.get(t, 0) > 0}
        tot = sum(ws.values())
        fm = sum(ws[t] / tot * m_sum[t] / m_n[t] for t in ws) if tot else np.nan
        return fm, fc

    fm, fc = stat(cert[col].sum(), len(cert), mm.groupby("tier")[col].sum().to_dict(),
                  mm.groupby("tier")[col].count().to_dict())
    papers = sorted(set(cert.arxiv_id) | set(mm.arxiv_id))
    pc = cert.groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
    pm = {t: mm[mm.tier == t].groupby("arxiv_id")[col].agg(["sum", "count"]).reindex(papers).fillna(0)
          for t in tiers}
    rng = np.random.default_rng(seed)
    diffs = []
    for idx in rng.integers(0, len(papers), (B, len(papers))):
        a, c = stat(pc["sum"].values[idx].sum(), pc["count"].values[idx].sum(),
                    {t: pm[t]["sum"].values[idx].sum() for t in tiers},
                    {t: pm[t]["count"].values[idx].sum() for t in tiers})
        diffs.append(a - c)
    lo, hi = np.nanquantile(diffs, [0.025, 0.975])
    return dict(screen=be, fp_manual_weighted=fm, fp_certified=fc, diff=fm - fc, diff_ci=[float(lo), float(hi)],
                n_certified=int(len(cert)), k_certified=int(cert[col].sum()),
                n_manual=int(len(mm)), k_manual=int(mm[col].sum()),
                manual_by_tier={t: [int(mm[mm.tier == t][col].sum()), int((mm.tier == t).sum())] for t in tiers},
                weights={t: round(float(w.get(t, 0.0)), 4) for t in tiers}, n_papers=len(papers),
                PASS=bool(lo > 0), seed=seed, boot=B)


if __name__ == "__main__":
    main()

