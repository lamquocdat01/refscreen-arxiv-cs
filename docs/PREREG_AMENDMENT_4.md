# PREREG_43 — Amendment 4: agreement criterion (PABAK), label-stratified recheck, second rater, tool scope, H3 wording

- **Date:** 2026-10-21. Written after the P1 results (`P1_REPORT_43.md`) and the CP-B1 decision
  (`CP_B1_DECISION_43_20261021.md`, GO with conditions, 2026-10-21 11:49). Written **before** any P2 data:
  - the 60-reference render sample (item f) is not drawn;
  - the P2 recheck sample (item b) is not drawn;
  - the hallucinator tool has not been run on any render paper.
- **Unchanged:** `PREREG_43.md` (`38378e74…`), `manual_protocol.md` (`9ab6c684…`), Amendment 1 (`f9137b5f…`),
  Amendment 2 (`bc53f7d0…`), Amendment 3 (`27b60150…`). H1–H5 and their PASS rules are unchanged.
- **Disclosure:** all P1 results were known when this was written, including:
  - Cohen's κ = 0 on the P1 recheck;
  - the pass-1 label counts of the P1 manual sample: 196 exists, 0 not-found, 4 ambiguous.

## Why

1. **κ is degenerate on the P1 recheck.**
   - In pass 1, all 40 rechecked rows were *exists*. Then p_e = p_o and κ = 0 whatever the agreement (raw 97.5 %,
     39/40).
   - This is the known prevalence paradox of κ (Feinstein & Cicchetti 1990). κ cannot measure reliability when one
     outcome has prevalence 100 % in the sample.
   - The P1 recheck sample was stratified by tier, not by outcome. Almost no hard cases could be tested.
2. **The P1 recheck was intra-rater only.** No second person rated any reference.
3. **Full tool run is too expensive.** The planned hallucinator run (100 papers × 3 styles) is estimated at
   25–35 machine hours with keyless online backends (P0 timing: 338 s for one 35-reference paper).
4. **The H3 point ratio rests on one flag.** The denominator of the H3 ratio has k = 1 (1/2,323). So the point ratio
   (6.02) is fragile; the lower bound of its CI (2.01) is not.

## What changes

### (a) Agreement criterion
- The recheck criterion **"Cohen's κ ≥ 0.7" is replaced by "PABAK ≥ 0.8"**.
  - PABAK is the prevalence- and bias-adjusted κ on the 3 outcomes (exists / not-found / ambiguous):
    PABAK = (3·p_o − 1)/2.
  - PASS if the point estimate is ≥ 0.8, computed on all rechecked rows pooled (item b).
- Also reported, with no PASS rule:
  - Gwet's AC1;
  - raw Cohen's κ;
  - raw agreement p_o;
  - the 3 × 3 table.
- Every agreement statistic gets a bootstrap 95 % CI: B = 1000, seed 42, resampling citing papers.
- Each is reported three ways: pooled, inter-rater (item c) and intra-rater.

### (b) P2 recheck sample: 40 references, stratified by the pass-1 outcome, seed 42
- **Pool:** the pass-1 rows of the P1 manual sample (200) and of the P2 render sample (60, item f).
  - The 40 rows already rechecked in P1 are excluded.
  - Rows with an empty pass-1 outcome are excluded.
- **Stratum E (20 rows):** pass-1 outcome *exists*, drawn stratified by tier as far as possible.
- **Stratum N (20 rows):** every row with pass-1 outcome *not-found* or *ambiguous*.
  - If there are more than 20, draw 20, stratified by outcome.
  - If there are fewer than 20, fill the stratum with pass-1 *exists* rows that remain def-1 unresolved after the
    full cascade (+S2): the hard cases. These are drawn stratified by tier.
  - The composition of stratum N is reported: how many not-found, ambiguous and filled rows.
- **Timing:** each row is rechecked ≥ 48 h after its own pass-1 timestamp, with the pass-1 outcome hidden.

### (c) Second rater
- The second author (`LQD`) rechecks ≥ 20 of the 40 rows.
  - These are the first 20 after a seed-42 shuffle, 10 from each stratum.
  - The result is the **inter-rater** agreement, between pass 1 (CC) and LQD.
- CC rechecks the remaining rows, giving the **intra-rater** agreement.
- **Sheet for LQD:** `results/p2_recheck_sheet.csv`.
  - It shows sample_id, citing-paper date, tier and the full `.bib` entry.
  - The outcome columns (`exists`, `evidence_url`, `evidence_note`, `checker`, `checked_at`) are empty.
  - The pass-1 outcome, the stratum and the screen status are **not** shown.
- The same search order and decision rule apply (`manual_protocol.md`).

### (d) Public tool (hallucinator v0.2.4) scope
- **Papers:** 30 render papers, drawn with seed 42 from the 100.
- **Styles:**
  - primary: IEEEtran v1.14, *strip* variant;
  - pair: IEEEtran-DOI *orig* on the same 30 papers, run only if the 6-hour total budget allows.
- **Configuration:**
  - DBLP from the offline database, built from the same dump as Amendment 3;
  - every other backend online and keyless, unless a key is obtained (recorded in the log);
  - no Kaggle arXiv database.
- **Outputs:**
  - FP on certified-real references;
  - recall on 100 fabricated references of family "fabricated title" (item g), mixed into the run.
- Outcome `inconclusive` is excluded from the denominators and counted.
- If the 6 h budget runs out, the run stops and the results are labelled *partial*.
- The tool result is descriptive. It enters no hypothesis.

### (e) H3 wording
- The H3 PASS rule is unchanged: point ratio ≥ 2, and H3-strong if the CI lower bound is > 1.
- Claims of effect size are stated from the **lower bound** of the paper-bootstrap 95 % CI, as "at least L×", not
  from the point ratio.

### (f) Render-paper manual sample (route b on the render set; descriptive)
- **Sample:** 60 references from the 100 render papers, seed 42, by `code/manual_sample.py --phase p2`.
  - 10 per tier (J, C, P, B, S, W).
  - Within a tier, references without DOI or arXiv id are drawn first.
- **Pass 1:** CC checks them by `manual_protocol.md`.
- **Analysis:** FP is computed among the *exists* rows for:
  - 3 styles: IEEEtran v1.14, IEEEtran-DOI, elsarticle-num;
  - × 2 variants (orig / strip);
  - × 2 parsers (GROBID / anystyle);
  - × 2 screens (Crossref-only, full cascade).
- These numbers are reported in the same table as the certified-real FP. They are descriptive, with Wilson
  intervals; n per tier < 10 is reported as k/n only.
- **Check of H3:** the H3 ratio is recomputed on these rows. If its direction reverses (ratio < 1), this is reported
  as a threat to H3.

### (g) Recall on fabricated references (descriptive)
- **Labelled sets:**
  1. Badalova–Mayr (Zenodo; 33 problematic, 71 verified);
  2. the GPTZero NeurIPS list, if it is public in machine-readable form;
  3. 300 generated references in 3 families × 100:
     - fabricated title;
     - real title, swapped authors;
     - real title, wrong venue/year.
- **Generated references:**
  - The generation prompt and seed are stored in the repository.
  - A generated reference is used only if its title similarity is < 0.8 to every backend answer.
  - Families 2 and 3 are exempt from this check, because their titles are real by design.
- **Screens:** the 5 cumulative backend columns of Amendment 3 (Crossref-only, +arXiv, +DBLP, +OpenAlex, +S2).
- **Outputs:**
  - recall per family × screen;
  - paired with the FP of the same screen on academic tiers, this gives a discrete ROC per backend.
- **Expectation:** def 1 (title only) cannot detect the "swapped authors" family (Thm 3). This is stated in advance.

## What does not change
- **H1–H5** and their analyses.
- **Ground truth:** P1 run10. The 388 rate-limited references (58 def 1, 330 def 2) stay excluded from the
  denominators and counted separately.
  - If a re-query (with an S2 key, or one keyless night pass) resolves some of them, the main table is updated only if
    a cell changes by ≥ 0.05 percentage points.
  - Both versions are reported.
- **Seeds:** seed 42 everywhere.
