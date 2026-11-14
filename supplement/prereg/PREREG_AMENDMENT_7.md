# PREREG_43 — Amendment 7 (POST-HOC): completed cascade, human-rated check, tier-rule check, exploratory analyses

- **Status: POST-HOC.** Written on 2026-11-07, after every P1–P3 result and after an independent review (Reviewer 2,
  questions Q1, Q2, Q5, Q6 and Q11) of manuscript v1.2. It is hashed before any API call and before any sample of this
  amendment is drawn.
- **Decision:** LQD, 2026-11-07 16:32, CP3 decision ("all 14 items as proposed"; item 3: option A if a second human
  rater is available before 2026-11-14, else option B).
- **Unchanged:** `PREREG_43.md` (`38378e74…`), `manual_protocol.md` (`9ab6c684…`), Amendments 1–6 (`f9137b5f…`,
  `bc53f7d0…`, `27b60150…`, `593e64b5…`, `64e192ad…`, `424a8d00…`). Amendment 6 said that no further amendment would
  follow; this amendment supersedes that sentence only, by the CP3 decision. Amendment 6 is merged into (b) below.
- **No change to H1–H5 definitions or PASS/FAIL rules.** No change to def 1, def 2, the similarity threshold (0.9),
  the tier rule, the identifier rule or the certified-real label for the primary analyses.

## (a) Completing the cascade

**Why.** OpenAlex was asked on the keyless pool, and the first refusal stopped every later OpenAlex call of the run
(Amendment 1). Many references therefore reached the end of the cascade without an OpenAlex answer. The registered
procedure meant to ask every backend; this part collects the answers that the procedure was meant to collect.

**Input.** `$THS_DATASETS/_derived/43/p2_groundtruth_refs_full.csv` (P1 ground truth with the P2 night retry; the
state behind the main table of v1.2).

**Target set.** Every reference with def-1 state resolved, unresolved or rate-limited for which at least one backend
of its cascade gave no answer: `oa_skipped = 1`, `s2_pending = 1`, `dblp_missing = 1`, or def-1 state rate-limited.
All tiers, both periods. Counts before the run (offline count, 2026-11-07):

| Period | Tier | resolved | unresolved | rate-limited | total |
|---|---|---:|---:|---:|---:|
| 2019–21 | J | 71 | 99 | 0 | 170 |
| 2019–21 | C | 62 | 43 | 0 | 105 |
| 2019–21 | P | 5 | 13 | 0 | 18 |
| 2019–21 | B | 54 | 43 | 0 | 97 |
| 2019–21 | S | 0 | 50 | 0 | 50 |
| 2019–21 | W | 70 | 556 | 0 | 626 |
| 2024–26 | J | 362 | 446 | 1 | 809 |
| 2024–26 | C | 143 | 279 | 2 | 424 |
| 2024–26 | P | 17 | 162 | 0 | 179 |
| 2024–26 | B | 210 | 299 | 3 | 512 |
| 2024–26 | S | 4 | 596 | 3 | 603 |
| 2024–26 | W | 135 | 2,448 | 11 | 2,594 |
| **All** | | **1,133** | **5,034** | **20** | **6,187** |

Academic references (J, C, P) never answered by OpenAlex: 293 in 2019–21 (155 of them unresolved) and 1,412 in
2024–26 (887 unresolved; 1,409 of them resolved or unresolved). S2 is missing only for the 20 rate-limited
references; DBLP is complete. A resolved reference in the target set was resolved by a backend later than OpenAlex
(S2), so its def-1 state cannot change; asking OpenAlex can only move its first-hit column.

**Procedure.** Each target reference is passed through the registered cascade again (`ground_truth_p1.resolve_ref`,
Amendment 3 order: Crossref → arXiv (arXiv id or tier P) → DBLP (offline dump) → OpenAlex → S2), with the registered
similarity threshold and the registered def-1 and def-2 rules.
- Stored answers of every backend are reused read-only from `$THS_DATASETS/_derived/43/cache/`. New answers are
  written only to `$THS_DATASETS/_derived/43/cache_p3e/`.
- OpenAlex: `OPENALEX_API_KEY` if set at run start, else the keyless pool (≤ 1 req/s). As in Amendment 1, the first
  refusal (HTTP 429 or budget/quota) ends OpenAlex calls for the rest of that pass.
- S2: `S2_API_KEY` if set, else keyless at ≤ 1 request per 3 s, with the registered back-off.
- No real e-mail in any parameter (`mailto` and User-Agent use `noreply@example.org`). Keys are read from the
  environment and are never printed or written.
- **Order of asking**, fixed now, so that a budget that runs out cannot select by resolvability: the target set is
  split into groups asked in this order —
  1. 2019–21 academic, unresolved; 2. 2024–26 academic, unresolved; 3. 2019–21 non-academic, unresolved;
  4. 2024–26 non-academic, unresolved; 5. rate-limited; 6. resolved (first-hit column only).
  Inside a group the order is a random permutation with seed 42.
- **Passes:** at most 3. Pass 1 starts after this file is hashed. Pass 2 starts 60 minutes after pass 1 ends. Pass 3
  starts at the first 00:10 UTC after pass 2 ends (the keyless budget is daily). A pass asks only the references that
  still lack an answer.
- **Log** (`P3E/cascade_run.log`, `P3E/cascade_targets.csv`): order, start and end of each pass, time of the first
  refusal per backend, number of retries, number of references still unanswered per backend, tier and period.

**Unanswered after pass 3.** A reference that still lacks an OpenAlex (or S2) answer keeps its registered state
(Amendment 1: it is judged on the backends that answered). Every cell that contains such references is reported with
an **interval [lower, upper]**: lower = those references counted as resolved; upper = counted as unresolved (the
registered state). The interval is never merged into the point estimate. Where a cell has no unanswered reference,
the completed rate is exact.

**Use.** The completed ground truth **replaces** the v1.2 ground truth in every table, figure and derived quantity
(main table, Fig. 1, ceilings, dispersion, R1–R3, empirical thresholds, 2024–26 comparison); the v1.2 numbers are
printed next to it in `P3E/CHANGES_43.md`. H1–H5 are recomputed on the completed data with the registered rules, and
both verdicts (v1.2 and completed) are reported. Outputs carry the suffix `_p3e`; earlier outputs are not overwritten.

## (b) Human-rated check (merges Amendment 6)

**Sheet H01–H68** (`code/p3e_human_sheet.py`):
- the 20 rows V01–V20 of Amendment 6, unchanged in content (10 real references, 5 planted `gen_a`, 5 planted `gen_c`;
  their key keeps its plaintext hash `c024336b…`);
- the academic references (J, C, P) of 2019–21 that are **unresolved under the completed full cascade** of (a)
  (registered state; no-title excluded; a reference already among V01–V20 is not drawn again). All of them if there
  are ≤ 48; otherwise 48, stratified over J, C, P with 16 per tier, simple random sampling within a tier (seed 47). A
  tier with fewer eligible references contributes all of them and its remainder is split equally over the other two
  tiers (an odd remainder goes to the larger tier).
- Rows have exactly the columns and presentation of the Amendment-6 sheet (`citing_paper_date`, `bib_version_date`,
  `tier`, `title`, `author`, `bib_entry`, `bbl_item`, empty label columns). Order shuffled with seed 45.
- **Key** (origin of each row: V-row id, or citing paper and cite key with tier and pipeline state) is written only in
  encrypted form to `$THS_DATASETS/_derived/43/keys/p3e_human_key.csv.enc`; the sha256 of its plaintext is written to
  `P3E/P3E_LOG.md` before the sheet is released. The key is opened only by the score step.
- **Rules:** `results/p3e_human_rules.md` = `results/p3c_validity_rules.md` verbatim; protocol `manual_protocol.md`.

**Raters.**
- **R_H1** = LQD (author; human; blind: opens no project file other than the sheet, the rules and the protocol before
  finishing). He knows the design (planted rows and screen-unresolved rows are present) but not which rows.
- **R_H2** = one person who is not an author (blind; told nothing about planted rows), if available before
  2026-11-14 (option A). Otherwise option B: R_H1 only, and the abstract says so.
- **R_B** = a new Claude Code sub-agent that reads only the sheet, the rules and the protocol.
- The V01–V20 sheet of Amendment 6 is no longer scored on its own.

**Statistics** (each rater separately, then pairs; Clopper–Pearson 95 % for counts; no bootstrap):
- negative recall on the 10 planted rows (not-exists or ambiguous; also not-exists alone), and separately for `gen_a`
  (n = 5) and `gen_c` (n = 5); the Amendment-6 expected reading of `gen_c` (a rule-following rater labels it *exists*)
  stands;
- positive agreement on the 10 real V rows (*exists*);
- *exists* share on the screen-unresolved rows;
- PABAK and Gwet's AC1 (3 outcomes and binary exists/not), raw agreement and Cohen's κ (or "undefined") for every
  available pair: human–human (R_H1–R_H2), human–AI (R_H1–R_B, R_H2–R_B), AI–AI (R_B against the earlier pass-1 AI
  label, on rows that have one).
- **Reading, stated now (descriptive, no PASS/FAIL):**
  - The sentence "an unresolved academic reference is one whose confirmation needs search depth, not one that is
    likely fabricated" is kept only if, for every human rater, the Clopper–Pearson lower bound of the *exists* share on
    the screen-unresolved rows exceeds 0.5. Otherwise it is withdrawn and the measured share is printed instead.
  - H4 on human labels: FP_human = u_A (completed, 2019–21) × the human *exists* share on the screen-unresolved rows,
    compared with FP_certified of the same screen. Reported next to the registered H4 result, which is not changed.

## (c) Tier-rule check

- 100 references drawn with seed 46 from all corpus references (both periods, all tiers; no-title included; a
  reference without any .bib entry or .bbl item text is skipped and replaced by the next draw).
- Sheet `results/p3e_tier_sheet.csv` (T001–T100: `bib_entry`, `bbl_item`, empty `tier_human`) with a guide that
  copies the six tier definitions and the conflict order P > S > J > C > B > W of PREREG §2. The rater assigns the
  tier that the cited work **is** (judged from the entry and, if needed, a web search), not the tier its entry type
  implies. Machine tiers are not shown.
- Rater: LQD, blind (`results/p3e_tier_rH1.csv`).
- Reported: accuracy of the machine rule (share agreeing, Clopper–Pearson 95 %), the 6 × 6 confusion matrix,
  per-tier precision and recall, and the academic/non-academic binary accuracy. Descriptive.

## (d) Exploratory analyses (labelled exploratory wherever reported; no new API call outside (a))

1. **Similarity-threshold sweep.** u_s at τ ∈ {0.80, 0.85, 0.90, 0.95} for Crossref-only and the completed full
   cascade, recomputed offline from the stored candidate lists (best candidate similarity per backend). Where a
   backend was not asked at τ = 0.9 because an earlier one resolved, and its answer is not stored, the cell is
   reported as an interval. False-match rate at each τ: share of the generated fabricated items
   (`results/p2_fake_items.csv`, family `gen_a`, and the other families separately) whose best similarity on the same
   backend set reaches τ.
2. **Absent vs present-but-unmatched.** J and C references with a DOI that resolved (certified-real) and that are
   unresolved under the Crossref-only title search: *present-but-unmatched* if the DOI resolved in Crossref,
   *absent from Crossref* if it resolved only elsewhere. The cases of supplement Tables S5 (D16, D31, D46, D48) and S6
   (GZ023) are listed with their similarities.
3. **PDF-parsed screen on the 60 identifier-free render references.** FP of the screen on titles parsed by GROBID
   from the rendered PDFs (stored screen answers of P2), next to the screen on the .bib title for the same rows. Rows
   without a stored answer are excluded and counted. No new API call.
4. **Simultaneous coverage.** Each parameter bound used by R1–R3 (tier rates u_s and, for R2/R3, the intra-paper
   correlations ρ_s) at the one-sided level 1 − η/m (Bonferroni; η = 0.05; m = number of bounds the rule uses: 3 for
   R1, 6 for R2 and R3). u_s from the paper bootstrap (B = 1000, seed 42); ρ_s from the exploratory beta-binomial
   bootstrap (B = 200, seed 42; the bound is then an order statistic, stated). Rules are re-derived and checked on
   the corpus; we report which thresholds remain α-safe. The word "guarantee" is used only for a bound with this
   simultaneous coverage.
5. **Empirical thresholds as the primary calibration result.** For legitimate papers, k_emp(α) = the smallest k at
   which the share of papers with N_A ≥ k is ≤ α (α = 0.05, 0.01), in 2019–21 (in sample) and 2024–26 (hold-out),
   overall and by n_A tertile (cut points from 2019–21, applied to both periods), Crossref-only and completed full
   cascade, with Wilson 95 % intervals on the shares. The threshold table of the identifier scenario adds columns for
   ρ = 0 and ρ = its upper bound.

## Reporting

A new row in the protocol table of the paper (Amendment 7, post hoc, written after review). Results of (a) replace
the v1.2 numbers; results of (b) and (c) go to §4, §5.4, the agreement table and §7; (d) goes to §5 (exploratory) and
the supplement. If the human files of (b) or (c) do not exist when the manuscript is rebuilt, those parts are marked
pending and the manuscript keeps the v1.2 statements about raters, with the AI-only rating stated in the abstract.
