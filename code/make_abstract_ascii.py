#!/usr/bin/env python3
"""Topic 43 / P3D: submission_package/abstract_keywords_ascii.txt, for the portal's plain-text fields.

Title, abstract and keywords are taken from main.tex with every \nv{key} filled from numbers_ms.tex, so the numbers
cannot drift from the manuscript. Fails on any non-ASCII character or leftover LaTeX command.
Usage: python make_abstract_ascii.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import ROOT  # noqa: E402

PKG = ROOT / "submission_package"


def plain(s, nv):
    s = re.sub(r"\\nv\{([^}]+)\}", lambda m: nv[m.group(1)], s)
    s = re.sub(r"\\texttt\{([^}]*)\}", r"\1", s)  # P3G: .bib / .bbl in the abstract
    s = s.replace("\\%", "%").replace("--", "-").replace("$", "")
    return " ".join(s.split())


def main():
    tex = (PKG / "latex" / "main.tex").read_text(encoding="utf-8")
    nv = dict(re.findall(r"\\nvset\{([^}]+)\}\{(.*)\}", (PKG / "latex" / "numbers_ms.tex").read_text(encoding="utf-8")))
    title = plain(re.search(r"\\title\[[^\]]*\]\{(.*?)\}\n", tex, re.S).group(1), nv)
    ab = plain(tex[tex.index("\\abstract{") + 10:tex.index("}\n\n\\keywords{")], nv)
    kw = plain(re.search(r"\\keywords\{(.*?)\}\n", tex, re.S).group(1), nv)
    for s in (title, ab, kw):
        if not s.isascii() or "\\" in s:
            raise SystemExit(f"not plain ASCII: {s[:80]}")
    out = f"TITLE\n{title}\n\nABSTRACT ({len(ab.split())} words)\n{ab}\n\nKEYWORDS\n{kw}\n"
    (PKG / "abstract_keywords_ascii.txt").write_text(out, encoding="utf-8")
    print(len(ab.split()), "words")


if __name__ == "__main__":
    main()
