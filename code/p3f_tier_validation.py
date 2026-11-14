#!/usr/bin/env python3
"""Topic 43 / P3F (PREREG_AMENDMENT_8 (I)): compare the machine tier with the type of the matched registry record.

--hydrate  fetch Crossref types of the DOIs matched by the cascade: batches `filter=doi:a,doi:b,...`, `select=DOI,type`,
           <= 2 requests/s, stored in cache_p3f/crossref/ (answers) and cache_p3f/crossref_types.json (doi -> type).
default    OFFLINE: results/p3f_tier_validation.{csv,json}. Record = first backend of the hits in cascade order; a record type
           outside the table of (I), and records from Semantic Scholar, are excluded and counted.
Usage: python code/p3f_tier_validation.py [--hydrate]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
import ground_truth_p1 as gt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
DER = gt.DERIVED
CACHE_F, CACHE_E, CACHE_0 = DER / "cache_p3f", DER / "cache_p3e", DER / "cache"
TYPES = CACHE_F / "crossref_types.json"
TIERS = ["J", "C", "P", "B", "S", "W"]
CR = {"journal-article": "J", "proceedings-article": "C", "posted-content": "P", "book": "B", "book-chapter": "B", "monograph": "B", "edited-book": "B",
      "dissertation": "B", "dataset": "S", "component": "S", "report": "W", "standard": "W", "other": "W"}
BATCH = 50


def rd(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False, low_memory=False)


def first_hit(mid):
    seg = mid.split(";")[0]
    if ":" not in seg:
        return "", ""
    b, i = seg.split(":", 1)
    return b, i


def load_gt():
    d = rd(DER / "p3e_groundtruth_refs_full.csv").drop_duplicates(["arxiv_id", "key"])
    d["ref_id"] = d.arxiv_id + "/" + d.key
    return d


def hydrate():
    rm.CACHE = CACHE_F
    rm.MIN_INTERVAL["crossref"] = 0.5
    d = load_gt()
    d = d[d.def1_status == "resolved"]
    dois = sorted({first_hit(m)[1].lower() for m in d.match_id if first_hit(m)[0] == "crossref"})
    types = json.loads(TYPES.read_text(encoding="utf-8")) if TYPES.exists() else {}
    todo = [x for x in dois if x not in types]
    print(f"crossref DOIs matched: {len(dois)}; to fetch: {len(todo)}", flush=True)
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        st, p = rm.cached_get("crossref", "https://api.crossref.org/works", {"filter": ",".join(f"doi:{x}" for x in chunk), "select": "DOI,type", "rows": BATCH, "mailto": rm.MAILTO}, tries=3)
        if st == 200 and p:
            for it in p.get("message", {}).get("items", []):
                types[it.get("DOI", "").lower()] = it.get("type", "")
        if i % (BATCH * 20) == 0:
            print(f"  {i}/{len(todo)}; {len(types)} types", flush=True)
            TYPES.write_text(json.dumps(types), encoding="utf-8")
    TYPES.write_text(json.dumps(types), encoding="utf-8")
    print("types stored:", len(types), flush=True)


def _cache_read(backend, url, params):
    key = hashlib.sha1((url + "?" + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    for c in (CACHE_E, CACHE_0, CACHE_F):
        f = c / backend / f"{key}.json"
        if f.exists():
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
                return j.get("payload")
            except (ValueError, OSError):
                return None
    return None


def dblp_tier(t, key):
    if key.startswith("journals/corr"):
        return "P"
    return {"article": "J", "inproceedings": "C", "book": "B", "incollection": "B", "phdthesis": "B"}.get(t)


def oa_tier(t, st):
    t, st = (t or "").lower(), (st or "").lower()
    if t == "preprint" or st == "repository":
        return "P"
    if t == "article" and st == "journal":
        return "J"
    if t == "article" and st == "conference":
        return "C"
    if t in ("book", "book-chapter"):
        return "B"
    if t == "dataset":
        return "S"
    return "W"


def record_tier(r, types):
    """(registry tier or None, source, type string) for a ref resolved by the cascade."""
    b, rid = first_hit(r["match_id"])
    if b == "crossref":
        t = types.get(rid.lower(), "")
        return CR.get(t), b, t
    if b == "arxiv":
        return "P", b, "arxiv"
    if b == "dblp":
        p = _cache_read("dblp", *rm.dblp_req(r["title"]))
        for h in (p or {}).get("hits", []):
            if h.get("key") == rid:
                return dblp_tier(h.get("type", ""), rid), b, h.get("type", "")
        return None, b, ""
    if b == "openalex":
        url, params = rm._openalex_req(r["title"])
        p = _cache_read("openalex", url, params)
        for w in (p or {}).get("results", []):
            if w.get("id") == rid:
                src = (w.get("primary_location") or {}).get("source") or {}
                return oa_tier(w.get("type", ""), src.get("type", "")), b, f"{w.get('type', '')}|{src.get('type', '')}"
        return None, b, ""
    return None, b or "none", ""


def gt3_tier(row):
    src, ty = row["source"], row["record_type"]
    if src == "crossref":
        return CR.get(ty)
    if src == "arxiv":
        return "P"
    if src == "dblp":
        return dblp_tier(ty, row["record_id"])
    if src == "openalex":
        a, b = (ty.split("|") + [""])[:2]
        return oa_tier(a, b)
    return None


def kappa(a, b):
    labels = TIERS
    idx = {l: i for i, l in enumerate(labels)}
    m = np.zeros((6, 6))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = (m.sum(0) * m.sum(1)).sum() / n ** 2
    return float((po - pe) / (1 - pe)) if pe < 1 else None, m.astype(int).tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hydrate", action="store_true")
    ap.add_argument("--partial", action="store_true", help="smoke test before the data are complete: writes P3F/interim_tier_validation.*")
    args = ap.parse_args()
    if args.hydrate:
        return hydrate()
    out_dir, stem = (ROOT / "P3F", "interim_tier_validation") if args.partial else (RES, "p3f_tier_validation")
    types = json.loads(TYPES.read_text(encoding="utf-8")) if TYPES.exists() else {}
    d = load_gt()
    rows, excl = [], {}
    for r in d[d.def1_status == "resolved"].to_dict("records"):
        t, s, ty = record_tier(r, types)
        if t is None:
            excl[s] = excl.get(s, 0) + 1
            continue
        rows.append(dict(ref_id=r["ref_id"], period=r["period"], tier_machine=r["tier"], tier_record=t, source=s, record_type=ty, via="cascade"))
    if (RES / "p3f_deep_search.csv").exists():
        x = rd(RES / "p3f_deep_search.csv")
        for r in x[(x.state == "found") & x.set.isin(["acad1921", "acad2426", "nonacad1921"])].to_dict("records"):
            t = gt3_tier(r)
            if t is None:
                key = "gt3:" + r["source"]
                excl[key] = excl.get(key, 0) + 1
                continue
            rows.append(dict(ref_id=r["ref_id"], period=r["period"], tier_machine=r["tier"], tier_record=t, source="gt3:" + r["source"], record_type=r["record_type"], via="gt3"))
    t = pd.DataFrame(rows)
    t.to_csv(out_dir / f"{stem}.csv", index=False)
    acc = float((t.tier_machine == t.tier_record).mean())
    k, m = kappa(t.tier_machine, t.tier_record)
    v = (((t.tier_machine == "P") & t.tier_record.isin(["J", "C"])) | (t.tier_machine.isin(["J", "C"]) & (t.tier_record == "P")))
    t2 = t[~v]
    out = {"label": "tier-rule validation (Amendment 8 (I)); only resolved references; S and W are rare in registries",
           "n": len(t), "agreement": acc, "kappa": k, "confusion_machine_rows_record_cols": m, "labels": TIERS, "excluded_counts": excl,
           "version_mismatch_n": int(v.sum()), "version_mismatch_by_pair": t[v].groupby(["tier_machine", "tier_record"]).size().rename("n").reset_index().to_dict("records"),
           "agreement_without_version_mismatches": float((t2.tier_machine == t2.tier_record).mean()), "n_without_version_mismatches": len(t2),
           "by_source": t.groupby("source").size().to_dict(), "crossref_types_stored": len(types)}
    out["interim"] = bool(args.partial)
    (out_dir / f"{stem}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({q: out[q] for q in ("n", "agreement", "kappa", "version_mismatch_n", "agreement_without_version_mismatches", "excluded_counts", "by_source")}, indent=1))


if __name__ == "__main__":
    main()
