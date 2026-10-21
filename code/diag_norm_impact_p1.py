#!/usr/bin/env python3
"""Topic 43 / P1 diagnostic (exploratory): size of three title-normalisation defects found in the 60-ref diag
(results/p1_diag_unresolved_jc60.csv), measured without network calls.

  (a) strip_latex accent regex: letter accents \\u \\v \\H \\t \\c \\d \\b \\k also fire at the start of longer
      commands (\\textemdash -> "extemdash", \\url -> "rl", \\cite -> "ite"); .bib side, so the *query* is wrong too.
  (b) registry markup: Crossref titles carry JATS/MathML tags (<sup>2</sup>, <i>, <mml:math>) that norm() keeps as
      words ("sup").
  (c) bytes: .bib read as latin-1 when not UTF-8, so cp1252 punctuation (0x96/0x97 dashes, 0x92 quotes) becomes C1
      control characters; plus U+FFFD in .bib or registry titles.
For (a) the corrected title is re-scored against the stored candidates of the *old* query only (lower bound on flips:
the corrected query was never sent). For (b) the stored candidates are re-scored with tags removed (exact).
Input: $THS_DATASETS/_derived/43/p1_diag_round1_replay_jcp.csv (from diag_unresolved_p1.py) + the .bib files.
Outputs: results/p1_diag_norm_impact.csv (affected refs), results/p1_diag_norm_impact.json
Usage: python diag_norm_impact_p1.py
"""
import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diag_unresolved_p1 as dg  # noqa: E402  (installs the cache-only cached_get)
import ground_truth_p1 as gt  # noqa: E402
import refmatch as rm  # noqa: E402
from ground_truth import cited_keys, parse_bibs  # noqa: E402

_ACC_FIXED = re.compile(r"\\(?:[`'^\"~=.]|[uvHtcdbk](?![A-Za-z]))\s*\{?([A-Za-z])\}?")
TAG = re.compile(r"<[^<>]{1,80}>")


def strip_latex_fixed(s):
    if not s:
        return ""
    s = s.replace("\\&", "&").replace("~", " ").replace("--", "-")
    s = _ACC_FIXED.sub(r"\1", s)
    for _ in range(4):
        s2 = rm._LATEX_CMD_ARG.sub(r"\1", s)
        if s2 == s:
            break
        s = s2
    s = rm._LATEX_CMD.sub(" ", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    return " ".join(s.split())


def raw_titles():
    """(arxiv_id, key) -> raw .bib title for bib-sourced papers."""
    with (gt.DATA / "arxiv_src_43" / "manifest.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] == "kept"]
    out = {}
    for r in rows:
        pdir = gt.SRC / r["arxiv_id"].replace("/", "_")
        bibs = sorted(pdir.rglob("*.bib"))
        if not bibs:
            continue
        for k, e in parse_bibs(bibs).items():
            out[(r["arxiv_id"], k)] = e.get("title", "")
    return out


def rescore(title, tier, has_arxiv, fix_tags=False):
    cs = dg.candidates(title, has_arxiv or tier == "P")
    best = 0.0
    for c in cs.values():
        for _, ts in c or []:
            for t in ts:
                best = max(best, rm.title_sim(TAG.sub(" ", t) if fix_tags else t, title))
    return best


def main():
    d = pd.read_csv(gt.DERIVED / "p1_diag_round1_replay_jcp.csv", low_memory=False, keep_default_na=False,
                     dtype={"arxiv_id": str, "key": str})
    d["has_arxiv"] = d.has_arxiv.astype(int)
    raw = raw_titles()
    rows = []
    for r in d.to_dict("records"):
        rt = raw.get((r["arxiv_id"], str(r["key"]).lower())) if r["ref_source"] == "bib" else None
        defects = []
        new_t = r["title"]
        if rt is not None and rm.norm(rm.strip_latex(rt)) != rm.norm(strip_latex_fixed(rt)):
            defects.append("a-latex-accent")
            new_t = strip_latex_fixed(rt)
        if re.search(r"[\x80-\x9f]", r["title"]):
            defects.append("c-c1-control")
        if "\ufffd" in r["title"]:
            defects.append("c-fffd-bib")
        st = r["def1_status"]
        flip_a = flip_b = None
        if st == "unresolved":
            if "a-latex-accent" in defects:
                flip_a = rescore(new_t, r["tier"], r["has_arxiv"]) >= rm.SIM_THRESHOLD
            sb = rescore(r["title"], r["tier"], r["has_arxiv"], fix_tags=True)
            if sb >= rm.SIM_THRESHOLD:
                defects.append("b-registry-markup")
                flip_b = True
        if defects:
            rows.append(dict(set=r["set"], tier=r["tier"], arxiv_id=r["arxiv_id"], key=r["key"], def1_status=st,
                             label=r["label"], defects=";".join(defects), flip_a_lower_bound=flip_a,
                             flip_b=flip_b, title=r["title"][:200], title_fixed=new_t[:200]))
    a = pd.DataFrame(rows)
    a.to_csv(gt.ROOT / "results" / "p1_diag_norm_impact.csv", index=False)
    out = {"label": "diagnostic, exploratory; cache only", "n_refs_jcp": int(len(d))}
    for dfc in ["a-latex-accent", "b-registry-markup", "c-c1-control", "c-fffd-bib"]:
        g = a[a.defects.str.contains(dfc)] if len(a) else a
        out[dfc] = {"refs": int(len(g)), "by_status": g.def1_status.value_counts().to_dict(),
                    "by_set_tier": {f"{s}/{t}": int(v) for (s, t), v in g.groupby(["set", "tier"]).size().items()},
                    "certified_real": int((g.label == "certified-real").sum())}
    out["a-latex-accent"]["unresolved_flip_lower_bound"] = int((a.flip_a_lower_bound == True).sum())  # noqa: E712
    out["b-registry-markup"]["unresolved_flip"] = int((a.flip_b == True).sum())  # noqa: E712
    for s in ["prellm", "pilot"]:
        g = d[(d.set == s) & d.tier.isin(["J", "C", "P"]) & d.def1_status.isin(["resolved", "unresolved"])]
        k, n = int((g.def1_status == "unresolved").sum()), len(g)
        fl = a[(a.set == s) & ((a.flip_a_lower_bound == True) | (a.flip_b == True))]  # noqa: E712
        out[f"u_A_{s}"] = {"round1_replay": [k, n, round(k / n, 4)],
                           "after_fixes_lower_bound": [k - len(fl), n, round((k - len(fl)) / n, 4)]}
    (gt.ROOT / "results" / "p1_diag_norm_impact.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
