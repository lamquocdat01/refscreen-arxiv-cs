# PREREG_43 — Amendment 2: two implementation defects in title normalisation (bug fix)

- **Date:** 2026-10-19, written before round 2 (live Semantic Scholar) and before any final u_s, FP or hypothesis
  test. `PREREG_43.md` (sha256 `38378e74…`) and Amendment 1 (sha256 `f9137b5f…`) are unchanged.
- **Disclosure:** when this amendment was written, the interim round-1 outputs were already known
  (`results/p1_groundtruth_round1_<set>.json`, labelled provisional; kept as `*_pre_amend2.json`). So was the
  diagnostic `P1_DIAG_JC60_20261019.md`.

## Why

`refmatch.title_sim` (PREREG §3) does not implement its own text correctly in two places. A 60-reference diagnostic
of unresolved J/C references found both. It was then measured on all 53,556 J/C/P references, with no network calls.

- **(a) LaTeX stripping.**
  - The defect: the accent pattern treated the letter accents `\u \v \H \t \c \d \b \k` as accents even at the start
    of a longer command. For example, `\textemdash` became "extemdash", `\url` became "rl" and `\times` became
    "imes". This text was also sent as the query.
  - Affected: 102 references (52 resolved, 50 unresolved).
- **(b) Registry markup.**
  - The defect: Crossref titles can contain JATS/MathML/HTML tags such as `<sup>2</sup>` and `<i>`. These were kept
    as words. They are markup, not title text.
  - Affected: 43 references move from unresolved to resolved.
- **Measured effect on round-1 u_A:** ≤ 0.2 percentage points in both periods. The upper bound applies if all 50
  references under (a) were to resolve.

## What changes (code only; `code/refmatch.py`)

1. **Accent pattern.** A letter accent matches only when it is not followed by another letter: `\c{c}` and `\v s` are
   still folded, but `\cite` and `\textit` are not. `\textemdash`, `\textendash`, `\textquoteright` and
   `\textquoteleft` become their characters.
2. **Tag removal.** `norm()` first removes tag-shaped markup, i.e. `<name>`, `</name>`, `<ns:name attr="…">` and
   `<name/>`. Text such as `a<b and c>d` or `< 0.5 MB` is left as it is.
3. **Re-run.** The full ground truth is re-run with the fixed code. Round 1 reads stored answers; only the queries whose
   text changed under (a) go to Crossref live. Then round 2 and the retry rounds follow as in Amendment 1. Identifier
   labels (certified-real) are recomputed with the same code.

## What does NOT change

- Similarity definition (max of normalised Levenshtein and token Jaccard) and the 0.9 threshold.
- def 1, def 2, the three states, tiers, cascade, schedule (Amendment 1), hypotheses, sample sizes, manual protocol
  and the five primary analyses.
- P0 numbers (`P0_REPORT_43.md`, closed) are not recomputed. P0 used the same defective code; the size of the effect
  there is expected to be of the same order (≤ 0.2 percentage points).

## Sensitivity (reported)

u_s with the pre-amendment normalisation. These come from the diagnostic replay, not from a second full run:
`results/p1_diag_norm_impact.json`, together with the count of references changed by (a) and (b).

Code: `code/refmatch.py`, with the pre-amendment copy at `%TEMP%\refmatch.py.bak_20261019`. Diagnostics:
`code/diag_unresolved_p1.py`, `code/diag_norm_impact_p1.py`.
