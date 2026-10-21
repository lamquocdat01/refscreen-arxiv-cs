#!/usr/bin/env python3
"""Topic 43 / P1 / T08: false positives of a public screening tool (hallucinator-cli v0.2.4, AGPL-3.0) on the
100 render papers (PREREG §6.3 "Scope"; tool facts and install: env/TOOLS_P0.md).

For each render paper x style (orig variant; IEEEtran v1.14, IEEEtran-DOI with escaped DOIs, elsarticle-num), the
cited entries are compiled into a PDF with one body line before the bibliography. Without it the tool's reference-
section detection keeps only the last page (P0: 11 of 35 references). The tool then runs in WSL:
  hallucinator-cli check --no-color --num-workers 2 --disable-dbs DBLP --cache-path <sqlite> --json <out> main.pdf
(DBLP disabled: its online API is behind a bot wall; no Kaggle token -> arXiv online, rate-limited, as in TOOLS_P0).
Tool results are mapped to .bbl keys via `original_number`. Flag = status in {not_found, mismatch, author_mismatch,
retracted}. inconclusive and skipped are excluded from the FP denominator and counted.
Outputs: $THS_DATASETS/_derived/43/tools/hall_p1/<id>/<style>/ (pdf, json, report)
         results/p1_tool_hallucinator.csv (per style: FP on certified-real + all refs, paper bootstrap CI)
Usage: python run_hallucinator.py --seed 42 [--limit N] [--resume] [--styles IEEEtran,IEEEtran_doi,elsarticle-num]

P2 (PREREG_AMENDMENT_4 (d)): python run_hallucinator.py --phase p2 --seed 42 --resume
  30 of the 100 render papers (seed 42); styles "IEEEtran:strip" (primary), then "IEEEtran_doi:orig" on the same
  papers while the 6 h budget lasts; DBLP from the offline database (--dblp-offline, built from the Amendment 3 dump);
  other backends online and keyless. 100 fabricated-title references (results/p2_fake_items.csv, set gen_a) are
  compiled into 4 extra PDFs of 25 (IEEEtran) for recall, run after the primary style. A new PDF is not started once
  the budget is used up; the results are then labelled partial.
  Outputs: $THS_DATASETS/_derived/43/tools/hall_p2/..., results/p2_tool_hallucinator.csv,
           results/p2_tool_hallucinator_refs.csv

P2 reduced (LQD 21-10 evening, "giam mau, ly do thoi gian"; execution detail of Amendment 4 (d), scope not widened):
  python run_hallucinator.py --phase p2 --seed 42 --resume --keep-first 7 --add 8 --no-fake --pairs --budget-hours 5.34
  15 papers = the first 7 of the seed-42 list of 30 (the papers already started) + 8 drawn with seed 42 from the other
  23; both styles per paper, run pair by pair (strip, then IEEEtran-DOI) so that a budget stop leaves whole pairs;
  the 4 fabricated-reference PDFs are dropped (recall of the tool is not measured here). Budget = 6 h cumulative
  minus the 0.66 h already used. FP is reported on complete pairs only (subset "... (paired)").
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_strip as rs  # noqa: E402
from ground_truth import DERIVED, ROOT, SRC, parse_bibs  # noqa: E402
from screen_baseline import boot_ci  # noqa: E402

OUT = DERIVED / "tools" / "hall_p1"
CLI = "~/tools43/bin/hallucinator-cli"
FLAG = {"not_found", "mismatch", "author_mismatch", "retracted"}
BODY_SKELETON = rs.SKELETON.replace("\\begin{document}\n", "\\begin{document}\nThis page lists the references.\n\n")


def wsl_path(p):
    s = str(Path(p).resolve()).replace("\\", "/")
    return "/mnt/" + s[0].lower() + s[2:]


def run_tool(pdf, out_json, report, cache, timeout=3600, dblp_offline=""):
    dbs = f"--dblp-offline '{dblp_offline}' " if dblp_offline else "--disable-dbs DBLP "
    cmd = (f"DB_TIMEOUT=30 DB_TIMEOUT_SHORT=15 {CLI} check --no-color --num-workers 2 {dbs}"
           f"--cache-path '{wsl_path(cache)}' --json '{wsl_path(out_json)}' -o '{wsl_path(report)}' '{wsl_path(pdf)}'")
    t0 = time.time()
    try:
        p = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "--", "bash", "-lc", cmd], capture_output=True,
                           timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = -9
    return rc, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="max papers")
    ap.add_argument("--resume", action="store_true", help="skip paper x style whose tool JSON already exists")
    ap.add_argument("--styles", default="IEEEtran,IEEEtran_doi,elsarticle-num")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--phase", choices=["p1", "p2"], default="p1")
    ap.add_argument("--n-papers", type=int, default=30)
    ap.add_argument("--dblp-offline", default="/root/tools43/db/dblp.sqlite")
    ap.add_argument("--budget-hours", type=float, default=6.0)
    ap.add_argument("--keep-first", type=int, default=0, help="p2 reduced: keep the first K of the 30 papers")
    ap.add_argument("--add", type=int, default=0, help="p2 reduced: draw A more papers (seed) from the rest")
    ap.add_argument("--no-fake", action="store_true", help="p2: skip the fabricated-reference PDFs")
    ap.add_argument("--pairs", action="store_true", help="p2: run both styles paper by paper")
    args = ap.parse_args()
    if args.phase == "p2":
        return main_p2(args)

    gt = pd.read_csv(DERIVED / "p1_groundtruth_refs_full.csv", dtype={"arxiv_id": str, "key": str}, low_memory=False)
    papers = rs.select_render100(gt, args.seed)
    if args.limit:
        papers = papers[:args.limit]
    lab = gt.drop_duplicates(["arxiv_id", "key"]).set_index(["arxiv_id", "key"])[["label", "tier"]]
    doi_bst = rs.find_doi_bst()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "hallucinator_cache.sqlite"
    rows = []
    for i, pid in enumerate(papers, 1):
        ents_all = parse_bibs(sorted((SRC / pid.replace("/", "_")).rglob("*.bib")))
        keys = [k for k in gt[gt.arxiv_id == pid].key if str(k).lower() in ents_all]
        ents = [ents_all[str(k).lower()] for k in keys]
        for style in args.styles.split(","):
            d = OUT / pid.replace("/", "_") / style
            js = d / "tool.json"
            if not (args.resume and js.exists()):
                shutil.rmtree(d, ignore_errors=True)
                d.mkdir(parents=True)
                bst = style
                if style == "IEEEtran_doi":
                    shutil.copy2(doi_bst, d / doi_bst.name)
                    bst = doi_bst.stem
                rs.write_bib(ents, d / "refs.bib", strip=False, escape_doi=(style == "IEEEtran_doi"))
                sk = rs.SKELETON
                rs.SKELETON = BODY_SKELETON
                try:
                    rs.compile_dir(d, bst)
                finally:
                    rs.SKELETON = sk
                rc, sec = run_tool(d / "main.pdf", js, d / "report.txt", cache)
                (d / "runtime.txt").write_text(f"rc={rc} seconds={sec:.0f}\n", encoding="utf-8")
                print(f"[{i}/{len(papers)}] {pid} {style}: rc={rc} {sec:.0f}s", flush=True)
            order = rs.bbl_keys(d)
            try:
                res = json.loads(js.read_text(encoding="utf-8"))[0]["references"]
            except (OSError, ValueError, IndexError, KeyError):
                res = []
            got = {}
            for r in res:
                n = r.get("original_number")
                if isinstance(n, int) and 1 <= n <= len(order):
                    got[n] = r
            for n, key in enumerate(order, 1):
                r = got.get(n)
                st = "not-extracted" if r is None else ("inconclusive" if r.get("inconclusive") else
                                                        (r.get("effective_status") or r.get("status") or ""))
                m = lab.loc[(pid, key)] if (pid, key) in lab.index else None
                rows.append(dict(arxiv_id=pid, style=style, n=n, key=key, tool_status=st,
                                 label=None if m is None else m["label"], tier=None if m is None else m["tier"]))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "hallucinator_refs.csv", index=False)
    df["flag"] = np.where(df.tool_status.isin(FLAG), 1.0,
                          np.where(df.tool_status.isin(["verified"]), 0.0, np.nan))
    summ = []
    for (style, subset), g in [((s, "certified-real"), x[x.label == "certified-real"]) for s, x in df.groupby("style")] + \
                              [((s, "all refs"), x) for s, x in df.groupby("style")]:
        e = g[g.flag.notna()]
        lo, hi = boot_ci(e, "flag", args.seed, args.boot) if len(e) else (np.nan, np.nan)
        summ.append(dict(tool="hallucinator-cli 0.2.4", style=style, subset=subset, n_refs=len(g),
                         n_papers=g.arxiv_id.nunique(), n_not_extracted=int((g.tool_status == "not-extracted").sum()),
                         n_inconclusive=int((g.tool_status == "inconclusive").sum()),
                         n_skipped=int((g.tool_status == "skipped").sum()), n_evaluated=len(e),
                         k_flagged=int(e.flag.sum()), fp=e.flag.mean() if len(e) else np.nan, ci_lo=lo, ci_hi=hi,
                         seed=args.seed, boot=args.boot, arxiv_backend="online (no Kaggle snapshot)",
                         dblp="disabled"))
    pd.DataFrame(summ).to_csv(ROOT / "results" / "p1_tool_hallucinator.csv", index=False)
    print(pd.DataFrame(summ).to_string())


def flag_col(df):
    return np.where(df.tool_status.isin(FLAG), 1.0, np.where(df.tool_status.isin(["verified"]), 0.0, np.nan))


def summ_row(g, style, subset, seed, boot, extra, ci=True):
    e = g[g.flag.notna()]
    lo, hi = boot_ci(e, "flag", seed, boot) if (ci and len(e)) else (np.nan, np.nan)
    return dict(tool="hallucinator-cli 0.2.4", style=style, subset=subset, n_refs=len(g),
                n_papers=g.arxiv_id.nunique(), n_not_extracted=int((g.tool_status == "not-extracted").sum()),
                n_inconclusive=int((g.tool_status == "inconclusive").sum()),
                n_skipped=int((g.tool_status == "skipped").sum()), n_evaluated=len(e), k_flagged=int(e.flag.sum()),
                share_flagged=e.flag.mean() if len(e) else np.nan, ci_lo=lo, ci_hi=hi, seed=seed, boot=boot, **extra)


def main_p2(args):
    t_start = time.time()
    out = DERIVED / "tools" / "hall_p2"
    gt = pd.read_csv(DERIVED / "p1_groundtruth_refs_full.csv", dtype={"arxiv_id": str, "key": str}, low_memory=False)
    p100 = sorted(rs.select_render100(gt, args.seed))
    rng = np.random.default_rng(args.seed)
    papers = [p100[i] for i in np.sort(rng.choice(len(p100), args.n_papers, replace=False))]
    reduced = bool(args.keep_first)
    if reduced:
        rest = papers[args.keep_first:]
        rng2 = np.random.default_rng(args.seed)
        papers = papers[:args.keep_first] + [rest[i] for i in np.sort(rng2.choice(len(rest), args.add, replace=False))]
    if args.limit:
        papers = papers[:args.limit]
    lab = gt.drop_duplicates(["arxiv_id", "key"]).set_index(["arxiv_id", "key"])[["label", "tier"]]
    doi_bst = rs.find_doi_bst()
    out.mkdir(parents=True, exist_ok=True)
    if reduced:
        (out / "papers_reduced15.txt").write_text("\n".join(papers) + "\n", encoding="utf-8")
    else:
        (out / "papers.txt").write_text("\n".join(papers) + "\n", encoding="utf-8")
    cache = out / "hallucinator_cache.sqlite"
    fp_ = ROOT / "results" / "p2_fake_items.csv"
    fake = pd.read_csv(fp_, dtype=str, keep_default_na=False) if fp_.exists() else pd.DataFrame(columns=["set", "item_id"])
    fake = fake[fake.set == "gen_a"].sort_values("item_id").reset_index(drop=True)
    if not len(fake):
        print("no gen_a items (results/p2_fake_items.csv missing): recall PDFs skipped", flush=True)
    if args.no_fake:
        fake = fake.iloc[0:0]
    fake_ents = []
    for r in fake.itertuples():
        e = {"ID": r.item_id, "title": r.title, "author": r.author, "year": r.year}
        if r.tier == "J":
            e.update(ENTRYTYPE="article", journal=r.venue)
        elif r.tier == "C":
            e.update(ENTRYTYPE="inproceedings", booktitle=r.venue)
        else:
            e.update(ENTRYTYPE="misc", howpublished="arXiv preprint")
        fake_ents.append(e)
    if args.pairs:
        jobs = [(pid, st, v) for pid in papers for st, v in (("IEEEtran", "strip"), ("IEEEtran_doi", "orig"))]
    else:
        jobs = [(pid, "IEEEtran", "strip") for pid in papers]
    jobs += [(f"FAKE{c + 1}", "IEEEtran", "orig") for c in range((len(fake_ents) + 24) // 25)]
    if not args.pairs:
        jobs += [(pid, "IEEEtran_doi", "orig") for pid in papers]
    rows, skipped_jobs = [], []
    for j, (pid, style, var) in enumerate(jobs, 1):
        d = out / pid.replace("/", "_") / f"{style}_{var}"
        js = d / "tool.json"
        if not (args.resume and js.exists()):
            if time.time() - t_start > args.budget_hours * 3600:
                skipped_jobs.append(f"{pid}/{style}_{var}")
                continue
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
            if pid.startswith("FAKE"):
                c = int(pid[4:]) - 1
                ents = fake_ents[25 * c: 25 * (c + 1)]
            else:
                ents_all = parse_bibs(sorted((SRC / pid.replace("/", "_")).rglob("*.bib")))
                ents = [ents_all[str(k).lower()] for k in gt[gt.arxiv_id == pid].key if str(k).lower() in ents_all]
            bst = style
            if style == "IEEEtran_doi":
                shutil.copy2(doi_bst, d / doi_bst.name)
                bst = doi_bst.stem
            rs.write_bib(ents, d / "refs.bib", strip=(var == "strip"), escape_doi=(style == "IEEEtran_doi"))
            sk = rs.SKELETON
            rs.SKELETON = BODY_SKELETON
            try:
                rs.compile_dir(d, bst)
            finally:
                rs.SKELETON = sk
            rc, sec = run_tool(d / "main.pdf", js, d / "report.txt", cache, dblp_offline=args.dblp_offline)
            (d / "runtime.txt").write_text(f"rc={rc} seconds={sec:.0f}\n", encoding="utf-8")
            print(f"[{j}/{len(jobs)}] {pid} {style}_{var}: rc={rc} {sec:.0f}s "
                  f"(total {(time.time() - t_start) / 3600:.2f} h)", flush=True)
        order = rs.bbl_keys(d)
        try:
            res = json.loads(js.read_text(encoding="utf-8"))[0]["references"]
        except (OSError, ValueError, IndexError, KeyError):
            res = []
        got = {r.get("original_number"): r for r in res if isinstance(r.get("original_number"), int)}
        for n, key in enumerate(order, 1):
            r = got.get(n)
            st = "not-extracted" if r is None else ("inconclusive" if r.get("inconclusive") else
                                                    (r.get("effective_status") or r.get("status") or ""))
            if pid.startswith("FAKE"):
                labl, tier = "fabricated (gen_a)", ""
            else:
                m = lab.loc[(pid, key)] if (pid, key) in lab.index else None
                labl, tier = (None, None) if m is None else (m["label"], m["tier"])
            rows.append(dict(arxiv_id=pid, style=f"{style}_{var}", n=n, key=key, tool_status=st, label=labl,
                             tier=tier))
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "results" / "p2_tool_hallucinator_refs.csv", index=False)
    df["flag"] = flag_col(df)
    extra = dict(arxiv_backend="online (no Kaggle snapshot)", dblp="offline (dump 2026-10-19)", s2="online keyless",
                 partial=bool(skipped_jobs), skipped_jobs=len(skipped_jobs), interim=False,
                 hours_this_run=round((time.time() - t_start) / 3600, 2),
                 hours_cumulative=round(sum(float(t.read_text().split("seconds=")[1]) for t in
                                            out.rglob("runtime.txt")) / 3600, 2),
                 sample=("reduced: 15 pairs, giam mau, ly do thoi gian" if reduced else "30 papers"))
    real, fk = df[~df.arxiv_id.str.startswith("FAKE")], df[df.arxiv_id.str.startswith("FAKE")]
    if args.pairs:
        done = real.groupby("arxiv_id")["style"].nunique()
        real = real[real.arxiv_id.isin(done[done == 2].index)]
        extra["n_pairs"] = int((done == 2).sum())
    sfx = " (paired)" if args.pairs else ""
    summ = []
    for style, x in real.groupby("style"):
        summ.append(summ_row(x[x.label == "certified-real"], style, "certified-real" + sfx, args.seed, args.boot, extra))
        summ.append(summ_row(x, style, "all refs" + sfx, args.seed, args.boot, extra))
    if len(fk):
        summ.append(summ_row(fk, "IEEEtran_orig", "fabricated (gen_a)", args.seed, args.boot, extra, ci=False))
    summ = pd.DataFrame(summ)
    summ.to_csv(ROOT / "results" / "p2_tool_hallucinator.csv", index=False)
    print(summ.to_string())
    if skipped_jobs:
        print("PARTIAL: budget used up; jobs not run:", len(skipped_jobs), skipped_jobs[:5])


if __name__ == "__main__":
    main()
