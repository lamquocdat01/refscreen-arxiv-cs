#!/usr/bin/env python3
"""Fetch a stratified corpus of arXiv CS LaTeX sources (topic 43, P0/T03 pilot; P1/T06b full corpus per PREREG_43.md).

Strata: primary category in {cs.CV, cs.LG, cs.CL, cs.NI, cs.CR} x year.
  --quotas p0 : pilot 2024/25/26 = 7/7/6 per field (100);  prellm 2019/20/21 = 2/2/2 per field (30)
  --quotas p1 : pilot 2024/25/26 = 67/67/66 per field (1,000); prellm 2019/20/21 = 20/20/20 per field (300)
Papers already in the manifest count towards the quotas (P0 papers are part of the P1 corpus).
A paper is KEPT only if its e-print contains a main .tex (has \\documentclass) and at least one .bib or .bbl.

Politeness: one HTTP request every >= 3 s to arxiv.org (API and e-print), no real e-mail in the User-Agent,
exponential back-off on 429/5xx. Raw tarballs are hashed (sha256), only .tex/.bib/.bbl/.bst/.cls/.sty text files are
extracted (safe paths only), then the tarball is deleted (dataset rule: do not keep archives after extraction+check).

Outputs (dataset area, outside Google Drive):
  $THS_DATASETS/arxiv_src_43/src/<id>/...      extracted text sources
  $THS_DATASETS/arxiv_src_43/manifest.csv      one row per attempted paper (kept or skipped)
  $THS_DATASETS/arxiv_src_43/listing_cache/    cached arXiv API responses
The manifest is also copied to <topic>/data_manifest/manifest.csv.

Usage: python -I fetch_arxiv.py --seed 42 [--limit N] [--sets pilot,prellm] [--quotas p1] [--resume]
"""
import argparse
import csv
import gzip
import hashlib
import io
import os
import random
import re
import shutil
import sys
import tarfile
import time
from pathlib import Path

import feedparser
import requests

FIELDS = ["cs.CV", "cs.LG", "cs.CL", "cs.NI", "cs.CR"]
QUOTAS = {
    "p0": {"pilot": {2024: 7, 2025: 7, 2026: 6}, "prellm": {2019: 2, 2020: 2, 2021: 2}},
    "p1": {"pilot": {2024: 67, 2025: 67, 2026: 66}, "prellm": {2019: 20, 2020: 20, 2021: 20}},
}
UA = "refscreen-43/0.1 (research pilot; mailto:noreply@example.org)"
API = "https://export.arxiv.org/api/query"  # P1: http now 301-redirects (two hits per request)
EPRINT = "https://arxiv.org/e-print/{}"
KEEP_EXT = {".tex", ".bib", ".bbl", ".bst", ".cls", ".sty"}
MAX_MEMBER_BYTES = 20 * 1024 * 1024
DELAY = float(os.environ.get("ARXIV_DELAY", "4.0"))  # P0: 3.2 s; P1 raised after sustained 429s on the API

TOPIC = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("THS_DATASETS", r"D:\Datasets")) / "arxiv_src_43"
MANIFEST_COLS = ["arxiv_id", "set", "field", "year", "primary_category", "title", "published", "status",
                 "has_main_tex", "n_tex", "n_bib", "n_bbl", "main_tex", "bytes", "sha256", "content_type",
                 "downloaded_at", "ref_branch"]

_last = [0.0]


def polite_get(url, params=None, stream=False, tries=5):
    """GET with >= DELAY seconds between consecutive requests and exponential back-off."""
    wait = 10.0
    for attempt in range(tries):
        gap = time.time() - _last[0]
        if gap < DELAY:
            time.sleep(DELAY - gap)
        _last[0] = time.time()
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=120, stream=stream)
        except requests.RequestException as e:
            print(f"  ! {e.__class__.__name__} on {url}; retry in {wait:.0f}s", flush=True)
            time.sleep(wait)
            wait *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            ra = r.headers.get("Retry-After")
            w = max(float(ra), wait) if ra and ra.isdigit() else wait
            print(f"  ! HTTP {r.status_code} on {url}; retry in {w:.0f}s", flush=True)
            time.sleep(w)
            wait *= 2
            continue
        return r
    return None


class ListingFailed(Exception):
    pass


def list_candidates(field, year, rng, cache_dir, day=None):
    """Random 3-day submission window inside `year`; returns shuffled entries whose primary category == field.
    Raises ListingFailed (window NOT consumed) when the API keeps refusing; the caller retries the same `day`."""
    if day is None:
        day = rng.randrange(0, 360 if year < 2026 else 280)  # 2026: up to early October
    start = time.strftime("%Y%m%d", time.gmtime(time.mktime((year, 1, 1, 12, 0, 0, 0, 0, 0)) + day * 86400))
    end = time.strftime("%Y%m%d", time.gmtime(time.mktime((year, 1, 1, 12, 0, 0, 0, 0, 0)) + (day + 3) * 86400))
    q = f"cat:{field} AND submittedDate:[{start}0000 TO {end}2359]"
    key = hashlib.sha1(q.encode()).hexdigest()[:16]
    cf = cache_dir / f"{key}.xml"
    if cf.exists():
        text = cf.read_text(encoding="utf-8")
    else:
        r = polite_get(API, params={"search_query": q, "start": 0, "max_results": 100,
                                    "sortBy": "submittedDate", "sortOrder": "ascending"})
        if r is None or r.status_code != 200:
            raise ListingFailed(day)
        text = r.text
        cf.write_text(text, encoding="utf-8")
    feed = feedparser.parse(text)
    out = []
    for e in feed.entries:
        aid = e.id.rsplit("/abs/", 1)[-1]
        aid = re.sub(r"v\d+$", "", aid)
        prim = getattr(e, "arxiv_primary_category", {}).get("term", "")
        if prim != field:
            continue
        out.append({"arxiv_id": aid, "primary_category": prim, "title": " ".join(e.title.split()),
                    "published": e.published[:10]})
    rng.shuffle(out)
    return out


def safe_member_path(name):
    name = name.replace("\\", "/").lstrip("/")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." or ":" in p for p in parts):
        return None
    return Path(*parts)


def extract(blob, dest):
    """Extract text sources from an e-print blob. Returns (content_type, list of relative paths written)."""
    written = []
    raw = blob
    if blob[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(blob)
        except OSError:
            return "bad-gzip", written
    if raw[:4] == b"%PDF":
        return "pdf-only", written
    try:
        tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r:*")
    except tarfile.TarError:
        tf = None
    if tf is None:
        # single gzipped .tex file
        txt = raw[:MAX_MEMBER_BYTES]
        if b"\\documentclass" in txt or b"\\begin{document}" in txt:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "main.tex").write_bytes(txt)
            return "single-tex", ["main.tex"]
        return "unknown", written
    with tf:
        for m in tf.getmembers():
            if not m.isfile() or m.size > MAX_MEMBER_BYTES:
                continue
            rel = safe_member_path(m.name)
            if rel is None or rel.suffix.lower() not in KEEP_EXT:
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(f.read())
            written.append(rel.as_posix())
    return "tar", written


def classify(dest, written):
    tex = [w for w in written if w.lower().endswith(".tex")]
    bib = [w for w in written if w.lower().endswith(".bib")]
    bbl = [w for w in written if w.lower().endswith(".bbl")]
    main = ""
    for t in sorted(tex, key=lambda s: (s.count("/"), len(s))):
        try:
            head = (dest / t).read_bytes()[:200000]
        except OSError:
            continue
        if re.search(rb"^[^%\n]*\\documentclass", head, re.M):
            main = t
            break
    return main, tex, bib, bbl


def load_manifest(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:  # P0 rows predate the ref_branch column
        if r.get("status") == "kept" and not r.get("ref_branch"):
            r["ref_branch"] = "bib" if int(r.get("n_bib") or 0) else "bbl"
    return rows


def write_manifest(path, rows):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="max e-print downloads in this run (0 = no limit)")
    ap.add_argument("--sets", default="pilot,prellm")
    ap.add_argument("--max-windows", type=int, default=60, help="listing windows tried per stratum")
    ap.add_argument("--quotas", default="p1", choices=sorted(QUOTAS))
    ap.add_argument("--listing-pause", type=int, default=600, help="seconds to wait after a refused listing")
    ap.add_argument("--max-listing-fails", type=int, default=12)
    ap.add_argument("--batch", type=int, default=100, help="flush manifest + pause 60 s every N downloads")
    ap.add_argument("--resume", action="store_true",
                    help="continue from the existing manifest (always on: kept/attempted ids are never re-fetched)")
    args = ap.parse_args()
    SETS = QUOTAS[args.quotas]

    rng = random.Random(args.seed)
    (DATA / "src").mkdir(parents=True, exist_ok=True)
    cache_dir = DATA / "listing_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    mpath = DATA / "manifest.csv"
    rows = load_manifest(mpath)
    seen = {r["arxiv_id"] for r in rows}
    downloads = 0

    for set_name in args.sets.split(","):
        for field in FIELDS:
            for year, quota in SETS[set_name].items():
                kept = sum(1 for r in rows if r["set"] == set_name and r["field"] == field
                           and r["year"] == str(year) and r["status"] == "kept")
                windows = 0
                while kept < quota and windows < args.max_windows:
                    windows += 1
                    day, fails = None, 0
                    while True:
                        try:
                            cands = list_candidates(field, year, rng, cache_dir, day)
                            break
                        except ListingFailed as e:  # P1 fix: a refused listing no longer burns the window
                            day, fails = e.args[0], fails + 1
                            if fails >= args.max_listing_fails:
                                write_manifest(mpath, rows)
                                shutil.copy2(mpath, TOPIC / "data_manifest" / "manifest.csv")
                                print(f"ABORT: arXiv API refused {fails} times in a row; manifest saved, re-run "
                                      f"with --resume later", flush=True)
                                return 2
                            print(f"  listing refused ({fails}); pause {args.listing_pause}s", flush=True)
                            time.sleep(args.listing_pause)
                    for c in cands[:4]:  # at most 4 tries per window -> spread over the year
                        if kept >= quota:
                            break
                        if c["arxiv_id"] in seen:
                            continue
                        if args.limit and downloads >= args.limit:
                            print("limit reached", flush=True)
                            write_manifest(mpath, rows)
                            shutil.copy2(mpath, TOPIC / "data_manifest" / "manifest.csv")
                            return
                        seen.add(c["arxiv_id"])
                        r = polite_get(EPRINT.format(c["arxiv_id"]))
                        downloads += 1
                        row = {k: "" for k in MANIFEST_COLS}
                        row.update(c)
                        row.update({"set": set_name, "field": field, "year": year,
                                    "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
                        if r is None or r.status_code != 200:
                            row["status"] = f"http-{getattr(r, 'status_code', 'none')}"
                            rows.append(row)
                            continue
                        blob = r.content
                        row["bytes"] = len(blob)
                        row["sha256"] = hashlib.sha256(blob).hexdigest()
                        dest = DATA / "src" / c["arxiv_id"].replace("/", "_")
                        ctype, written = extract(blob, dest)
                        row["content_type"] = ctype
                        main_tex, tex, bib, bbl = classify(dest, written)
                        row.update({"has_main_tex": int(bool(main_tex)), "n_tex": len(tex), "n_bib": len(bib),
                                    "n_bbl": len(bbl), "main_tex": main_tex})
                        if main_tex and (bib or bbl):
                            row["status"] = "kept"
                            kept += 1
                        else:
                            row["status"] = "skip-no-bib" if main_tex else f"skip-{ctype}"
                            shutil.rmtree(dest, ignore_errors=True)
                        row["ref_branch"] = ("bib" if bib else "bbl") if row["status"] == "kept" else ""
                        rows.append(row)
                        if args.batch and downloads % args.batch == 0:
                            write_manifest(mpath, rows)
                            shutil.copy2(mpath, TOPIC / "data_manifest" / "manifest.csv")
                            print(f"--- batch of {args.batch} done ({downloads} downloads this run); pause 60 s",
                                  flush=True)
                            time.sleep(60)
                        print(f"[{set_name} {field} {year}] {c['arxiv_id']} {row['status']} "
                              f"bib={len(bib)} bbl={len(bbl)} ({kept}/{quota})", flush=True)
                        if len(rows) % 2 == 0:
                            write_manifest(mpath, rows)
                if kept < quota:
                    print(f"WARNING stratum {set_name} {field} {year}: kept {kept}/{quota}", flush=True)
                write_manifest(mpath, rows)

    write_manifest(mpath, rows)
    (TOPIC / "data_manifest").mkdir(exist_ok=True)
    shutil.copy2(mpath, TOPIC / "data_manifest" / "manifest.csv")
    k = sum(r["status"] == "kept" for r in rows)
    print(f"done: {len(rows)} attempted, {k} kept, {downloads} downloads this run (seed {args.seed})", flush=True)


if __name__ == "__main__":
    sys.exit(main())
