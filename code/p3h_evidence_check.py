#!/usr/bin/env python3
"""Topic 43 / P3H (PREREG_AMENDMENT_9.md (D); POST HOC): rule check of the web evidence, offline on the capture cache.

Inputs:  results/p3h_evidence_sheet.csv (blind sheet), results/p3h_evidence_agent.csv (ID, url, class, note from the
         searcher agents), $THS_DATASETS/_derived/43/cache_p3h/<sha1(url)>.txt (capture text written by the capture
         step: header lines URL/FETCHED_UTC/STATUS, then the fields returned by WebFetch).
Rule:    page title = CITATION_TITLE, else DC_TITLE, else DISPLAYED_TITLE; sim = refmatch.title_sim(sheet title, page
         title); surname match = a sheet surname (last token of each name, lower case, accents removed) occurs as a
         word in the page author text (CITATION_AUTHORS, DC_CREATOR, DISPLAYED_AUTHORS; else the whole capture).
         PASS  sim >= 0.90 and surname;  NEAR  0.80 <= sim < 0.90, surname, |page year - sheet year| <= 1;
         FAIL  otherwise (also a search-results URL);  NONE  no URL;  needs_browser  STATUS robots/blocked/error.
Output:  results/p3h_evidence_checked.csv
Usage:   python code/p3h_evidence_check.py
"""
import hashlib
import os
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
CACHE = Path(os.environ.get("THS_DATASETS", "D:/Datasets")) / "_derived" / "43" / "cache_p3h"
SEARCH_RE = re.compile(r"(scholar\.google\.|google\.[a-z.]+/search|bing\.com/search|duckduckgo\.com/\?|"
                       r"[?&](q|query|search)=|/search(\?|/|$))", re.I)
FIELDS = ("URL", "FETCHED_UTC", "STATUS", "CITATION_TITLE", "CITATION_AUTHORS", "CITATION_DATE", "DC_TITLE",
          "DC_CREATOR", "DC_DATE", "DISPLAYED_TITLE", "DISPLAYED_AUTHORS", "YEAR", "NOTE")


def cache_file(url):
    return CACHE / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.txt"


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def surnames(authors):
    out = []
    for a in (authors or "").split(","):
        a = a.strip()
        if not a or a.lower().startswith("et al"):
            continue
        t = re.findall(r"[^\W\d_][\w'-]*", fold(a))
        if t:
            out.append(t[-1])
    return sorted({s for s in out if len(s) >= 2})


def parse(txt):
    f = {k: "" for k in FIELDS}
    for line in txt.splitlines():
        m = re.match(r"^([A-Z_]+):\s?(.*)$", line)
        if m and m.group(1) in f:
            f[m.group(1)] = m.group(2).strip()
    return f


def year_of(*vals):
    for v in vals:
        m = re.search(r"\b(1[89]\d\d|20\d\d)\b", v or "")
        if m:
            return int(m.group(1))
    return None


def main():
    sheet = pd.read_csv(RES / "p3h_evidence_sheet.csv", dtype=str, keep_default_na=False)
    agent = pd.read_csv(RES / "p3h_evidence_agent.csv", dtype=str, keep_default_na=False)
    d = sheet.merge(agent, on="ID", how="left").fillna("")
    rows = []
    for r in d.itertuples():
        out = dict(ID=r.ID, url=r.url, url_class=r.url_class, state="", page_title="", sim="", surnames_matched="",
                   page_year="", content_sha256="", fetched_utc="", capture_status="")
        if not r.url:
            out["state"] = "NONE"
            rows.append(out)
            continue
        if SEARCH_RE.search(r.url):
            out["state"] = "FAIL"
            out["capture_status"] = "search-results URL"
            rows.append(out)
            continue
        cf = cache_file(r.url)
        if not cf.exists():
            out["state"] = "needs_browser"
            out["capture_status"] = "not captured"
            rows.append(out)
            continue
        raw = cf.read_text(encoding="utf-8")
        f = parse(raw)
        out.update(content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(), fetched_utc=f["FETCHED_UTC"],
                   capture_status=f["STATUS"])
        if f["STATUS"] != "ok":
            out["state"] = "needs_browser"
            rows.append(out)
            continue
        title = f["CITATION_TITLE"] or f["DC_TITLE"] or f["DISPLAYED_TITLE"]
        if not (title or f["CITATION_AUTHORS"] or f["DC_CREATOR"] or f["DISPLAYED_AUTHORS"]):
            # the fetch returned no readable content (e.g. a compressed PDF): the capture agents reported this both as
            # "ok" with empty fields and as "error"; it is treated uniformly as a page the tool could not read
            out["state"] = "needs_browser"
            out["capture_status"] = "no readable content"
            rows.append(out)
            continue
        if title.strip().lower().endswith(".dvi") and not f["DISPLAYED_TITLE"]:
            out["state"] = "needs_browser"
            out["capture_status"] = "no readable content (file name only)"
            rows.append(out)
            continue
        sim = rm.title_sim(r.title, title) if title else 0.0
        page_text = " ".join(v for k, v in f.items() if k not in ("URL", "FETCHED_UTC", "STATUS"))
        page_text = re.sub(r"(?m)^ROBOTS:.*$", "", page_text)
        auth_text = " ".join([f["CITATION_AUTHORS"], f["DC_CREATOR"], f["DISPLAYED_AUTHORS"]]).strip() or page_text
        words = set(re.findall(r"[^\W\d_][\w'-]*", fold(auth_text)))
        hit = [s for s in surnames(r.authors) if s in words]
        py = year_of(f["CITATION_DATE"], f["DC_DATE"], f["YEAR"])
        sy = year_of(r.year)
        if sim >= 0.90 and hit:
            st = "PASS"
        elif sim >= 0.80 and hit and py is not None and sy is not None and abs(py - sy) <= 1:
            st = "NEAR"
        else:
            st = "FAIL"
        out.update(state=st, page_title=title, sim=round(sim, 4), surnames_matched=";".join(hit),
                   page_year=py if py is not None else "")
        rows.append(out)
    x = pd.DataFrame(rows)
    x.to_csv(RES / "p3h_evidence_checked.csv", index=False, encoding="utf-8")
    print(x.state.value_counts().to_dict())


if __name__ == "__main__":
    main()
