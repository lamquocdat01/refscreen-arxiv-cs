# PREREG_43 — Amendment 5 (POST-HOC): revised decision rules (b′), (c′), (d′), a new label-stratified recheck, and adjudication of the P2 disagreements

- **Status: POST-HOC.** Written on 2026-10-24, after every P2 result was known, including all three rater labels
  (R1, R2, R3) on the 40 P2 recheck rows K01–K40 and the agreement results. The change of rules is motivated by
  those results. Every analysis under this amendment is reported as **post-hoc and supplementary**.
- **Decision:** CP-B2, LQD 2026-10-24 15:11, option "P2" (`CP_B2_DECISION_43_20261024.md`, `P2_REPORT_43.md` §11).
- **Unchanged:** `PREREG_43.md` (`38378e74…`), `manual_protocol.md` (`9ab6c684…`), Amendments 1–4
  (`f9137b5f…`, `bc53f7d0…`, `27b60150…`, `593e64b5…`).
  - H1–H5 and their PASS rules are unchanged.
  - The registered P2 agreement result stays the primary result and is reported verbatim:
    - PABAK(R1–R3) = 0.70 [0.40; 0.92], n = 20, **FAIL**;
    - pooled Amendment-4 PABAK = 0.74 [0.55; 0.91], n = 40, FAIL.
  - Nothing in this amendment replaces, re-labels or re-computes that result.

## Why
The 4 disagreements between R1 (CC pass 1) and R3 (Cowork, blind, approved row by row by LQD) on the P2 recheck all
lie on the exists ↔ ambiguous boundary. None lies on exists ↔ not-found. Three of them trace to gaps in
`manual_protocol.md`:

1. **K25, K29 — condition (c).**
   - The reference matches on title (a) and author (b), but it appeared after the citing paper's arXiv **v1** date.
   - Our .bib files come from the arXiv e-print, which serves the **latest** version at download time, so a
     reference added in a later version fails (c) against v1 by construction.
   - The protocol assigns no outcome to "(a) and (b) met, (c) failed".
2. **K33 — condition (b) for software and data.**
   - The .bib names an organisation (a lab), but the repository at the cited URL belongs to a personal account.
   - The protocol counts the "owning organisation or repository owner" as author, but does not say what to do
     when the two differ.
3. **K10, K15 (P2 intra-rater disagreements) — input.**
   - For references taken from the author's .bbl whose title could not be parsed, the recheck sheet showed only an
     author surname, while pass 1 had the full .bbl item.

## What changes

### (b′) Author condition for software, datasets and other repositories
- When the entry names an organisation and the resource is hosted under a personal account, the personal owner
  counts as that organisation **if** the repository README, or the paper that accompanies the resource, names the
  organisation.
- Otherwise (b) is not met.

### (c′) Date condition: reference date = date of the version the .bib was taken from
- The reference date is `src_version_date` in `data_manifest/manifest_src_version.csv` (`code/src_version.py`).
- This is the date of the arXiv version served by the e-print endpoint when the source was downloaded. It is
  recovered offline from the cached arXiv API listings.
  - For each paper, the latest listing queried at or before the download is used.
  - 0 of 1,300 kept papers needed a later listing.
- A resource meets (c′) if it existed no later than that date.
- **Outcome gap closed:** if (a) and (b) hold and (c′) fails, the outcome is **ambiguous**.
- Both reference dates are shown on the sheet: v1 and the .bib version.

### (d′) Recheck sheet input
- Next to the .bib entry, the sheet shows the matching item of the author's own .bbl (`bbl_item`), when the arXiv
  source contains a .bbl with that key.
- For references taken from the .bbl, this is the full item text that pass 1 had.

### (e′) New recheck sample (40 rows, seed 43)
- **Pool:** the pass-1 rows of the P1 manual sample (200) and of the P2 render sample (60). Excluded:
  - the 40 rows rechecked in P1;
  - the 40 rows K01–K40 rechecked in P2.
- What remains: 180 rows, all pass-1 *exists*.
- **Stratum N (20):**
  - No pass-1 not-found or ambiguous row remains, so the stratum is filled entirely with pass-1 *exists* rows that
    are def-1 unresolved after the full cascade (39 available).
  - These are drawn stratified by tier with seed 43.
- **Stratum E (20):** the other pass-1 *exists* rows, stratified by tier, seed 43.
- **Raters:**
  - **R1** = the existing pass-1 label, assigned under the **original** rules (not re-labelled).
  - **R2** = a fresh Claude Code sub-agent without session context, under the revised rules.
  - **R3** = Cowork, blind, under the revised rules.
  - Neither R2 nor R3 sees the pass-1 labels, the strata or the screen status.
- **Statistics:** as Amendment 4 (a), all with a bootstrap 95 % CI (B = 1000, seed 43, resampling citing papers):
  - PABAK, Gwet's AC1, raw κ, raw agreement and the 3 × 3 table for each pair R1–R3, R1–R2 and R2–R3;
  - the three-rater AC1.
- **Reading:**
  - PABAK(R1–R3) ≥ 0.8 is reported against the same threshold as P2.
  - R2–R3 (both raters under the revised rules) is reported alongside. It is the pair that tests the revised rules
    themselves; R1–R3 mixes old and new rules.
  - The result is labelled "recheck after Amendment 5 (post-hoc)". It is supplementary: it does not replace or offset
    the P2 FAIL.
- **Timing:** each row is rechecked ≥ 48 h after its own pass-1 timestamp. All pass-1 timestamps are ≤ 2026-10-21.

### (f′) Adjudication of the 4 P2 disagreements (FP_manual only)
- For K25, K29, K33 and K39, the adjudicated label is the majority of R1, R2 and R3:
  - K25 ambiguous;
  - K29 ambiguous;
  - K33 ambiguous;
  - K39 exists.
- The adjudicated labels are used **only** in FP_manual (H4). Agreement statistics always use the raw labels.
- H4 is reported twice: with the pass-1 labels (as registered) and with the adjudicated labels.

## What does not change
- The search order and conditions (a) of `manual_protocol.md`, including the "≤ 2 word differences" rule of (a).
- All P1/P2 labels, ground truth, screens, hypotheses and seeds of earlier amendments.
- The P2 recheck result and its FAIL.
