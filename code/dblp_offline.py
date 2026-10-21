#!/usr/bin/env python3
"""Topic 43 / P1: DBLP as an offline title backend (PREREG_AMENDMENT_3).

The DBLP search API (dblp.org, dblp.uni-trier.de, dblp.dagstuhl.de) sits behind a proof-of-work bot wall (checked
2026-10-19), so DBLP is queried from its XML dump instead:
  $THS_DATASETS/dblp/dblp.xml.gz (+ dblp.dtd; see DATA_SOURCES.md there)

  build  stream the dump once -> $THS_DATASETS/_derived/43/dblp/dblp_titles_<release>.tsv.gz
         (key, type, year, venue, title, norm title, first 10 author names)
  match  answer every query title that Crossref did not resolve (a superset of the titles that reach DBLP in the
         cascade of ground_truth_p1.py). Each answer is the top 5 DBLP records by refmatch.title_sim and is written to the normal API cache
         (cache/dblp/<sha1>.json, refmatch.dblp_req), so ground_truth_p1.py reads DBLP like any other backend.
Search = blocking + exact scoring. A record is scored against a query only if it shares one of the query's 3 rarest
tokens (document frequency in DBLP). A record with similarity >= 0.9 is missed only if all three of those tokens were
edited. This stands in for the API's top-5 ranking.
Usage: python dblp_offline.py build
       python dblp_offline.py match                 (queries from p1_refs_stage0.csv; Crossref from cache only)
       python dblp_offline.py blockcheck --seed 42  (blocking sensitivity, 200 queries)
"""
import argparse
import gzip
import heapq
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402

DBLP_DIR = rm.CACHE.parents[1].parent / "dblp"  # $THS_DATASETS/dblp
OUT_DIR = rm.CACHE.parent / "dblp"
TYPES = {"article", "inproceedings", "proceedings", "book", "incollection", "phdthesis", "mastersthesis", "data"}


def index_path():
    return OUT_DIR / f"dblp_titles_{rm.DBLP_RELEASE}.tsv.gz"


def build():
    from lxml import etree
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src = DBLP_DIR / "dblp.xml.gz"
    n, t0 = 0, time.time()
    tmp = index_path().with_suffix(".tmp")
    with gzip.open(src, "rb") as f, gzip.open(tmp, "wt", encoding="utf-8") as out:
        class _DTD(etree.Resolver):  # dblp.xml names "dblp.dtd" relative to itself; the stream has no base URL
            def resolve(self, url, pubid, context):
                return self.resolve_filename(str(DBLP_DIR / "dblp.dtd"), context) if url.endswith("dblp.dtd") else None

        ctx = etree.iterparse(f, events=("end",), load_dtd=True, resolve_entities=True, huge_tree=True,
                              no_network=True, tag=list(TYPES))
        ctx.resolvers.add(_DTD())
        for _, el in ctx:
            t = el.find("title")
            title = " ".join("".join(t.itertext()).split()) if t is not None else ""
            nt = rm.norm(title)
            if len(nt) >= 10:
                auth = [" ".join("".join(a.itertext()).split()) for a in el.findall("author")] or \
                       [" ".join("".join(a.itertext()).split()) for a in el.findall("editor")]
                venue = el.findtext("journal") or el.findtext("booktitle") or el.findtext("publisher") or ""
                row = [el.get("key", ""), el.tag, el.findtext("year") or "", venue, title, nt, "|".join(auth[:10])]
                out.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in row) + "\n")
                n += 1
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]
            if n and n % 1_000_000 == 0:
                print(f"  {n:,} records ({time.time() - t0:.0f}s)", flush=True)
    tmp.replace(index_path())
    print(f"index: {n:,} records with a title -> {index_path()} ({time.time() - t0:.0f}s)", flush=True)


def rows():
    with gzip.open(index_path(), "rt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) == 7:
                yield p


def match(queries):
    """queries: list of raw titles. Writes one cache file per distinct normalised query; returns counts."""
    todo = {}
    for q in queries:
        nq = rm.norm(q)
        if len(nq) >= 10 and not rm.is_cached("dblp", *rm.dblp_req(q)):
            todo.setdefault(nq, q)
    print(f"queries: {len(set(map(rm.norm, queries)))} distinct, {len(todo)} not cached", flush=True)
    if not todo:
        return {"written": 0}
    qtok = {nq: set(nq.split()) for nq in todo}
    vocab = set().union(*qtok.values())
    df, t0 = Counter(), time.time()
    for p in rows():  # pass 1: document frequency of the query vocabulary
        df.update(set(p[5].split()) & vocab)
    print(f"pass 1 (df) {time.time() - t0:.0f}s", flush=True)
    keyed = defaultdict(list)
    for nq, toks in qtok.items():
        rare = sorted((t for t in toks if df[t] > 0), key=lambda t: df[t])[:3] or sorted(toks)[:3]
        for t in rare:
            keyed[t].append(nq)
    best = {nq: [] for nq in todo}  # min-heaps of (sim, key, record)
    n_pairs = 0
    for p in rows():  # pass 2: exact scoring of blocked pairs
        hit = set(p[5].split()) & keyed.keys()
        if not hit:
            continue
        cand = set()
        for t in hit:
            cand.update(keyed[t])
        for nq in cand:
            s = rm.title_sim_norm(p[5], nq)
            n_pairs += 1
            h = best[nq]
            item = (s, p[0], {"key": p[0], "type": p[1], "year": p[2], "venue": p[3], "title": p[4],
                              "authors": [a for a in p[6].split("|") if a]})
            if len(h) < 5:
                heapq.heappush(h, item)
            elif s > h[0][0]:
                heapq.heapreplace(h, item)
    print(f"pass 2 (score) {time.time() - t0:.0f}s, {n_pairs:,} pairs", flush=True)
    for nq, h in best.items():
        hits = [it for _, _, it in sorted(h, key=lambda x: -x[0])]
        rm.cache_put("dblp", *rm.dblp_req(todo[nq]), status=200, payload={"hits": hits})
    return {"written": len(best), "pairs": n_pairs}


def stage0_queries():
    """Titles of p1_refs_stage0.csv that Crossref (stored answers) did not resolve."""
    import pandas as pd
    import ground_truth_p1 as gt
    d = pd.read_csv(gt.DERIVED / "p1_refs_stage0.csv", dtype={"arxiv_id": str, "key": str}, keep_default_na=False,
                    low_memory=False)
    out = []
    for r in d.to_dict("records"):
        t = r["title"]
        if len(rm.norm(t)) < 10:
            continue
        res = rm.crossref_search(t, cache_only=True)
        if isinstance(res, list) and rm.best_sim(res, title=t)[0] >= rm.SIM_THRESHOLD:
            continue
        out.append(t)
    return out


def blockcheck(queries, seed, n=200):
    """Sensitivity of the blocking (PREREG_AMENDMENT_3): n random queries scored against the whole index with
    rapidfuzz (normalised Levenshtein, no blocking). Reports queries where an unblocked record reaches >= 0.9 while the
    stored (blocked) answer does not."""
    import random
    from rapidfuzz import process
    from rapidfuzz.distance import Levenshtein
    qs = sorted({rm.norm(q): q for q in queries if len(rm.norm(q)) >= 10}.items())
    random.Random(seed).shuffle(qs)
    qs = qs[:n]
    names = [p[5] for p in rows()]
    out = []
    for nq, q in qs:
        m = process.extractOne(nq, names, scorer=Levenshtein.normalized_similarity)
        res = rm.dblp_search(q)
        blocked = rm.best_sim(res, title=q)[0] if isinstance(res, list) else None
        out.append({"query": nq, "unblocked_best": round(m[1], 4), "unblocked_title": m[0],
                    "blocked_best": None if blocked is None else round(blocked, 4)})
    miss = [o for o in out if o["unblocked_best"] >= rm.SIM_THRESHOLD and (o["blocked_best"] or 0) < rm.SIM_THRESHOLD]
    res = {"n": len(out), "missed_by_blocking": len(miss), "examples": miss[:10]}
    (rm.CACHE.parent / "dblp" / "blockcheck.json").write_text(json.dumps({"summary": res, "rows": out}, indent=1),
                                                             encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "match", "blockcheck"])
    ap.add_argument("--seed", type=int, default=42, help="blockcheck sample; match/build are deterministic")
    args = ap.parse_args()
    if args.cmd == "build":
        build()
    elif args.cmd == "match":
        print(json.dumps(match(stage0_queries())), flush=True)
    else:
        print(json.dumps(blockcheck(stage0_queries(), args.seed)), flush=True)


if __name__ == "__main__":
    main()
