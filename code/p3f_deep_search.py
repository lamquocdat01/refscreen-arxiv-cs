#!/usr/bin/env python3
"""Topic 43 / P3F (PREREG_AMENDMENT_8 (D)-(F)): GT-3, the pre-specified automated deep search.

Sets (--set): acad1921 (i), acad2426 (ii), decoy (iii: 200 D-splice decoys + 5 gen_a), posctl (iv), nonacad1921 (v).
Sources, in order; a reference stops at the first source with a candidate meeting the rule of Amendment 8 (D):
  crossref (query.bibliographic on the full string) -> dblp (offline dump) -> arxiv (all:) -> s2 (paper/search) ->
  openalex (search). Tiers S/W with a URL: url (HEAD) -> wayback (CDX) instead of the title rule.
Every answer is stored under $THS_DATASETS/_derived/43/cache_p3f/<source>/ with the cache key of the request without key.
States are computed from stored answers only (`evaluate`, offline), so the pipeline can be stopped and resumed.
OpenAlex key: read from ROOT/.env by p3e_complete_cascade.read_env_key, added at the session level, never printed or stored.

Usage:
  python code/p3f_deep_search.py --seed 48 --resume --set decoy [--no-openalex]   ask the sources, then evaluate that set
  python code/p3f_deep_search.py --evaluate                                       offline: results/p3f_deep_search.csv
  python code/p3f_deep_search.py --set decoy --dry 5                              offline: print examples, no request
"""
import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import logging
import math
import random
import re
import sys
import threading
import time
import urllib.parse as up
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
import ground_truth as gtm  # noqa: E402
import ground_truth_p1 as gt  # noqa: E402
import p3e_complete_cascade as cc  # noqa: E402
from p3_recheck import bbl_lookup  # noqa: E402

logging.getLogger("bibtexparser").setLevel(logging.ERROR)  # one warning per @string macro otherwise
logging.getLogger("bibtexparser.bibdatabase").setLevel(logging.ERROR)
logging.getLogger("bibtexparser.bparser").setLevel(logging.ERROR)
ROOT = Path(__file__).resolve().parents[1]
DER = gt.DERIVED
RES = ROOT / "results"
OUT = ROOT / "P3F"
OLD_CACHE = DER / "cache"
P3E_CACHE = DER / "cache_p3e"
CACHE = DER / "cache_p3f"
GT_FILE = DER / "p3e_groundtruth_refs_full.csv"
LOG = OUT / "deep_search.log"
STATE = OUT / "deep_search_state.json"
DECOYS = RES / "p3f_decoys.csv"
OUTCSV = RES / "p3f_deep_search.csv"
SETS = ["decoy", "posctl", "acad1921", "nonacad1921", "acad2426"]
SOURCES = ["crossref", "dblp", "arxiv", "s2", "openalex"]
NO_ASK_AFTER = dt.datetime(2026, 11, 12, 23, 59, tzinfo=dt.timezone.utc)
ACAD = {"J", "C", "P"}
RAM_MIN_GB = 6.0
BREAKER = 25
QUERY_CUT = 500

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def awake(on):
    """Keep the machine out of idle sleep while a pass runs (P3F2 Viec 2, LQD 2026-11-11); no effect off Windows."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


def now():
    return dt.datetime.now(dt.timezone.utc)


def stamp():
    return f"{now():%Y-%m-%dT%H:%M:%SZ}"


def log(msg):
    line = f"{stamp()} {msg}"
    print(line, flush=True)
    OUT.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def free_ram():
    return cc._free_ram()


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def install():
    """All new answers go to cache_p3f; polite intervals of Amendment 8; OpenAlex key at the session level."""
    rm.CACHE = CACHE
    CACHE.mkdir(parents=True, exist_ok=True)
    # S2 key (LQD 2026-11-09): header x-api-key only (refmatch.cached_get), <= 1 req/s, cache keys and stored URLs stay keyless
    rm.S2_API_KEY = rm.S2_API_KEY or cc.read_s2_key()
    rm.MIN_INTERVAL.update(crossref=0.5, arxiv=3.1, s2=3.0 if not rm.S2_API_KEY else 1.5, openalex=1.0)  # S2 with key: 1.5 s (LQD 2026-11-09; ~half 429 at 1.0 s)
    for b in ("wayback", "url"):
        rm.MIN_INTERVAL[b] = 1.0
        rm._locks[b] = threading.Lock()
        rm._last[b] = 0.0
    rm._sess = cc._sess
    cc.BUDGET["enabled"] = True


# ------------------------------------------------------------------------------------------- reference fields
BIB_CACHE, BBL_CACHE, BBL_YEAR = {}, {}, {}
YEAR_RE = re.compile(r"(?<![\d.])((?:19|20)\d{2})(?![\d])")
_ID_PATTERNS = [r"https?://\S+", r"\bdoi:\s*\S+", r"\b10\.\d{4,9}/\S+", r"\barXiv:\s*\S+", r"\babs/\S+", r"\b\d{4}\.\d{4,5}(v\d+)?\b"]
ID_RE = re.compile("|".join(_ID_PATTERNS), re.I)
PAGE_RE = re.compile(r"\b\d{1,5}\s*[-\u2013\u2014]+\s*\d{1,5}\b")
URL_RE = re.compile(r"https?://[^\s{}\\\"<>]+", re.I)


def bib_entry(paper, key):
    if paper not in BIB_CACHE:
        pdir = gtm.SRC / paper.replace("/", "_")
        BIB_CACHE[paper] = gtm.parse_bibs(sorted(pdir.rglob("*.bib"))) if pdir.exists() else {}
    return BIB_CACHE[paper].get(key.lower(), {})


def bbl_years(paper):
    """cite key (lower case) -> year from the raw .bbl: natbib label "(YYYY)", or biblatex \\field{year}."""
    if paper in BBL_YEAR:
        return BBL_YEAR[paper]
    out = {}
    pdir = gtm.SRC / paper.replace("/", "_")
    for b in sorted(pdir.rglob("*.bbl")) if pdir.exists() else []:
        t = gtm.read_text(b)
        for m in re.finditer(r"\\entry\{([^}]+)\}\{[^}]*\}\{[^}]*\}(.*?)\\endentry", t, re.S):
            y = re.search(r"\\field\{(?:label)?year\}\{(\d{4})", m.group(2))
            if y:
                out.setdefault(m.group(1).lower(), int(y.group(1)))
        for m in re.finditer(r"\\bibitem\s*\[((?:[^\[\]]|\[[^\]]*\])*)\]\s*%?\s*\{([^}]+)\}", t):
            y = re.search(r"\(((?:19|20)\d{2})[a-z]?\)", m.group(1))
            if y:
                out.setdefault(m.group(2).lower(), int(y.group(1)))
    BBL_YEAR[paper] = out
    return out


def year_from_text(text):
    s = PAGE_RE.sub(" ", ID_RE.sub(" ", text or ""))
    found = YEAR_RE.findall(s)
    return int(found[-1]) if found else None


def int_year(v):
    m = re.search(r"\d{4}", str(v or ""))
    return int(m.group(0)) if m else None


def template(authors, title, venue, year):
    """"{authors}. {title}. {venue}, {year}." ; a missing field is omitted with its punctuation."""
    s = ""
    if authors:
        s += f"{authors}. "
    if title:
        s += f"{title}. "
    if venue and year:
        s += f"{venue}, {year}."
    elif venue:
        s += f"{venue}."
    elif year:
        s += f"{year}."
    return " ".join(s.split())[:QUERY_CUT]


def bib_authors_text(a):
    return re.sub(r"\s+and\s+", ", ", rm.strip_latex(a or ""))


def first_url(*texts):
    for t in texts:
        m = URL_RE.search((t or "").replace("\\_", "_").replace("\\%", "%").replace("\\&", "&"))
        if m:
            return m.group(0).rstrip(".,;)]}'")
    return ""


def make_ref(row, set_name, strip_ids=False):
    """row: a dict of the ground-truth file."""
    paper, key = row["arxiv_id"], row["key"]
    title = row["title"]
    is_bib = row["ref_source"] == "bib"
    e = bib_entry(paper, key) if is_bib else {}
    item = bbl_lookup(paper, key, BBL_CACHE) or ""
    if is_bib:
        year = int_year(e.get("year")) or int_year(e.get("date"))
    else:
        year = bbl_years(paper).get(key.lower()) or year_from_text(item)
    venue_bib = next((rm.strip_latex(e.get(f, "")) for f in ("journal", "booktitle", "publisher", "howpublished",
                                                             "institution") if e.get(f, "").strip()), "")
    venue = venue_bib if is_bib else (row.get("f_journal") or row.get("f_booktitle") or "")
    if item.strip():
        q = " ".join(item.split())
        if strip_ids:
            q = " ".join(ID_RE.sub(" ", q).split())
        q = q[:QUERY_CUT]
        qsrc = "bbl"
    else:
        q, qsrc = template(bib_authors_text(row["author"]), title, venue, year or ""), "template"
    url = ""
    if not strip_ids and row["tier"] in ("S", "W"):
        url = first_url(e.get("url"), e.get("howpublished"), e.get("note")) if is_bib else first_url(item)
    return {"set": set_name, "ref_id": f"{paper}/{key}", "paper": paper, "key": key, "period": row["period"], "tier": row["tier"],
            "title": title, "surnames": rm.bib_surnames(row["author"]), "year": year, "query": q, "qsrc": qsrc, "url": url,
            "ref_source": row["ref_source"]}


# ------------------------------------------------------------------------------------------- sets
def load_gt():
    return pd.read_csv(GT_FILE, dtype=str, keep_default_na=False, low_memory=False).drop_duplicates(["arxiv_id", "key"])


def cascade_complete():
    p = ROOT / "P3E" / "cascade_passes.json"
    if not p.exists():
        return False
    st = json.loads(p.read_text(encoding="utf-8"))
    return st.get("unanswered_after_last_pass", {}).get("n_scope_unanswered") == 0


def set_rows(d, name):
    if name == "acad1921":
        return d[(d.period == "2019-21") & d.tier.isin(ACAD) & (d.def1_status == "unresolved")]
    if name == "nonacad1921":
        return d[(d.period == "2019-21") & d.tier.isin(["B", "S", "W"]) & (d.def1_status == "unresolved")]
    if name == "acad2426":
        if not (cascade_complete() or now() > NO_ASK_AFTER):
            sys.exit("set (ii) is fixed only when the Addendum-2 cascade has finished or at 2026-11-12T23:59Z")
        m = (d.period == "2024-26") & d.tier.isin(ACAD) & (d.def1_status == "unresolved")
        ok = (d.oa_skipped.map(cc.as_int) == 0) & (d.s2_pending.map(cc.as_int) == 0) & (d.dblp_missing.map(cc.as_int) == 0)
        return d[m & ok]
    raise ValueError(name)


def posctl_refs(d):
    pool = d[(d.period == "2019-21") & (d.certified_real == "1")].sort_values(["arxiv_id", "key"]).to_dict("records")
    return [make_ref(r, "posctl", strip_ids=True) for r in random.Random(50).sample(pool, 100)]


def build_decoys(d, seed=49, n=200):
    """Amendment 8 (E). Writes results/p3f_decoys.csv once; its sha256 goes to P3F/P3F_LOG.md before any decoy request."""
    pool = d[(d.period == "2019-21") & d.tier.isin(ACAD) & d.def1_status.isin(["resolved", "unresolved"])]
    pool = pool[pool.title.map(lambda t: len(rm.norm(t).split()) >= 6)].sort_values(["arxiv_id", "key"]).to_dict("records")
    n_pool = len(pool)
    random.Random(seed).shuffle(pool)
    rows, skipped = [], {"same_paper": 0, "A_no_surname_or_year": 0, "sim_ge_080": 0}
    for i in range(0, len(pool) - 1, 2):
        if len(rows) == n:
            break
        A, B = pool[i], pool[i + 1]
        if A["arxiv_id"] == B["arxiv_id"]:
            skipped["same_paper"] += 1
            continue
        ra = make_ref(A, "decoy")
        if not ra["surnames"] or not ra["year"]:
            skipped["A_no_surname_or_year"] += 1
            continue
        ta, tb = rm.norm(A["title"]).split(), rm.norm(B["title"]).split()
        title = " ".join(ta[:math.ceil(len(ta) / 2)] + tb[-(len(tb) // 2):])
        if max(rm.title_sim(title, A["title"]), rm.title_sim(title, B["title"])) >= 0.80:
            skipped["sim_ge_080"] += 1
            continue
        venue = (bib_entry(A["arxiv_id"], A["key"]).get("journal") or bib_entry(A["arxiv_id"], A["key"]).get("booktitle") or
                 A.get("f_journal") or A.get("f_booktitle") or "") if A["ref_source"] == "bib" else (A.get("f_journal") or A.get("f_booktitle") or "")
        venue = rm.strip_latex(venue)
        rows.append({"decoy_id": f"D{len(rows) + 1:03d}", "family": "D-splice", "title": title, "author": A["author"],
                     "year": ra["year"], "venue": venue, "query": template(bib_authors_text(A["author"]), title, venue, ra["year"]),
                     "tier": A["tier"], "src_a": f"{A['arxiv_id']}/{A['key']}", "src_b": f"{B['arxiv_id']}/{B['key']}"})
    if len(rows) < n:
        sys.exit(f"only {len(rows)} decoys could be built")
    rows += gen_a_rows()
    x = pd.DataFrame(rows)
    x.to_csv(DECOYS, index=False)
    meta = {"pool": n_pool, "skipped": skipped, "n_dsplice": n, "n_gen_a": int((x.family == "gen_a").sum())}
    log(f"decoys built: {meta}; sha256 {sha_file(DECOYS)}")
    with (OUT / "P3F_LOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n{stamp()} — results/p3f_decoys.csv sha256 {sha_file(DECOYS)} (TRƯỚC mọi request của mồi); {meta}\n")
    return x


def gen_a_rows():
    """The 5 planted gen_a rows of Amendment 6 (their .bbl item is the query string)."""
    import io
    import p3c_validity as p3c
    buf = p3c.fernet().decrypt(p3c.KEYENC.read_bytes())
    vsha = (p3c.KEYDIR / "p3c_validity_key.sha256").read_text().split()[0]
    if hashlib.sha256(buf).hexdigest() != vsha:
        sys.exit("STOP: V key plaintext hash differs from its commitment")
    k = pd.read_csv(io.BytesIO(buf), dtype=str, keep_default_na=False)
    ids = set(k.check_id[k.family == "gen_a"])
    s = pd.read_csv(RES / "p3c_validity_sheet.csv", dtype=str, keep_default_na=False)
    out = []
    for r in s[s.check_id.isin(ids)].sort_values("check_id").to_dict("records"):
        m = re.search(r"\byear\s*=\s*[{\"]?\s*(\d{4})", r["bib_entry"], re.I)
        year = int(m.group(1)) if m else year_from_text(r["bbl_item"])
        out.append({"decoy_id": r["check_id"], "family": "gen_a", "title": r["title"], "author": r["author"], "year": year, "venue": "",
                    "query": " ".join(r["bbl_item"].split())[:QUERY_CUT] or template(bib_authors_text(r["author"]), r["title"], "", year or ""),
                    "tier": r["tier"], "src_a": "", "src_b": ""})
    return out


def decoy_refs():
    x = pd.read_csv(DECOYS, dtype=str, keep_default_na=False)
    return [{"set": "decoy", "ref_id": r["decoy_id"], "paper": "", "key": r["decoy_id"], "period": "decoy", "tier": r["tier"], "title": r["title"],
             "surnames": rm.bib_surnames(r["author"]), "year": int(r["year"]) if r["year"] else None, "query": r["query"],
             "qsrc": "template" if r["family"] == "D-splice" else "bbl", "url": "", "ref_source": "decoy", "family": r["family"]}
            for r in x.to_dict("records")]


def load_refs(name, seed):
    d = load_gt()
    if name == "decoy":
        if not DECOYS.exists():
            build_decoys(d)
        refs = decoy_refs()
    elif name == "posctl":
        refs = posctl_refs(d)
    else:
        refs = [make_ref(r, name) for r in set_rows(d, name).sort_values(["arxiv_id", "key"]).to_dict("records")]
    random.Random(seed).shuffle(refs)  # order of asking only
    return refs


# ------------------------------------------------------------------------------------------- source requests
def req_crossref(ref):
    return ("https://api.crossref.org/works", {"query.bibliographic": ref["query"], "rows": 5, "mailto": rm.MAILTO,
                                               "select": "DOI,title,subtitle,issued,author,type"})


def req_arxiv(ref):
    return "http://export.arxiv.org/api/query", {"search_query": "all:" + rm.norm(ref["title"]), "max_results": 5}


def req_s2(ref):
    return ("https://api.semanticscholar.org/graph/v1/paper/search",
            {"query": rm.norm(ref["title"])[:300], "limit": 5, "fields": "title,year,authors,venue,publicationTypes,externalIds"})


def req_openalex(ref):
    return ("https://api.openalex.org/works", {"search": rm.norm(ref["title"])[:300], "per-page": 5, "mailto": rm.MAILTO})


REQ = {"crossref": req_crossref, "arxiv": req_arxiv, "s2": req_s2, "openalex": req_openalex}


def cands_crossref(p):
    out = []
    for it in (p or {}).get("message", {}).get("items", []):
        dp = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
        out.append({"id": it.get("DOI", "").lower(), "titles": rm._crossref_titles(it), "authors": [rm.norm(a.get("family") or a.get("name") or "") for a in it.get("author", [])],
                    "year": dp[0] if dp and dp[0] else None, "type": it.get("type", "")})
    return out


def cands_arxiv(txt):
    import feedparser
    out = []
    for e in feedparser.parse(txt or "").entries:
        if getattr(e, "title", "") and e.title != "Error":
            out.append({"id": e.id, "titles": [" ".join(e.title.split())], "authors": [rm.norm(a.get("name", "")) for a in e.get("authors", [])],
                        "year": int(e.published[:4]) if getattr(e, "published", "") else None, "type": "arxiv"})
    return out


def cands_s2(p):
    return [{"id": d.get("paperId", ""), "titles": [d.get("title") or ""], "authors": [rm.norm(a.get("name") or "") for a in d.get("authors") or []],
             "year": d.get("year"), "type": ";".join(d.get("publicationTypes") or [])} for d in (p or {}).get("data") or []]


def cands_openalex(p):
    out = []
    for w in (p or {}).get("results") or []:
        src = ((w.get("primary_location") or {}).get("source") or {})
        out.append({"id": w.get("id", ""), "titles": [w.get("title") or w.get("display_name") or ""],
                    "authors": [rm.norm((a.get("author") or {}).get("display_name") or "") for a in w.get("authorships") or []],
                    "year": w.get("publication_year"), "type": f"{w.get('type', '')}|{src.get('type', '')}"})
    return out


def cands_dblp(p):
    return [{"id": h.get("key", ""), "titles": [h.get("title", "")], "authors": [rm.norm(a) for a in h.get("authors", [])],
             "year": int(h["year"]) if str(h.get("year", "")).isdigit() else None, "type": h.get("type", "")} for h in (p or {}).get("hits", [])]


PARSE = {"crossref": cands_crossref, "arxiv": cands_arxiv, "s2": cands_s2, "openalex": cands_openalex, "dblp": cands_dblp}


def stored(source, ref):
    """Stored candidates of `source` for `ref`: a list (possibly empty) when answered, None when there is no stored answer."""
    if source == "dblp":
        if len(rm.norm(ref["title"])) < 10:
            return []
        st, p = rm.cached_get("dblp", *rm.dblp_req(ref["title"]), cache_only=True)
    else:
        st, p = rm.cached_get(source, *REQ[source](ref), cache_only=True)
    if st == -3:
        return None
    return PARSE[source](p) if st == 200 and p else []


# ------------------------------------------------------------------------------------------- the match rule
def check(ref, cand):
    sim = max([rm.title_sim(ref["title"], t) for t in cand["titles"] if t] or [0.0])
    need = 0.90 if (not ref["surnames"] or ref["year"] is None) else 0.80
    if sim < need:
        return None
    author_ok, year_ok = "na", "na"
    if ref["surnames"]:
        author_ok = bool(cand["authors"]) and any(f" {s} " in f" {n} " for s in ref["surnames"] for n in cand["authors"] if n)
        if not author_ok:
            return None
    if ref["year"] is not None:
        year_ok = cand["year"] is not None and abs(int(ref["year"]) - int(cand["year"])) <= 1
        if not year_ok:
            return None
    return {"sim": round(sim, 4), "author_ok": author_ok, "year_ok": year_ok, "record_id": cand["id"], "record_type": cand["type"]}


def best_match(ref, cands):
    hits = [m for m in (check(ref, c) for c in cands) if m]
    return max(hits, key=lambda m: m["sim"]) if hits else None


def url_public(u):
    try:
        h = up.urlsplit(u).hostname or ""
        if not h or h == "localhost" or h.endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(h)
            return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
        except ValueError:
            return True
    except ValueError:
        return False


def url_cache_file(u):
    return CACHE / "url" / f"{hashlib.sha1(u.encode()).hexdigest()}.json"


def stored_url(u):
    f = url_cache_file(u)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))["code"]
    except (ValueError, KeyError, OSError):
        return None


def check_url(u):
    """Status of a HEAD request (GET stream, closed unread, if HEAD is refused), redirects not followed; 0 = no response."""
    c = stored_url(u)
    if c is not None:
        return c
    code = 0
    if url_public(u):
        rm._wait("url")
        s = rm._sess()
        try:
            r = s.request("HEAD", u, allow_redirects=False, timeout=15)
            code = r.status_code
            r.close()
        except (requests.RequestException, ValueError, UnicodeError):
            code = 0
        if code == 0 or code in (400, 401, 403, 405, 406, 429, 500, 501, 503):
            try:
                r = requests.Session.get(s, u, stream=True, allow_redirects=False, timeout=15)
                code = r.status_code
                r.close()
            except (requests.RequestException, ValueError, UnicodeError):
                code = code or 0
    f = url_cache_file(u)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"url": u, "code": code, "fetched": stamp()}), encoding="utf-8")
    return code


def manifest_dates():
    m = pd.read_csv(ROOT / "data_manifest" / "manifest_src_version.csv", dtype=str, keep_default_na=False)
    return dict(zip(m.arxiv_id, m.src_version_date))


def wayback_req(u, to):
    return ("https://web.archive.org/cdx/search/cdx", {"url": u, "to": to.replace("-", ""), "filter": "statuscode:200", "limit": 1, "output": "json"})


def stored_wayback(u, to):
    st, p = rm.cached_get("wayback", *wayback_req(u, to), cache_only=True)
    if st == -3:
        return None
    return bool(st == 200 and p and len(p) > 1)


# ------------------------------------------------------------------------------------------- evaluation (offline)
def cascade_dois(title):
    """DOIs among the candidates of the cascade's stored Crossref title query for this title."""
    out = set()
    q = title[:500]
    for sel in ("DOI,title,subtitle,issued", "DOI,title,subtitle,issued,author"):
        params = {"query.bibliographic": q, "rows": 5, "mailto": rm.MAILTO, "select": sel}
        key = hashlib.sha1(("https://api.crossref.org/works?" + json.dumps(params, sort_keys=True)).encode()).hexdigest()
        for c in (OLD_CACHE, P3E_CACHE):
            f = c / "crossref" / f"{key}.json"
            if f.exists():
                try:
                    p = json.loads(f.read_text(encoding="utf-8")).get("payload") or {}
                    out |= {it.get("DOI", "").lower() for it in p.get("message", {}).get("items", [])}
                except (ValueError, OSError):
                    pass
    return out


def depth_reason(ref, source, m):
    if source == "crossref" and m["record_id"] not in cascade_dois(ref["title"]):
        return "1 full string"
    if m["sim"] < 0.90:
        return "2 threshold band"
    if source in ("arxiv", "s2", "openalex"):
        return "3 source or candidate beyond cascade top"
    return "4 DBLP only" if source == "dblp" else "2 threshold band"


def evaluate_ref(ref, dates):
    out = {k: ref[k] for k in ("ref_id", "period", "tier", "set")}
    out.update(state="", source="", sim="", author_ok="", year_ok="", record_id="", record_type="", depth_reason="", missing_sources="")
    if ref["url"]:
        code = stored_url(ref["url"])
        if code is None:
            out.update(state="unanswered", missing_sources="url")
            return out
        if 200 <= code < 400:
            out.update(state="found", source="url", record_id=ref["url"], record_type=f"http {code}", depth_reason="URL")
            return out
        to = dates.get(ref["paper"], "")
        wb = stored_wayback(ref["url"], to) if to else False
        if wb is None:
            out.update(state="unanswered", missing_sources="wayback")
            return out
        if wb:
            out.update(state="found", source="wayback", record_id=ref["url"], record_type="capture 200", depth_reason="URL")
            return out
        out.update(state="not found")
        return out
    missing = []
    for s in SOURCES:
        c = stored(s, ref)
        if c is None:
            missing.append(s)
            continue
        m = best_match(ref, c)
        if m:
            out.update(state="found", source=s, depth_reason=depth_reason(ref, s, m), **m)
            return out
    out.update(state="unanswered" if missing else "not found", missing_sources=";".join(missing))
    return out


def evaluate(sets=None):
    dates = manifest_dates()
    rows, seen = [], []
    for name in sets or SETS:
        if name == "decoy" and not DECOYS.exists():
            continue
        if name == "acad2426" and not (cascade_complete() or now() > NO_ASK_AFTER):
            continue
        for r in load_refs(name, 48):
            rows.append(evaluate_ref(r, dates))
        seen.append(name)
    x = pd.DataFrame(rows).sort_values(["set", "ref_id"])
    cols = ["ref_id", "period", "tier", "set", "state", "source", "sim", "author_ok", "year_ok", "record_id", "record_type", "depth_reason", "missing_sources"]
    x[cols].to_csv(OUTCSV, index=False)
    log(f"evaluate: {len(x)} rows, sets {seen}; {x.groupby(['set', 'state']).size().to_dict()}")
    return x


# ------------------------------------------------------------------------------------------- asking
def load_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


def needs_after(ref, sources):
    """False once a source earlier in `sources` already has a matching stored candidate."""
    for s in sources:
        c = stored(s, ref)
        if c is not None and best_match(ref, c):
            return False
    return True


def run_dblp(refs):
    ram = free_ram()
    if ram is not None and ram < RAM_MIN_GB:
        log(f"dblp: free RAM {ram} GB < {RAM_MIN_GB} GB; DBLP not run in this pass (Amendment 8; recorded, to be redone)")
        return False
    import dblp_offline as dbl
    todo = [r["title"] for r in refs if not r["url"] and needs_after(r, ["crossref"]) and stored("dblp", r) is None]
    log(f"dblp: {len(todo)} titles to match (RAM {ram} GB)")
    if todo:
        log(f"dblp: {dbl.match(todo)}")
    return True


def ask_source(name, source, refs, state):
    order = SOURCES[:SOURCES.index(source)]
    todo = [r for r in refs if not r["url"] and stored(source, r) is None and needs_after(r, order)]
    passes = state.setdefault(name, {}).setdefault(source, {"n": 0, "last_end": ""})
    if not todo:
        return
    if source in ("arxiv", "s2") and passes["n"] >= 3:
        log(f"{name}/{source}: 3 passes used; {len(todo)} requests remain unanswered")
        return
    if source in ("arxiv", "s2") and passes["last_end"]:
        gap = (now() - dt.datetime.strptime(passes["last_end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)).total_seconds() / 60
        if gap < 60 and passes.get("broke"):
            log(f"{name}/{source}: last pass stopped by the failure breaker {gap:.0f} min ago; next pass >= 60 min after it")
            return
    log(f"{name}/{source}: start, {len(todo)} requests, free RAM {free_ram()} GB")
    fails = 0
    broke = False
    for i, r in enumerate(todo, 1):
        if now() > NO_ASK_AFTER:
            log(f"{name}/{source}: end date reached; asking stops")
            break
        if source == "openalex" and rm.OA_EXHAUSTED.is_set():
            log(f"{name}/openalex: budget stop (header) or refusal; asking stops for this pass")
            break
        url, params = REQ[source](r)
        st, _ = rm.cached_get(source, url, params, tries=3)
        if source == "s2" and st == 403 and rm.S2_API_KEY:  # a refused key is not one of the 3 passes (LQD 2026-11-09)
            log(f"{name}/s2: key refused (HTTP 403) at {i}/{len(todo)}; asking stops, pass NOT counted")
            return
        if source == "openalex" and "search_credits" not in state and cc.BUDGET.get("credits_per_call") is not None and st == 200:
            state["search_credits"] = cc.BUDGET["credits_per_call"]
            log(f"openalex search: credits per call from first response = {cc.BUDGET['credits_per_call']}")
        if st in (-1, -2) or st >= 402 and st != 404:
            fails += 1
            if source in ("arxiv", "s2") and fails >= BREAKER:
                log(f"{name}/{source}: {BREAKER} consecutive failures at {i}/{len(todo)}; pass stops")
                broke = True
                break
        else:
            fails = 0
        if i % 100 == 0:
            log(f"{name}/{source}: {i}/{len(todo)}; requests {dict(cc.STATS.get('requests', {}))}")
    passes.update(n=passes["n"] + 1, last_end=stamp(), broke=broke)
    log(f"{name}/{source}: end; requests {dict(cc.STATS.get('requests', {}))}; refusals {dict(cc.STATS.get('refusals', {}))}; first refusal "
        f"{dict(cc.STATS.get('first_refusal', {}))}; free RAM {free_ram()} GB")


def ask_urls(name, refs):
    dates = manifest_dates()
    todo = [r for r in refs if r["url"]]
    log(f"{name}/url: {len(todo)} references with a URL")
    for i, r in enumerate(todo, 1):
        code = check_url(r["url"])
        if not (200 <= code < 400):
            to = dates.get(r["paper"], "")
            if to:
                rm.cached_get("wayback", *wayback_req(r["url"], to), tries=3)
        if i % 100 == 0:
            log(f"{name}/url: {i}/{len(todo)}")


def run_set(name, seed, no_openalex):
    refs = load_refs(name, seed)
    state = load_state()
    cc._reset_stats()
    rm.OA_EXHAUSTED.clear()
    log(f"=== set {name}: {len(refs)} refs; OpenAlex {'not asked in this pass' if no_openalex else ('key' if cc.has_key() else 'keyless')}; S2 "
        f"{'key' if rm.S2_API_KEY else 'keyless'}; free RAM {free_ram()} GB")
    ask_urls(name, refs)
    ask_source(name, "crossref", refs, state)
    if not run_dblp(refs):
        save_state(state)
        return
    for s in ("arxiv", "s2"):
        ask_source(name, s, refs, state)
    if not no_openalex:
        ask_source(name, "openalex", refs, state)
    save_state(state)
    evaluate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=48)
    ap.add_argument("--resume", action="store_true", help="stored answers are reused (always true; kept for the documented command)")
    ap.add_argument("--set", choices=SETS)
    ap.add_argument("--no-openalex", action="store_true")
    ap.add_argument("--evaluate", action="store_true")
    ap.add_argument("--dry", type=int, default=0)
    args = ap.parse_args()
    install()
    cc._OA_KEY["value"] = cc.read_env_key()
    if args.evaluate:
        evaluate()
        return
    if not args.set:
        ap.error("--set or --evaluate is required")
    if args.dry:
        rm.OFFLINE = True
        refs = load_refs(args.set, args.seed)
        print(len(refs), "refs")
        for r in refs[:args.dry]:
            print({k: (v if k != "query" else v[:160]) for k, v in r.items() if k in ("ref_id", "tier", "title", "surnames", "year", "query", "qsrc", "url", "family")})
        print("qsrc", pd.Series([r["qsrc"] for r in refs]).value_counts().to_dict(), "no year", sum(r["year"] is None for r in refs),
              "no surname", sum(not r["surnames"] for r in refs), "url", sum(bool(r["url"]) for r in refs))
        return
    awake(True)
    try:
        run_set(args.set, args.seed, args.no_openalex)
    finally:
        awake(False)


if __name__ == "__main__":
    main()
