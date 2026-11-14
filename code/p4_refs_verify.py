#!/usr/bin/env python3
"""Topic 43 / P4 (checklist C5): verify every reference rendered in the article (cited keys of main.aux) against its
registry: a DOI is resolved in Crossref (or, for 10.48550/arXiv.<id>, in the arXiv API) and its title (similarity
>= 0.90), year (any of the registry's dates, +-1) and first-author surname are compared; a URL-only entry is fetched
(status). Responses are cached by verify_refs.cached_get ($THS_DATASETS/_derived/43/cache/lit/); mailto is the
noreply placeholder of verify_refs.
Output: P4/REFS_VERIFY_43.md, results/p4_refs_verify.csv
Usage: python code/p4_refs_verify.py
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_refs as vr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "submission_package" / "latex"


def parse_bib(text):
    out = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", text, re.S):
        typ, key, body = m.group(1), m.group(2).strip(), m.group(3)
        f = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}", body):
            f[fm.group(1).lower()] = fm.group(2)
        out[key] = dict(type=typ, **f)
    return out


def delatex(s):
    """LaTeX accents and symbols of the .bib written out, so that they compare with registry text."""
    s = (s or "").replace(r"{\textperiodcentered}", "·").replace(r"\textperiodcentered", "·")
    s = re.sub(r"\\[\'`\"^~.=uvHc]\s*\{?([A-Za-z])\}?", r"\1", s)
    return s.replace("{", "").replace("}", "").replace(r"\%", "%").replace(r"\&", "&")


def fold(s):
    s = unicodedata.normalize("NFKD", delatex(s))
    s = re.sub("[‐‑‒–—]", "-", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def first_surname(author):
    a = (author or "").split(" and ")[0].strip().strip("{}")
    a = a.split(",")[0] if "," in a else a.split()[-1] if a.split() else ""
    return fold(a).strip()


def main():
    aux = (TEX / "main.aux").read_text(encoding="utf-8", errors="replace")
    keys = sorted({k.strip() for m in re.finditer(r"\\citation\{([^}]*)\}", aux) for k in m.group(1).split(",")})
    bib = parse_bib((TEX / "refs.bib").read_text(encoding="utf-8"))
    rows = []
    for k in keys:
        e = bib.get(k)
        if e is None:
            rows.append(dict(key=k, id="MISSING IN BIB", result="FAIL"))
            continue
        doi = (e.get("doi") or "").strip()
        url = (e.get("url") or "").strip()
        title, year = delatex(e.get("title", "")), e.get("year", "")
        sur = first_surname(e.get("author", ""))
        r = dict(key=k, type=e["type"], id=f"doi:{doi}" if doi else (f"url:{url}" if url else "none"), title_sim="",
                 year_ok="", author_ok="", status="", note_field=e.get("note", ""), result="")
        if doi.lower().startswith("10.48550/arxiv."):
            rec = vr.arxiv_record(doi.split(".", 2)[2])
            if rec:
                r["title_sim"] = round(vr.sim(title, rec["title"]), 3)
                py = int(rec["published"][:4]) if rec.get("published") else None
                r["year_ok"] = py is not None and abs(py - int(year)) <= 1
                r["author_ok"] = any(sur and sur in fold(a) for a in rec["authors"])
                r["status"] = "arXiv record"
            else:
                r["status"] = "arXiv: no record"
        elif doi:
            msg = vr.crossref_work(doi)
            if msg:
                r["title_sim"] = round(vr.sim(title, vr.cr_title(msg)), 3)
                ys = vr.cr_years(msg)
                r["year_ok"] = bool(ys) and any(abs(y - int(year)) <= 1 for y in ys)
                au = [fold((a.get("family") or a.get("name") or "")) for a in msg.get("author", [])]
                au += [fold(a.get("name", "")) for a in msg.get("editor", [])]
                r["author_ok"] = (not au) or any(sur and sur in a for a in au)
                r["status"] = "Crossref record" + ("" if au else " (no author list)")
            else:
                r["status"] = "Crossref: DOI not resolved"
        elif url:
            st, fin = vr.url_check(url)
            r["status"] = f"HTTP {st}"
            r["title_sim"], r["year_ok"], r["author_ok"] = "n/a", "n/a", "n/a"
        ok_id = bool(doi or url)
        if doi:
            ok = r["status"].endswith("record") or r["status"].startswith("Crossref record")
            ok = ok and isinstance(r["title_sim"], float) and r["title_sim"] >= 0.90 and r["year_ok"] and r["author_ok"]
        else:
            ok = ok_id and r["status"].startswith("HTTP 2") or r["status"].startswith("HTTP 3")
        bad_note = bool(re.search(r"(?i)todo|internal|P\d[A-Z]?\b|CP\d|LQD|cowork", r["note_field"]))
        r["result"] = "PASS" if ok and not bad_note else ("CHECK" if ok_id else "FAIL")
        rows.append(r)
    d = pd.DataFrame(rows)
    d.to_csv(ROOT / "results" / "p4_refs_verify.csv", index=False, encoding="utf-8")
    n = len(d)
    md = ["# REFS_VERIFY_43 — tham chiếu của bản rendered (v1.7), kiểm C5",
          "",
          f"Nguồn: các khoá được trích trong `main.aux` ({n} mục) và `refs.bib`. DOI: Crossref REST (mailto noreply) hoặc "
          "arXiv API cho `10.48550/arXiv.<id>`; URL: GET (cache). Tiêu chí PASS: title sim ≥ 0,90, năm ±1, họ tác giả "
          "đầu có trong bản ghi; URL trả 2xx/3xx; trường `note` không có ghi chú nội bộ.",
          "",
          f"**Tổng:** {(d.result == 'PASS').sum()} PASS · {(d.result == 'CHECK').sum()} CHECK · {(d.result == 'FAIL').sum()} FAIL · "
          f"không định danh: {(d.id == 'none').sum()}.",
          "",
          "| Key | Loại | Định danh | Title sim | Năm | Tác giả | Trạng thái | Kết quả |",
          "|---|---|---|---|---|---|---|---|"]
    for r in d.itertuples():
        md.append(f"| {r.key} | {getattr(r, 'type', '')} | {r.id} | {r.title_sim} | {r.year_ok} | {r.author_ok} | {r.status} | {r.result} |")
    (ROOT / "P4" / "REFS_VERIFY_43.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(d.result.value_counts().to_dict())
    print(d[d.result != "PASS"][["key", "id", "title_sim", "year_ok", "author_ok", "status"]].to_string())


if __name__ == "__main__":
    main()
