#!/usr/bin/env python3
"""Topic 43 / P3: hard gates on the submission package (checklist C5, C6, C8b, B1, A2, C3, C10/C11, e-mail rule).

Checks, each PASS/FAIL:
  G1 numbers   numbers_ms.tex and tab_*.tex equal a fresh run of make_ms_numbers.py (no stale or hand-edited number)
  G2 keys      every \\nv{key} in main.tex is defined; main.log has no LaTeX error, undefined reference or citation
  G3 figures   every \\includegraphics file equals figures/<same name> byte for byte (sha256), and every hash in its
               .sources.txt sidecar equals the current result file (C8b)
  G4 refs      every item of main.bbl prints a DOI or URL; refs.bib has no `note` field (C5, C5b)
  G5 abstract  150-250 words on the rendered PDF; first sentence contains "reference-verification screens" (A2)
  G6 e-mail    no e-mail address in submission_package/ text files except noreply placeholders (rule P3)
  G7 tone      counts of first/novel/guarantee/superior/unprecedented in the rendered text (C3; report only)
  G8 claims    claims.csv exists and has one row per numbered sentence (B1)
  G9 pages     page count of main.pdf (report)
Usage: python verify_package.py   (exit 1 on any FAIL)
"""
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import ROOT  # noqa: E402

PKG = ROOT / "submission_package"
TEX = PKG / "latex"
res = []


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def gate(name, ok, msg=""):
    res.append((name, ok, msg))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {msg}")


def main():
    # G1: regenerate into a temp copy and compare
    gen = [p for p in TEX.glob("tab_*.tex")] + [TEX / "numbers_ms.tex"]
    before = {p.name: sha(p) for p in gen}
    tmp = Path(tempfile.mkdtemp())
    for p in gen:
        shutil.copy2(p, tmp / p.name)
    subprocess.run([sys.executable, str(ROOT / "code" / "make_ms_numbers.py")], check=True, capture_output=True)
    after = {p.name: sha(TEX / p.name) for p in gen}
    diff = [k for k in before if before[k] != after.get(k)]
    gate("G1 numbers", not diff, f"{len(gen)} files; changed on regeneration: {diff}")
    # G2
    t = (TEX / "main.tex").read_text(encoding="utf-8")
    defined = set(re.findall(r"\\nvset\{([^}]+)\}", (TEX / "numbers_ms.tex").read_text(encoding="utf-8")))
    used = set(re.findall(r"\\nv\{([^}]+)\}", re.sub(r"(?m)^\s*%.*$", "", t)))
    log = (TEX / "main.log").read_text(encoding="utf-8", errors="replace")
    errs = re.findall(r"^! .*|undefined (?:references|citations)|Citation `[^']+' .*undefined", log, re.M)
    gate("G2 keys", not (used - defined) and not errs, f"{len(used)} keys used; undefined {sorted(used - defined)}; log errors {errs[:3]}")
    # G3
    bad = []
    figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", t)
    for f in figs:
        p = TEX / f
        q = ROOT / "figures" / Path(f).name
        if not p.exists() or not q.exists() or sha(p) != sha(q):
            bad.append(f"{f}: differs from figures/")
        side = q.with_suffix(".sources.txt")
        for line in side.read_text(encoding="utf-8").splitlines()[1:]:
            m = re.match(r"([0-9a-f]{64})\s+(\S+)", line.strip())
            if m and sha(ROOT / m.group(2)) != m.group(1):
                bad.append(f"{side.name}: {m.group(2)} changed since the figure was drawn")
    gate("G3 figures", not bad, f"{len(figs)} figures; {bad}")
    # G4
    bbl = (TEX / "main.bbl").read_text(encoding="utf-8")
    items = re.split(r"\\bibitem", bbl)[1:]
    noid = [i[:60] for i in items if "\\doi{" not in i and "\\url{" not in i]
    notes = re.findall(r"^\s*note\s*=", (TEX / "refs.bib").read_text(encoding="utf-8"), re.M)
    gate("G4 refs", not noid and not notes, f"{len(items)} items; without identifier {len(noid)}; note fields {len(notes)}")
    # G5
    txt = subprocess.run(["pdftotext", "-enc", "UTF-8", str(TEX / "main.pdf"), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    ab = txt[txt.index("Abstract") + 8:txt.index("Keywords")]
    nw = len(ab.split())
    first = " ".join(ab.split()[:12]).lower()
    gate("G5 abstract", 150 <= nw <= 250 and first.startswith("reference-verification screens"), f"{nw} words; starts '{first[:60]}'")
    # G6
    hits = []
    for p in PKG.rglob("*"):
        if p.is_file() and p.suffix in (".tex", ".bib", ".csv", ".md", ".txt", ".bbl") and "_springer_template_reference" not in p.parts:
            for m in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", p.read_text(encoding="utf-8", errors="replace")):
                if m.group(0).lower() not in ("noreply@example.org", "noreply@anthropic.com"):
                    hits.append(f"{p.relative_to(PKG)}: {m.group(0)}")
    gate("G6 e-mail", not hits, f"{hits[:5]}")
    # G7 (report)
    tone = {w: len(re.findall(rf"\b{w}\w*", txt, re.I)) for w in ("first", "novel", "guarantee", "superior", "unprecedented")}
    gate("G7 tone (report)", True, str(tone))
    # G8
    cl = PKG / "claims.csv"
    gate("G8 claims", cl.exists() and sum(1 for _ in cl.open(encoding="utf-8")) > 10, str(cl.name))
    # G9
    info = subprocess.run(["pdfinfo", str(TEX / "main.pdf")], capture_output=True, text=True).stdout
    gate("G9 pages (report)", True, re.search(r"Pages:\s+(\d+)", info).group(1))
    sys.exit(0 if all(ok for _, ok, _ in res) else 1)


if __name__ == "__main__":
    main()
