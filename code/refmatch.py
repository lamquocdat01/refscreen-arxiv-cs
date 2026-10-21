"""Shared reference-matching utilities for topic 43 (cache, polite HTTP, title normalisation, registry lookups).

Backends
  crossref : https://api.crossref.org  (works/<doi>; works?query.bibliographic=...)   polite pool, mailto=noreply@example.org
  s2       : https://api.semanticscholar.org/graph/v1/paper/search/match  (keyless shared pool, ~1 req/s)
  arxiv    : http://export.arxiv.org/api/query (id_list / ti: search)       >= 3 s between requests
  openalex : https://api.openalex.org  works/doi:<doi> is free; search costs budget (keyless: $0.10/day per IP)
  datacite : https://api.datacite.org/dois/<doi>
Every response is cached as JSON under $THS_DATASETS/_derived/43/cache/<backend>/<sha1>.json and never re-fetched.
"""
import hashlib
import json
import os
import random
import re
import threading
import time
import unicodedata
from pathlib import Path

import requests
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

UA = "refscreen-43/0.1 (research; mailto:noreply@example.org)"
MAILTO = "noreply@example.org"
CACHE = Path(os.environ.get("THS_DATASETS", r"D:\Datasets")) / "_derived" / "43" / "cache"
SIM_THRESHOLD = 0.9
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")
S2_API_KEY = os.environ.get("S2_API_KEY", "")
# PREREG_AMENDMENT_1: Crossref polite pool <= 10 req/s; S2 1 req/s; arXiv 1 req/3 s; OpenAlex keyless <= 1 req/s
# Crossref polite pool as served on 2026-10-18: x-rate-limit-limit 3 / 1 s, x-concurrency-limit 3
MIN_INTERVAL = {"crossref": 0.34, "s2": 1.0, "arxiv": 3.1, "openalex": 0.2 if OPENALEX_API_KEY else 1.0,
                "datacite": 0.3}
_locks = {k: threading.Lock() for k in MIN_INTERVAL}
_last = {k: 0.0 for k in MIN_INTERVAL}
_session = threading.local()
_concurrency = {"crossref": threading.BoundedSemaphore(3)}
CR_AUTHORS = {}  # DOI -> author surnames seen in Crossref search answers (def 2 without a second request)
# keyless OpenAlex: the first 429 / budget refusal stops all further OpenAlex calls in this process ("oa_skipped")
OA_EXHAUSTED = threading.Event()
# title search costs budget: enabled explicitly (OPENALEX_SEARCH=1) or whenever a key is set (PREREG_43.md §4)
OPENALEX_SEARCH_ENABLED = os.environ.get("OPENALEX_SEARCH", "0") == "1" or bool(OPENALEX_API_KEY)
NO_ARXIV = os.environ.get("NO_ARXIV", "0") == "1"  # testing only: skip arXiv calls while another job uses the budget
# interim replay (--interim): stored answers only, never a request; set by the caller before any lookup
OFFLINE = False


def _sess():
    if not hasattr(_session, "s"):
        _session.s = requests.Session()
        _session.s.headers["User-Agent"] = UA
    return _session.s


def _wait(backend):
    with _locks[backend]:
        gap = time.time() - _last[backend]
        if gap < MIN_INTERVAL[backend]:
            time.sleep(MIN_INTERVAL[backend] - gap)
        _last[backend] = time.time()


def cached_get(backend, url, params=None, tries=6, cache_only=False):
    """GET JSON (or text for arXiv) with on-disk cache. Returns (status_code, payload). 404 is cached as a result.
    Special statuses (never cached): -1 failed after retries; -2 OpenAlex skipped (keyless budget refused);
    -3 not in cache (cache_only=True)."""
    key = hashlib.sha1((url + "?" + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    cf = CACHE / backend / f"{key}.json"
    if cf.exists():
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
            return d["status"], d["payload"]
        except (ValueError, KeyError, OSError):  # truncated file from a killed run -> re-fetch
            pass
    if cache_only:
        return -3, None
    if OFFLINE:  # a missing OpenAlex answer reads as skipped, any other as a failed query (-> rate-limited)
        return (-2 if backend == "openalex" else -1), None
    oa_keyless = backend == "openalex" and not OPENALEX_API_KEY
    if oa_keyless and OA_EXHAUSTED.is_set():
        return -2, None
    cf.parent.mkdir(parents=True, exist_ok=True)
    headers = {"x-api-key": S2_API_KEY} if backend == "s2" and S2_API_KEY else None
    wait = 5.0
    for _ in range(tries):
        _wait(backend)
        sem = _concurrency.get(backend)
        try:
            if sem:
                sem.acquire()
            # arXiv now 301-redirects http -> https; request https directly but keep the http URL as cache key
            r = _sess().get(url.replace("http://export.arxiv.org", "https://export.arxiv.org"), params=params,
                            headers=headers, timeout=60)
        except requests.RequestException:
            if sem:
                sem.release()
            time.sleep(wait)
            wait = min(wait * 2, 120)
            continue
        if sem:
            sem.release()
        if oa_keyless and (r.status_code == 429 or (r.status_code in (402, 403) and
                                                     re.search(r"budget|credit|limit|quota", r.text, re.I))):
            if not OA_EXHAUSTED.is_set():
                OA_EXHAUSTED.set()
                print(f"  ! OpenAlex keyless refused (HTTP {r.status_code}); OpenAlex skipped from now on", flush=True)
            return -2, None
        if r.status_code in (429, 500, 502, 503, 504):
            ra = r.headers.get("Retry-After")
            time.sleep(float(ra) if ra and ra.replace(".", "").isdigit() else wait + random.random())
            wait = min(wait * 2, 120)
            continue
        if r.status_code == 200:
            try:
                payload = r.text if backend == "arxiv" else r.json()
            except ValueError:  # HTML error page with status 200 -> transient
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
        elif r.status_code in (400, 404):
            payload = None
        else:
            return r.status_code, None  # not cached (e.g. 403 budget exhausted)
        tmp = cf.with_suffix(f".{threading.get_ident()}.tmp")  # atomic: a kill never leaves a half-written cache file
        tmp.write_text(json.dumps({"url": r.url, "status": r.status_code, "payload": payload,
                                   "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}),
                       encoding="utf-8")
        os.replace(tmp, cf)
        return r.status_code, payload
    return -1, None


# ---------------------------------------------------------------- text normalisation
# letter accents (\u \v \H \t \c \d \b \k) only when not the start of a longer command (\textemdash, \url):
# PREREG_AMENDMENT_2 (a)
_LATEX_ACCENT = re.compile(r"\\(?:[`'^\"~=.]|[uvHtcdbk](?![A-Za-z]))\s*\{?([A-Za-z])\}?")
_LATEX_CMD_ARG = re.compile(r"\\[a-zA-Z]+\*?\s*\{([^{}]*)\}")
_LATEX_CMD = re.compile(r"\\[a-zA-Z]+\*?")
_TEXTSYM = {"textemdash": " - ", "textendash": "-", "textquoteright": "'", "textquoteleft": "'"}
_LATEX_TEXTSYM = re.compile(r"\\(" + "|".join(_TEXTSYM) + r")(?![A-Za-z])\s*(?:\{\})?")


def strip_latex(s):
    if not s:
        return ""
    s = s.replace("\\&", "&").replace("~", " ").replace("--", "-")
    s = _LATEX_TEXTSYM.sub(lambda m: _TEXTSYM[m.group(1)], s)
    s = _LATEX_ACCENT.sub(r"\1", s)
    for _ in range(4):
        s2 = _LATEX_CMD_ARG.sub(r"\1", s)
        if s2 == s:
            break
        s = s2
    s = _LATEX_CMD.sub(" ", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    return " ".join(s.split())


# JATS / MathML / HTML tags in registry titles (<sup>2</sup>, <i>, <mml:math>): PREREG_AMENDMENT_2 (b)
_MARKUP = re.compile(r"</?(?:[A-Za-z]+:)?[A-Za-z][A-Za-z0-9]*(?:\s+[\w:.-]+\s*=\s*\"[^\"]*\")*\s*/?>")


def norm(s):
    s = _MARKUP.sub(" ", s or "")
    s = strip_latex(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def title_sim(a, b):
    """max(normalised Levenshtein similarity, token Jaccard) of normalised titles."""
    return title_sim_norm(norm(a), norm(b))


def title_sim_norm(na, nb):
    """title_sim on titles that are already normalised (norm())."""
    if not na or not nb:
        return 0.0
    lev = Levenshtein.normalized_similarity(na, nb)
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb)
    return max(lev, jac)


def contained_sim(title, refstring):
    """How well a registry title appears inside a rendered reference string (partial ratio, normalised)."""
    nt, nr = norm(title), norm(refstring)
    if len(nt) < 10 or not nr:
        return 0.0
    return fuzz.partial_ratio(nt, nr) / 100.0


# ---------------------------------------------------------------- identifiers
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>{}]+)", re.I)
ARXIV_NEW = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])")
ARXIV_OLD = re.compile(r"\b([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?\b")


def clean_doi(d):
    if not d:
        return ""
    d = d.strip().strip("{}").strip()
    d = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    m = DOI_RE.search(d)
    if not m:
        return ""
    return m.group(1).rstrip(".,;)").lower()


def arxiv_from_text(s):
    if not s:
        return ""
    m = re.search(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", s, re.I)
    if m:
        return m.group(1)
    m = re.search(r"arxiv(?:\.org/(?:abs|pdf)/|\s*:\s*|\s+preprint\s+(?:arxiv:)?\s*|\s*abs/|\s+)\s*(\d{4}\.\d{4,5})",
                  s, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(?:corr|arxiv)[^0-9]{0,20}abs/(\d{4}\.\d{4,5})", s, re.I)
    if m:
        return m.group(1)
    return ""


# ---------------------------------------------------------------- registry lookups
def crossref_doi(doi):
    st, p = cached_get("crossref", f"https://api.crossref.org/works/{doi}", {"mailto": MAILTO})
    if st == 200 and p:
        it = p.get("message", {})
        return _crossref_titles(it)
    return None


def _crossref_titles(it):
    t = (it.get("title") or [""])[0]
    sub = (it.get("subtitle") or [""])
    full = t + (": " + sub[0] if sub and sub[0] else "")
    return [x for x in {t, full} if x]


def openalex_doi(doi):
    st, p = cached_get("openalex", f"https://api.openalex.org/works/doi:{doi}", {"mailto": MAILTO})
    if st == 200 and p:
        return [p.get("title") or p.get("display_name") or ""]
    return None


def datacite_doi(doi):
    st, p = cached_get("datacite", f"https://api.datacite.org/dois/{doi}")
    if st == 200 and p:
        ts = p.get("data", {}).get("attributes", {}).get("titles", [])
        return [t.get("title", "") for t in ts if t.get("title")]
    return None


def resolve_doi(doi):
    """Returns (backend, titles) of the first registry that knows the DOI, or (None, None)."""
    if doi.startswith("10.48550/arxiv."):
        aid = doi.split("arxiv.", 1)[1]
        t = arxiv_ids([aid]).get(aid)
        return ("arxiv", [t]) if t else (None, None)
    for name, fn in (("crossref", crossref_doi), ("openalex", openalex_doi), ("datacite", datacite_doi)):
        t = fn(doi)
        if t:
            return name, t
    return None, None


def arxiv_ids(ids):
    """Batch title lookup for arXiv ids (cached per batch). Returns {id: title}."""
    import feedparser
    out = {}
    if NO_ARXIV:
        return out
    ids = sorted(set(i for i in ids if i))
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        st, txt = cached_get("arxiv", "http://export.arxiv.org/api/query",
                             {"id_list": ",".join(chunk), "max_results": len(chunk)})
        if st != 200 or not txt:
            continue
        for e in feedparser.parse(txt).entries:
            aid = re.sub(r"v\d+$", "", e.id.rsplit("/abs/", 1)[-1])
            if getattr(e, "title", "") and e.title != "Error":
                out[aid] = " ".join(e.title.split())
    return out


def arxiv_titles_from_cache():
    """{arXiv id: title} from every stored arXiv answer (id_list batches and ti: searches); no request."""
    import feedparser
    out = {}
    for cf in (CACHE / "arxiv").glob("*.json"):
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if d.get("status") != 200 or not d.get("payload"):
            continue
        for e in feedparser.parse(d["payload"]).entries:
            if getattr(e, "title", "") and e.title != "Error" and getattr(e, "id", ""):
                out.setdefault(re.sub(r"v\d+$", "", e.id.rsplit("/abs/", 1)[-1]), " ".join(e.title.split()))
    return out


def crossref_search(query, rows=5, cache_only=False):
    """Stored answers of the original request are reused; a new request also selects `author`, so def 2 needs no
    second Crossref call (CR_AUTHORS)."""
    base = {"query.bibliographic": query[:500], "rows": rows, "mailto": MAILTO}
    st, p = cached_get("crossref", "https://api.crossref.org/works", dict(base, select="DOI,title,subtitle,issued"),
                       cache_only=True)
    if st == -3:
        st, p = cached_get("crossref", "https://api.crossref.org/works",
                           dict(base, select="DOI,title,subtitle,issued,author"), cache_only=cache_only)
        if st == 200 and p:
            for it in p.get("message", {}).get("items", []):
                if it.get("author"):
                    CR_AUTHORS[it.get("DOI", "").lower()] = [norm(a.get("family") or a.get("name") or "")
                                                             for a in it["author"]]
    if st == 200 and p:
        return [(it.get("DOI", ""), _crossref_titles(it)) for it in p.get("message", {}).get("items", [])]
    return [] if st in (200, 400, 404) else None


def _cache_file(backend, url, params):
    key = hashlib.sha1((url + "?" + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    return CACHE / backend / f"{key}.json"


def is_cached(backend, url, params=None):
    return _cache_file(backend, url, params).exists()


def s2_match_req(title):
    return ("https://api.semanticscholar.org/graph/v1/paper/search/match",
            {"query": norm(title)[:300], "fields": "title,year,externalIds"})


def s2_match(title, cache_only=False, tries=6):
    """None = failed; "not-cached" when cache_only and no stored answer (PREREG_AMENDMENT_1, round 1)."""
    st, p = cached_get("s2", *s2_match_req(title), tries=tries, cache_only=cache_only)
    if st == -3:
        return "not-cached"
    if st == 200 and p:
        return [(d.get("paperId", ""), [d.get("title", "")]) for d in p.get("data", [])]
    return [] if st in (200, 400, 404) else None


def _arxiv_ti_req(title):
    return "http://export.arxiv.org/api/query", {"search_query": f'ti:"{norm(title)}"', "max_results": 5}


def arxiv_title_search(title):
    import feedparser
    q = norm(title)
    if not q or NO_ARXIV:
        return [] if not q else None
    st, txt = cached_get("arxiv", *_arxiv_ti_req(title))
    if st != 200 or not txt:
        return None
    return [(e.id, [" ".join(e.title.split())]) for e in feedparser.parse(txt).entries if getattr(e, "title", "")]


def arxiv_search_authors(title, rid):
    """Author names of record `rid` from the stored ti: answer (no new request); None if not available."""
    import feedparser
    st, txt = cached_get("arxiv", *_arxiv_ti_req(title), cache_only=True)
    if st != 200 or not txt:
        return None
    for e in feedparser.parse(txt).entries:
        if e.id == rid:
            return [norm(a.get("name", "")) for a in e.get("authors", [])] or None
    return None


# DBLP (PREREG_AMENDMENT_3): offline, from the XML dump (the search API is behind a bot wall); answers are written
# by dblp_offline.py match into the normal cache and only ever read here
DBLP_RELEASE = os.environ.get("DBLP_RELEASE", "2026-10-19")


def dblp_req(title):
    return f"dblp-offline://{DBLP_RELEASE}/search", {"q": norm(title)[:300]}


def cache_put(backend, url, params, status, payload):
    cf = _cache_file(backend, url, params)
    cf.parent.mkdir(parents=True, exist_ok=True)
    tmp = cf.with_suffix(f".{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps({"url": url, "status": status, "payload": payload,
                               "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}), encoding="utf-8")
    os.replace(tmp, cf)


def dblp_search(title):
    """Stored offline answer; "not-cached" if dblp_offline.py match has not answered this title."""
    st, p = cached_get("dblp", *dblp_req(title), cache_only=True)
    if st == -3:
        return "not-cached"
    if st == 200 and p:
        return [(h.get("key", ""), [h.get("title", "")]) for h in p.get("hits", [])]
    return []


def dblp_search_authors(title, rid):
    st, p = cached_get("dblp", *dblp_req(title), cache_only=True)
    if st != 200 or not p:
        return None
    for h in p.get("hits", []):
        if h.get("key") == rid:
            return [norm(a) for a in h.get("authors", [])] or None
    return None


def _openalex_req(title):
    return ("https://api.openalex.org/works",
            dict({"filter": f"title.search:{norm(title)[:200]}", "per-page": 5, "mailto": MAILTO},
                 **({"api_key": OPENALEX_API_KEY} if OPENALEX_API_KEY else {})))


def openalex_search(title, force=False):
    """force=True: query even without a key (keyless pool, PREREG_AMENDMENT_1); returns "skipped" once refused."""
    if not (OPENALEX_SEARCH_ENABLED or force):
        return None
    st, p = cached_get("openalex", *_openalex_req(title), tries=3)
    if st == -2:
        return "skipped"
    if st == 200 and p:
        return [(w.get("id", ""), [w.get("title") or ""]) for w in p.get("results", [])]
    return [] if st in (200, 400, 404) else None


def openalex_search_authors(title, rid):
    """Author names of work `rid` from the stored title-search answer (no new request)."""
    st, p = cached_get("openalex", *_openalex_req(title), cache_only=True)
    if st != 200 or not p:
        return None
    for w in p.get("results", []):
        if w.get("id") == rid:
            return [norm((a.get("author") or {}).get("display_name") or "") for a in w.get("authorships", [])] or None
    return None


def best_sim(candidates, title=None, refstring=None):
    """Best similarity of any candidate title to `title` (title_sim) or contained in `refstring` (contained_sim)."""
    best, best_id = 0.0, ""
    for cid, titles in candidates or []:
        for t in titles:
            s = title_sim(t, title) if title else contained_sim(t, refstring)
            if s > best:
                best, best_id = s, cid
    return best, best_id


def select_render_papers(manifest_rows, seed, per_field=6):
    """Deterministic choice of the render-strip pilot: pilot-set papers with a .bib, `per_field` per field."""
    rng = random.Random(seed)
    out = []
    for f in ["cs.CV", "cs.LG", "cs.CL", "cs.NI", "cs.CR"]:
        c = sorted(r["arxiv_id"] for r in manifest_rows
                   if r["set"] == "pilot" and r["field"] == f and r["status"] == "kept" and int(r["n_bib"] or 0) > 0)
        rng.shuffle(c)
        out += c[:per_field]
    return sorted(out)


# ---------------------------------------------------------------- citation parsers (GROBID / anystyle), see env/SETUP.md
GROBID_URL = os.environ.get("GROBID_URL", "http://localhost:8070")


def grobid_parse(strings, batch=40):
    """Parse raw citation strings with GROBID processCitationList (form-urlencoded). Returns list of dicts
    {title, doi, arxiv} aligned with `strings` (empty dict on failure)."""
    import xml.etree.ElementTree as ET
    ns = {"t": "http://www.tei-c.org/ns/1.0"}
    out = []
    for i in range(0, len(strings), batch):
        chunk = strings[i:i + batch]
        res = [{} for _ in chunk]
        try:
            r = requests.post(GROBID_URL + "/api/processCitationList",
                              data=[("citations", s or " ") for s in chunk] + [("consolidateCitations", "0")],
                              headers={"Accept": "application/xml"}, timeout=300)
            if r.status_code == 200:
                root = ET.fromstring("<root>" + re.sub(r"<\?xml[^>]*\?>", "", r.text) + "</root>")
                bs = root.findall(".//t:biblStruct", ns)
                for j, b in enumerate(bs[:len(chunk)]):
                    t = b.find(".//t:analytic/t:title", ns)
                    if t is None or not "".join(t.itertext()).strip():
                        t = b.find(".//t:monogr/t:title", ns)
                    doi = b.find(".//t:idno[@type='DOI']", ns)
                    ax = b.find(".//t:idno[@type='arXiv']", ns)
                    res[j] = {"title": " ".join("".join(t.itertext()).split()) if t is not None else "",
                              "doi": doi.text.strip() if doi is not None and doi.text else "",
                              "arxiv": ax.text.strip() if ax is not None and ax.text else ""}
                    # extra TEI fields for the P1 tier rule (PREREG_43.md §2); absent -> ""
                    def _txt(path):
                        el = b.find(path, ns)
                        return " ".join("".join(el.itertext()).split()) if el is not None else ""
                    ptr = b.find(".//t:ptr", ns)
                    sur = b.find(".//t:analytic/t:author/t:persName/t:surname", ns)
                    if sur is None:
                        sur = b.find(".//t:monogr/t:author/t:persName/t:surname", ns)
                    res[j]["first_author_surname"] = " ".join("".join(sur.itertext()).split()) if sur is not None else ""
                    res[j].update(journal=_txt(".//t:monogr/t:title[@level='j']"),
                                  booktitle=_txt(".//t:monogr/t:title[@level='m']") or _txt(".//t:meeting"),
                                  publisher=_txt(".//t:monogr/t:imprint/t:publisher"),
                                  url=ptr.get("target", "") if ptr is not None else "",
                                  has_analytic=int(b.find(".//t:analytic/t:title", ns) is not None))
        except (requests.RequestException, ET.ParseError):
            pass
        out += res
    return out


def anystyle_parse(strings, workdir):
    """Parse citation strings with anystyle (WSL). Returns list of {title} aligned with `strings`."""
    import subprocess
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    f = workdir / "anystyle_in.txt"
    f.write_text("\n".join((s or "-").replace("\n", " ") for s in strings) + "\n", encoding="utf-8")
    wsl_path = "/mnt/" + str(f.resolve()).replace(":", "").replace("\\", "/")
    wsl_path = wsl_path[:5] + wsl_path[5].lower() + wsl_path[6:]
    p = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "--", "anystyle", "-f", "json", "parse", wsl_path],
                       capture_output=True, timeout=1800)
    try:
        data = json.loads(p.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return [{} for _ in strings]
    out = []
    for d in data:
        t = d.get("title") or d.get("container-title") or [""]
        out.append({"title": (t[0] if isinstance(t, list) else str(t)).strip(" .,")})
    out += [{} for _ in range(len(strings) - len(out))]
    return out[:len(strings)]


# ---------------------------------------------------------------- author check (u0 definition 2, P0B)
def bib_surnames(author_field):
    """Normalised surnames from a BibTeX author field ("Last, First and First Last and others")."""
    out = []
    for a in re.split(r"\s+and\s+", author_field or ""):
        a = a.strip()
        if not a or a.lower() in ("others", "et al", "et al."):
            continue
        a = strip_latex(a)
        sur = a.split(",", 1)[0] if "," in a else (a.split()[-1] if a.split() else "")
        sur = norm(sur)
        if sur:
            out.append(sur)
    return out


def crossref_doi_authors(doi):
    st, p = cached_get("crossref", f"https://api.crossref.org/works/{doi}", {"mailto": MAILTO})
    if st == 200 and p:
        return [norm(a.get("family") or a.get("name") or "") for a in p.get("message", {}).get("author", [])]
    return None


def s2_paper_authors(pid):
    st, p = cached_get("s2", f"https://api.semanticscholar.org/graph/v1/paper/{pid}", {"fields": "authors"})
    if st == 200 and p:
        return [norm(a.get("name") or "") for a in p.get("authors", [])]
    return None


def arxiv_entry_authors(entry_id):
    aid = re.sub(r"v\d+$", "", entry_id.rsplit("/abs/", 1)[-1])
    import feedparser
    st, txt = cached_get("arxiv", "http://export.arxiv.org/api/query", {"id_list": aid, "max_results": 1})
    if st != 200 or not txt:
        return None
    es = feedparser.parse(txt).entries
    return [norm(a.get("name", "")) for a in es[0].get("authors", [])] if es else None


def first_author_match(bib_sur, reg_names):
    """True if the first .bib surname occurs (as whole tokens) in any registry author name."""
    if not bib_sur or not reg_names:
        return None
    s = f" {bib_sur[0]} "
    return any(s in f" {n} " for n in reg_names if n)
