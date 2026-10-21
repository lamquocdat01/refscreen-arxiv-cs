# Manual verification protocol (route b) — topic 43, P1

Companion to `PREREG_43.md` §6.3. This file is frozen together with it (hash in `results/prereg_hash.txt`).

## Input
- `results/p1_manual_sample.csv`, written by `code/manual_sample.py --seed 42`. Each row holds one reference with:
  - paper id and citing-paper date;
  - tier;
  - the full `.bib` entry text (title, authors, venue, year, url, howpublished, note).
- The checker sees the `.bib` entry and the screen's def-1/def-2 status. The screen status is shown only after the
  outcome is recorded: the columns are filled left to right.

## Search order (stop at the first conclusive hit)
1. Exact title in quotes on Google Scholar; then on DBLP (CS venues).
2. Publisher / venue site named in the entry (proceedings page, journal issue, publisher catalogue).
3. Software / dataset / model: the URL in the entry; otherwise the GitHub, Hugging Face, Zenodo or Kaggle search for the
   title or name.
4. Web page, report or standard: the URL in the entry; if it is dead, the Wayback Machine capture closest to (and not
   after) the citing paper's submission date; for standards, the standards body's catalogue (IEEE, ISO, IETF RFC, 3GPP, NIST).
5. General web search for the title in quotes plus the first-author surname.

No LLM is asked whether a reference exists. Search engines and fetched pages are the only evidence.

## Decision rule
**exists** when a document or resource is found that satisfies all three conditions:
- (a) **Title:** the same title, up to case, punctuation, a dropped or added subtitle after ":"/"—", or ≤ 2 word
  differences. A translation does not count.
- (b) **Author:** ≥ 1 author surname matches. For software or web resources without persons, the owning organisation
  or repository owner counts as the author.
- (c) **Date:** it existed no later than the citing paper's arXiv v1 date. For a web resource, a Wayback capture or an
  in-page date proves this; a later version of the same resource is accepted.

**not-found** when the five search steps give no candidate meeting (a) and (b).

**ambiguous** in two cases:
- a candidate meets only one of (a) and (b) (e.g. same title, different authors);
- the resource is cited too vaguely to identify, e.g. "TensorFlow" with no version or URL.

## Recording (one row per reference, never overwritten)
| Column | Content |
|---|---|
| `exists` | exists / not-found / ambiguous |
| `evidence_url` | the URL that decided the outcome (Wayback URL for archived pages); empty for not-found |
| `evidence_note` | ≤ 1 line: which condition failed / which variant was accepted |
| `checker` | rater id (`CC` = Claude Code session; `LQD` = second author) |
| `checked_at` | ISO-8601 UTC timestamp |

## Recheck and agreement
- **Sample:** 40 rows (20 %, seed 42, stratified by tier as far as possible), listed in `results/p1_manual_recheck.csv`.
- **Timing:** rechecked ≥ 48 h after the first pass, with the first-pass outcome hidden.
- **Agreement:** Cohen's κ on the 3 outcomes, together with the raw agreement and the 3 × 3 table.
- **Rater:** if the second author does the recheck, κ is inter-rater. Otherwise the same checker rechecks and κ is
  reported as **intra-rater**.

## Use in the analysis
- **FP_manual:** among references with outcome *exists*, the share that the screen flags (def 1 unresolved).
- **Exclusions:** *ambiguous* rows are excluded from FP_manual, counted, and reported. *not-found* rows are candidate
  non-existent references; they are reported, but are not part of any FP denominator.
