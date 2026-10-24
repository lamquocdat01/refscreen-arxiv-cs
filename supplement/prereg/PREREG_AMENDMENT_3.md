# PREREG_43 — Amendment 3: DBLP added as a title backend (offline dump); cascade order; cumulative-backend table

- **Date:** 2026-10-19, written before the final u_s, FP or hypothesis tests. It was written while round 2 (live S2)
  was in progress: run7 was stopped at 1,500 / 16,809 references; the S2 answers received so far are kept in the cache
  and reused.
- **Unchanged:** `PREREG_43.md` (`38378e74…`), Amendment 1 (`f9137b5f…`), Amendment 2 (`bc53f7d0…`).
- **Disclosure:** when this was written, the following were known:
  - the round-1 interim u_s (provisional, before and after Amendment 2);
  - the diagnostic `P1_DIAG_JC60_20261019.md`.

## Why

- **What the diagnostic found.** Of 60 unresolved J/C references (round 1), 47 are real papers missed by the search.
  Most are from venues that have no Crossref DOI (ICLR, ICML, NeurIPS, USENIX, ACL, JMLR…).
- **Why DBLP.** DBLP indexes these venues, so a screen that uses DBLP will flag fewer of them.
- **Implication for the paper.** The false-positive rate of a screen depends on its backend set. The paper therefore
  reports u_s for each cumulative set of backends.

## What changes

1. **DBLP backend, offline.**
   - Source: the DBLP XML dump `dblp.xml.gz`, release of 2026-10-19 (md5 and sha256 in
     `D:\Datasets\dblp\DATA_SOURCES.md`; licence CC0).
   - Why not the API: the DBLP search API (dblp.org, dblp.uni-trier.de, dblp.dagstuhl.de) answered every request with
     a proof-of-work bot-wall page (HTTP 202, checked 2026-10-19). It cannot be queried by a script.
   - Each query title gets the top 5 DBLP records by `refmatch.title_sim`, with blocking on the query's 3 rarest
     tokens. The answers are stored in the normal cache (`cache/dblp/`).
   - Resolved means similarity ≥ 0.9, as for every other backend.
   - For def 2, DBLP author names come from the same record.
   - Code: `code/dblp_offline.py`, `refmatch.dblp_search`.
2. **Cascade order** (both rounds). The cascade still stops at the first backend that resolves.
   1. Crossref;
   2. arXiv `ti:`, only for references with an arXiv id or in tier P (Amendment 1);
   3. DBLP;
   4. OpenAlex (keyless; skipped once refused);
   5. S2: stored answers in round 1, live calls from round 2.

   Under Amendment 1, S2 was second. It moves to the end so that the order of first hits gives the cumulative table
   (item 4) directly. Resolution (any backend ≥ 0.9) does not depend on the order. Only the attribution
   (`backends_hit`) and the set of calls made change.
   - Cost: about 2,776 references (tier P or with an arXiv id) that were resolved by a stored S2 answer now need an
     arXiv `ti:` call first, at 1 request / 3 s.
3. **Scope of DBLP.** DBLP answers are computed for every titled reference that Crossref did not resolve (23,498
   references; offline, so no rate limit). This is a superset of the references that are still unresolved: the "+DBLP"
   column needs DBLP for every reference that reaches it in the cascade.
   - Run of 2026-10-19: 16,269 distinct normalised titles. Index of 8,799,858 DBLP records. 1.09 × 10⁹ scored
     pairs (pass 2 took 5,351 s). Every one of the 23,498 references has a stored DBLP answer.
   - 16,609 of the 23,498 (70.7 %) have a DBLP hit with similarity ≥ 0.9. Many of these were already resolved by
     arXiv or S2, and the per-column counts come only from the table in item 5. This count is mechanical and was
     computed before any u_s with DBLP.
4. **Round 2 S2.** Live S2 runs only on the references still unresolved after Crossref → arXiv → DBLP → OpenAlex
   (plus def-2 references waiting for S2 author lists). The retry rounds stay as in Amendment 1.
5. **New main descriptive table** (`code/p1_backend_table.py` → `results/p1_backend_table.{csv,json}`).
   - Contents: def-1 u_s for each period × tier (J, C, P, B, S, W, A, all, certified-real), plus tier P split by
     identifier (arXiv id / DOI only / no id).
   - Columns, cumulative: Crossref-only → +arXiv → +DBLP → +OpenAlex → +S2. The denominator is the same in every
     column.
   - CIs: Wilson for every column; paper-level bootstrap for Crossref-only and +S2.
   - The Crossref-only column is kept.

## What does NOT change

- **Definitions:** def 1, def 2, the 0.9 threshold, `title_sim` (with Amendment 2), and the three states.
- **The primary u_s:** these are the last column (+S2, i.e. all backends).
- **Everything else:** tiers, H1–H5, sample sizes, the manual protocol and the five primary analyses.

## Notes and sensitivity (reported)

- **Manual check (independence).** One row of the first pass (M098) used a DBLP web record as evidence. The other DBLP
  attempts failed (39 rows noted "DBLP 429"). κ and the manual-vs-route-(a) comparison are reported with and without
  M098.
- **Blocking (sensitivity).** A random sample of 200 DBLP queries is re-scored against the full index without blocking.
  The number of top-1 differences is reported.
- **Secondary findings.**
  - Tier P with no identifier in 2024–26 is reported as its own row. Its round-1 u is 14.3 %, twice that of P with an
    arXiv id.
  - Among unresolved P references with an arXiv id, 512 of 785 (2024–26, round 1) are `mismatch`: the id resolves, but
    the `.bib` title differs from the arXiv title. This is reported as a finding (authors edit the title when citing a
    preprint).

Code: `code/refmatch.py`, `code/ground_truth_p1.py`, `code/dblp_offline.py`, `code/p1_backend_table.py`. Backups of the
pre-amendment versions: `%TEMP%\*.bak_20261019`.
