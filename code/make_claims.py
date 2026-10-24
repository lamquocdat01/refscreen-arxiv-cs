#!/usr/bin/env python3
"""Topic 43 / P3 (B1): claim-evidence table of the manuscript.

Every sentence of submission_package/latex/main.tex that prints a number through \\nv{key} becomes one row: section,
the sentence with the values filled in, the keys, and for each key its source file and field
(results/numbers_ms_sources.csv). A row is marked has_interval when the sentence prints an interval key (ci*, *Ci*)
or a k/n count; rows in the abstract, introduction and conclusion are marked headline.
Output: submission_package/claims.csv
Usage: python make_claims.py
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import ROOT  # noqa: E402

TEX = ROOT / "submission_package" / "latex" / "main.tex"


def main():
    src = {r["key"]: r for r in csv.DictReader((ROOT / "results" / "numbers_ms_sources.csv").open(encoding="utf-8"))}
    t = TEX.read_text(encoding="utf-8")
    t = t[t.index("\\abstract{"):t.index("\\begin{appendices}")]
    rows, section = [], "Abstract"
    for para in re.split(r"\n\s*\n", t):
        m = re.search(r"\\(?:sub)?section\{([^}]*)\}", para)
        if m:
            section = m.group(1)
        if "\\bmhead" in para:
            section = "Back matter"
        for sent in re.split(r"(?<=[.;])\s+(?=[A-Z\\(])", para):
            keys = re.findall(r"\\nv\{([^}]+)\}", sent)
            if not keys:
                continue
            text = re.sub(r"\\nv\{([^}]+)\}", lambda k: src[k.group(1)]["value"], sent)
            text = " ".join(re.sub(r"\\(cite[pt]?|label|ref)\{[^}]*\}", "", text).split())
            rows.append(dict(
                section=section, headline=section in ("Abstract", "Introduction") or section.startswith("Conclusion"),
                claim=text[:400], keys=" ".join(keys),
                sources=" | ".join(sorted({src[k]["source"] for k in keys})),
                fields=" | ".join(f"{k}={src[k]['field']}" for k in keys),
                has_interval=any(re.search(r"(^ci|Ci|CiHi|CiLo)", k) for k in keys) or bool(re.search(r"\d+/\d", text))))
    out = ROOT / "submission_package" / "claims.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "claims;", sum(r["headline"] for r in rows), "headline;",
          sum(not r["has_interval"] for r in rows), "without interval or k/n in the same sentence")


if __name__ == "__main__":
    main()
