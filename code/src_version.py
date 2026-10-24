#!/usr/bin/env python3
"""Topic 43 / P3 / Amendment 5 (c'): which arXiv version each downloaded .bib comes from, and its date.

The e-print endpoint (https://arxiv.org/e-print/<id>, no version suffix) serves the latest version at download time.
The cached arXiv API listing responses ($THS_DATASETS/arxiv_src_43/listing_cache/*.xml, queried during the download
runs) give, per paper, the latest version id (<id>.../abs/<arxiv_id>vN) and that version's date (<updated>).
This script joins them to data_manifest/manifest.csv (offline, no network).
Check: the listing response must be queried no later than the e-print download (downloaded_at); otherwise a version
posted in between could be missed -> flagged in column `listing_after_download`.
Output: data_manifest/manifest_src_version.csv (arxiv_id, src_version, src_version_date, listing_queried_at,
        downloaded_at, listing_after_download)
Usage: python src_version.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, ROOT  # noqa: E402

LIST = DATA / "arxiv_src_43" / "listing_cache"
ENTRY = re.compile(r"<entry>.*?<id>https?://arxiv\.org/abs/([^<]+?)v(\d+)</id>.*?<updated>([^<]+)</updated>", re.S)
FEED_UPD = re.compile(r"<updated>([^<]+)</updated>")


def main():
    obs = {}
    for f in sorted(LIST.glob("*.xml")):
        t = f.read_text(encoding="utf-8", errors="replace")
        q = FEED_UPD.search(t).group(1)
        for aid, v, upd in ENTRY.findall(t):
            obs.setdefault(aid, []).append((int(v), upd, q))
    man = pd.read_csv(ROOT / "data_manifest" / "manifest.csv", dtype=str, keep_default_na=False)
    man = man[man.status == "kept"][["arxiv_id", "published", "downloaded_at"]]
    rows = []
    for r in man.itertuples():
        o = obs.get(r.arxiv_id, [])
        before = [x for x in o if x[2] <= r.downloaded_at]
        # latest listing at or before the download; else the earliest listing after it (flagged)
        b = max(before, key=lambda x: (x[2], x[0])) if before else (min(o, key=lambda x: x[2]) if o else None)
        rows.append(dict(arxiv_id=r.arxiv_id, published_v1=r.published,
                         src_version=f"v{b[0]}" if b else "", src_version_date=b[1][:10] if b else "",
                         listing_queried_at=b[2] if b else "", downloaded_at=r.downloaded_at,
                         listing_after_download=bool(b and b[2] > r.downloaded_at)))
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data_manifest" / "manifest_src_version.csv", index=False)
    print(len(out), "kept papers;", (out.src_version == "").sum(), "without listing;",
          (out.src_version != "v1").sum() - (out.src_version == "").sum(), "with version > 1;",
          int(out.listing_after_download.sum()), "listing after download")


if __name__ == "__main__":
    main()
