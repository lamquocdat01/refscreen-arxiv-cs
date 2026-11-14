# POSTHOC NOTE P3G — Topic 43 (RefScreen), 2026-11-12

Status: **POST HOC.** Every analysis below was specified after the results of v1.4 and the S6′ pre-submission review by an AI model (`P3/R2_REVIEW_43_S6P_20261112.md`, Fable 5.2 · high) were known. None is registered. In the manuscript each result carries the label "post hoc". This note is hashed into `results/prereg_hash.txt` and the first line of `P3G/P3G_LOG.md` before any of these analyses runs.

Authorisation: LQD, CP3d decision 2026-11-12 16:55 ICT (`CP3d_DECISION_43_20261112.md`; all ten points as proposed, point 3 = B: no manual verification, stated as the main limitation in the abstract).

Constraints: offline only. Inputs are the stored answers in `cache/`, `cache_p3e/` and `cache_p3f/`, the state files `P3E/cascade_passes.json` and `P3F/deep_search_state.json`, and the existing result files. No new API request is made. The GT-3 request window closed at 2026-11-12T23:59Z. Any analysis that would need a new request is reported as "not possible offline". No human label is read and no key is decrypted beyond the one already opened for the AI rater R_B. Earlier result files are not modified; new outputs carry the suffix `_p3g`.

## What was known when this note was written

- All v1.4 numbers, for example:
  - u_A 2019–21 = 1.96 % [1.53; 2.42] (215/10,973);
  - FP bounds A = [0.39 %; 1.96 %], f_hi = 1.86 %;
  - F/U = 46/215 and 181/827;
  - two-flag share 15.1 % (45/299);
  - k_emp 4/8 in sample and 5/9 hold-out;
  - dispersion ratio 3.20 (full cascade);
  - R/N 1.54 % vs 1.52 %;
  - H4-auto CI [0.05; 0.47];
  - tier agreement 73.1 %.
- From S6′ (computed from the PDFs) and from Supplement S23:
  - 91 of 163 not-found references come from `.bbl` titles parsed by GROBID;
  - 26/91 of them show an extraction sign, against 1/72 for `.bib`;
  - the sensitivity of the lower bound to f, as recomputed by S6′, is 0.42 / 0.39 / 0.34 / 0.25 / 0 / 0 % for f = 0 / 1.86 / 5 / 10 / ≥ 21.4 / 52.2 %;
  - the P tier without identifier has 0/101 (2019–21) → 5.59 % (2024–26);
  - certified-real 0.09 % → 0.29 %;
  - the binary academic/non-academic tier agreement is 92.2 %, per S6′'s recomputation from Table S24.
- Not known: any branch-split number (papers, N, U, u_A, F, R, two-flag, k_emp, dispersion by `.bib`/`.bbl`); the lower-end paper-level counts; the per-family f under the GT-3 rule; the 2xx/3xx/Wayback split; the three-group split of not-found references; per-tier R/N differences with intervals; the count of `.bbl` unresolved references that lack author or year.

## Unit of count

Rows of the ground-truth file, i.e. reference entries of a paper, are the unit throughout. This is the unit of N and U. The deep-search state of a distinct (paper, key) is mapped onto every row that carries it. Distinct counts are given only in captions, marked "distinct".

## Analyses

P1. **Branch split (S6′ S2).** Branch = `ref_source` of the ground truth (`bib`; `bbl`, i.e. parsed by GROBID). For each branch and period:
- papers, N, U, u_A with a paper-bootstrap 95 % CI (B = 1000, seed 42);
- F, R, F/U (2019–21 academic; 2024–26 academic);
- the shares with ≥ k unresolved academic references, k = 1…5 (Wilson);
- k_emp at α = 0.05 / 0.01, in sample and hold-out;
- the dispersion ratio Σ(N_A − λ)² / ΣV0 with the branch's own tier rates (full cascade).

Also counted: the `.bbl` unresolved academic references of 2019–21 that lack surnames or a year in the deep-search reference. For these, the GT-3 rule falls back to 0.90 title-only.

P1-rule. **Choice of the main numbers (fixed here, before P1 runs).**
- If the u_A of the two branches (2019–21, full cascade) differ by more than 0.5 percentage points, **or** their dispersion ratios differ by more than 20 % (relative to the `.bib` ratio), then the headline u_A, the clustering result and the thresholds are taken from the `.bib` branch. The `.bbl` branch and the pooled numbers are reported beside them.
- Otherwise the pooled numbers stay the main numbers, and a per-branch table is printed.

P2. **Two ends (S1).** Lower end: a reference counts as a flag only if it is unresolved **and** the deep search found it (F; confirmed real).
- 2019–21: number and share of papers with ≥ 1, ≥ 2, ≥ 3 F-flags among academic references.
- k_emp at α = 0.05 / 0.01, in sample, and hold-out with the 2024–26 academic F.
- PPV ceiling at both ends with π = 0.39 % (Zhao), using u = upper end U/N and lower end FP_lower.
- Upper-end rows repeat v1.4.

P3. **Lower-bound sensitivity (S4).** FP_lower(A, 2019–21) at f = 0; 1.86 % (D-splice f_hi); 5 %; 10 %; 21.4 %; 52.2 % (gen_a f_hi).

P4. **Decoys (S4).**
- The construction counts of `build_decoys` (pool, skipped per reason, including sim ≥ 0.80 with A or B), recomputed offline with the same seed.
- f and f_hi when the 4 unanswered D-splice decoys enter the denominator:
  - as not found (0/200);
  - as found, the worst case (4/200);
  - with the resulting lower bound.

P5. **GT-3 rule offline on stored candidates (S4).**
- Families: GPTZero, Badalova–Mayr, gen_b, gen_c, gen_a (`results/p2_fake_items.csv`).
- Rule: similarity ≥ 0.80 plus surname plus year ± 1 (0.90 title-only without surnames or year). It is applied to every candidate stored for the cascade's title requests of that item (Crossref, arXiv, DBLP, OpenAlex, S2) in `cache/`, `cache_p3e/` and `cache_p3f/`.
- Reported: f per family with Clopper–Pearson, and the number of items with at least one stored answer.
- These are cascade (title) requests, not the deep search's full-string Crossref request; this coverage limit is stated.

P6. **URL answers (S6′ S7).** The found S/W references of 2019–21, split into HTTP 2xx, HTTP 3xx (redirect not followed) and Wayback capture, from the stored codes.

P7. **Two periods (S8).**
- R/N difference (2024–26 minus 2019–21) by tier J, C, P with a paper-bootstrap CI (B = 1000, seed 42).
- U/N of preprints without identifier, both periods, with the difference and its CI.
- Approximate power of the academic R/N comparison to detect +0.39 points (two-sided α = 0.05, bootstrap SE).
- A check of why the registered and the not-found-only differences have the same CI to two decimals.

P8. **Not-found split (S6).** The academic 2019–21 not-found references, in three groups from stored deep-search candidates:
- (a) no candidate with similarity ≥ 0.80 at any source;
- (b) a candidate ≥ 0.80 that fails the surname or year condition;
- (c) best similarity in 0.60–0.80 (reported inside (a)), with the remainder < 0.60.

P9. **k_emp with Wilson (S10).** The smallest k whose Wilson upper limit is ≤ α, next to k_emp, both periods, full cascade.

P10. **Tier rule, binary (S13).** From the tier-validation confusion matrix:
- the academic / non-academic agreement;
- the precision of each side of the rule.

P11. **Policy statements (S9).** In the policy survey, the count of statements whose rejection does not pass a human confirmation step, coded from the quoted text already in `results/p2_policy_survey.csv`, without new fetching.

P12. **H4-auto table (S12).** The existing H4-auto numbers as a supplement table, with the effect size of the lower end (0.26 points).

Descriptive only, with no inferential claim: P1 (beyond the selection rule), P4–P6, P8, P10, P11.
