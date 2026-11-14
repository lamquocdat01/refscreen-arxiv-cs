# Amendment 9 — web evidence for the flagged .bib references of 2019–21 (post hoc)

Copies of the files of Amendment 9 (`PREREG_AMENDMENT_9.md`, hashed before any step); working files stay in `results/`.
- `p3h_evidence_sheet.csv`: blind sheet (81 real + 19 planted rows, E001–E100).
- `p3h_evidence_agent.csv`: one URL per row from the searcher sub-agents.
- `capture_raw_*.txt`, `capture_manifest.csv`: page captures (verbatim fields), with UTC time and sha256 per page.
- `p3h_evidence_checked.csv`: rule check (code/p3h_evidence_check.py).
- `evidence_review.html`, `p3h_evidence_author_form.csv`: the author's form; `rate_tool.html` (built by
  `make_rate_tool.py` from `rate_tool_template.html`, sheet, rule check and empty form only; no key): the tool used to fill it.
- `p3h_evidence_author.csv`: the author's decisions (y / n / ?).
- `p3h_evidence_key.csv`: the key, released after the author's file existed (sha256 logged before the search).
- `p3h_evidence_score.csv`: joined rows with the confirmation of each.
- `SHA256SUMS`: hashes of every file in this folder.
