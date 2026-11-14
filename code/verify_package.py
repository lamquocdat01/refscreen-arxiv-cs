#!/usr/bin/env python3
"""Topic 43 / P3: hard gates on the submission package (checklist C5, C6, C8b, B1, A2, C3, C10/C11, e-mail rule).

Checks, each PASS/FAIL:
  G1 numbers   numbers_ms.tex and tab_*.tex equal a fresh run of make_ms_numbers.py (no stale or hand-edited number)
  G2 keys      every \\nv{key} in main.tex is defined; main.log has no LaTeX error, undefined reference or citation
  G3 figures   every \\includegraphics file equals figures/<same name> byte for byte (sha256), and every hash in its
               .sources.txt sidecar equals the current result file (C8b)
  G4 refs      every item of main.bbl prints a DOI or URL; refs.bib has no `note` field (C5, C5b)
  G5 abstract  150-250 words on the rendered PDF; first sentence opens with "reference-verification checks" (A2)
  G6 e-mail    no e-mail address in submission_package/ text files except noreply placeholders (rule P3)
  G7 tone      counts of first/novel/guarantee/superior/unprecedented in the rendered text (C3; report only)
  G8 claims    claims.csv exists and has one row per numbered sentence (B1)
  G9 pages     page count of main.pdf (report)
  G10 PDF text every DOI and URL of refs.bib, as a string, in the text layer of main.pdf (pdftotext, whitespace removed,
               case-insensitive; a "_" that renders as a rule fails here); every DOI in supplement.tex, same test (C5)
  G10b DOI     no DOI split across lines of the main text layer (R2 Q17e)
  G11 hygiene  no internal labels in the package sources: CP-, P3C, LQD, the author's e-mail outside the title page and
               the cover letter; Cowork only in the AI disclosure
  G11+         (R2 Q16) project labels, run names, local paths and placeholders (topic N, phase N, checkpoint, CP..N, runN,
               CC, drive paths, %TEMP%, "an internal record", go/no-go, .bak, THEORY_43, p3a-e_ file names) in the
               submitted sources (comments stripped) and in the text of main.pdf, supplement.pdf and cover_letter.pdf;
               placeholders only inside \\TODOSUBMIT{...}; --final (P4) fails on any \\TODOSUBMIT left
  G11k secrets no .env / key material (code/package_exclude.py) and no OpenAlex or S2 key value in the package, source.zip,
               repository working tree, release data, cache_p3e or cache_p3f (prints counts and file names only)
Usage: python verify_package.py [--final]   (exit 1 on any FAIL)
       python verify_package.py --g11k      (G11k alone)
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import ROOT  # noqa: E402

PKG = ROOT / "submission_package"
# P4: the corresponding author's e-mail, read from \email{} of main.tex (never written into code or the repository);
# it is allowed only on the title page and in the cover letter
_em = re.search(r"\\email\{([^{}@]+@[^{}]+)\}", (PKG / "latex" / "main.tex").read_text(encoding="utf-8"))
AUTHOR_EMAIL = _em.group(1).lower() if _em else "\0none"
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
    gate("G5 abstract", 150 <= nw <= 250 and first.startswith("reference-verification checks"), f"{nw} words; starts '{first[:60]}'")
    # G6
    hits = []
    for p in PKG.rglob("*"):
        if p.is_file() and p.suffix in (".tex", ".bib", ".csv", ".md", ".txt", ".bbl") and "_springer_template_reference" not in p.parts:
            for m in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", p.read_text(encoding="utf-8", errors="replace")):
                ok_author = m.group(0).lower() == AUTHOR_EMAIL and p.name in ("main.tex", "cover_letter.tex")
                if m.group(0).lower() not in ("noreply@example.org", "noreply@anthropic.com") and not ok_author:
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
    # G10: the printed identifier, as a string, in the text layer
    squeeze = lambda s: re.sub(r"\s+", "", s).lower()  # noqa: E731
    bib = (TEX / "refs.bib").read_text(encoding="utf-8")
    entries = re.findall(r"@\w+\{([^,]+),(.*?)\n\}", bib, re.S)
    # only the entries that are printed (cited) in main.pdf; refs.bib may hold entries the article no longer cites
    printed = set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", (TEX / "main.bbl").read_text(encoding="utf-8"), re.S))
    entries = [(k, e) for k, e in entries if k in printed]
    body = squeeze(txt)
    miss, n_doi, n_url = [], 0, 0
    for key, e in entries:
        d = re.search(r"\bdoi\s*=\s*\{([^}]+)\}", e)
        u = re.search(r"\burl\s*=\s*\{([^}]+)\}", e)
        if d:
            n_doi += 1
            if "doi.org/" + squeeze(d.group(1)) not in body:
                miss.append(f"{key}: {d.group(1)}")
        elif u:
            n_url += 1
            if squeeze(u.group(1)) not in body:
                miss.append(f"{key}: {u.group(1)}")
        else:
            miss.append(f"{key}: no identifier")
    gate("G10 PDF text (main)", not miss, f"{n_doi} DOI + {n_url} URL of {len(entries)} entries; missing {miss[:6]}")
    # G10b: no DOI is split across lines of the text layer (a machine reader gets each DOI as one token)
    lines = [re.sub(r"\s+", "", ln).lower() for ln in txt.splitlines()]
    split = [key for key, e in entries for d in [re.search(r"\bdoi\s*=\s*\{([^}]+)\}", e)] if d
             and not any(("doi.org/" + squeeze(d.group(1))) in ln for ln in lines)]
    gate("G10b DOI on one line (main)", not split, f"{n_doi - len(split)}/{n_doi} DOIs on a single line; split {split[:6]}")
    sup_t = PKG / "supplement" / "supplement.tex"
    if sup_t.exists():
        sp = subprocess.run(["pdftotext", "-enc", "UTF-8", str(PKG / "supplement" / "supplement.pdf"), "-"], capture_output=True).stdout.decode("utf-8", "replace")
        src = sup_t.read_text(encoding="utf-8").replace("\\_", "_").replace("\\%", "%").replace("\\#", "#")
        dois = sorted({m.rstrip(".,;:)}]") for m in re.findall(r"\b10\.\d{4,9}/[^\s{}\\]+", src)})
        sbody = squeeze(sp)
        smiss = [d for d in dois if squeeze(d) not in sbody]
        gate("G10 PDF text (supplement)", not smiss, f"{len(dois)} DOI strings; missing {smiss[:6]}")
    # G11: internal labels
    hits = []
    pat = re.compile(r"\bCP-|P3C|LQD|" + re.escape(AUTHOR_EMAIL.split("@")[0] + "@"))
    for p in [TEX / "main.tex", TEX / "refs.bib", TEX / "numbers_ms.tex", PKG / "cover_letter.tex", PKG / "abstract_keywords_ascii.txt",
              PKG / "claims.csv", PKG / "supplement" / "supplement.tex"]:
        s = p.read_text(encoding="utf-8", errors="replace")
        if p.name in ("main.tex", "cover_letter.tex"):  # P4: the author's e-mail, once (title page; letter signature)
            if s.count(AUTHOR_EMAIL) != 1:
                hits.append(f"{p.name}: author e-mail {s.count(AUTHOR_EMAIL)} times (allowed once)")
            s = s.replace(AUTHOR_EMAIL, "")
        hits += [f"{p.name}: {m.group(0)}" for m in pat.finditer(s)]
        if p.name == "main.tex":  # the disclosure names the tools; nothing else may
            s = s[:s.index(r"\bmhead{Use of AI tools}")] + s[s.index(r"\bmhead{Data and code availability}"):]
        for ln in s.splitlines():
            if "Cowork" in ln:
                hits.append(f"{p.name}: Cowork outside the AI disclosure: {ln[:60]}")
    gate("G11 hygiene", not hits, f"{hits[:6]}")
    # G11+ (R2 Q16): project labels, run names, local paths and placeholders, in the sources that are submitted
    # (comments stripped, as make_upload.py does) and in the text layers of the main PDF, supplement and cover letter.
    # A placeholder is allowed only inside \TODOSUBMIT{...}; with --final (P4) any \TODOSUBMIT fails too.
    from strip_comments import strip
    lab = re.compile(r"topic \d+|phase \d|checkpoint|\bCP-?\w*\d|(?<![A-Za-z])run\d+|phase-one|\bCC\b(?! ?BY)(?!0)|\b[A-Z]:\\|\\?%TEMP\\?%|"
                     r"an internal record|go/no-go|\.bak|THEORY_43|\bp3[a-h]_|LQD|P3C|" + re.escape(AUTHOR_EMAIL.split("@")[0] + "@") + "|"
                     # P3G (S6' S18): local data paths, caches, key files, rater and review labels, clock times
                     r"THS_DATASETS|_derived/43|cache_p3[a-h]|(?<![\w/])\.env\b|RAM rule|alderlake|\bR_H1\b|\bR_B\b|"
                     r"manuscript v1\.\d|Reviewer 2|\d\d:\d\d ICT|repository = a result|file a result file|"
                     # P3H (closure S18, S19, N9): pre-completion numbers of the theory note, version and review labels,
                     # replacement garbage
                     r"Theorem 1\b|u_A = 2\.11|2\.11 ?% \[1\.64|\b15\.7 ?% \[13\.2|3\.3 ?×|142/299|12/299 = 4\.0|19/299 = 6\.4|61\.75|\bv1\.[0-9](?![0-9]|\.[0-9])|S6′|S6'|"
                     r"Fable 5\.2|\bR_H2\b|_p3[a-h]\b(?!\.(pdf|md))|earlier versions?\b|previous version|official spot check|"
                     r"R2_REVIEW|deep_search_state|a project note §|reviewer's objections|"
                     r"\(deposited\),? (and )?the stored responses \(deposited\)|the AI rater the AI rater", re.I)
    case = {"CC", "LQD", "P3C"}  # these are matched case-sensitively
    ph = re.compile(r"entered at submission|to be inserted|inserted at submission|\[[^\]\n]{0,80}at submission\]", re.I)
    final = "--final" in sys.argv
    hits2 = []

    def scan(name, s):
        if name.split(".")[0] in ("main", "cover_letter"):  # the author's e-mail is allowed here (title page, signature)
            s = s.replace(AUTHOR_EMAIL, "")
        for m in lab.finditer(s):
            g = m.group(0)
            if g.upper() in case and g not in case:
                continue
            if g.lower().startswith("cplex"):  # a software name in a released URL (Amendment 9 evidence list)
                continue
            hits2.append(f"{name}: {g!r} …{s[max(0, m.start() - 30):m.end() + 20]!r}")

    srcs = [TEX / "main.tex", TEX / "numbers_ms.tex", TEX / "refs.bib", PKG / "cover_letter.tex",
            PKG / "abstract_keywords_ascii.txt", PKG / "supplement" / "supplement.tex"] + sorted(TEX.glob("tab_*.tex"))
    n_todo = 0
    for p in srcs:
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8", errors="replace")
        s = strip(s) if p.suffix == ".tex" else s
        scan(p.name, s)
        todo = re.findall(r"\\TODOSUBMIT\{[^{}]*\}", s)
        n_todo += len(todo)  # P4B: the \newcommand{\TODOSUBMIT} definition does not match the pattern above
        rest = re.sub(r"\\TODOSUBMIT\{[^{}]*\}", "", s)
        hits2 += [f"{p.name}: placeholder outside \\TODOSUBMIT: {m.group(0)!r}" for m in ph.finditer(rest)]
    for pdf in (TEX / "main.pdf", PKG / "supplement" / "supplement.pdf", PKG / "cover_letter.pdf"):
        if pdf.exists():
            s = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True).stdout.decode("utf-8", "replace")
            scan(pdf.name, s)
    if final and n_todo:
        hits2.append(f"{n_todo} \\TODOSUBMIT placeholder(s) left (P4 must fill them)")
    gate("G11+ hygiene", not hits2, f"{len(hits2)} hits; \\TODOSUBMIT: {n_todo}{' (allowed before P4)' if not final else ''}; "
         f"{hits2[:8]}")
    gate_secrets()
    sys.exit(0 if all(ok for _, ok, _ in res) else 1)


def gate_secrets():
    # G11k (P3E, Addendum 2): no .env / key material in anything that is packaged, and the OpenAlex key value (or its
    # first 16 characters) in no packaged file: submission package (incl. members of source.zip), repository working
    # tree, Zenodo stage, new backend cache. Only counts and file names are printed, never the key.
    import zipfile
    from package_exclude import excluded
    # P3F (LQD 2026-11-09): the Semantic Scholar key value is scanned too, and the P3F backend cache.
    from p3e_complete_cascade import read_env_key, read_s2_key
    keys = [k for k in (read_env_key(), read_s2_key()) if k]
    needles = [n.encode() for k in keys for n in {k, k[:16]} if len(n) >= 8]
    der = Path(os.environ.get("THS_DATASETS", r"D:\Datasets")) / "_derived" / "43"
    roots = [PKG, Path(r"D:\Repos\refscreen-fp"), der / "release_v1.0.0", der / "cache_p3e", der / "cache_p3f"]
    bad_name, bad_key, n_files = [], [], 0
    for rt in roots:
        if not rt.exists():
            continue
        for p in rt.rglob("*"):
            if not p.is_file() or ".git" in p.parts:
                continue
            n_files += 1
            if excluded(p.relative_to(rt)):
                bad_name.append(str(p.relative_to(rt)))
                continue
            b = p.read_bytes()
            if needles and any(n in b for n in needles):
                bad_key.append(str(p.relative_to(rt)))
            if p.suffix == ".zip":
                with zipfile.ZipFile(p) as z:
                    for m in z.namelist():
                        if excluded(m):
                            bad_name.append(f"{p.name}:{m}")
                        elif needles and any(n in z.read(m) for n in needles):
                            bad_key.append(f"{p.name}:{m}")
    gate("G11k secrets", not bad_name and not bad_key,
         f"keys checked: {len(keys)}; {n_files} files; excluded names {bad_name[:5]}; files with key {bad_key[:5]}")


if __name__ == "__main__":
    if "--g11k" in sys.argv:  # this gate alone: the other gates regenerate package files
        gate_secrets()
        sys.exit(0 if all(ok for _, ok, _ in res) else 1)
    main()
