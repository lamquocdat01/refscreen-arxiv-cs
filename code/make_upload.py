#!/usr/bin/env python3
"""Topic 43 / P3: assemble submission_package/upload/ for the Springer Nature portal.

Copies main.pdf, supplement.pdf, cover_letter.pdf, abstract_keywords_ascii.txt, and zips the LaTeX source
(main.tex, main.bbl, numbers_ms.tex, tab_*.tex, refs.bib, sn-jnl.cls, sn-basic.bst, figures/*.pdf) as source.zip, with
comments removed from the .tex files by strip_comments.py;
writes MANIFEST.csv (file, bytes, sha256) and checks that the zip compiles is NOT done here (verify_package.py G1-G9
covers the source). Usage: python make_upload.py
"""
import csv
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import ROOT  # noqa: E402
from strip_comments import strip  # noqa: E402

PKG = ROOT / "submission_package"
UP = PKG / "upload"


def main():
    UP.mkdir(exist_ok=True)
    tex = PKG / "latex"
    for src, dst in ((tex / "main.pdf", "manuscript.pdf"), (PKG / "supplement" / "supplement.pdf", "supplementary_material.pdf"),
                     (PKG / "cover_letter.pdf", "cover_letter.pdf"), (PKG / "abstract_keywords_ascii.txt", "abstract_keywords_ascii.txt")):
        shutil.copy2(src, UP / dst)
    files = ["main.tex", "main.bbl", "numbers_ms.tex", "refs.bib", "sn-jnl.cls", "sn-basic.bst"] + \
        sorted(p.name for p in tex.glob("tab_*.tex"))
    with zipfile.ZipFile(UP / "source.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if f.endswith(".tex"):
                z.writestr(f, strip((tex / f).read_text(encoding="utf-8")))
            else:
                z.write(tex / f, f)
        for p in sorted((tex / "figures").glob("*.pdf")):
            z.write(p, f"figures/{p.name}")
    from package_exclude import assert_clean  # .env and key material never enter a package
    with zipfile.ZipFile(UP / "source.zip") as z:
        assert_clean(z.namelist())
    assert_clean(p.name for p in UP.iterdir())
    rows = []
    for p in sorted(UP.iterdir()):
        if p.name == "MANIFEST.csv":
            continue
        rows.append(dict(file=p.name, bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    with (UP / "MANIFEST.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "bytes", "sha256"])
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r["file"], r["bytes"], r["sha256"][:12])


if __name__ == "__main__":
    main()
