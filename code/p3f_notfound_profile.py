#!/usr/bin/env python3
"""Topic 43 / P3F: POST-HOC descriptive profile of the acad1921 references that GT-3 did not find (LQD 2026-11-09).
Offline. Does not change any GT-3 rule; not used for inference. Output: P3F/gt3_notfound_profile.md
12-11 (P3F2 Viec 3a): tables split by reference source (.bib vs .bbl parsed by GROBID) and a fixed list of signs of a
title-extraction error (EXTRACT_SIGNS below, written before this run, descriptive); counts also in
results/p3f_notfound_profile.json for the manuscript (Sect. 5 paragraph "extraction error vs outside the indexes").
Usage: python code/p3f_notfound_profile.py
"""
import json
import re
import hashlib
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3f_deep_search as ds  # noqa: E402
import refmatch as rm  # noqa: E402

OUT = ds.OUT / "gt3_notfound_profile.md"
SEED = 52
TIERS = ["J", "C", "P"]
VENUE_FIELDS = ("journal", "booktitle", "publisher", "howpublished", "institution")


def venue_of(row):
    if row["ref_source"] == "bib":
        e = ds.bib_entry(row["arxiv_id"], row["key"])
        return next((rm.strip_latex(e.get(f, "")) for f in VENUE_FIELDS if e.get(f, "").strip()), "")
    return row.get("f_journal") or row.get("f_booktitle") or ""


MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}
# signs that the stored title is not the cited title (an extraction or entry error), each a fixed string test
EXTRACT_SIGNS = [
    ("title carries quote marks or a trailing 'in <venue>'", lambda t, v: bool(re.search(r"(,''|``|''|,\s*in\s+[A-Z])", t))),
    ("title carries layout residue (1em plus, minus)", lambda t, v: bool(re.search(r"\d?em plus|minus 0\.\d", t + " " + v))),
    ("title is a document identifier (Internet-Draft, RFC, draft-)", lambda t, v: bool(re.search(r"Internet-Draft|draft-|RFC\s?\d", t))),
    ("venue field is a month or repeats the title", lambda t, v: v.strip().strip(".").lower() in MONTHS or
     (v.strip() != "" and rm.norm(v) == rm.norm(t))),
    ("title holds volume/page residue (vol., pp., no.)", lambda t, v: bool(re.search(r"(vol|pp|no)\.\s?\d", t, re.I))),
]


def extract_sign(title, venue):
    hit = [name for name, f in EXTRACT_SIGNS if f(title or "", venue or "")]
    return hit[0] if hit else ""


def year_bin(y):
    if y is None:
        return "không có năm"
    return "trước 2000" if y < 2000 else ("2000–2015" if y <= 2015 else "sau 2015")


def len_bin(n):
    return "≤ 5 từ" if n <= 5 else ("6–10 từ" if n <= 10 else ("11–15 từ" if n <= 15 else "≥ 16 từ"))


def table(x, col, levels, head):
    lines = [f"| {head} | " + " | ".join(TIERS) + " | Tổng | % |", "|---|" + "---:|" * (len(TIERS) + 2)]
    for lv in levels:
        s = x[x[col] == lv]
        lines.append(f"| {lv} | " + " | ".join(str(int((s.tier == t).sum())) for t in TIERS) + f" | {len(s)} | {100 * len(s) / len(x):.1f} |")
    lines.append("| **Tổng** | " + " | ".join(str(int((x.tier == t).sum())) for t in TIERS) + f" | {len(x)} | 100.0 |")
    return lines


def main():
    res = pd.read_csv(ds.OUTCSV, dtype=str, keep_default_na=False)
    ids = set(res.ref_id[(res.set == "acad1921") & (res.state == "not found")])
    gt = ds.load_gt()
    gt["ref_id"] = gt.arxiv_id + "/" + gt.key
    gt = gt[gt.ref_id.isin(ids)]
    refs = {r["ref_id"]: r for r in ds.load_refs("acad1921", 48) if r["ref_id"] in ids}
    rows = []
    for r in gt.to_dict("records"):
        f = refs[r["ref_id"]]
        words = len(rm.norm(f["title"]).split())
        v = venue_of(r)
        rows.append({"ref_id": r["ref_id"], "tier": f["tier"], "year": f["year"], "title": " ".join(f["title"].split()), "venue": " ".join(v.split()),
                     "nam": year_bin(f["year"]), "venue_co": "có venue" if v.strip() else "không có venue",
                     "ascii": "có ký tự ngoài ASCII" if any(ord(c) > 127 for c in f["title"]) else "chỉ ASCII",
                     "dai": len_bin(words), "n_words": words, "n_chars": len(f["title"]), "nguon": r["ref_source"],
                     "dau_hieu": extract_sign(" ".join(f["title"].split()), " ".join(v.split()))})
    x = pd.DataFrame(rows).sort_values("ref_id").reset_index(drop=True)
    if len(x) != len(ids):
        sys.exit(f"STOP: {len(ids)} ids, {len(x)} rows")
    sample = random.Random(SEED).sample(x.to_dict("records"), min(20, len(x)))
    L = ["# GT-3: hồ sơ các ref acad1921 \"không tìm thấy\" (POST-HOC, MÔ TẢ)", "",
         "**Nhãn: POST-HOC, chỉ mô tả.** LQD yêu cầu 2026-11-09, sau khi đã thấy kết quả GT-3 tạm. Không đổi luật GT-3 (Amendment 8 (D)). "
         "Không dùng bảng này để suy luận, không đưa vào cận FP.", "",
         f"- Nguồn: `results/p3f_deep_search.csv`, sha256 `{hashlib.sha256(ds.OUTCSV.read_bytes()).hexdigest()}`, tập `acad1921`, trạng thái *not found*: **{len(x)} ref** (chạy lại 12-11 trên kết quả cuối).",
         "- Ref thiếu trả lời S2 (5 ref *unanswered*) không nằm trong bảng.",
         "- Năm: trường năm mà luật GT-3 dùng (`.bib`; ref chỉ có `.bbl` lấy theo Amendment 8 (D)).",
         "- Venue: `journal`, `booktitle`, `publisher`, `howpublished` hoặc `institution` của `.bib`; ref chỉ có `.bbl` dùng trường GROBID. \"Có venue\" chỉ nghĩa là trường đó không rỗng; chuỗi có thể là lỗi tách (ví dụ \"Nov\").",
         "- Ký tự ngoài ASCII: tính trên cột title như đã lưu. Dấu viết bằng lệnh LaTeX không được tính.",
         "- Độ dài: số từ sau `refmatch.norm`.", ""]
    for head, col, levels in [("Năm tài liệu được trích", "nam", ["trước 2000", "2000–2015", "sau 2015", "không có năm"]),
                              ("Venue", "venue_co", ["có venue", "không có venue"]),
                              ("Ký tự trong title", "ascii", ["chỉ ASCII", "có ký tự ngoài ASCII"]),
                              ("Độ dài title", "dai", ["≤ 5 từ", "6–10 từ", "11–15 từ", "≥ 16 từ"])]:
        L += [f"## {head}", ""] + table(x, col, levels, head) + [""]
    x["nguon_ref"] = x.nguon.map(lambda s: ".bib" if s == "bib" else ".bbl (GROBID)")
    x["co_dau_hieu"] = x.dau_hieu.map(lambda s: "có dấu hiệu lỗi trích" if s else "không có dấu hiệu")
    L += ["## Tách theo nguồn ref (.bib / .bbl-GROBID) × dấu hiệu lỗi trích title", "",
          "Dấu hiệu (danh sách cố định, viết trước lần chạy 12-11; một ref tính theo dấu hiệu đầu tiên khớp): " +
          "; ".join(n for n, _ in EXTRACT_SIGNS) + ".", ""]
    lines = ["| Nguồn ref | có dấu hiệu lỗi trích | không có dấu hiệu | Tổng |", "|---|---:|---:|---:|"]
    for s in (".bib", ".bbl (GROBID)"):
        q = x[x.nguon_ref == s]
        lines.append(f"| {s} | {int((q.dau_hieu != '').sum())} | {int((q.dau_hieu == '').sum())} | {len(q)} |")
    lines.append(f"| **Tổng** | {int((x.dau_hieu != '').sum())} | {int((x.dau_hieu == '').sum())} | {len(x)} |")
    L += lines + ["", "| Dấu hiệu | .bib | .bbl (GROBID) | Tổng |", "|---|---:|---:|---:|"]
    for n, _ in EXTRACT_SIGNS:
        q = x[x.dau_hieu == n]
        L.append(f"| {n} | {int((q.nguon_ref == '.bib').sum())} | {int((q.nguon_ref != '.bib').sum())} | {len(q)} |")
    L.append("")
    for head, col, levels in [("Năm × nguồn ref", "nam", ["trước 2000", "2000–2015", "sau 2015", "không có năm"]),
                              ("Độ dài title × nguồn ref", "dai", ["≤ 5 từ", "6–10 từ", "11–15 từ", "≥ 16 từ"])]:
        L += [f"## {head}", "", f"| {head.split(' ×')[0]} | .bib | .bbl (GROBID) | Tổng |", "|---|---:|---:|---:|"]
        for lv in levels:
            q = x[x[col] == lv]
            L.append(f"| {lv} | {int((q.nguon_ref == '.bib').sum())} | {int((q.nguon_ref != '.bib').sum())} | {len(q)} |")
        L.append("")
    js = {"label": "POST-HOC, descriptive (LQD 2026-11-09, extended 2026-11-12); acad1921 not found; not used for inference",
          "gt3_file_sha256": hashlib.sha256(ds.OUTCSV.read_bytes()).hexdigest(), "n": int(len(x)),
          "by_source": {s: int((x.nguon_ref == s).sum()) for s in (".bib", ".bbl (GROBID)")},
          "extract_sign": {s: int(((x.nguon_ref == s) & (x.dau_hieu != "")).sum()) for s in (".bib", ".bbl (GROBID)")},
          "extract_sign_total": int((x.dau_hieu != "").sum()),
          "by_sign": {n: int((x.dau_hieu == n).sum()) for n, _ in EXTRACT_SIGNS},
          "by_tier": {t: int((x.tier == t).sum()) for t in TIERS},
          "cited_before_2000": int((x.nam == "trước 2000").sum()), "no_year": int((x.nam == "không có năm").sum()),
          "title_le5_words": int((x.dai == "≤ 5 từ").sum()), "median_words": float(x.n_words.median())}
    (ds.ROOT / "results" / "p3f_notfound_profile.json").write_text(json.dumps(js, indent=1, ensure_ascii=False), encoding="utf-8")
    L += [f"Độ dài title: trung vị {x.n_words.median():.0f} từ, {x.n_chars.median():.0f} ký tự. Nguồn ref: " +
          ", ".join(f"{k} {v}" for k, v in x.nguon.value_counts().items()) + ".", "",
          f"## 20 ví dụ ngẫu nhiên (seed {SEED})", "", "| # | ref_id | Tầng | Năm | Nguồn | Dấu hiệu | Title | Venue |", "|---:|---|---|---:|---|---|---|---|"]
    esc = lambda s: str(s).replace("|", "\\|")  # noqa: E731
    for i, r in enumerate(sample, 1):
        L.append(f"| {i} | `{r['ref_id']}` | {r['tier']} | {'' if r['year'] is None or pd.isna(r['year']) else int(r['year'])} | {r['nguon']} | {esc(r['dau_hieu'] or '—')} | {esc(r['title'])} | {esc(r['venue'])} |")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("rows", len(x), "| tiers", x.tier.value_counts().to_dict(), "|", x.nam.value_counts().to_dict(), "|", x.venue_co.value_counts().to_dict(), "|", x.ascii.value_counts().to_dict(), "|", x.dai.value_counts().to_dict())
    print("sha256", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
