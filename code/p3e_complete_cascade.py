#!/usr/bin/env python3
"""Topic 43 / P3E (PREREG_AMENDMENT_7 (a)): complete the registered cascade on every reference that a backend never
answered (OpenAlex keyless refusals, S2 rate limits).

Target set: def-1 state resolved / unresolved / rate-limited and (oa_skipped = 1 or s2_pending = 1 or dblp_missing = 1
or def-1 rate-limited), read from $THS_DATASETS/_derived/43/p2_groundtruth_refs_full.csv (P1 + P2 night retry).
Each target goes through ground_truth_p1.resolve_ref again (registered order, threshold 0.9, def 1 / def 2), with
live OpenAlex and live S2. Stored answers are read from _derived/43/cache/ (read-only); new answers are written only to
_derived/43/cache_p3e/.
Order (Amendment 7): groups 1..6 = 2019-21 academic unresolved, 2024-26 academic unresolved, 2019-21 non-academic
unresolved, 2024-26 non-academic unresolved, rate-limited, resolved; seed-42 permutation inside a group; one worker,
so the order is exact. Passes: <= 3; pass 2 starts 60 min after pass 1 ends; pass 3 at the first 00:10 UTC after
pass 2 ends; a pass asks only the references still lacking an answer.
Keys: OPENALEX_API_KEY / S2_API_KEY from the environment, never printed or written. mailto = noreply@example.org.
Outputs: P3E/cascade_targets.csv (one row per distinct target: ref_id, tier, period, missing backends, reason, group,
         order, pass in which the missing backends answered, state before/after),
         P3E/cascade_run.log (appended), P3E/cascade_passes.json (pass times, first refusals, counts),
         $THS_DATASETS/_derived/43/p3e_groundtruth_refs_full.csv (input with the target rows re-resolved).
Usage: python code/p3e_complete_cascade.py --seed 42 --resume [--max-passes 10] [--no-wait]
       --resume: passes already recorded in cascade_passes.json are not repeated (answers come from the caches)
       --no-wait: testing only; do not sleep until the scheduled start of the next pass, stop instead

Amendment 7 Addendum A (P3E/AMENDMENT_7_ADDENDUM.md, 2026-11-08; procedural deviation): passes 1-2 as above; from
pass 3 on, one pass per UTC day at/after 00:10 UTC, keyless, asking only the 2019-21 academic (J/C/P) targets
(--scope acad1921, default) in the registered order; after every OpenAlex response X-RateLimit-Remaining is read and
OpenAlex asking stops for the day when it falls below max(2 x credits per call, 5 % of X-RateLimit-Limit); asking
ends when the subset is complete or at --deadline (2026-11-13T23:59Z). The pass in which a reference was answered is
kept in P3E/cascade_answered.json (replay does not re-attribute). Free RAM < 6 GB is logged, never a reason to skip.

Amendment 7 Addendum 2 (P3E/AMENDMENT_7_ADDENDUM_2.md, 2026-11-08; procedural deviation): from pass 4 on, the OpenAlex
key of ROOT/.env is used (read only by read_env_key() in this file; never printed or written; added at the session
level so cache keys stay keyless and stored URLs are scrubbed), the scope is the academic (J/C/P) targets of BOTH
periods, 2019-21 first and then 2024-26, each in the registered order; same header budget stop; pass 4 starts at
launch, later passes at the next 00:10 UTC (60 min after a refusal); 2024-26 references are not asked after
2026-11-12T23:59Z, 2019-21 references not after 2026-11-13T23:59Z (Addendum A). --probe sends one request only.
"""
import argparse
import datetime as dt
import hashlib
import json
import random
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402
import ground_truth_p1 as gt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DER = gt.DERIVED
OLD_CACHE, NEW_CACHE = rm.CACHE, DER / "cache_p3e"
OUT_DIR = ROOT / "P3E"
LOG = OUT_DIR / "cascade_run.log"
PASSES = OUT_DIR / "cascade_passes.json"
ANSWERED = OUT_DIR / "cascade_answered.json"  # ref_id -> pass in which its missing backends answered (Addendum A)
ADDENDUM_FROM_PASS = 3  # Addendum A applies from pass 3 on
ADDENDUM2_FROM_PASS = 4  # Addendum 2 (key, academic both periods) applies from pass 4 on; pass 4 starts at launch
# PREREG 4: 3 retry rounds after the first pass, then excluded and counted (LQD 2026-11-09). A 2024-26 reference still
# rate-limited has had them after pass 6: passes 2, 5 and 6 (Addendum A's pass 3 excluded 2024-26; pass 4 stopped before group 5)
RL_LAST_ROUND_PASS = 6
DEADLINES = {"2019-21": "2026-11-13T23:59:00Z",  # Addendum A
             "2024-26": "2026-11-12T23:59:00Z"}  # Addendum 2
RAM_WARN_GB = 6.0

# ------------------------------------------------------------------ OpenAlex key (Addendum 2)
# The key is read ONLY here, from ROOT/.env, and is never printed, logged or written. It is added to the OpenAlex
# request at the session level, so (i) cache keys stay those of the keyless request (stored answers replay without a
# request) and (ii) the URL stored in a cache file is scrubbed of the key.
ENV_FILE = ROOT / ".env"
_OA_KEY = {"value": ""}


def read_env_key(name="OPENALEX_API_KEY"):
    """Value of `name` in ROOT/.env (self-parsed; no python-dotenv). Callers must never print or store it."""
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if k.startswith("export "):
            k = k[7:].strip()
        if k == name:
            return v.strip().strip('"').strip("'")
    return ""


def read_s2_key():
    """Semantic Scholar key of ROOT/.env (LQD's file names it `S2 API Key`; `S2_API_KEY` also accepted). Never print or store it."""
    return read_env_key("S2_API_KEY") or read_env_key("S2 API Key")


def has_key():
    return bool(_OA_KEY["value"])


def _scrub(url):
    """URL without api_key (and without the key value anywhere)."""
    import urllib.parse as up
    p = up.urlsplit(url)
    q = [(a, b) for a, b in up.parse_qsl(p.query, keep_blank_values=True) if a.lower() not in ("api_key", "api-key")]
    out = up.urlunsplit((p.scheme, p.netloc, p.path, up.urlencode(q), p.fragment))
    if _OA_KEY["value"]:
        out = out.replace(_OA_KEY["value"], "")
    return out
GROUPS = {1: "2019-21 academic unresolved", 2: "2024-26 academic unresolved", 3: "2019-21 non-academic unresolved",
          4: "2024-26 non-academic unresolved", 5: "rate-limited", 6: "resolved (first-hit column only)"}
RESOLVE_COLS = ["def1_status", "def2_status", "backends_hit", "backends_failed", "s2_pending", "oa_skipped",
                "dblp_missing", "match_id"] + [f"sim_{b}" for b in gt.BACKENDS]


def log(msg):
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ status bookkeeping (status codes only, never URLs)
STATS = {"lock": threading.Lock()}
BUDGET = {"stop": False, "enabled": False, "remaining": None, "credits_per_call": None, "limit": None,
          "reserve": None, "remaining_first": None}


def _reset_stats():
    with STATS["lock"]:
        STATS.update(requests={}, first_refusal={}, refusals={})
        BUDGET.update(stop=False, remaining=None, credits_per_call=None, limit=None, reserve=None,
                      remaining_first=None)


def _int_header(r, name):
    try:
        return int(float(r.headers.get(name, "")))
    except (TypeError, ValueError):
        return None


def _budget_check(r):
    """Addendum A: read the OpenAlex rate-limit headers; stop OpenAlex asking before the daily budget is reached."""
    rem, cost, lim = (_int_header(r, "X-RateLimit-Remaining"), _int_header(r, "X-RateLimit-Credits-Used"),
                      _int_header(r, "X-RateLimit-Limit"))
    num = {}
    for h, v in r.headers.items():
        if h.lower().startswith("x-ratelimit"):
            try:
                num[h] = float(v)
            except ValueError:
                pass
    BUDGET["headers_numeric"] = num  # numbers only
    if rem is None:
        return
    BUDGET["remaining"] = rem
    if BUDGET["remaining_first"] is None:
        BUDGET["remaining_first"] = rem + (cost or 0)
    if cost:
        BUDGET["credits_per_call"] = cost
    if lim:
        BUDGET["limit"] = lim
    reserve = max(2 * (BUDGET["credits_per_call"] or 10), int(0.05 * (BUDGET["limit"] or 1000)))
    BUDGET["reserve"] = reserve
    if BUDGET["enabled"] and rem < reserve and not BUDGET["stop"]:
        BUDGET["stop"] = True
        rm.OA_EXHAUSTED.set()  # no further OpenAlex request in this pass; stored answers are still read
        BUDGET["stop_time"] = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}"


class _LoggingSession(requests.Session):
    def get(self, url, **kw):
        backend = ("openalex" if "openalex.org" in url else "s2" if "semanticscholar" in url else
                   "crossref" if "crossref.org" in url else "arxiv" if "arxiv.org" in url else "other")
        if backend == "openalex" and _OA_KEY["value"]:
            kw["params"] = dict(kw.get("params") or {}, api_key=_OA_KEY["value"])
        r = super().get(url, **kw)
        if backend == "openalex":
            r.url = _scrub(r.url)  # refmatch stores r.url in the cache file
        with STATS["lock"]:
            if backend == "openalex":
                _budget_check(r)
            STATS["requests"][backend] = STATS["requests"].get(backend, 0) + 1
            if r.status_code in (402, 403, 429):
                STATS["refusals"][backend] = STATS["refusals"].get(backend, 0) + 1
                STATS["first_refusal"].setdefault(
                    backend, f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} HTTP {r.status_code}")
        return r


_local = threading.local()


def _sess():
    if not hasattr(_local, "s"):
        _local.s = _LoggingSession()
        _local.s.headers["User-Agent"] = rm.UA
    return _local.s


_orig_cached_get = rm.cached_get


def layered_get(backend, url, params=None, tries=6, cache_only=False):
    """Stored answer from the P1/P2 cache (read-only) first; otherwise the normal call, cached under cache_p3e."""
    key = hashlib.sha1((url + "?" + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    cf = OLD_CACHE / backend / f"{key}.json"
    if cf.exists():
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
            return d["status"], d["payload"]
        except (ValueError, KeyError, OSError):
            pass
    return _orig_cached_get(backend, url, params, tries=tries, cache_only=cache_only)


def install():
    rm.CACHE = NEW_CACHE
    NEW_CACHE.mkdir(parents=True, exist_ok=True)
    rm.cached_get = layered_get
    rm._sess = _sess
    # Addendum 4 (from pass 6, also section (H)): S2 key of .env, header only; cache keys and stored URLs stay keyless
    rm.S2_API_KEY = rm.S2_API_KEY or read_s2_key()
    rm.MIN_INTERVAL["s2"] = 1.5 if rm.S2_API_KEY else 3.0  # keyless: Amendment 7, <= 1 request per 3 s


# ------------------------------------------------------------------ targets
def as_int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def load():
    d = pd.read_csv(DER / "p2_groundtruth_refs_full.csv", dtype=str, keep_default_na=False, low_memory=False)
    for c in ("oa_skipped", "s2_pending", "dblp_missing"):
        d[c + "_i"] = d[c].map(as_int)
    ev = d.def1_status.isin(["resolved", "unresolved", "rate-limited"])
    miss = (d.oa_skipped_i == 1) | (d.s2_pending_i == 1) | (d.dblp_missing_i == 1) | (d.def1_status == "rate-limited")
    d["target"] = ev & miss
    return d


def missing_of(r):
    m = [b for b, c in (("openalex", "oa_skipped"), ("s2", "s2_pending"), ("dblp", "dblp_missing"))
         if as_int(r[c]) == 1]
    if r["def1_status"] == "rate-limited":
        m += [b for b in str(r["backends_failed"]).split(";") if b and b not in m]
    return m


def group_of(r):
    acad = r["tier"] in gt.ACADEMIC
    if r["def1_status"] == "unresolved":
        return (1 if acad else 3) if r["period"] == "2019-21" else (2 if acad else 4)
    return 5 if r["def1_status"] == "rate-limited" else 6


def build_targets(d, seed):
    t = d[d.target].drop_duplicates(["arxiv_id", "key"]).copy()
    t["ref_id"] = t.arxiv_id + "/" + t.key
    t["missing"] = t.apply(lambda r: ";".join(missing_of(r)), axis=1)
    t["reason"] = t.apply(lambda r: "rate-limited" if r.def1_status == "rate-limited" else
                          "never answered (" + r.missing + ")", axis=1)
    t["group"] = t.apply(group_of, axis=1)
    rng = random.Random(seed)
    order = []
    for g in sorted(GROUPS):
        ids = sorted(t.ref_id[t.group == g])
        rng.shuffle(ids)
        order += ids
    pos = {r: i + 1 for i, r in enumerate(order)}
    t["order"] = t.ref_id.map(pos)
    return t.sort_values("order")


def answered(r_after):
    """True when no backend of the reference's cascade is left without an answer."""
    return (as_int(r_after.get("oa_skipped")) == 0 and as_int(r_after.get("s2_pending")) == 0
            and as_int(r_after.get("dblp_missing")) == 0 and r_after.get("def1_status") != "rate-limited")


def to_ref(row):
    r = {k: row[k] for k in ("arxiv_id", "key", "title", "author", "tier", "period")}
    r["has_arxiv"] = as_int(row["has_arxiv"])
    r["has_doi"] = as_int(row["has_doi"])
    return r


# ------------------------------------------------------------------ passes
def run_pass(k, todo, rows_by_id, results, seed, offline=False, attrib=None, deadlines=None):
    """offline=True replays a finished pass from the caches only (no request at all).
    Live passes under Addendum A / Addendum 2 (k >= 3) stop at the header budget stop or at an OpenAlex refusal;
    a reference whose period deadline has passed is not asked; references not reached keep their replayed state and
    are asked on the next pass."""
    rm.OFFLINE = offline
    rm.OA_EXHAUSTED.clear()
    _reset_stats()
    addendum = (not offline) and k >= ADDENDUM_FROM_PASS
    BUDGET["enabled"] = addendum
    t0 = dt.datetime.now(dt.timezone.utc)
    ram0 = _free_ram()
    log(f"pass {k} {'replay (offline)' if offline else 'start'}: {len(todo)} refs still lacking an answer; OpenAlex "
        f"{'key' if has_key() else 'keyless'}; S2 {'key' if rm.S2_API_KEY else 'keyless (1 req/3 s)'}"
        + (f"; free RAM {ram0} GB" if not offline else ""))
    if not offline and ram0 is not None and ram0 < RAM_WARN_GB:
        log(f"  ! LOW RAM: {ram0} GB free (< {RAM_WARN_GB} GB) at pass {k} start; reported to LQD, pass NOT skipped")
    n_new, n_asked, n_late, stop_reason = 0, 0, 0, ""
    for i, rid in enumerate(todo, 1):
        if addendum:
            dl = (deadlines or {}).get(rows_by_id[rid]["period"])
            if dl and dt.datetime.now(dt.timezone.utc) > dl:
                n_late += 1  # period deadline passed: not asked
                continue
            if BUDGET["stop"]:
                stop_reason = "budget (header)"
                break
            if rm.OA_EXHAUSTED.is_set():
                stop_reason = "OpenAlex refusal"
                break
        r = to_ref(rows_by_id[rid])
        try:
            gt.resolve_ref(r, s2_live=True)
        except Exception as e:  # one bad reference never kills the run
            r.update(def1_status="rate-limited", def2_status="rate-limited", backends_failed="error")
            log(f"  ! error {rid}: {e.__class__.__name__}")
        n_asked += 1
        if answered(r):
            n_new += 1
            if attrib is not None:
                attrib.setdefault(rid, k)  # replay never overwrites the recorded pass
                r["answered_pass"] = attrib[rid]
            else:
                r["answered_pass"] = k
        results[rid] = r
        if i % 250 == 0 or (addendum and i % 25 == 0):
            log(f"  pass {k}: {i}/{len(todo)} done, {n_new} now complete, OpenAlex refused: {rm.OA_EXHAUSTED.is_set()}"
                + (f", OpenAlex remaining {BUDGET['remaining']} credits" if addendum else ""))
    t1 = dt.datetime.now(dt.timezone.utc)
    with STATS["lock"]:
        st = {"requests": dict(STATS["requests"]), "refusals": dict(STATS["refusals"]),
              "first_refusal": dict(STATS["first_refusal"])}
    ram1 = _free_ram()
    info = {"pass": k, "start": f"{t0:%Y-%m-%dT%H:%M:%SZ}", "end": f"{t1:%Y-%m-%dT%H:%M:%SZ}", "asked": len(todo),
            "completed_in_pass": n_new, "openalex_refused": rm.OA_EXHAUSTED.is_set() and not BUDGET["stop"], **st,
            "free_ram_gb": ram1}
    if addendum:
        a2 = k >= ADDENDUM2_FROM_PASS
        info.update(addendum="2" if a2 else "A", openalex_key=has_key(),
                    scope=("academic (J/C/P), 2019-21 first, then 2024-26" if a2 else "2019-21 academic (J/C/P)"),
                    reached=n_asked, not_asked_after_deadline=n_late, stop_reason=stop_reason or "all reached",
                    free_ram_gb_start=ram0, openalex_budget={
                        k2: BUDGET.get(k2) for k2 in ("remaining_first", "remaining", "credits_per_call", "limit",
                                                       "reserve", "stop_time")})
    log(f"pass {k} end: {n_new}/{len(todo)} now complete; requests {st['requests']}; refusals {st['refusals']}; "
        f"first refusal {st['first_refusal']}"
        + (f"; reached {n_asked}/{len(todo)}; stop: {stop_reason or 'all reached'}; OpenAlex remaining "
           f"{BUDGET['remaining']} (reserve {BUDGET['reserve']}); free RAM {ram1} GB" if addendum else ""))
    if not offline and ram1 is not None and ram1 < RAM_WARN_GB:
        log(f"  ! LOW RAM: {ram1} GB free (< {RAM_WARN_GB} GB) at pass {k} end; reported to LQD")
    return info


def _free_ram():
    try:
        import psutil
        return round(psutil.virtual_memory().available / 2 ** 30, 1)
    except Exception:
        return None


def load_attrib():
    """ref_id -> pass of answer. First use: seeded from cascade_targets.csv (passes 1-2) and the 2026-11-08 probe
    (P3E/oa_probe.jsonl; its answer was obtained on the pass-3 day before pass 3, attributed to pass 3)."""
    if ANSWERED.exists():
        return {k: int(v) for k, v in json.loads(ANSWERED.read_text(encoding="utf-8")).items()}
    a = {}
    ct = OUT_DIR / "cascade_targets.csv"
    if ct.exists():
        c = pd.read_csv(ct, dtype=str, keep_default_na=False)
        a.update({r: int(p) for r, p in zip(c.ref_id, c.answered_pass) if p})
    pr = OUT_DIR / "oa_probe.jsonl"
    if pr.exists():
        for line in pr.read_text(encoding="utf-8").splitlines():
            j = json.loads(line)
            if j.get("status") == 200:
                a.setdefault(j["ref_id"], ADDENDUM_FROM_PASS)
    save_attrib(a)
    return a


def save_attrib(a):
    ANSWERED.write_text(json.dumps(dict(sorted(a.items())), indent=0), encoding="utf-8")


def next_start(k, prev_end, prev_stop=""):
    end = dt.datetime.strptime(prev_end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if k == ADDENDUM2_FROM_PASS:  # Addendum 2: pass 4 starts when launched (after the addendum is hashed)
        return dt.datetime.now(dt.timezone.utc)
    if k == 2 or (k > ADDENDUM2_FROM_PASS and prev_stop == "OpenAlex refusal"):
        return end + dt.timedelta(minutes=60)  # after a refusal (not a budget stop): 60 min later
    t = end.replace(hour=0, minute=10, second=0)
    return t if t > end else t + dt.timedelta(days=1)


def write_outputs(d, targets, results):
    out = d.drop(columns=[c for c in d.columns if c.endswith("_i")] + ["target"]).copy()
    rid = out.arxiv_id + "/" + out.key
    for c in RESOLVE_COLS:
        if c not in out:
            out[c] = ""
    new = pd.DataFrame.from_dict(results, orient="index")
    for c in RESOLVE_COLS:
        if c in new:
            m = rid.isin(new.index)
            out.loc[m, c] = rid[m].map(new[c]).map(lambda v: "" if (isinstance(v, float) and np.isnan(v)) else v)
    out.to_csv(DER / "p3e_groundtruth_refs_full.csv", index=False)
    t = targets.copy()
    t["state_before"] = t.def1_status
    t["state_after"] = t.ref_id.map(lambda x: results.get(x, {}).get("def1_status", ""))
    t["missing_after"] = t.ref_id.map(lambda x: ";".join(missing_of({**{"oa_skipped": 0, "s2_pending": 0,
                                                                         "dblp_missing": 0, "backends_failed": ""},
                                                                      **results[x]})) if x in results else "")
    t["answered_pass"] = t.ref_id.map(lambda x: results.get(x, {}).get("answered_pass", ""))
    t["backends_hit_after"] = t.ref_id.map(lambda x: results.get(x, {}).get("backends_hit", ""))
    t[["ref_id", "tier", "period", "missing", "reason", "group", "order", "state_before", "state_after",
       "missing_after", "answered_pass", "backends_hit_after"]].to_csv(OUT_DIR / "cascade_targets.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-passes", type=int, default=10, help="Addendum A: daily passes until --deadline")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--keyless", action="store_true", help="do not read the OpenAlex key from .env")
    ap.add_argument("--probe", action="store_true",
                    help="Addendum 2: ONE OpenAlex request (next in-scope reference), print the numeric rate-limit "
                         "headers, store the answer; no pass")
    ap.add_argument("--dry", type=int, default=0, help="testing only: offline, first N targets, no file written")
    args = ap.parse_args()
    OUT_DIR.mkdir(exist_ok=True)
    install()
    if not args.keyless:
        _OA_KEY["value"] = read_env_key()
    print(f"OpenAlex key present: {has_key()}", flush=True)  # True/False only
    d = load()
    targets = build_targets(d, args.seed)
    deadlines = {p: dt.datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
                 for p, v in DEADLINES.items()}
    acad = targets.tier.isin(gt.ACADEMIC)
    scope_a = set(targets.ref_id[(targets.period == "2019-21") & acad])  # Addendum A (pass 3)
    scope_2 = set(targets.ref_id[acad])  # Addendum 2 (pass >= 4): academic, both periods
    rank2 = {r: (p != "2019-21", o) for r, p, o in zip(targets.ref_id, targets.period, targets.order)}
    if args.probe:
        return probe(targets, d, scope_2, rank2)
    if args.dry:
        global log  # noqa: PLW0603
        log = print  # noqa: F811
        rm.OFFLINE = True
        res = {}
        rb = {r.arxiv_id + "/" + r.key: r._asdict() for r in d[d.target].drop_duplicates(["arxiv_id", "key"]).itertuples()}
        ids = list(targets.ref_id[:args.dry])
        run_pass(0, ids, rb, res, args.seed, offline=True)
        x = pd.DataFrame.from_dict(res, orient="index")
        print(x[["tier", "period", "def1_status", "oa_skipped", "s2_pending", "backends_hit"]].head(12).to_string())
        print("groups:", targets.group.value_counts().sort_index().to_dict())
        print("states after replay:", x.def1_status.value_counts().to_dict(),
              "same as before:", int((x.def1_status.values == targets.def1_status[:args.dry].values).sum()), "/", len(x))
        return
    rows_by_id = {r.arxiv_id + "/" + r.key: r for r in d[d.target].drop_duplicates(["arxiv_id", "key"]).itertuples()}
    rows_by_id = {k: v._asdict() for k, v in rows_by_id.items()}
    log(f"targets: {len(targets)} distinct refs ({int(d.target.sum())} rows); groups "
        + ", ".join(f"{g}={int((targets.group == g).sum())}" for g in sorted(GROUPS)))
    state = json.loads(PASSES.read_text(encoding="utf-8")) if (args.resume and PASSES.exists()) else {"passes": []}
    attrib = load_attrib() if args.resume else {}
    in_scope = scope_2
    results = {}
    # replay finished passes from the caches (answers are stored, so this asks only what is still missing)
    done = len(state["passes"])
    todo = list(targets.ref_id)
    all_todo = todo
    for k in range(1, args.max_passes + 1):
        if k > 1:
            all_todo = [x for x in all_todo if not answered(results.get(x, {"def1_status": "rate-limited"}))]
            todo = all_todo
            if k == ADDENDUM_FROM_PASS:
                todo = [x for x in todo if x in scope_a]  # Addendum A: order kept, scope restricted
            elif k >= ADDENDUM2_FROM_PASS:  # Addendum 2: 2019-21 academic first, then 2024-26, registered order
                todo = sorted([x for x in todo if x in scope_2], key=rank2.get)
                if k > RL_LAST_ROUND_PASS:
                    todo = [x for x in todo if results.get(x, {}).get("def1_status") != "rate-limited"]
            if not todo and k <= done:  # replay only: the restricted scope of a recorded pass (Addendum A) can be empty now
                continue
            if not todo:
                log("every target answered; no further pass" if k < ADDENDUM_FROM_PASS else
                    f"pass {k}: academic scope complete (every reference answered); no further pass")
                break
        if k <= done:
            log(f"pass {k} already recorded ({state['passes'][k - 1]['end']}); replaying from the caches")
        elif k > 1:
            prev = state["passes"][k - 2]
            start = next_start(k, prev["end"], prev.get("stop_reason", ""))
            open_dl = [deadlines[rows_by_id[x]["period"]] for x in todo]
            if start > max(open_dl):
                log(f"pass {k} would start {start:%Y-%m-%dT%H:%M:%SZ}, after every open deadline; asking ends "
                    "(Addenda A and 2)")
                break
            wait = (start - dt.datetime.now(dt.timezone.utc)).total_seconds()
            if wait > 0:
                if args.no_wait:
                    log(f"pass {k} scheduled for {start:%Y-%m-%dT%H:%M:%SZ}; --no-wait, stopping")
                    break
                log(f"pass {k} scheduled for {start:%Y-%m-%dT%H:%M:%SZ}; waiting {wait / 60:.0f} min "
                    f"({len(todo)} refs in scope still lacking an answer)")
                write_outputs(d, targets, results)
                time.sleep(wait)
        info = run_pass(k, todo, rows_by_id, results, args.seed, offline=k <= done, attrib=attrib,
                        deadlines=deadlines)
        rm.OFFLINE = False
        if k > done:
            state["passes"].append(info)
            PASSES.write_text(json.dumps(state, indent=1), encoding="utf-8")
            save_attrib(attrib)
        write_outputs(d, targets, results)
    left = [x for x in targets.ref_id if not answered(results.get(x, {"def1_status": "rate-limited"}))]
    t = targets.set_index("ref_id")
    summ = {}
    for x in left:
        key = f"{t.loc[x, 'period']} {t.loc[x, 'tier']} {t.loc[x, 'def1_status']}"
        summ[key] = summ.get(key, 0) + 1
    left_scope = [x for x in left if x in in_scope]
    rl_out = [x for x in left_scope if len(state["passes"]) >= RL_LAST_ROUND_PASS
              and results.get(x, {}).get("def1_status") == "rate-limited"]  # PREREG 4: excluded and reported separately
    left_scope = [x for x in left_scope if x not in rl_out]
    left_a = [x for x in left if x in scope_a]
    state["unanswered_after_last_pass"] = {"n": len(left), "by_period_tier_state_before": summ,
                                           "scope": "acad (Addendum 2)", "n_scope": len(in_scope),
                                           "n_scope_unanswered": len(left_scope),
                                           "scope_rate_limited_after_rounds": rl_out,
                                           "n_acad1921": len(scope_a), "n_acad1921_unanswered": len(left_a)}
    PASSES.write_text(json.dumps(state, indent=1), encoding="utf-8")
    write_outputs(d, targets, results)
    log(f"finished: {len(targets) - len(left)}/{len(targets)} targets answered; {len(left)} still unanswered; "
        f"academic scope: {len(in_scope) - len(left_scope) - len(rl_out)}/{len(in_scope)} answered, "
        f"{len(rl_out)} excluded as rate-limited after the registered rounds "
        f"(2019-21: {len(scope_a) - len(left_a)}/{len(scope_a)})")


def probe(targets, d, scope, rank):
    """Addendum 2 probe: one OpenAlex request for the first in-scope reference (2019-21 first) without a stored
    OpenAlex answer; prints only numbers; the answer is cached (scrubbed URL) and attributed to pass 4."""
    rows = d[d.target].drop_duplicates(["arxiv_id", "key"])
    title = dict(zip(rows.arxiv_id + "/" + rows.key, rows.title))
    for rid in sorted(scope, key=rank.get):
        t = title.get(rid, "")
        if not t:
            continue
        url, params = rm._openalex_req(t)
        if layered_get("openalex", url, params, cache_only=True)[0] != -3:
            continue
        break
    else:
        print("no in-scope reference without a stored OpenAlex answer")
        return
    _reset_stats()
    t0 = dt.datetime.now(dt.timezone.utc)
    st, _ = layered_get("openalex", url, params, tries=1)
    out = {"time": f"{t0:%Y-%m-%dT%H:%M:%SZ}", "ref_id": rid, "kind": "filter=title.search (cascade request)",
           "key": has_key(), "status": st, "headers_numeric": BUDGET.get("headers_numeric", {})}
    print(json.dumps(out, indent=1))
    with (OUT_DIR / "oa_probe.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    if st == 200:
        a = load_attrib()
        a.setdefault(rid, ADDENDUM2_FROM_PASS)
        save_attrib(a)


if __name__ == "__main__":
    main()
