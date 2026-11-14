#!/usr/bin/env python3
"""Topic 43 / P3H (PREREG_AMENDMENT_9.md (D); POST HOC): store the capture blocks returned by the capture sub-agents.

Input:  P3H/capture_raw_*.txt, each a sequence of blocks
          === URL: <url>
          STATUS: ok|robots|blocked|error
          ROBOTS: ...
          CITATION_TITLE: ... (and the other fields of p3h_evidence_check.FIELDS)
        and the UTC time of the capture run (--utc, the time the agent returned).
Output: $THS_DATASETS/_derived/43/cache_p3h/<sha1(url)>.txt (header URL/FETCHED_UTC, then the block verbatim), and
        P3H/capture_manifest.csv (url, file, sha256, status, utc). Existing files are not overwritten.
Usage:  python code/p3h_capture_store.py --utc 2026-11-13T02:10:00Z P3H/capture_raw_1.txt ...
"""
import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3h_evidence_check import CACHE, cache_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def blocks(txt):
    for part in re.split(r"(?m)^=== URL:\s*", txt)[1:]:
        lines = part.strip("\n").splitlines()
        yield lines[0].strip(), "\n".join(l.rstrip() for l in lines[1:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--utc", required=True)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    man = ROOT / "P3H" / "capture_manifest.csv"
    new = not man.exists()
    with man.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["url", "file", "sha256", "status", "utc", "raw_file"])
        for f in a.files:
            for url, body in blocks(Path(f).read_text(encoding="utf-8")):
                cf = cache_file(url)
                if cf.exists():
                    print("exists, kept:", url)
                    continue
                txt = f"URL: {url}\nFETCHED_UTC: {a.utc}\n{body}\n"
                cf.write_text(txt, encoding="utf-8")
                st = re.search(r"(?m)^STATUS:\s*(\S+)", body)
                w.writerow([url, cf.name, hashlib.sha256(txt.encode("utf-8")).hexdigest(), st.group(1) if st else "",
                            a.utc, Path(f).name])
                print(st.group(1) if st else "?", url)


if __name__ == "__main__":
    main()
