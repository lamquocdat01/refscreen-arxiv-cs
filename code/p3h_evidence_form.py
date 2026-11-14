#!/usr/bin/env python3
"""Topic 43 / P3H (PREREG_AMENDMENT_9.md (E); POST HOC): the author's confirmation form.

Inputs:  results/p3h_evidence_sheet.csv, results/p3h_evidence_checked.csv (no key is read).
Outputs: P3H/evidence_review.html (self-contained; every row by ID, no colouring by suspicion);
         results/p3h_evidence_author_form.csv (ID, author_check, note) for PASS, NEAR and needs_browser rows only.
Usage:   python code/p3h_evidence_form.py
"""
import html
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
TO_CHECK = ("PASS", "NEAR", "needs_browser")


def main():
    sh = pd.read_csv(RES / "p3h_evidence_sheet.csv", dtype=str, keep_default_na=False)
    ck = pd.read_csv(RES / "p3h_evidence_checked.csv", dtype=str, keep_default_na=False)
    d = sh.merge(ck, on="ID", how="left").fillna("").sort_values("ID")
    form = d[d.state.isin(TO_CHECK)][["ID"]].assign(author_check="", note="")
    form.to_csv(RES / "p3h_evidence_author_form.csv", index=False, encoding="utf-8")
    rows = []
    for r in d.itertuples():
        link = (f'<a href="{html.escape(r.url)}" target="_blank" rel="noopener noreferrer">{html.escape(r.url)}</a>'
                if r.url else "")
        need = "yes" if r.state in TO_CHECK else ""
        rows.append(f"<tr><td>{r.ID}</td><td>{need}</td><td>{html.escape(r.reference)}</td>"
                    f"<td>{html.escape(r.page_title)}</td><td>{html.escape(r.state)}</td><td class=u>{link}</td></tr>")
    n = d.state.value_counts().to_dict()
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>P3H evidence review</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--line:#d0d0d0;--head:#f2f2f2;--link:#0b57d0}}
@media (prefers-color-scheme: dark){{:root{{--bg:#151515;--fg:#e6e6e6;--line:#3a3a3a;--head:#222;--link:#8ab4f8}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;margin:16px}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid var(--line);padding:4px 6px;vertical-align:top;text-align:left}}
th{{background:var(--head);position:sticky;top:0}} a{{color:var(--link)}} td.u{{word-break:break-all;max-width:28em}}
</style></head><body>
<h1>P3H — web evidence, author confirmation (Amendment 9 (E))</h1>
<p>Rows are in ID order. "Check" = yes for rows with machine state PASS, NEAR or needs_browser: open the link, compare
the title and authors on the page with the reference string, and write <b>y</b> (the page is the cited work),
<b>n</b>, or <b>?</b> in <code>results/p3h_evidence_author_form.csv</code>; save it as
<code>results/p3h_evidence_author.csv</code>. Rows without "yes" need nothing. Do not open <code>keys/</code>.</p>
<p>Machine states: {html.escape(', '.join(f'{k} {v}' for k, v in sorted(n.items())))}; rows to check: {len(form)}.</p>
<table><thead><tr><th>ID</th><th>Check</th><th>Reference (as cited)</th><th>Title on the page</th><th>Machine</th>
<th>Link</th></tr></thead><tbody>
{chr(10).join(rows)}
</tbody></table></body></html>
"""
    (ROOT / "P3H" / "evidence_review.html").write_text(page, encoding="utf-8")
    print("form rows:", len(form), "| states:", n)


if __name__ == "__main__":
    main()
