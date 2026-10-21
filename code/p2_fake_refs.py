#!/usr/bin/env python3
"""Topic 43 / P2 / T10b: recall of title screens on fabricated references, per cumulative backend
(PREREG_AMENDMENT_4 (g)).

Labelled items:
  gen_a     fabricated title (generated; prompt + candidates in code/fake_refs/); used only if the best title
            similarity is < 0.8 on every backend (Crossref, arXiv ti: forced, DBLP offline, OpenAlex, S2) -> 100 drawn
  gen_b     real title + swapped authors: a 2019-21 reference resolved under def 2 (tier J/C/P), its authors replaced
            by those of another such reference with a different first surname
  gen_c     real title + wrong venue/year: venue replaced by another reference's venue, year drawn in 2000-2018
  badalova  Badalova & Mayr, Zenodo 10.5281/zenodo.21457492 (33 problematic, 71 verified)
  gptzero   GPTZero NeurIPS 2025 table (100 hallucinated citations)
Titles/authors of the free-text sets (badalova, gptzero) come from anystyle (WSL).
Screens = the cumulative columns of Amendment 3: crossref, +arxiv, +dblp, +openalex, +s2. arXiv counts only where it
applies in the cascade (arXiv id in the entry or tier P; Amendment 1). def 1 flags an item when no backend of the
screen reaches title similarity >= 0.9; def 2 also flags it when no such backend's record has the first author
surname. Items whose screen had a failed (rate-limited) backend and no hit are excluded from that screen's
denominator and counted. Recall = flagged / evaluated among fabricated/problematic items; for badalova's verified
items the same share is an FP.
Stages: build -> query (network; resumable via the API cache) -> select -> recall
Outputs: $THS_DATASETS/_derived/43/fake/{items,items_queried}.csv, results/p2_fake_items.csv (used items),
         results/p2_recall.csv, results/p2_recall.json
Usage: python p2_fake_refs.py build|query|select|recall --seed 42 [--workers 3]
"""
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dblp_offline  # noqa: E402
import ground_truth_p1 as gt1  # noqa: E402
import refmatch as rm  # noqa: E402
from ground_truth import DATA, ROOT  # noqa: E402

HERE = Path(__file__).resolve().parent
DER = DATA / "_derived" / "43" / "fake"
SCREENS = ["crossref", "arxiv", "dblp", "openalex", "s2"]  # cumulative, cascade order
EXIST_SIM = 0.8  # non-existence check for gen_a (Amendment 4 (g))


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def anystyle(strings, workdir):
    """title + 'Family and Family' author string per citation string (anystyle, WSL)."""
    workdir.mkdir(parents=True, exist_ok=True)
    f = workdir / "anystyle_in.txt"
    f.write_text("\n".join((s or "-").replace("\n", " ") for s in strings) + "\n", encoding="utf-8")
    wp = "/mnt/" + str(f.resolve()).replace(":", "").replace("\\", "/")
    wp = wp[:5] + wp[5].lower() + wp[6:]
    p = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "--", "anystyle", "-f", "json", "parse", wp],
                       capture_output=True, timeout=1800)
    data = json.loads(p.stdout.decode("utf-8", "replace"))
    out = []
    for d in data:
        t = d.get("title") or [""]
        au = [a.get("family") or a.get("literal") or "" for a in d.get("author", []) if isinstance(a, dict)]
        out.append({"title": (t[0] if isinstance(t, list) else str(t)).strip(" .,"),
                    "author": " and ".join(a for a in au if a)})
    out += [{"title": "", "author": ""} for _ in range(len(strings) - len(out))]
    return out[:len(strings)]


def build(args):
    rng = np.random.default_rng(args.seed)
    rows = []
    a = pd.read_csv(HERE / "fake_refs" / "family_a_candidates.csv", dtype=str, keep_default_na=False)
    for r in a.itertuples():
        rows.append(dict(item_id=r.cand_id, set="gen_a", label="fabricated", title=r.title, author=r.authors,
                         venue=r.venue, year=r.year, tier=r.tier, has_arxiv=int(bool(r.arxiv_id)), raw=""))
    full = pd.read_csv(DATA / "_derived" / "43" / "p1_groundtruth_refs_full.csv", dtype=str, keep_default_na=False,
                       low_memory=False)
    pool = full[(full.period == "2019-21") & (full.def2_status == "resolved") & full.tier.isin(["J", "C", "P"])
                & (full.title.str.len() >= 20) & (full.author != "")].drop_duplicates("title")
    pool = pool.sort_values(["arxiv_id", "key"]).reset_index(drop=True)
    pool["venue"] = np.where(pool.f_journal != "", pool.f_journal, pool.f_booktitle)
    idx = rng.permutation(len(pool))
    rec_b, rec_c, donors = idx[:100], idx[100:200], idx[200:]
    sur = [set(rm.bib_surnames(x)) for x in pool.author]
    di = 0
    for j, i in enumerate(rec_b, 1):
        while sur[donors[di % len(donors)]] & sur[i] or not sur[donors[di % len(donors)]]:
            di += 1
        d = donors[di % len(donors)]
        di += 1
        r = pool.iloc[i]
        rows.append(dict(item_id=f"B{j:03d}", set="gen_b", label="fabricated", title=r.title,
                         author=pool.author.iloc[d], venue=r.venue, year="", tier=r.tier, has_arxiv=int(r.has_arxiv),
                         raw=f"source {r.arxiv_id}/{r.key}; authors from {pool.arxiv_id.iloc[d]}/{pool.key.iloc[d]}"))
    vpool = [v for v in pool.venue.unique() if v]
    for j, i in enumerate(rec_c, 1):
        r = pool.iloc[i]
        v = r.venue
        while v == r.venue:
            v = vpool[rng.integers(len(vpool))]
        rows.append(dict(item_id=f"C{j:03d}", set="gen_c", label="fabricated", title=r.title, author=r.author,
                         venue=v, year=str(int(rng.integers(2000, 2019))), tier=r.tier, has_arxiv=int(r.has_arxiv),
                         raw=f"source {r.arxiv_id}/{r.key}; true venue {r.venue}"))
    bm = pd.read_csv(DATA / "badalova_mayr_21457492" / "manual_reference_verification_dataset.csv", dtype=str,
                     encoding="cp850", keep_default_na=False)
    gz = pd.read_csv(DATA / "gptzero_neurips2025" / "table.csv", dtype=str, keep_default_na=False)
    ext = [("badalova", f"BM_{r.document_id}_{r.reference_number}", r.manual_label, r.reference)
           for r in bm.itertuples()]
    ext += [("gptzero", f"GZ{i + 1:03d}", "hallucinated", s) for i, s in
            enumerate(gz["Example of Verified Hallucination"])]
    parsed = anystyle([e[3] for e in ext], DER / "anystyle")
    for (st, iid, lab, raw), p in zip(ext, parsed):
        rows.append(dict(item_id=iid, set=st, label=lab, title=p["title"], author=p["author"], venue="", year="",
                         tier="", has_arxiv=int(bool(re.search(r"arxiv", raw, re.I))), raw=raw))
    DER.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    out.to_csv(DER / "items.csv", index=False)
    print(out.groupby(["set", "label"]).size().to_string())
    print("empty titles:", out[out.title.str.len() < 10].groupby("set").size().to_dict())


def query_one(r):
    t = r["title"]
    res = dict(item_id=r["item_id"])
    if len(rm.norm(t)) < 10:
        res["status"] = "no-title"
        return res
    fns = {"crossref": rm.crossref_search, "arxiv": rm.arxiv_title_search, "dblp": rm.dblp_search,
           "openalex": lambda q: rm.openalex_search(q, force=True), "s2": lambda q: rm.s2_match(q, tries=2)}
    bs = rm.bib_surnames(r["author"])
    for b, fn in fns.items():
        out = fn(t)
        if b == "openalex" and isinstance(out, str):  # keyless pool refused: not asked (as oa_skipped in P1)
            res["skip_openalex"] = 1
            continue
        if out is None or isinstance(out, str):
            res[f"fail_{b}"] = 1
            continue
        s, i = rm.best_sim(out, title=t)
        res[f"sim_{b}"], res[f"id_{b}"] = round(s, 4), i
        if s >= rm.SIM_THRESHOLD and bs:
            ok, names = gt1._authors(b, i, t, s2_live=True)
            res[f"auth_{b}"] = (None if not names else int(bool(rm.first_author_match(bs, names)))) if ok else None
    res["status"] = "ok"
    return res


def query(args):
    items = pd.read_csv(DER / "items.csv", dtype=str, keep_default_na=False)
    titles = [t for t in items.title if len(rm.norm(t)) >= 10]
    print(dblp_offline.match(titles), flush=True)
    recs = items.to_dict("records")
    done = [0]

    def run(r):
        try:
            out = query_one(r)
        except Exception as e:  # one bad item never kills the run
            out = dict(item_id=r["item_id"], status=f"error {e.__class__.__name__}")
        done[0] += 1
        if done[0] % 50 == 0:
            print(f"  {done[0]}/{len(recs)}", flush=True)
        return out

    with ThreadPoolExecutor(args.workers) as ex:
        res = list(ex.map(run, recs))
    q = items.merge(pd.DataFrame(res), on="item_id", how="left")
    q.to_csv(DER / "items_queried.csv", index=False)
    fails = {b: int(q.get(f"fail_{b}", pd.Series(dtype=float)).fillna(0).astype(float).sum()) for b in SCREENS}
    print("failed calls per backend:", fails, "| status:", q.status.value_counts().to_dict())


def select(args):
    q = pd.read_csv(DER / "items_queried.csv", dtype=str, keep_default_na=False)
    a = q[q.set == "gen_a"].copy()
    sims = a[[f"sim_{b}" for b in SCREENS]].replace("", np.nan).astype(float)
    # OpenAlex keyless is refused after a few hundred calls; as in the P1 cascade (oa_skipped) a refused or failed
    # OpenAlex call means "not asked": the check then rests on Crossref, arXiv, DBLP and S2 (reported)
    fails = a[[f"fail_{b}" for b in SCREENS if f"fail_{b}" in a and b != "openalex"]].replace("", "0").astype(float).sum(axis=1)
    a["openalex_asked"] = a[["sim_openalex"]].replace("", np.nan).notna().values
    a["max_sim"] = sims.max(axis=1)
    a["check"] = np.where(a.max_sim >= EXIST_SIM, "excluded-similar",
                          np.where(fails > 0, "unverified", "passed"))
    print("gen_a check:", a.check.value_counts().to_dict())
    passed = a[a.check == "passed"]
    rng = np.random.default_rng(args.seed)
    if len(passed) >= 100:
        use_a = passed.iloc[np.sort(rng.choice(len(passed), 100, replace=False))]
    else:  # fill with unverified (labelled), never with excluded-similar
        unv = a[a.check == "unverified"]
        k = min(100 - len(passed), len(unv))
        use_a = pd.concat([passed, unv.iloc[np.sort(rng.choice(len(unv), k, replace=False))] if k else unv.head(0)])
    a[["item_id", "title", "max_sim", "check", "openalex_asked"]].to_csv(DER / "gen_a_check.csv", index=False)
    print("gen_a: OpenAlex answered for", int(a.openalex_asked.sum()), "of", len(a))
    used = pd.concat([use_a.drop(columns=["max_sim", "check", "openalex_asked"]), q[q.set != "gen_a"]])
    used = used.merge(a[["item_id", "check"]], on="item_id", how="left").fillna({"check": ""})
    used.to_csv(ROOT / "results" / "p2_fake_items.csv", index=False)
    print(used.groupby(["set", "label"]).size().to_string())


def flags(df, upto, definition):
    """1 flagged, 0 not, NaN excluded (failed backend and no hit) for screen = SCREENS[:upto+1]."""
    out = []
    for r in df.itertuples():
        if r.status != "ok":
            out.append(np.nan)
            continue
        hit = fail = False
        for b in SCREENS[:upto + 1]:
            if b == "arxiv" and not (str(r.has_arxiv) == "1" or r.tier == "P"):
                continue  # Amendment 1: arXiv ti: only where it applies
            s = getattr(r, f"sim_{b}")
            if b == "openalex" and s in ("", None):
                continue  # not asked (keyless refused), as oa_skipped in the P1 cascade
            if str(getattr(r, f"fail_{b}", "")) in ("1", "1.0"):
                fail = True
                continue
            if s not in ("", None) and float(s) >= rm.SIM_THRESHOLD:
                if definition == 1 or str(getattr(r, f"auth_{b}", "")) in ("1", "1.0"):
                    hit = True
        out.append(0.0 if hit else (np.nan if fail else 1.0))
    return np.array(out)


def recall(args):
    u = pd.read_csv(ROOT / "results" / "p2_fake_items.csv", dtype=str, keep_default_na=False)
    for b in SCREENS:
        for c in (f"sim_{b}", f"fail_{b}", f"auth_{b}"):
            if c not in u:
                u[c] = ""
    rows = []
    groups = [((s, lab), g) for (s, lab), g in u.groupby(["set", "label"])]
    for (st, lab), g in groups:
        for i, b in enumerate(SCREENS):
            for d in (1, 2):
                f = flags(g, i, d)
                n, k = int(np.isfinite(f).sum()), int(np.nansum(f))
                lo, hi = wilson(k, n)
                rows.append(dict(set=st, label=lab, screen="crossref" if i == 0 else f"+{b}", definition=d,
                                 n_items=len(g), n_evaluated=n, n_excluded=len(g) - n, k_flagged=k,
                                 share_flagged=k / n if n else np.nan, wilson_lo=lo, wilson_hi=hi,
                                 # excluded items are exactly the unresolved-so-far ones whose last backend failed,
                                 # i.e. would-be flags: bounds treat all of them as not flagged / flagged
                                 bound_lo=k / len(g) if len(g) else np.nan,
                                 bound_hi=(k + len(g) - n) / len(g) if len(g) else np.nan,
                                 measure="FP" if lab == "verified" else "recall", seed=args.seed, interim=False))
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "results" / "p2_recall.csv", index=False)
    meta = dict(interim=False, seed=args.seed, sim_threshold=rm.SIM_THRESHOLD, exist_check_sim=EXIST_SIM,
                items=u.groupby(["set", "label"]).size().rename("n").reset_index().to_dict("records"),
                gen_a_check=u[u.set == "gen_a"].check.value_counts().to_dict(),
                note="def 1 = title only; def 2 = title + first-author surname. gen_b (swapped authors) is "
                     "undetectable by def 1 by construction (Thm 3); gen_c (wrong venue/year) is undetectable by "
                     "both definitions, which check neither venue nor year.")
    (ROOT / "results" / "p2_recall.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    piv = out.pivot_table(index=["set", "label", "definition"], columns="screen", values="share_flagged")
    print(piv[["crossref", "+arxiv", "+dblp", "+openalex", "+s2"]].round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "query", "select", "recall"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    {"build": build, "query": query, "select": select, "recall": recall}[args.stage](args)


if __name__ == "__main__":
    main()
