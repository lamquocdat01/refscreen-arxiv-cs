#!/usr/bin/env python3
"""Topic 43 / P1 diagnostic (exploratory, NOT a primary analysis): why are tier J/C references unresolved after
round 1, and how does tier P split by identifier?

No network: every registry call is answered from the on-disk cache only (cache miss -> S2 "not-cached",
OpenAlex "skipped", Crossref/arXiv "failed"), so the round-1 states of ground_truth_p1.py are replayed exactly.
Steps
  1. replay round 1 (def 1) for all refs of tiers J, C, P in $THS_DATASETS/_derived/43/p1_refs_stage0.csv and
     check the counts against results/p1_groundtruth_round1_<set>.json;
  2. every unresolved J/C ref: best candidate per backend + automatic failure pattern (normalisation variants);
  3. 60-ref sample (seed 42; 15 per tier x set) with candidate titles for manual reading;
  4. tier P split: with arXiv id / DOI vs without.
Outputs: results/p1_diag_unresolved_jc60.csv, results/p1_diag_unresolved_patterns.csv, results/p1_diag.json
Usage: python diag_unresolved_p1.py --seed 42
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
import ground_truth_p1 as gt  # noqa: E402

_orig_get = rm.cached_get


def _cache_only_get(backend, url, params=None, tries=6, cache_only=False):
    st, p = _orig_get(backend, url, params, tries=tries, cache_only=True)
    if st == -3 and backend == "openalex":
        return -2, None  # round 1: OpenAlex refused -> skipped
    return st, p


rm.cached_get = _cache_only_get


def candidates(t, has_arxiv_rule):
    out = {"crossref": rm.crossref_search(t), "s2": rm.s2_match(t, cache_only=True)}
    if has_arxiv_rule:
        out["arxiv"] = rm.arxiv_title_search(t)
    out["openalex"] = rm.openalex_search(t, force=True)
    return {k: (v if isinstance(v, list) else None) for k, v in out.items()}


def variants(a, b):
    """Automatic failure patterns between a .bib title a and a registry title b (both raw)."""
    na, nb = rm.norm(a), rm.norm(b)
    if not na or not nb:
        return []
    pats = []
    if na.replace(" ", "") == nb.replace(" ", ""):
        pats.append("space/hyphen-only")
    if nb.startswith(na) or na.startswith(nb):
        pats.append("prefix (subtitle missing/extra)")
    elif na in nb or nb in na:
        pats.append("contained")
    ta, tb = set(na.split()), set(nb.split())
    if ta <= tb or tb <= ta:
        pats.append("token-subset")
    if re.search(r"[\\{}$^_]", a):
        pats.append("latex-residue-in-bib")
    if re.search(r"[^\x00-\x7f]", b) and not re.search(r"[^\x00-\x7f]", a):
        pats.append("non-ascii-in-registry")
    return pats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-per-cell", type=int, default=15)
    args = ap.parse_args()
    df = pd.read_csv(gt.DERIVED / "p1_refs_stage0.csv", low_memory=False, keep_default_na=False,
                     dtype={"arxiv_id": str, "key": str})
    df = df[df.tier.isin(["J", "C", "P"])].copy()
    recs = df.to_dict("records")
    for r in recs:
        r["has_arxiv"] = int(r["has_arxiv"] or 0)
        gt.resolve_ref(r, s2_live=False)
    d = pd.DataFrame(recs)
    d.to_csv(gt.DERIVED / "p1_diag_round1_replay_jcp.csv", index=False)

    # 1. replay check against the interim json
    check = {}
    for s in ["prellm", "pilot"]:
        js = json.loads((gt.ROOT / "results" / f"p1_groundtruth_round1_{s}.json").read_text(encoding="utf-8"))
        ref = js["u"]["all"][gt.PERIOD[s]]["def1"]
        for t in ["J", "C", "P"]:
            g = d[(d.set == s) & (d.tier == t) & d.def1_status.isin(["resolved", "unresolved"])]
            check[f"{s}/{t}"] = {"replay": [int((g.def1_status == "unresolved").sum()), int(len(g))],
                                 "round1_json": [ref[t]["k"], ref[t]["n"]]}
    print("replay check:", json.dumps(check), flush=True)

    # 2. unresolved J/C: best candidate per backend and pattern
    un = d[d.tier.isin(["J", "C"]) & (d.def1_status == "unresolved")].copy()
    rows = []
    for r in un.to_dict("records"):
        cs = candidates(r["title"], gt._arxiv_applies(r))
        best = {"sim": 0.0, "backend": "", "title": "", "id": ""}
        for b, c in cs.items():
            for cid, ts in c or []:
                for tt in ts:
                    s = rm.title_sim(tt, r["title"])
                    if s > best["sim"]:
                        best = {"sim": s, "backend": b, "title": tt, "id": cid}
        rows.append(dict(set=r["set"], tier=r["tier"], arxiv_id=r["arxiv_id"], key=r["key"],
                         ref_source=r["ref_source"], has_doi=r["has_doi"], has_arxiv=r["has_arxiv"],
                         label=r["label"], s2_pending=r["s2_pending"], oa_skipped=r["oa_skipped"],
                         answered=";".join(b for b, c in cs.items() if c is not None),
                         n_cand=sum(len(c or []) for c in cs.values()),
                         bib_title=r["title"], best_backend=best["backend"], best_sim=round(best["sim"], 4),
                         best_title=best["title"], best_id=best["id"],
                         patterns=";".join(variants(r["title"], best["title"])) if best["title"] else "",
                         f_journal=r["f_journal"], f_booktitle=r["f_booktitle"]))
    u = pd.DataFrame(rows)
    u["sim_band"] = pd.cut(u.best_sim, [-0.01, 0.5, 0.7, 0.8, 0.9], labels=["<0.5", "0.5-0.7", "0.7-0.8", "0.8-0.9"])
    u.to_csv(gt.ROOT / "results" / "p1_diag_unresolved_patterns.csv", index=False)

    # 3. sample of 60 for manual reading
    smp = (u.groupby(["tier", "set"], group_keys=False)
           .apply(lambda g: g.sample(min(args.n_per_cell, len(g)), random_state=args.seed)))
    smp = smp.sort_values(["tier", "set", "best_sim"], ascending=[True, True, False])
    smp.insert(0, "diag_id", [f"D{i + 1:02d}" for i in range(len(smp))])
    smp.to_csv(gt.ROOT / "results" / "p1_diag_unresolved_jc60.csv", index=False)

    # 4. tier P split
    p = d[d.tier == "P"].copy()
    p["id_group"] = np.where(p.has_arxiv == 1, "arxiv-id", np.where(p.has_doi.astype(int) == 1, "doi-only", "no-id"))
    psplit = {}
    for (s, g_), g in p.groupby(["set", "id_group"]):
        ev = g[g.def1_status.isin(["resolved", "unresolved"])]
        k = int((ev.def1_status == "unresolved").sum())
        psplit.setdefault(s, {})[g_] = {"k": k, "n": int(len(ev)), "u": round(k / len(ev), 4) if len(ev) else None,
                                        "wilson95": [round(x, 4) for x in gt.wilson(k, len(ev))] if len(ev) else None,
                                        "n_total": int(len(g)), "no_title": int((g.def1_status == "no-title").sum()),
                                        "rate_limited": int((g.def1_status == "rate-limited").sum()),
                                        "certified_real": int((g.label == "certified-real").sum()),
                                        "hit_by": g.backends_hit.value_counts().to_dict()}
    summary = {"seed": args.seed, "label": "diagnostic, exploratory; round 1 replayed from cache (no network)",
               "replay_check": check,
               "unresolved_jc": {"n": int(len(u)),
                                 "by_set_tier": {f"{a}/{b}": int(v) for (a, b), v in u.groupby(["set", "tier"]).size().items()},
                                 "s2_pending": int(u.s2_pending.sum()),
                                 "sim_band": u.sim_band.value_counts().sort_index().astype(int).to_dict(),
                                 "patterns": u.patterns.str.split(";").explode().replace("", np.nan).dropna()
                                 .value_counts().to_dict(),
                                 "no_candidates": int((u.n_cand == 0).sum())},
               "tier_P_split": psplit}
    (gt.ROOT / "results" / "p1_diag.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
