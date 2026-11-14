#!/usr/bin/env python3
"""Topic 43 / P3F: two descriptive checks of GT-3 (PROMPT_43_P3F Viec 2 item 9 and Viec 4 item 16). Offline; no request.

rb-vs-gt3   R_B label x GT-3 state on the 48 flagged rows (origin U of the withdrawn sheet = 2019-21 academic unresolved,
            i.e. members of set acad1921). The key of H01-H68 is decrypted in memory only (plaintext hash checked by
            p3e_human_sheet.load_key_rows); only counts are written. -> results/p3f_rB_vs_gt3.{csv,json}. Supplement only.
spotcheck   10 found references drawn with seed 51 from the title-rule matches of the bound sets (acad1921, acad2426,
            nonacad1921; URL/Wayback matches have no record title and are left out): reference title beside the matched
            record's title. A table for readers to look at, not a scoring step. -> P3F/gt3_spotcheck.md, or
            P3F/interim_gt3_spotcheck.md while GT-3 may still ask (before 2026-11-12T23:59Z with acad2426 unanswered).
Usage: python code/p3f_gt3_checks.py rb-vs-gt3 | spotcheck
"""
import hashlib
import json
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3f_deep_search as ds  # noqa: E402

RES = ds.RES
STATES = ["found", "not found", "unanswered", "not in acad1921"]
LABELS = ["exists", "ambiguous", "not-exists"]
BOUND_SETS = ["acad1921", "acad2426", "nonacad1921"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rb_vs_gt3():
    import p3e_human_sheet as hs
    k, _ = hs.load_key_rows()
    rb = hs.rd(hs.RES / hs.RATERS["R_B"])[["check_id", "exists"]]
    m = k[k.origin == "U"][["check_id", "paper_id", "key"]].merge(rb, on="check_id", how="left")
    m["label"] = m.exists.str.strip().str.lower()
    m["ref_id"] = m.paper_id + "/" + m.key
    x = pd.read_csv(ds.OUTCSV, dtype=str, keep_default_na=False)
    a = x[x.set == "acad1921"].set_index("ref_id")
    m["gt3"] = [a.loc[r, "state"] if r in a.index else "not in acad1921" for r in m.ref_id]
    m["gt3_source"] = [a.loc[r, "source"] if r in a.index else "" for r in m.ref_id]
    tab = pd.crosstab(m.label, m.gt3).reindex(index=LABELS, columns=STATES, fill_value=0)
    tab["total"] = tab.sum(axis=1)
    tab.loc["total"] = tab.sum()
    tab.index.name = "R_B label \\ GT-3 state"
    tab.to_csv(RES / "p3f_rB_vs_gt3.csv")
    found_src = m[m.gt3 == "found"].gt3_source.value_counts().to_dict()
    out = {"label": "R_B (AI sub-agent) label x GT-3 state, 48 flagged rows; Supplement only; descriptive; no inference",
           "n": len(m), "crosstab": {r: {c: int(tab.loc[r, c]) for c in tab.columns} for r in tab.index},
           "found_by_source": found_src, "gt3_file_sha256": sha(ds.OUTCSV),
           "rater_file_sha256": sha(hs.RES / hs.RATERS["R_B"]), "key_plaintext_sha256_checked": hs.KEY_PLAIN_SHA,
           "note": "acad1921 has no request left (S2 3/3 passes, other sources answered); its states are final"}
    (RES / "p3f_rB_vs_gt3.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(tab.to_string())
    print("found by source:", found_src)


def gt3_open(x):
    """Open while acad2426 has an unanswered row whose missing source still has a pass left (arXiv/S2: 3 per set)."""
    a = x[(x.set == "acad2426") & (x.state == "unanswered")]
    if ds.now() > ds.NO_ASK_AFTER or not len(a):
        return False
    import json
    st = json.loads((ds.OUT / "deep_search_state.json").read_text(encoding="utf-8")).get("acad2426", {})
    miss = {s.strip() for m in a.missing_sources for s in m.replace(";", ",").split(",") if s.strip()}
    return any(s not in ("arxiv", "s2") or st.get(s, {}).get("n", 0) < 3 for s in miss)


def spotcheck():
    ds.install()  # stored answers of GT-3 live in cache_p3f
    ds.rm.OFFLINE = True  # never a request
    x = pd.read_csv(ds.OUTCSV, dtype=str, keep_default_na=False)
    interim = gt3_open(x)
    out = ds.OUT / ("interim_gt3_spotcheck.md" if interim else "gt3_spotcheck.md")
    pool = x[x.set.isin(BOUND_SETS) & (x.state == "found") & ~x.source.isin(["url", "wayback"])].sort_values(["set", "ref_id"])
    pick = random.Random(51).sample(pool.to_dict("records"), 10)
    refs = {}
    for s in sorted({p["set"] for p in pick}):
        refs.update({(s, r["ref_id"]): r for r in ds.load_refs(s, 48)})
    esc = lambda t: " ".join(str(t).split()).replace("|", "\\|")  # noqa: E731
    L = ["# GT-3 spot-check: 10 ref *found* (seed 51)" + (" — TẠM" if interim else ""), "",
         "Bảng để người đọc tự xem, **không** phải bước chấm (PROMPT_43_P3F Việc 4 mục 16).", "",
         f"- Nguồn: `results/p3f_deep_search.csv`, sha256 `{sha(ds.OUTCSV)}`.",
         f"- Tập rút: ref *found* bằng luật title trong {', '.join(BOUND_SETS)} (n = {len(pool)}); ref tìm qua URL/Wayback bỏ ra vì không có title bản ghi.",
         "- Rút: sắp theo (set, ref_id), `random.Random(51).sample(…, 10)`.", ""]
    if interim:
        L += ["**TẠM:** acad2426 còn ref chưa đủ nguồn và GT-3 còn hỏi đến 2026-11-12T23:59Z; bảng chính thức rút lại khi GT-3 xong.", ""]
    L += ["| # | Tập | ref_id | Tầng | Nguồn | sim | tác giả | năm | Title của ref | Title bản ghi | Bản ghi |",
          "|---:|---|---|---|---|---:|---|---|---|---|---|"]
    for i, p in enumerate(pick, 1):
        r = refs[(p["set"], p["ref_id"])]
        cands = ds.stored(p["source"], r) or []
        c = next((c for c in cands if c["id"] == p["record_id"]), None)
        rt = max(c["titles"], key=lambda t: ds.rm.title_sim(r["title"], t)) if c else "(không thấy trong câu trả lời đã lưu)"
        L.append(f"| {i} | {p['set']} | `{p['ref_id']}` | {p['tier']} | {p['source']} | {float(p['sim']):.3f} | {p['author_ok']} | {p['year_ok']} | "
                 f"{esc(r['title'])} | {esc(rt)} | `{esc(p['record_id'])}` |")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out.name, "pool", len(pool), "sha256", sha(out))


if __name__ == "__main__":
    {"rb-vs-gt3": rb_vs_gt3, "spotcheck": spotcheck}[sys.argv[1]]()
