#!/usr/bin/env python3
"""Topic 43 / P3D: remove LaTeX comments from a copy of a .tex file, for the source.zip of the submission.

A whole-line comment is deleted with its line, so no paragraph break appears. In a line with text, everything after an
unescaped % is deleted and the % itself stays, because a trailing % also suppresses the end-of-line space. A \\% stays.
Blank lines are kept. The working files are not changed: the function returns text, and the command line writes a copy.
Usage: python strip_comments.py IN.tex OUT.tex
"""
import re
import sys
from pathlib import Path

UNESCAPED = re.compile(r"(?<!\\)(?:\\\\)*%")


def strip(text):
    out = []
    for line in text.split("\n"):
        m = UNESCAPED.search(line)
        if m is None:
            out.append(line)
        elif not line[:m.start()].strip():
            continue
        else:
            out.append(line[:m.end()])
    return "\n".join(out)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(strip(src.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
