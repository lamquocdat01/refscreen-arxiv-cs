#!/usr/bin/env python3
"""Topic 43 / P3E: one keyless OpenAlex request to read the rate-limit headers (cost per call, daily budget).

The request is the registered cascade request (rm._openalex_req = filter title.search, per-page 5) for the FIRST
target of Amendment-7 group 1 that has no stored OpenAlex answer, so the answer is not wasted: it is written to
_derived/43/cache_p3e/openalex/ in the cache format of refmatch.cached_get and is reused by p3e_complete_cascade.py.
Prints status and every header whose name contains "ratelimit", "credit", "budget", "retry" or "cost"; never prints a
key or the URL. Output JSON line is appended to P3E/oa_probe.jsonl.
Usage: python code/p3e_oa_probe.py
"""
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
import p3e_complete_cascade as cc  # noqa: E402

KEEP = ("ratelimit", "credit", "budget", "retry", "cost", "x-ratelimit")


def main():
    d = cc.load()
    t = cc.build_targets(d, 42)
    rows = d[d.target].drop_duplicates(["arxiv_id", "key"]).set_index(d[d.target].drop_duplicates(
        ["arxiv_id", "key"]).arxiv_id + "/" + d[d.target].drop_duplicates(["arxiv_id", "key"]).key)
    new_cache = cc.NEW_CACHE / "openalex"
    new_cache.mkdir(parents=True, exist_ok=True)
    for rid in t.ref_id[t.group == 1]:
        title = rows.loc[rid, "title"]
        if not title:
            continue
        url, params = rm._openalex_req(title)
        key = hashlib.sha1((url + "?" + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        if (rm.CACHE / "openalex" / f"{key}.json").exists() or (new_cache / f"{key}.json").exists():
            continue
        break
    else:
        print("no group-1 target without a stored OpenAlex answer")
        return
    s = requests.Session()
    s.headers["User-Agent"] = rm.UA
    t0 = dt.datetime.now(dt.timezone.utc)
    r = s.get(url, params=params, timeout=60)
    hdr = {k: v for k, v in r.headers.items() if any(w in k.lower() for w in KEEP)}
    out = {"time": f"{t0:%Y-%m-%dT%H:%M:%SZ}", "ref_id": rid, "kind": "filter=title.search (cascade request)",
           "key": bool(rm.OPENALEX_API_KEY), "status": r.status_code, "headers": hdr}
    if r.status_code != 200:
        out["body_head"] = r.text[:300]
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if r.status_code in (200, 400, 404):
        payload = r.json() if r.status_code == 200 else None
        cf = new_cache / f"{key}.json"
        cf.write_text(json.dumps({"url": r.url, "status": r.status_code, "payload": payload,
                                  "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}), encoding="utf-8")
        out["cached"] = str(cf.name)
    with (cc.OUT_DIR / "oa_probe.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
