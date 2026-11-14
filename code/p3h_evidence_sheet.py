#!/usr/bin/env python3
"""Topic 43 / P3H (PREREG_AMENDMENT_9.md (A); POST HOC): build the blind web-evidence sheet.

Real rows: academic (J/C/P) references of 2019-21 from the authors' .bib, unresolved under the full cascade.
Planted rows: 19 never-used, never-released family-(a) candidates of the stored generation
(code/fake_refs/family_a_candidates.csv minus results/p2_fake_items.csv), drawn with --seed 53; each checked offline
against the stored backend candidates (max title similarity < 0.80).
All rows rendered by one template; no URL/DOI/arXiv id. Shuffled with --shuffle-seed 54 -> E001..E100.
Key (ID, origin, source id) written only encrypted to $THS_DATASETS/_derived/43/keys/p3h_evidence_key.csv.enc;
the sha256 of the plaintext is printed (and goes to P3H/P3H_LOG.md).
Outputs: results/p3h_evidence_sheet.csv
Usage: python code/p3h_evidence_sheet.py --seed 53 --shuffle-seed 54
"""
import argparse
import re
import hashlib
import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refmatch as rm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
DER = Path(os.environ.get("THS_DATASETS", "D:/Datasets")) / "_derived" / "43"
KEYDIR = DER / "keys"
KEYENC = KEYDIR / "p3h_evidence_key.csv.enc"
FKEY = KEYDIR / "p3c_fernet.key"
N_PLANT = 19
SIM_MAX = 0.80


def given_family(a):
    """'Last, First and First2 Last2' -> 'First Last, First2 Last2' (LaTeX stripped)."""
    out = []
    for p in rm.strip_latex(a or "").replace("\n", " ").split(" and "):
        p = " ".join(p.split())
        if not p:
            continue
        if p.lower() in ("others", "et al.", "et al"):
            out.append("et al.")
            continue
        if "," in p:
            last, first = [x.strip() for x in p.split(",", 1)]
            p = f"{first} {last}".strip()
        out.append(p)
    return ", ".join(out)


URL_RE = re.compile(r"(https?://|www\.)\S+|\[\s*accessed[^\]]*\]|\\url\{[^}]*\}", re.I)


def clean_venue(v):
    """no URL, DOI or arXiv id in any row (Amendment 9 (A))."""
    v = URL_RE.sub(" ", v.replace(chr(92) + "_", "_"))
    v = re.sub(r"\b(doi:?\s*10\.\S+|arXiv:\s*\S+)", " ", v, flags=re.I)
    return " ".join(v.split()).strip(" ,;")


def template(authors, title, venue, year):
    s = (f"{authors} " if authors.endswith(".") else f"{authors}. ") if authors else ""
    s += f"{title}. " if title else ""
    if venue and year:
        s += f"{venue}, {year}."
    elif venue or year:
        s += f"{venue or year}."
    return s.strip()


def real_rows():
    import p3g_branch_split as bs
    import p3f_deep_search as ds
    d = bs.base()
    s = d[(d.period == "2019-21") & (d.ref_source == "bib") & d.tier.isin(["J", "C", "P"]) & (d.u == 1)]
    rows = []
    for r in s.to_dict("records"):
        m = ds.make_ref(r, "real")
        e = ds.bib_entry(r["arxiv_id"], r["key"])
        venue = next((rm.strip_latex(e.get(f, "")) for f in ("journal", "booktitle", "publisher", "howpublished",
                                                              "institution") if e.get(f, "").strip()), "")
        venue = clean_venue(venue)
        rows.append(dict(origin="real", source_id=r["ref_id"], title=" ".join(rm.strip_latex(r["title"]).split()),
                         authors=given_family(r["author"]), year=str(m["year"] or ""), venue=venue))
    return rows


def planted_rows(seed):
    cand = pd.read_csv(ROOT / "code" / "fake_refs" / "family_a_candidates.csv", dtype=str, keep_default_na=False)
    used = set(pd.read_csv(RES / "p2_fake_items.csv", dtype=str).item_id)
    pool = cand[~cand.cand_id.isin(used)].reset_index(drop=True)
    q = pd.read_csv(DER / "fake" / "items_queried.csv", dtype=str, keep_default_na=False).set_index("item_id")
    sims = q[[c for c in q.columns if c.startswith("sim_")]].replace("", np.nan).astype(float).max(axis=1)
    order = np.random.default_rng(seed).permutation(len(pool))
    rows, log = [], []
    for i in order:
        r = pool.iloc[i]
        ms = sims.get(r.cand_id, np.nan)
        if not (ms < SIM_MAX):
            log.append(f"replaced {r.cand_id}: max stored sim {ms}")
            continue
        venue = "arXiv preprint" if r.tier == "P" and not r.venue.strip() else r.venue
        rows.append(dict(origin="planted", source_id=r.cand_id, title=r.title, authors=given_family(r.authors),
                         year=str(r.year), venue=venue, _maxsim=float(ms)))
        if len(rows) == N_PLANT:
            break
    return rows, log, len(pool)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=53)
    ap.add_argument("--shuffle-seed", type=int, default=54)
    a = ap.parse_args()
    real = real_rows()
    plant, log, npool = planted_rows(a.seed)
    print(f"real rows: {len(real)}; planted pool: {npool}; planted drawn: {len(plant)}; "
          f"max stored sim of drawn: {max(p['_maxsim'] for p in plant):.4f}")
    for line in log:
        print(line)
    df = pd.DataFrame(real + [{k: v for k, v in p.items() if k != "_maxsim"} for p in plant])
    df = df.iloc[np.random.default_rng(a.shuffle_seed).permutation(len(df))].reset_index(drop=True)
    df["ID"] = [f"E{i + 1:03d}" for i in range(len(df))]
    df["reference"] = [template(r.authors, r.title, r.venue, r.year) for r in df.itertuples()]
    sheet = df[["ID", "reference", "title", "authors", "year", "venue"]]
    sheet.to_csv(RES / "p3h_evidence_sheet.csv", index=False, encoding="utf-8")
    buf = io.StringIO()
    df[["ID", "origin", "source_id"]].to_csv(buf, index=False)
    plain = buf.getvalue().encode("utf-8")
    from cryptography.fernet import Fernet
    KEYENC.write_bytes(Fernet(FKEY.read_bytes()).encrypt(plain))
    print("sheet rows:", len(sheet), "| key plaintext sha256:", hashlib.sha256(plain).hexdigest())
    print("encrypted key:", KEYENC.name, "sha256", hashlib.sha256(KEYENC.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
