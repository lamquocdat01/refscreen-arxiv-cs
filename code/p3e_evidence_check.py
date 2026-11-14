#!/usr/bin/env python3
"""Topic 43 / P3E Addendum 3: check the R_H1 evidence pack before release.

Inputs: results/p3e_evidence_pack.csv, P3E/evidence_pack.md, results/p3e_human_sheet.csv.
Checks:
  1. 68 rows H01-H68 in both files, in order; candidate source in {Crossref, arXiv, OpenAlex, Web}; <= 3 candidates.
  2. Forbidden words (labels, evaluative words, scores) in text the agent wrote. "Agent text" = each cell / line after
     removing verbatim bibliographic strings: the row's sheet fields (title, author, bib_entry, bbl_item, and their
     words, for the query strings) and the returned-record fields of that row (cand*_title/authors/venue/year/doi_url).
     Required: 0 hits. Hits inside verbatim bibliographic strings are counted and listed separately.
  3. Leaks: the OpenAlex key value (or its first 16 characters), "api_key", and sheet-key vocabulary (origin, V-row
     ids, family names). Only counts are printed; the key value never is.
--fix: delete offending md lines / blank offending csv cells (agent text only), and print what was removed.
Usage: python code/p3e_evidence_check.py [--fix]
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CSV, MD, SHEET = ROOT / "results" / "p3e_evidence_pack.csv", ROOT / "P3E" / "evidence_pack.md", \
    ROOT / "results" / "p3e_human_sheet.csv"
FORBID = re.compile(r"(?<![\w-])(not-exists|exists?|ambiguous|likely|fake|fabricated|hallucinated|planted|synthetic|"
                    r"real|suspicious|mismatch\w*|score[sd]?|similarity|relevance)(?![\w-])", re.I)
KEYVOCAB = re.compile(r"\b(gen_a|gen_c|V[0-2]\d|origin|unresolved|resolved|pipeline|u_with)\b", re.I)
SOURCES = {"Crossref", "arXiv", "OpenAlex", "Web"}
CF = ["title", "authors", "year", "venue", "doi_url", "source"]


def strip_known(text, known):
    for k in sorted({k for k in known if k and len(k) >= 3}, key=len, reverse=True):
        text = text.replace(k, " ")
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()
    s = pd.read_csv(SHEET, dtype=str, keep_default_na=False).set_index("check_id")
    p = pd.read_csv(CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    md = MD.read_text(encoding="utf-8-sig").splitlines()
    ids = [f"H{i:02d}" for i in range(1, 69)]
    errs, verbatim, removed = [], [], []
    if list(p.row_id) != ids:
        errs.append(f"csv rows: {len(p)} (expected H01-H68 in order)")
    md_ids = [ln[3:].strip() for ln in md if ln.startswith("## ")]
    if md_ids != ids:
        errs.append(f"md entries: {len(md_ids)} (expected H01-H68 in order)")
    known = {}
    for _, r in p.iterrows():
        sr = s.loc[r.row_id]
        sheet_txt = [sr.title, sr.author, sr.bib_entry, sr.bbl_item]
        words = set(w for t in sheet_txt for w in re.findall(r"[\w'’-]+", t))
        cand = [r[f"cand{i}_{c}"] for i in (1, 2, 3) for c in CF if f"cand{i}_{c}" in p.columns]
        known[r.row_id] = set(sheet_txt) | words | set(cand)
        for i in (1, 2, 3):
            src = r.get(f"cand{i}_source", "")
            if src and src not in SOURCES:
                errs.append(f"{r.row_id} cand{i}_source={src!r}")
            for c in ("title", "authors", "venue"):
                v = r.get(f"cand{i}_{c}", "")
                for m in FORBID.finditer(v):
                    verbatim.append((r.row_id, f"cand{i}_{c}", m.group(0)))
        for col in ("queries_tried", "no_candidate_returned_by"):
            res = strip_known(r[col], known[r.row_id])
            hits = FORBID.findall(res)
            if hits:
                errs.append(f"{r.row_id} {col}: agent-text hits {hits}")
                if a.fix:
                    removed.append((r.row_id, col, r[col]))
                    p.loc[p.row_id == r.row_id, col] = ""
            for m in FORBID.finditer(r[col]):
                if not FORBID.search(res):
                    verbatim.append((r.row_id, col, m.group(0)))
    cur, keep = None, []
    for ln in md:
        if ln.startswith("## "):
            cur = ln[3:].strip()
        res = strip_known(ln, known.get(cur, set()))
        hits = FORBID.findall(res)
        if hits:
            errs.append(f"md {cur}: agent-text hits {hits} in line: {ln[:120]}")
            if a.fix:
                removed.append((cur, "md", ln))
                continue
        keep.append(ln)
    # leaks
    sys.path.insert(0, str(HERE))
    from p3e_complete_cascade import read_env_key  # reads ROOT/.env; value never printed
    key = read_env_key() or ""
    blob = CSV.read_text(encoding="utf-8-sig") + "\n" + MD.read_text(encoding="utf-8-sig")
    leak_key = sum(blob.count(k) for k in {key, key[:16]} if len(k) >= 8)
    leak_api = blob.lower().count("api_key")
    vocab = [m.group(0) for m in KEYVOCAB.finditer(strip_known(blob, set().union(*known.values())))]
    print(f"rows csv={len(p)} md={len(md_ids)}; agent-text forbidden hits={sum('agent-text' in e for e in errs)}; "
          f"verbatim bibliographic hits={len(verbatim)}; key-value hits={leak_key}; 'api_key' hits={leak_api}; "
          f"sheet-key vocabulary hits={len(vocab)} {sorted(set(vocab))}")
    for v in verbatim:
        print("  verbatim:", *v)
    for e in errs:
        print("  ERROR:", e)
    if a.fix and removed:
        p.to_csv(CSV, index=False, encoding="utf-8-sig")
        MD.write_text("\n".join(keep) + "\n", encoding="utf-8")
        for r in removed:
            print("  REMOVED:", r[0], r[1], r[2][:160])
    ok = not errs and leak_key == 0 and leak_api == 0 and not vocab
    print("PACK CHECK", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
